"""Route optimization using Google OR-Tools"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from typing import List, Optional, Tuple, Dict
import logging

from shared.models import Activity, DistanceMatrix, GPSCoordinates
from shared.utils import setup_logging, time_to_minutes, minutes_to_time, add_minutes_to_time, get_service_time
from shared.config import settings

logger = setup_logging("optimizer-service")


class RouteOptimizer:
    """Optimize routes using Google OR-Tools VRP solver"""

    def __init__(self):
        self.timeout_seconds = settings.OPTIMIZATION_TIMEOUT_SECONDS

    def optimize_single_route(
        self,
        activities: List[Activity],
        distance_matrix: DistanceMatrix,
        start_coordinates: GPSCoordinates,
        max_time_minutes: int,
        service_times_dict: Dict[str, int]
    ) -> Optional[List[int]]:
        """
        Optimize route for a single crew using TSP
        Returns list of activity indices in optimal order, or None if infeasible
        """
        if not activities:
            return []

        # Create distance matrix including start point
        num_locations = len(activities) + 1  # +1 for start depot
        distance_matrix_with_depot = self._build_matrix_with_depot(
            activities,
            distance_matrix,
            start_coordinates
        )

        # Create routing model
        manager = pywrapcp.RoutingIndexManager(
            num_locations,
            1,  # Single vehicle
            0   # Start from depot (index 0)
        )

        routing = pywrapcp.RoutingModel(manager)

        # Create distance callback
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix_with_depot[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Add time dimension
        time_callback_index = self._create_time_callback(
            routing,
            manager,
            distance_matrix_with_depot,
            activities,
            service_times_dict
        )

        routing.AddDimension(
            time_callback_index,
            0,  # No slack
            max_time_minutes,
            True,  # Start cumul to zero
            'Time'
        )

        # Set search parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )

        # Use faster metaheuristic for better performance
        # AUTOMATIC will choose the best strategy based on problem size
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC
        )

        # Reduce timeout for single crew (should be faster)
        timeout = min(self.timeout_seconds, 60)  # Max 60 seconds for single crew
        search_parameters.time_limit.seconds = timeout

        logger.info(f"Starting single-route optimization for {len(activities)} activities (timeout: {timeout}s)")

        # Solve
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            return self._extract_route(solution, routing, manager)
        else:
            logger.warning("No solution found for single route optimization")
            return None

    def optimize_multiple_routes(
        self,
        activities: List[Activity],
        distance_matrix: DistanceMatrix,
        start_coordinates: GPSCoordinates,
        num_vehicles: int,
        max_time_minutes: int,
        service_times_dict: Dict[str, int]
    ) -> Optional[List[List[int]]]:
        """
        Optimize routes for multiple crews using VRP
        Returns list of routes, where each route is a list of activity indices
        """
        if not activities:
            return []

        if num_vehicles <= 0:
            raise ValueError("Number of vehicles must be positive")

        # Build distance matrix with depot
        num_locations = len(activities) + 1
        distance_matrix_with_depot = self._build_matrix_with_depot(
            activities,
            distance_matrix,
            start_coordinates
        )

        # Create routing model
        manager = pywrapcp.RoutingIndexManager(
            num_locations,
            num_vehicles,
            0  # All vehicles start from depot
        )

        routing = pywrapcp.RoutingModel(manager)

        # Distance callback
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix_with_depot[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Add time dimension
        time_callback_index = self._create_time_callback(
            routing,
            manager,
            distance_matrix_with_depot,
            activities,
            service_times_dict
        )

        routing.AddDimension(
            time_callback_index,
            30,  # 30 minutes slack (flexibility)
            max_time_minutes,
            True,
            'Time'
        )

        # Set search parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )

        # Use faster metaheuristic for multi-vehicle
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC
        )

        # Scale timeout based on problem size
        timeout = min(self.timeout_seconds, 120)  # Max 2 minutes for multi-vehicle
        search_parameters.time_limit.seconds = timeout

        # Solve
        logger.info(f"Starting multi-vehicle optimization for {num_vehicles} vehicles and {len(activities)} activities (timeout: {timeout}s)")
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            logger.info(f"Optimization completed successfully for {num_vehicles} vehicles")
            routes = self._extract_routes(solution, routing, manager, num_vehicles)
            return routes
        else:
            logger.warning("No solution found for multi-vehicle optimization")
            return None

    def _build_matrix_with_depot(
        self,
        activities: List[Activity],
        distance_matrix: DistanceMatrix,
        depot_coordinates: GPSCoordinates
    ) -> List[List[int]]:
        """
        Build distance matrix including depot as first location
        Returns matrix in minutes (rounded to int)
        """
        from ..distance_service.calculator import haversine_distance, calculate_duration_minutes

        n = len(activities)
        matrix = [[0 for _ in range(n + 1)] for _ in range(n + 1)]

        # Distances between activities (offset by 1 for depot)
        for i in range(n):
            for j in range(n):
                # Convert to minutes
                duration = distance_matrix.durations_minutes[i][j]
                matrix[i + 1][j + 1] = duration

        # Distances from/to depot
        for i, activity in enumerate(activities):
            if not activity.coordinates:
                activity.parse_coordinates()

            dist = haversine_distance(depot_coordinates, activity.coordinates)
            duration = calculate_duration_minutes(dist, settings.DEFAULT_SPEED_KMH)

            matrix[0][i + 1] = duration  # Depot to activity
            matrix[i + 1][0] = duration  # Activity to depot

        return matrix

    def _create_time_callback(
        self,
        routing,
        manager,
        distance_matrix: List[List[int]],
        activities: List[Activity],
        service_times_dict: Dict[str, int]
    ):
        """Create time callback including service times"""

        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)

            # Travel time
            travel_time = distance_matrix[from_node][to_node]

            # Service time at 'from' location (if not depot)
            service_time = 0
            if from_node > 0:  # Not depot
                activity = activities[from_node - 1]
                service_time = get_service_time(activity.servicio, service_times_dict)

            return travel_time + service_time

        return routing.RegisterTransitCallback(time_callback)

    def _extract_route(self, solution, routing, manager) -> List[int]:
        """Extract route from solution (single vehicle)"""
        route = []
        index = routing.Start(0)

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node > 0:  # Skip depot
                route.append(node - 1)  # Adjust for depot offset
            index = solution.Value(routing.NextVar(index))

        return route

    def _extract_routes(
        self,
        solution,
        routing,
        manager,
        num_vehicles: int
    ) -> List[List[int]]:
        """Extract all routes from multi-vehicle solution"""
        routes = []

        for vehicle_id in range(num_vehicles):
            route = []
            index = routing.Start(vehicle_id)

            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node > 0:  # Skip depot
                    route.append(node - 1)  # Adjust for depot offset
                index = solution.Value(routing.NextVar(index))

            # Only include non-empty routes
            if route:
                routes.append(route)

        return routes

    def validate_route_feasibility(
        self,
        route_indices: List[int],
        activities: List[Activity],
        distance_matrix: DistanceMatrix,
        start_coordinates: GPSCoordinates,
        max_time_minutes: int,
        service_times_dict: Dict[str, int],
        include_return: bool = True
    ) -> Tuple[bool, int, float]:
        """
        Validate if a route is feasible within time constraints
        Returns (is_feasible, total_minutes, total_km)
        """
        from ..distance_service.calculator import haversine_distance

        if not route_indices:
            return True, 0, 0.0

        total_time = 0
        total_distance = 0.0
        current_location = start_coordinates

        # Travel through route
        for idx in route_indices:
            activity = activities[idx]
            if not activity.coordinates:
                activity.parse_coordinates()

            # Distance to this activity
            if current_location == start_coordinates:
                dist = haversine_distance(start_coordinates, activity.coordinates)
            else:
                # Use pre-calculated distance matrix
                prev_idx = route_indices[route_indices.index(idx) - 1] if idx != route_indices[0] else None
                if prev_idx is not None:
                    dist = distance_matrix.distances_km[prev_idx][idx]
                else:
                    dist = haversine_distance(start_coordinates, activity.coordinates)

            # Calculate time
            from ..distance_service.calculator import calculate_duration_minutes
            travel_time = calculate_duration_minutes(dist, settings.DEFAULT_SPEED_KMH)
            service_time = get_service_time(activity.servicio, service_times_dict)

            total_time += travel_time + service_time
            total_distance += dist
            current_location = activity.coordinates

        # Return to depot if required
        if include_return and route_indices:
            last_activity = activities[route_indices[-1]]
            dist = haversine_distance(last_activity.coordinates, start_coordinates)
            travel_time = calculate_duration_minutes(dist, settings.DEFAULT_SPEED_KMH)

            total_time += travel_time
            total_distance += dist

        is_feasible = total_time <= max_time_minutes

        return is_feasible, total_time, round(total_distance, 2)

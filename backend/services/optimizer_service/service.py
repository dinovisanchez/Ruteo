"""Optimization orchestration service"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from typing import List, Dict, Tuple
import math

from shared.models import (
    Activity,
    ActivityLot,
    WorkConfiguration,
    DistanceMatrix,
    OptimizationResult,
    CrewRoute,
    RouteStop
)
from shared.utils import (
    setup_logging,
    time_to_minutes,
    minutes_to_time,
    add_minutes_to_time,
    calculate_utilization,
    Timer,
    get_service_time
)
from .optimizer import RouteOptimizer
from .clustering import (
    kmeans_geographic_clustering,
    balance_clusters,
    estimate_optimal_clusters,
    calculate_cluster_statistics
)

logger = setup_logging("optimizer-service")


class OptimizationService:
    """Service for route optimization orchestration"""

    def __init__(self):
        self.optimizer = RouteOptimizer()

    def optimize_activity_lot(
        self,
        activity_lot: ActivityLot,
        distance_matrix: DistanceMatrix
    ) -> OptimizationResult:
        """
        Optimize routes for an activity lot
        """
        with Timer("Full optimization", logger):
            config = activity_lot.configuracion
            activities = activity_lot.actividades

            # Create service times dictionary
            service_times_dict = {
                st.servicio: st.duracion_minutos
                for st in config.tiempos_servicio
            }

            # Calculate maximum available time
            max_time_minutes = int(config.horas_laborales * 60)

            # Estimate number of crews needed
            num_crews = self.estimate_crews_needed(
                activities,
                config,
                service_times_dict
            )

            logger.info(f"Estimated {num_crews} crews needed for {len(activities)} activities")
            logger.info(f"Starting optimization for {len(activities)} activities with {num_crews} crews")

            # Optimize routes
            if num_crews == 1:
                # Single crew - use TSP
                routes = self._optimize_single_crew(
                    activities,
                    distance_matrix,
                    config,
                    max_time_minutes,
                    service_times_dict
                )
            else:
                # Multiple crews - use clustering + VRP
                routes = self._optimize_multiple_crews(
                    activities,
                    distance_matrix,
                    config,
                    num_crews,
                    max_time_minutes,
                    service_times_dict
                )

            # Build result
            result = self._build_optimization_result(
                activity_lot,
                routes,
                config,
                service_times_dict
            )

            return result

    def estimate_crews_needed(
        self,
        activities: List[Activity],
        config: WorkConfiguration,
        service_times_dict: Dict[str, int]
    ) -> int:
        """
        Estimate number of crews needed based on time constraints
        """
        # Calculate total work time needed
        total_service_time = sum(
            get_service_time(act.servicio, service_times_dict)
            for act in activities
        )

        # Estimate average travel time (rough heuristic: 20% of service time)
        estimated_travel_time = total_service_time * 0.25

        total_time_needed = total_service_time + estimated_travel_time

        # Available time per crew
        available_time_per_crew = config.horas_laborales * 60

        # Calculate crews needed
        crews_by_time = math.ceil(total_time_needed / available_time_per_crew)

        # Check capacity constraint
        if config.capacidad_maxima_actividades:
            crews_by_capacity = math.ceil(
                len(activities) / config.capacidad_maxima_actividades
            )
            crews_needed = max(crews_by_time, crews_by_capacity)
        else:
            crews_needed = crews_by_time

        return max(1, crews_needed)

    def _optimize_single_crew(
        self,
        activities: List[Activity],
        distance_matrix: DistanceMatrix,
        config: WorkConfiguration,
        max_time_minutes: int,
        service_times_dict: Dict[str, int]
    ) -> List[List[int]]:
        """Optimize route for single crew"""
        logger.info("Optimizing for single crew")

        route_indices = self.optimizer.optimize_single_route(
            activities,
            distance_matrix,
            config.punto_partida,
            max_time_minutes,
            service_times_dict
        )

        if route_indices is None:
            logger.warning("Failed to find feasible route for single crew")
            # Return simple sequential route
            route_indices = list(range(len(activities)))

        return [route_indices]

    def _optimize_multiple_crews(
        self,
        activities: List[Activity],
        distance_matrix: DistanceMatrix,
        config: WorkConfiguration,
        num_crews: int,
        max_time_minutes: int,
        service_times_dict: Dict[str, int]
    ) -> List[List[int]]:
        """Optimize routes for multiple crews using clustering"""
        logger.info(f"Optimizing for {num_crews} crews")

        # Cluster activities geographically
        logger.info(f"Starting geographic clustering for {len(activities)} activities into {num_crews} clusters")
        clusters = kmeans_geographic_clustering(activities, num_crews)
        logger.info(f"Clustering completed, generated {len(clusters)} clusters")

        # Balance clusters if needed
        if config.capacidad_maxima_actividades:
            clusters = balance_clusters(clusters, config.capacidad_maxima_actividades)

        stats = calculate_cluster_statistics(clusters)
        logger.info(f"Cluster statistics: {stats}")

        # Optimize each cluster
        all_routes = []
        activity_to_global_idx = {act.codigo_bia: idx for idx, act in enumerate(activities)}

        logger.info(f"Starting optimization of {len(clusters)} clusters")
        for cluster_idx, (cluster_id, cluster_activities) in enumerate(clusters.items(), start=1):
            if not cluster_activities:
                continue

            logger.info(f"Optimizing cluster {cluster_idx}/{len(clusters)} (ID: {cluster_id}) with {len(cluster_activities)} activities")

            # Create sub-distance matrix for this cluster
            cluster_indices = [activity_to_global_idx[act.codigo_bia] for act in cluster_activities]
            sub_distance_matrix = self._create_sub_matrix(distance_matrix, cluster_indices)

            # Optimize this cluster's route
            route_indices = self.optimizer.optimize_single_route(
                cluster_activities,
                sub_distance_matrix,
                config.punto_partida,
                max_time_minutes,
                service_times_dict
            )

            if route_indices is None:
                logger.warning(f"No solution for cluster {cluster_id}, using sequential order")
                route_indices = list(range(len(cluster_activities)))
            else:
                logger.info(f"Cluster {cluster_idx}/{len(clusters)} optimized successfully with {len(route_indices)} stops")

            # Map back to global indices
            global_route = [cluster_indices[idx] for idx in route_indices]
            all_routes.append(global_route)

        return all_routes

    def _create_sub_matrix(
        self,
        full_matrix: DistanceMatrix,
        indices: List[int]
    ) -> DistanceMatrix:
        """Create sub-matrix for a subset of activities"""
        n = len(indices)
        sub_distances = [[0.0 for _ in range(n)] for _ in range(n)]
        sub_durations = [[0 for _ in range(n)] for _ in range(n)]

        for i in range(n):
            for j in range(n):
                orig_i = indices[i]
                orig_j = indices[j]
                sub_distances[i][j] = full_matrix.distances_km[orig_i][orig_j]
                sub_durations[i][j] = full_matrix.durations_minutes[orig_i][orig_j]

        sub_ids = [full_matrix.activities_ids[idx] for idx in indices]

        return DistanceMatrix(
            activities_ids=sub_ids,
            distances_km=sub_distances,
            durations_minutes=sub_durations
        )

    def _build_optimization_result(
        self,
        activity_lot: ActivityLot,
        routes_indices: List[List[int]],
        config: WorkConfiguration,
        service_times_dict: Dict[str, int]
    ) -> OptimizationResult:
        """Build complete optimization result with all details"""
        activities = activity_lot.actividades
        crew_routes = []
        total_distance = 0.0
        all_viable = True

        for crew_id, route_indices in enumerate(routes_indices, start=1):
            crew_route = self._build_crew_route(
                crew_id,
                route_indices,
                activities,
                config,
                service_times_dict
            )

            crew_routes.append(crew_route)
            total_distance += crew_route.distancia_total_km

            if not crew_route.viable:
                all_viable = False

        # Calculate metrics
        metricas = self._calculate_metrics(crew_routes, config)

        result = OptimizationResult(
            nombre_lote=activity_lot.nombre_lote,
            total_actividades=len(activities),
            cuadrillas_necesarias=len(crew_routes),
            rutas=crew_routes,
            distancia_total_km=round(total_distance, 2),
            viable_en_un_dia=all_viable,
            metricas=metricas
        )

        return result

    def _build_crew_route(
        self,
        crew_id: int,
        route_indices: List[int],
        activities: List[Activity],
        config: WorkConfiguration,
        service_times_dict: Dict[str, int]
    ) -> CrewRoute:
        """Build detailed route for a single crew"""
        from ..distance_service.calculator import haversine_distance, calculate_duration_minutes

        stops = []
        current_time = config.horario_inicio
        current_location = config.punto_partida

        total_distance = 0.0
        total_work_time = 0
        total_travel_time = 0

        # Build stops
        for seq, activity_idx in enumerate(route_indices, start=1):
            activity = activities[activity_idx]

            if not activity.coordinates:
                activity.parse_coordinates()

            # Calculate distance and travel time
            dist = haversine_distance(current_location, activity.coordinates)
            travel_time = calculate_duration_minutes(dist, config.velocidad_promedio_kmh)

            # Arrival time
            arrival_time = add_minutes_to_time(current_time, travel_time)

            # Service time
            service_time = get_service_time(activity.servicio, service_times_dict)

            # Departure time
            departure_time = add_minutes_to_time(arrival_time, service_time)

            # Create stop
            stop = RouteStop(
                secuencia=seq,
                actividad=activity,
                hora_llegada_estimada=arrival_time,
                hora_salida_estimada=departure_time,
                distancia_desde_anterior_km=round(dist, 2),
                tiempo_desplazamiento_minutos=travel_time
            )

            stops.append(stop)

            # Update totals
            total_distance += dist
            total_work_time += service_time
            total_travel_time += travel_time

            # Update current position and time
            current_location = activity.coordinates
            current_time = departure_time

        # Add return to depot if required
        if config.incluir_retorno and stops:
            last_location = stops[-1].actividad.coordinates
            dist = haversine_distance(last_location, config.punto_partida)
            travel_time = calculate_duration_minutes(dist, config.velocidad_promedio_kmh)

            total_distance += dist
            total_travel_time += travel_time
            current_time = add_minutes_to_time(current_time, travel_time)

        # Calculate metrics
        total_time = total_work_time + total_travel_time
        available_time = int(config.horas_laborales * 60)
        utilization = calculate_utilization(total_work_time, total_travel_time, available_time)
        # Compare elapsed time, not clock time (the clock wraps around after 24 h)
        viable = time_to_minutes(config.horario_inicio) + total_time <= time_to_minutes(config.horario_fin)

        return CrewRoute(
            cuadrilla_id=crew_id,
            paradas=stops,
            distancia_total_km=round(total_distance, 2),
            tiempo_total_minutos=total_time,
            tiempo_trabajo_minutos=total_work_time,
            tiempo_desplazamiento_minutos=total_travel_time,
            hora_inicio=config.horario_inicio,
            hora_fin=current_time,
            utilization_percent=round(utilization, 2),
            viable=viable
        )

    def _calculate_metrics(
        self,
        crew_routes: List[CrewRoute],
        config: WorkConfiguration
    ) -> Dict:
        """Calculate overall optimization metrics"""
        if not crew_routes:
            return {}

        total_activities = sum(len(route.paradas) for route in crew_routes)
        total_distance = sum(route.distancia_total_km for route in crew_routes)
        avg_utilization = sum(route.utilization_percent for route in crew_routes) / len(crew_routes)
        max_route_time = max(route.tiempo_total_minutos for route in crew_routes)
        min_route_time = min(route.tiempo_total_minutos for route in crew_routes)

        return {
            "total_activities": total_activities,
            "total_crews": len(crew_routes),
            "total_distance_km": round(total_distance, 2),
            "avg_distance_per_crew": round(total_distance / len(crew_routes), 2),
            "avg_utilization_percent": round(avg_utilization, 2),
            "max_route_time_minutes": max_route_time,
            "min_route_time_minutes": min_route_time,
            "max_activities_per_crew": max(len(route.paradas) for route in crew_routes),
            "min_activities_per_crew": min(len(route.paradas) for route in crew_routes),
            "all_routes_viable": all(route.viable for route in crew_routes)
        }

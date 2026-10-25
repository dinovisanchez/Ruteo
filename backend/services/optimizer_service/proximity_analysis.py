"""Proximity-based clustering analysis service"""
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
    ClusterInfo,
    ProximityClusteringResult,
    OptimizedClusterRoute,
    ClusterOptimizationResult,
    CrewRoute,
    RouteStop,
    GPSCoordinates
)
from shared.utils import (
    setup_logging,
    add_minutes_to_time,
    calculate_utilization,
    Timer,
    get_service_time
)
from .clustering import (
    analyze_proximity_clustering,
    calculate_cluster_centroid,
    calculate_cluster_metrics,
    find_nearest_cluster_neighbors
)
from .optimizer import RouteOptimizer

logger = setup_logging("proximity-analysis")


class ProximityAnalysisService:
    """Service for analyzing and optimizing routes based on proximity clustering"""

    def __init__(self):
        self.optimizer = RouteOptimizer()

    def analyze_clusters(
        self,
        activity_lot: ActivityLot,
        max_distance_km: float = 20.0,
        method: str = "proximity"
    ) -> ProximityClusteringResult:
        """
        Analyze activities and group them by proximity

        Args:
            activity_lot: Batch of activities to analyze
            max_distance_km: Maximum distance for proximity clustering
            method: "proximity" or "kmeans"

        Returns:
            ProximityClusteringResult with all cluster information
        """
        with Timer(f"Proximity analysis ({method})", logger):
            activities = activity_lot.actividades

            # Perform clustering analysis
            clusters, global_metrics = analyze_proximity_clustering(
                activities,
                max_distance_km,
                method
            )

            # Build detailed cluster information
            cluster_info_list = []

            for cluster_id, cluster_activities in clusters.items():
                metrics = calculate_cluster_metrics(cluster_activities)

                cluster_info = ClusterInfo(
                    cluster_id=cluster_id,
                    actividades=cluster_activities,
                    num_actividades=metrics["num_activities"],
                    centroid=metrics["centroid"],
                    distancia_promedio_al_centroid_km=round(metrics["avg_distance_to_centroid"], 2),
                    distancia_maxima_al_centroid_km=round(metrics["max_distance_to_centroid"], 2),
                    densidad_km2=round(metrics["density"], 4) if metrics["density"] != float('inf') else None
                )

                cluster_info_list.append(cluster_info)

            # Sort clusters by size (largest first)
            cluster_info_list.sort(key=lambda x: x.num_actividades, reverse=True)

            result = ProximityClusteringResult(
                nombre_lote=activity_lot.nombre_lote,
                total_actividades=len(activities),
                num_clusters=len(clusters),
                clusters=cluster_info_list,
                distancia_maxima_usado_km=max_distance_km,
                metodo=method,
                metricas_globales=global_metrics
            )

            logger.info(
                f"Analysis completed: {result.num_clusters} clusters, "
                f"sizes: {global_metrics['cluster_mas_pequeno']}-{global_metrics['cluster_mas_grande']}"
            )

            return result

    def optimize_by_clusters(
        self,
        activity_lot: ActivityLot,
        distance_matrix: DistanceMatrix,
        max_distance_km: float = 20.0,
        method: str = "proximity"
    ) -> ClusterOptimizationResult:
        """
        Analyze clusters and optimize route for each cluster independently

        This creates optimized routes where each cluster is treated as a separate
        work unit, allowing to see the best route within each geographic group.

        Args:
            activity_lot: Batch of activities to optimize
            distance_matrix: Pre-calculated distance matrix
            max_distance_km: Maximum distance for proximity clustering
            method: "proximity" or "kmeans"

        Returns:
            ClusterOptimizationResult with optimized routes per cluster
        """
        with Timer("Cluster-based optimization", logger):
            config = activity_lot.configuracion
            activities = activity_lot.actividades

            # First, analyze clusters
            clustering_result = self.analyze_clusters(
                activity_lot,
                max_distance_km,
                method
            )

            logger.info(f"Optimizing {clustering_result.num_clusters} clusters independently")

            # Create service times dictionary
            service_times_dict = {
                st.servicio: st.duracion_minutos
                for st in config.tiempos_servicio
            }

            # Optimize each cluster independently
            optimized_clusters = []
            total_distance = 0.0
            total_time = 0

            # Create activity index mapping
            activity_to_global_idx = {
                act.codigo_bia: idx
                for idx, act in enumerate(activities)
            }

            for cluster_info in clustering_result.clusters:
                logger.info(
                    f"Optimizing cluster {cluster_info.cluster_id} "
                    f"({cluster_info.num_actividades} activities)"
                )

                # Get global indices for this cluster
                cluster_indices = [
                    activity_to_global_idx[act.codigo_bia]
                    for act in cluster_info.actividades
                ]

                # Create sub-distance matrix
                sub_distance_matrix = self._create_sub_matrix(
                    distance_matrix,
                    cluster_indices
                )

                # Use cluster centroid as optimal starting point
                optimal_start = cluster_info.centroid

                # Calculate distance from original starting point to cluster centroid
                from ..distance_service.calculator import haversine_distance
                distance_from_start = haversine_distance(
                    config.punto_partida,
                    optimal_start
                )

                # Optimize this cluster's route
                max_time_minutes = int(config.horas_laborales * 60)

                route_indices = self.optimizer.optimize_single_route(
                    cluster_info.actividades,
                    sub_distance_matrix,
                    optimal_start,  # Use cluster centroid as start
                    max_time_minutes,
                    service_times_dict
                )

                if route_indices is None:
                    logger.warning(
                        f"No optimal solution for cluster {cluster_info.cluster_id}, "
                        "using sequential order"
                    )
                    route_indices = list(range(len(cluster_info.actividades)))

                # Build detailed route for this cluster
                crew_route = self._build_cluster_route(
                    cluster_info.cluster_id,
                    route_indices,
                    cluster_info.actividades,
                    config,
                    service_times_dict,
                    optimal_start
                )

                optimized_cluster = OptimizedClusterRoute(
                    cluster_id=cluster_info.cluster_id,
                    cluster_info=cluster_info,
                    ruta=crew_route,
                    punto_partida_optimo=optimal_start,
                    distancia_desde_punto_partida_km=round(distance_from_start, 2)
                )

                optimized_clusters.append(optimized_cluster)
                total_distance += crew_route.distancia_total_km
                total_time += crew_route.tiempo_total_minutos

            # Calculate overall metrics
            metricas = self._calculate_cluster_metrics(
                optimized_clusters,
                clustering_result
            )

            result = ClusterOptimizationResult(
                nombre_lote=activity_lot.nombre_lote,
                total_actividades=len(activities),
                clustering_info=clustering_result,
                rutas_por_cluster=optimized_clusters,
                distancia_total_km=round(total_distance, 2),
                tiempo_total_minutos=total_time,
                metricas=metricas
            )

            logger.info(
                f"Cluster optimization completed: {len(optimized_clusters)} routes, "
                f"{total_distance:.1f} km total"
            )

            return result

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

    def _build_cluster_route(
        self,
        cluster_id: int,
        route_indices: List[int],
        activities: List[Activity],
        config: WorkConfiguration,
        service_times_dict: Dict[str, int],
        start_point: GPSCoordinates
    ) -> CrewRoute:
        """Build detailed route for a cluster"""
        # Ensure cuadrilla_id is always >= 1 (cluster_id is 0-based)
        cuadrilla_id = max(1, cluster_id + 1)
        if cuadrilla_id < 1:
            logger.error(f"Invalid cuadrilla_id calculated: {cuadrilla_id} from cluster_id: {cluster_id}")
            cuadrilla_id = 1  # Fallback to 1 if somehow still invalid
        
        from ..distance_service.calculator import haversine_distance, calculate_duration_minutes

        stops = []
        current_time = config.horario_inicio
        current_location = start_point

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

        # Add return to start point if required
        if config.incluir_retorno and stops:
            last_location = stops[-1].actividad.coordinates
            dist = haversine_distance(last_location, start_point)
            travel_time = calculate_duration_minutes(dist, config.velocidad_promedio_kmh)

            total_distance += dist
            total_travel_time += travel_time
            current_time = add_minutes_to_time(current_time, travel_time)

        # Calculate metrics
        from shared.utils import time_to_minutes
        total_time = total_work_time + total_travel_time
        available_time = int(config.horas_laborales * 60)
        utilization = calculate_utilization(total_work_time, total_travel_time, available_time)
        viable = time_to_minutes(current_time) <= time_to_minutes(config.horario_fin)

        return CrewRoute(
            cuadrilla_id=cuadrilla_id,  # Use calculated cuadrilla_id (always >= 1)
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

    def _calculate_cluster_metrics(
        self,
        optimized_clusters: List[OptimizedClusterRoute],
        clustering_result: ProximityClusteringResult
    ) -> Dict:
        """Calculate overall metrics for cluster-based optimization"""
        if not optimized_clusters:
            return {}

        distances = [oc.ruta.distancia_total_km for oc in optimized_clusters]
        times = [oc.ruta.tiempo_total_minutos for oc in optimized_clusters]
        densities = [
            oc.cluster_info.densidad_km2
            for oc in optimized_clusters
            if oc.cluster_info.densidad_km2 is not None
        ]

        # Find most compact and dispersed clusters
        cluster_compactness = [
            (oc.cluster_id, oc.cluster_info.distancia_promedio_al_centroid_km)
            for oc in optimized_clusters
        ]
        cluster_compactness.sort(key=lambda x: x[1])

        return {
            "num_clusters": len(optimized_clusters),
            "avg_cluster_distance_km": round(sum(distances) / len(distances), 2),
            "min_cluster_distance_km": round(min(distances), 2),
            "max_cluster_distance_km": round(max(distances), 2),
            "avg_cluster_time_minutes": round(sum(times) / len(times), 1),
            "most_compact_cluster": cluster_compactness[0][0] if cluster_compactness else None,
            "most_dispersed_cluster": cluster_compactness[-1][0] if cluster_compactness else None,
            "avg_density": round(sum(densities) / len(densities), 4) if densities else None,
            "all_clusters_viable": all(oc.ruta.viable for oc in optimized_clusters),
            "viable_clusters": sum(1 for oc in optimized_clusters if oc.ruta.viable),
            "cluster_sizes": clustering_result.metricas_globales.get("cluster_sizes", [])
        }

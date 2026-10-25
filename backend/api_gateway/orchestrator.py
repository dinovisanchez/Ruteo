"""Orchestrator for coordinating calls between microservices"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import httpx
from typing import List, Dict, Any
import asyncio

from shared.models import (
    Activity,
    ActivityLot,
    DistanceMatrix,
    OptimizationResult,
    ProximityClusteringResult,
    ClusterOptimizationResult
)
from shared.config import settings
from shared.utils import setup_logging, Timer

logger = setup_logging("api-gateway", settings.LOG_LEVEL)


class ServiceOrchestrator:
    """Orchestrate calls between microservices"""

    def __init__(self):
        self.data_service_url = settings.DATA_SERVICE_URL
        self.distance_service_url = settings.DISTANCE_SERVICE_URL
        self.optimizer_service_url = settings.OPTIMIZER_SERVICE_URL
        self.timeout = httpx.Timeout(300.0, connect=10.0)  # 5 minute timeout for long operations

    async def process_file_and_optimize(
        self,
        file_path: str,
        activity_lot: ActivityLot
    ) -> OptimizationResult:
        """
        Full pipeline: validate data -> calculate distances -> optimize routes
        """
        with Timer("Full optimization pipeline", logger):
            # Step 1: Validate data
            logger.info("Step 1: Validating activity data")
            await self._validate_activities(activity_lot)

            # Step 2: Calculate distance matrix
            logger.info("Step 2: Calculating distance matrix")
            distance_matrix = await self._calculate_distances(
                activity_lot.actividades,
                activity_lot.configuracion.velocidad_promedio_kmh
            )

            # Step 3: Optimize routes
            logger.info("Step 3: Optimizing routes")
            result = await self._optimize_routes(activity_lot, distance_matrix)

            return result

    async def _validate_activities(self, activity_lot: ActivityLot) -> bool:
        """Call data service to validate activities"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.data_service_url}/validate",
                    json=activity_lot.model_dump(mode='json')
                )

                if response.status_code == 200:
                    logger.info("Activities validated successfully")
                    return True
                else:
                    error_detail = response.json().get('detail', 'Unknown error')
                    raise Exception(f"Validation failed: {error_detail}")

        except httpx.RequestError as e:
            logger.error(f"Error connecting to data service: {str(e)}")
            raise Exception(f"Data service unavailable: {str(e)}")

    async def _calculate_distances(
        self,
        activities: List[Activity],
        speed_kmh: float
    ) -> DistanceMatrix:
        """Call distance service to calculate distance matrix"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                request_data = {
                    "activities": [act.model_dump(mode='json') for act in activities],
                    "speed_kmh": speed_kmh,
                    "use_cache": True
                }

                response = await client.post(
                    f"{self.distance_service_url}/calculate-matrix",
                    json=request_data
                )

                if response.status_code == 200:
                    data = response.json()
                    matrix = DistanceMatrix(**data)
                    logger.info(f"Distance matrix calculated: {len(matrix.activities_ids)} activities")
                    return matrix
                else:
                    error_detail = response.json().get('detail', 'Unknown error')
                    raise Exception(f"Distance calculation failed: {error_detail}")

        except httpx.RequestError as e:
            logger.error(f"Error connecting to distance service: {str(e)}")
            raise Exception(f"Distance service unavailable: {str(e)}")

    async def _optimize_routes(
        self,
        activity_lot: ActivityLot,
        distance_matrix: DistanceMatrix
    ) -> OptimizationResult:
        """Call optimizer service to optimize routes"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                request_data = {
                    "activity_lot": activity_lot.model_dump(mode='json'),
                    "distance_matrix": distance_matrix.model_dump(mode='json')
                }

                response = await client.post(
                    f"{self.optimizer_service_url}/optimize",
                    json=request_data
                )

                if response.status_code == 200:
                    data = response.json()
                    result = OptimizationResult(**data)
                    logger.info(
                        f"Optimization complete: {result.cuadrillas_necesarias} crews, "
                        f"{result.distancia_total_km} km"
                    )
                    return result
                else:
                    error_detail = response.json().get('detail', 'Unknown error')
                    raise Exception(f"Optimization failed: {error_detail}")

        except httpx.RequestError as e:
            logger.error(f"Error connecting to optimizer service: {str(e)}")
            raise Exception(f"Optimizer service unavailable: {str(e)}")

    async def estimate_crews(self, activity_lot: ActivityLot) -> Dict[str, Any]:
        """Call optimizer service to estimate crews needed"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                request_data = {
                    "activities": [act.model_dump(mode='json') for act in activity_lot.actividades],
                    "configuration": activity_lot.configuracion.model_dump(mode='json')
                }

                response = await client.post(
                    f"{self.optimizer_service_url}/estimate-crews",
                    json=request_data
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_detail = response.json().get('detail', 'Unknown error')
                    raise Exception(f"Crew estimation failed: {error_detail}")

        except httpx.RequestError as e:
            logger.error(f"Error connecting to optimizer service: {str(e)}")
            raise Exception(f"Optimizer service unavailable: {str(e)}")

    async def check_services_health(self) -> Dict[str, Any]:
        """Check health of all services"""
        services = {
            "data-service": f"{self.data_service_url}/health",
            "distance-service": f"{self.distance_service_url}/health",
            "optimizer-service": f"{self.optimizer_service_url}/health"
        }

        health_status = {}

        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            for service_name, health_url in services.items():
                try:
                    response = await client.get(health_url)
                    if response.status_code == 200:
                        health_status[service_name] = {
                            "status": "healthy",
                            "details": response.json()
                        }
                    else:
                        health_status[service_name] = {
                            "status": "unhealthy",
                            "error": f"Status code: {response.status_code}"
                        }
                except Exception as e:
                    health_status[service_name] = {
                        "status": "unreachable",
                        "error": str(e)
                    }

        # Overall status
        all_healthy = all(
            service["status"] == "healthy"
            for service in health_status.values()
        )

        return {
            "overall_status": "healthy" if all_healthy else "degraded",
            "services": health_status
        }

    async def get_geographic_summary(self, activities: List[Activity]) -> Dict[str, Any]:
        """Get geographic summary from distance service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.distance_service_url}/geographic-summary",
                    json=[act.model_dump(mode='json') for act in activities]
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_detail = response.json().get('detail', 'Unknown error')
                    raise Exception(f"Geographic summary failed: {error_detail}")

        except httpx.RequestError as e:
            logger.error(f"Error connecting to distance service: {str(e)}")
            raise Exception(f"Distance service unavailable: {str(e)}")

    async def analyze_proximity_clusters(
        self,
        activity_lot: ActivityLot,
        max_distance_km: float = 20.0,
        method: str = "proximity"
    ) -> ProximityClusteringResult:
        """
        Analyze activities and group by proximity

        Args:
            activity_lot: Batch of activities to analyze
            max_distance_km: Maximum distance for proximity clustering
            method: "proximity" or "kmeans"

        Returns:
            ProximityClusteringResult with cluster information
        """
        with Timer(f"Proximity clustering analysis ({method})", logger):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    request_data = {
                        "activity_lot": activity_lot.model_dump(mode='json'),
                        "max_distance_km": max_distance_km,
                        "method": method
                    }

                    response = await client.post(
                        f"{self.optimizer_service_url}/analyze-proximity",
                        json=request_data
                    )

                    if response.status_code == 200:
                        data = response.json()
                        result = ProximityClusteringResult(**data)
                        logger.info(
                            f"Proximity analysis complete: {result.num_clusters} clusters found, "
                            f"avg size: {result.metricas_globales.get('promedio_actividades_por_cluster', 0):.1f}"
                        )
                        return result
                    else:
                        error_detail = response.json().get('detail', 'Unknown error')
                        raise Exception(f"Proximity analysis failed: {error_detail}")

            except httpx.RequestError as e:
                logger.error(f"Error connecting to optimizer service: {str(e)}")
                raise Exception(f"Optimizer service unavailable: {str(e)}")

    async def optimize_by_clusters(
        self,
        activity_lot: ActivityLot,
        max_distance_km: float = 20.0,
        method: str = "proximity"
    ) -> ClusterOptimizationResult:
        """
        Full pipeline for cluster-based optimization:
        1. Validate activities
        2. Calculate distance matrix
        3. Analyze proximity clusters
        4. Optimize each cluster independently

        Args:
            activity_lot: Batch of activities to optimize
            max_distance_km: Maximum distance for proximity clustering
            method: "proximity" or "kmeans"

        Returns:
            ClusterOptimizationResult with optimized routes per cluster
        """
        with Timer(f"Full cluster-based optimization pipeline ({method})", logger):
            # Step 1: Validate data
            logger.info("Step 1: Validating activity data")
            await self._validate_activities(activity_lot)

            # Step 2: Calculate distance matrix
            logger.info("Step 2: Calculating distance matrix")
            distance_matrix = await self._calculate_distances(
                activity_lot.actividades,
                activity_lot.configuracion.velocidad_promedio_kmh
            )

            # Step 3: Optimize by clusters
            logger.info("Step 3: Analyzing clusters and optimizing routes")
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    request_data = {
                        "activity_lot": activity_lot.model_dump(mode='json'),
                        "distance_matrix": distance_matrix.model_dump(mode='json'),
                        "max_distance_km": max_distance_km,
                        "method": method
                    }

                    response = await client.post(
                        f"{self.optimizer_service_url}/optimize-by-clusters",
                        json=request_data
                    )

                    if response.status_code == 200:
                        data = response.json()
                        result = ClusterOptimizationResult(**data)
                        logger.info(
                            f"Cluster optimization complete: {len(result.rutas_por_cluster)} clusters optimized, "
                            f"{result.distancia_total_km} km total"
                        )
                        return result
                    else:
                        error_detail = response.json().get('detail', 'Unknown error')
                        raise Exception(f"Cluster optimization failed: {error_detail}")

            except httpx.RequestError as e:
                logger.error(f"Error connecting to optimizer service: {str(e)}")
                raise Exception(f"Optimizer service unavailable: {str(e)}")

"""Optimizer Service FastAPI application"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

from shared.models import (
    Activity,
    ActivityLot,
    WorkConfiguration,
    DistanceMatrix,
    OptimizationResult,
    HealthResponse,
    ProximityClusteringResult,
    ClusterOptimizationResult,
    AssignmentRequest,
    AssignmentResult
)
from shared.config import settings
from shared.utils import setup_logging, get_service_time
from .service import OptimizationService
from .proximity_analysis import ProximityAnalysisService
from .assignment import asignar, repartir_lote

# Setup logging
logger = setup_logging("optimizer-service", settings.LOG_LEVEL)

# Create FastAPI app
app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Optimizer Service",
    description="Service for route optimization using OR-Tools",
    version=settings.VERSION
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
optimization_service = OptimizationService()
proximity_service = ProximityAnalysisService()


# Request models
class OptimizeRequest(BaseModel):
    activity_lot: ActivityLot
    distance_matrix: DistanceMatrix


class EstimateCrewsRequest(BaseModel):
    activities: List[Activity]
    configuration: WorkConfiguration


class ProximityAnalysisRequest(BaseModel):
    activity_lot: ActivityLot
    max_distance_km: float = 20.0
    method: str = "proximity"  # "proximity" or "kmeans"


class ClusterOptimizationRequest(BaseModel):
    activity_lot: ActivityLot
    distance_matrix: DistanceMatrix
    max_distance_km: float = 20.0
    method: str = "proximity"  # "proximity" or "kmeans"


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="optimizer-service",
        version=settings.VERSION
    )


@app.post("/optimize", response_model=OptimizationResult)
async def optimize_routes(request: OptimizeRequest):
    """
    Optimize routes for activity lot
    """
    try:
        logger.info(f"Optimizing routes for lot: {request.activity_lot.nombre_lote}")

        # Validate inputs
        if not request.activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        if len(request.activity_lot.actividades) != len(request.distance_matrix.activities_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity count and distance matrix size mismatch"
            )

        # Optimize
        result = optimization_service.optimize_activity_lot(
            request.activity_lot,
            request.distance_matrix
        )

        logger.info(
            f"Optimization complete: {result.cuadrillas_necesarias} crews, "
            f"{result.distancia_total_km} km total, "
            f"viable: {result.viable_en_un_dia}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in optimization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization error: {str(e)}"
        )


@app.post("/estimate-crews", response_model=dict)
async def estimate_crews(request: EstimateCrewsRequest):
    """
    Estimate number of crews needed
    """
    try:
        if not request.activities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        # Create service times dictionary
        service_times_dict = {
            st.servicio: st.duracion_minutos
            for st in request.configuration.tiempos_servicio
        }

        # Estimate crews
        num_crews = optimization_service.estimate_crews_needed(
            request.activities,
            request.configuration,
            service_times_dict
        )

        # Calculate some basic stats
        total_service_time = sum(
            get_service_time(act.servicio, service_times_dict)
            for act in request.activities
        )

        available_time_per_crew = request.configuration.horas_laborales * 60

        return {
            "success": True,
            "estimated_crews": num_crews,
            "total_activities": len(request.activities),
            "total_service_time_minutes": total_service_time,
            "available_time_per_crew_minutes": int(available_time_per_crew),
            "max_activities_per_crew": request.configuration.capacidad_maxima_actividades
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error estimating crews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@app.post("/validate-feasibility", response_model=dict)
async def validate_feasibility(request: OptimizeRequest):
    """
    Validate if activities can be completed within constraints
    """
    try:
        if not request.activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        config = request.activity_lot.configuracion

        # Create service times dictionary
        service_times_dict = {
            st.servicio: st.duracion_minutos
            for st in config.tiempos_servicio
        }

        # Estimate crews needed
        num_crews = optimization_service.estimate_crews_needed(
            request.activity_lot.actividades,
            config,
            service_times_dict
        )

        # Calculate total times
        total_service_time = sum(
            get_service_time(act.servicio, service_times_dict)
            for act in request.activity_lot.actividades
        )

        # Rough estimate of travel time from distance matrix
        avg_distance = sum(
            sum(row) for row in request.distance_matrix.distances_km
        ) / len(request.distance_matrix.distances_km) ** 2

        estimated_total_travel = avg_distance * len(request.activity_lot.actividades) * 0.5
        estimated_travel_time = int((estimated_total_travel / config.velocidad_promedio_kmh) * 60)

        total_time_needed = total_service_time + estimated_travel_time
        total_available_time = num_crews * config.horas_laborales * 60

        is_feasible = total_time_needed <= total_available_time

        return {
            "success": True,
            "is_feasible": is_feasible,
            "estimated_crews": num_crews,
            "total_time_needed_minutes": total_time_needed,
            "total_available_time_minutes": int(total_available_time),
            "time_utilization_percent": round((total_time_needed / total_available_time) * 100, 2),
            "details": {
                "service_time_minutes": total_service_time,
                "estimated_travel_time_minutes": estimated_travel_time,
                "work_hours_per_crew": config.horas_laborales
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating feasibility: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@app.post("/analyze-proximity", response_model=ProximityClusteringResult)
async def analyze_proximity(request: ProximityAnalysisRequest):
    """
    Analyze activities and group by proximity without optimization
    Returns clusters with detailed metrics about geographic grouping
    """
    try:
        logger.info(
            f"Analyzing proximity for lot: {request.activity_lot.nombre_lote}, "
            f"method: {request.method}, max_distance: {request.max_distance_km}km"
        )

        if not request.activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        if request.method not in ["proximity", "kmeans"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Method must be 'proximity' or 'kmeans'"
            )

        # Analyze clusters
        result = proximity_service.analyze_clusters(
            request.activity_lot,
            request.max_distance_km,
            request.method
        )

        logger.info(
            f"Proximity analysis complete: {result.num_clusters} clusters, "
            f"sizes: {result.metricas_globales.get('cluster_mas_pequeno', 0)}-"
            f"{result.metricas_globales.get('cluster_mas_grande', 0)}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in proximity analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proximity analysis error: {str(e)}"
        )


@app.post("/optimize-by-clusters", response_model=ClusterOptimizationResult)
async def optimize_by_clusters(request: ClusterOptimizationRequest):
    """
    Analyze proximity clusters and optimize routes for each cluster independently
    This creates separate optimized routes where each geographic group is treated as a unit
    """
    try:
        logger.info(
            f"Cluster-based optimization for lot: {request.activity_lot.nombre_lote}, "
            f"method: {request.method}, max_distance: {request.max_distance_km}km"
        )

        if not request.activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        if request.method not in ["proximity", "kmeans"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Method must be 'proximity' or 'kmeans'"
            )

        if len(request.activity_lot.actividades) != len(request.distance_matrix.activities_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activity count and distance matrix size mismatch"
            )

        # Optimize by clusters
        result = proximity_service.optimize_by_clusters(
            request.activity_lot,
            request.distance_matrix,
            request.max_distance_km,
            request.method
        )

        logger.info(
            f"Cluster optimization complete: {len(result.rutas_por_cluster)} routes, "
            f"{result.distancia_total_km} km total"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in cluster optimization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cluster optimization error: {str(e)}"
        )


@app.post("/assign", response_model=AssignmentResult)
async def assign_activities(request: AssignmentRequest):
    """
    Assign activities to in-house technicians or to the nearest contractor of each OR
    """
    try:
        logger.info(f"Assigning {len(request.actividades)} activities, mode: {request.modo}")

        if not request.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay OTs para asignar"
            )

        result = asignar(request)

        logger.info(
            f"Assignment complete: {len(result.rutas)} routes, "
            f"{len(result.sin_asignar)} unassigned, {result.distancia_total_km} km total"
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error in assignment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assignment error: {str(e)}"
        )



class LotePedido(BaseModel):
    pedido: AssignmentRequest
    codigos: List[str]
    # OT → cuadrilla ("t1+t2") que le da el plan actual: lo que cada técnico ya tiene ese día
    plan_actual: Dict[str, str] = {}


@app.post("/lote", response_model=dict)
async def lote(request: LotePedido):
    """Propuesta para un lote: OTs cercanas juntas, cada grupo al técnico con la UTR más baja"""
    try:
        return repartir_lote(request.pedido, request.codigos, request.plan_actual)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

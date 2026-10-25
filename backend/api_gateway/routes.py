"""API routes for gateway"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Form
from typing import Optional
import shutil
from pathlib import Path
import uuid
import json

from shared.models import (
    ActivityLot,
    OptimizationResult,
    HealthResponse,
    ProximityClusteringResult,
    ClusterOptimizationResult
)
from shared.config import settings
from shared.utils import setup_logging
from .orchestrator import ServiceOrchestrator

logger = setup_logging("api-gateway", settings.LOG_LEVEL)

# Create router
router = APIRouter()

# Initialize orchestrator
orchestrator = ServiceOrchestrator()

# Create upload directory
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check for API gateway"""
    return HealthResponse(
        status="healthy",
        service="api-gateway",
        version=settings.VERSION
    )


@router.get("/health/services", response_model=dict)
async def check_services_health():
    """Check health of all backend services"""
    try:
        health_status = await orchestrator.check_services_health()
        return health_status
    except Exception as e:
        logger.error(f"Error checking services health: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking services: {str(e)}"
        )


@router.post("/upload", response_model=dict)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload activity data file (Excel or CSV)
    """
    try:
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}{file_ext}"

        # Save file
        logger.info(f"Uploading file: {file.filename}")
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Process file through data service
        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            with file_path.open("rb") as f:
                files = {"file": (file.filename, f, file.content_type)}
                response = await client.post(
                    f"{settings.DATA_SERVICE_URL}/upload",
                    files=files
                )

                if response.status_code != 200:
                    # Clean up file
                    file_path.unlink(missing_ok=True)
                    error_detail = response.json().get('detail', 'Unknown error')
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_detail
                    )

                result = response.json()
                result["gateway_file_id"] = file_id

                logger.info(f"File uploaded successfully: {result['total_activities']} activities")

                return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload error: {str(e)}"
        )
    finally:
        await file.close()


@router.post("/optimize", response_model=OptimizationResult)
async def optimize_routes(activity_lot: ActivityLot):
    """
    Optimize routes for activity lot
    Full pipeline: validate -> calculate distances -> optimize
    """
    try:
        logger.info(f"Starting optimization for lot: {activity_lot.nombre_lote}")

        if not activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        # Run full optimization pipeline
        result = await orchestrator.process_file_and_optimize(
            None,  # File already processed
            activity_lot
        )

        logger.info(
            f"Optimization completed: {result.cuadrillas_necesarias} crews, "
            f"{result.total_actividades} activities, "
            f"{result.distancia_total_km} km"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in optimization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization error: {str(e)}"
        )


@router.post("/estimate-crews", response_model=dict)
async def estimate_crews(activity_lot: ActivityLot):
    """
    Estimate number of crews needed for activities
    """
    try:
        if not activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        result = await orchestrator.estimate_crews(activity_lot)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error estimating crews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@router.post("/geographic-summary", response_model=dict)
async def get_geographic_summary(activity_lot: ActivityLot):
    """
    Get geographic summary and statistics for activities
    """
    try:
        if not activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        result = await orchestrator.get_geographic_summary(activity_lot.actividades)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting geographic summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@router.post("/analyze-proximity", response_model=ProximityClusteringResult)
async def analyze_proximity_clusters(
    activity_lot: ActivityLot,
    max_distance_km: float = 20.0,
    method: str = "proximity"
):
    """
    Analyze activities and group them by proximity

    This endpoint analyzes geographic proximity between activities and creates clusters
    of nearby activities. It provides detailed metrics about each cluster including:
    - Number of activities per cluster
    - Centroid coordinates
    - Average and maximum distance to centroid
    - Density (activities per km²)

    Args:
        activity_lot: Batch of activities to analyze
        max_distance_km: Maximum distance (in km) for proximity-based clustering (default: 20)
        method: Clustering method - "proximity" or "kmeans" (default: "proximity")

    Returns:
        ProximityClusteringResult with detailed cluster information
    """
    try:
        logger.info(
            f"Analyzing proximity clusters for lot: {activity_lot.nombre_lote}, "
            f"method: {method}, max_distance: {max_distance_km}km"
        )

        if not activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        if method not in ["proximity", "kmeans"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Method must be 'proximity' or 'kmeans'"
            )

        result = await orchestrator.analyze_proximity_clusters(
            activity_lot,
            max_distance_km,
            method
        )

        logger.info(
            f"Proximity analysis completed: {result.num_clusters} clusters, "
            f"sizes: {result.metricas_globales.get('cluster_mas_pequeno', 0)}-"
            f"{result.metricas_globales.get('cluster_mas_grande', 0)}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in proximity analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proximity analysis error: {str(e)}"
        )


@router.post("/optimize-by-clusters", response_model=ClusterOptimizationResult)
async def optimize_by_clusters(
    activity_lot: ActivityLot,
    max_distance_km: float = 20.0,
    method: str = "proximity"
):
    """
    Analyze proximity clusters and optimize routes for each cluster independently

    This is a powerful feature that:
    1. Groups activities by geographic proximity
    2. Creates an optimized route for each cluster separately
    3. Uses the cluster centroid as the optimal starting point for each route

    Perfect for analyzing 60+ activities to see which ones are closest together
    and what the best route would be for each geographic group.

    Args:
        activity_lot: Batch of activities to optimize
        max_distance_km: Maximum distance (in km) for proximity-based clustering (default: 20)
        method: Clustering method - "proximity" or "kmeans" (default: "proximity")

    Returns:
        ClusterOptimizationResult with optimized routes for each cluster
    """
    try:
        logger.info(
            f"Starting cluster-based optimization for lot: {activity_lot.nombre_lote}, "
            f"method: {method}, max_distance: {max_distance_km}km"
        )

        if not activity_lot.actividades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No activities provided"
            )

        if method not in ["proximity", "kmeans"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Method must be 'proximity' or 'kmeans'"
            )

        result = await orchestrator.optimize_by_clusters(
            activity_lot,
            max_distance_km,
            method
        )

        logger.info(
            f"Cluster optimization completed: {len(result.rutas_por_cluster)} clusters optimized, "
            f"{result.distancia_total_km} km total distance"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in cluster optimization: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cluster optimization error: {str(e)}"
        )


@router.get("/info", response_model=dict)
async def get_info():
    """Get API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "endpoints": {
            "upload": "/api/upload - Upload activity file",
            "optimize": "/api/optimize - Optimize routes",
            "estimate-crews": "/api/estimate-crews - Estimate crews needed",
            "geographic-summary": "/api/geographic-summary - Get geographic summary",
            "analyze-proximity": "/api/analyze-proximity - Analyze proximity clusters",
            "optimize-by-clusters": "/api/optimize-by-clusters - Optimize routes by proximity clusters",
            "health": "/api/health - Health check",
            "services-health": "/api/health/services - Check all services health"
        },
        "services": {
            "data-service": settings.DATA_SERVICE_URL,
            "distance-service": settings.DISTANCE_SERVICE_URL,
            "optimizer-service": settings.OPTIMIZER_SERVICE_URL
        }
    }

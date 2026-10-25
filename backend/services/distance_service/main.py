"""Distance Service FastAPI application"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel

from shared.models import Activity, GPSCoordinates, DistanceMatrix, HealthResponse
from shared.config import settings
from shared.utils import setup_logging
from .service import DistanceService

# Setup logging
logger = setup_logging("distance-service", settings.LOG_LEVEL)

# Create FastAPI app
app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Distance Service",
    description="Service for calculating distances and durations between GPS coordinates",
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

# Initialize service
distance_service = DistanceService()


# Request models
class DistanceMatrixRequest(BaseModel):
    activities: List[Activity]
    speed_kmh: float = 30.0
    use_cache: bool = True


class TwoPointDistanceRequest(BaseModel):
    coord1: GPSCoordinates
    coord2: GPSCoordinates
    speed_kmh: float = 30.0


class NearestNeighborsRequest(BaseModel):
    origin: Activity
    candidates: List[Activity]
    k: int = 5


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="distance-service",
        version=settings.VERSION
    )


@app.post("/calculate-matrix", response_model=DistanceMatrix)
async def calculate_distance_matrix(request: DistanceMatrixRequest):
    """
    Calculate complete distance and duration matrix for activities
    """
    try:
        if not request.activities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one activity is required"
            )

        if request.speed_kmh <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Speed must be greater than 0"
            )

        logger.info(f"Calculating distance matrix for {len(request.activities)} activities")

        matrix = distance_service.calculate_matrix_for_activities(
            request.activities,
            request.speed_kmh,
            request.use_cache
        )

        return matrix

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating distance matrix: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating distances: {str(e)}"
        )


@app.post("/distance-between-two", response_model=dict)
async def calculate_two_point_distance(request: TwoPointDistanceRequest):
    """
    Calculate distance and duration between two GPS coordinates
    """
    try:
        result = distance_service.calculate_distance_between(
            request.coord1,
            request.coord2,
            request.speed_kmh
        )

        return {
            "success": True,
            "coord1": request.coord1.model_dump(),
            "coord2": request.coord2.model_dump(),
            "result": result
        }

    except Exception as e:
        logger.error(f"Error calculating distance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@app.post("/nearest-neighbors", response_model=dict)
async def find_nearest_neighbors(request: NearestNeighborsRequest):
    """
    Find k nearest activities to origin activity
    """
    try:
        if request.k < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="k must be at least 1"
            )

        if not request.candidates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one candidate activity is required"
            )

        results = distance_service.find_nearest_activities(
            request.origin,
            request.candidates,
            request.k
        )

        return {
            "success": True,
            "origin": {
                "codigo_bia": request.origin.codigo_bia,
                "nombre": request.origin.nombre
            },
            "nearest": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding nearest neighbors: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@app.post("/geographic-summary", response_model=dict)
async def get_geographic_summary(activities: List[Activity]):
    """
    Get geographic summary and statistics for activities
    """
    try:
        if not activities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one activity is required"
            )

        summary = distance_service.get_geographic_summary(activities)

        return {
            "success": True,
            "summary": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating geographic summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@app.get("/cache/stats", response_model=dict)
async def get_cache_stats():
    """Get cache statistics"""
    try:
        stats = distance_service.get_cache_stats()
        return {
            "success": True,
            "cache": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@app.delete("/cache/clear", response_model=dict)
async def clear_cache():
    """Clear distance matrix cache"""
    try:
        deleted = distance_service.clear_cache()
        return {
            "success": True,
            "message": f"Cleared {deleted} cache entries"
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

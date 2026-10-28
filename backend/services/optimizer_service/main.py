"""Optimizer service: plan of the day (/assign) and batch proposals (/lote)"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

from shared.models import HealthResponse, AssignmentRequest, AssignmentResult
from shared.config import settings
from shared.utils import setup_logging
from .assignment import asignar, repartir_lote

# Setup logging
logger = setup_logging("optimizer-service", settings.LOG_LEVEL)

# Create FastAPI app
app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Optimizer Service",
    description="Plan of the day and batch proposals with OR-Tools",
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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="optimizer-service",
        version=settings.VERSION
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
    except Exception as e:
        logger.error(f"Error in batch proposal: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error armando la propuesta: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

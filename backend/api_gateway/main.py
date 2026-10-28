"""API Gateway FastAPI application - Main entry point"""
import sys
import os
from contextlib import asynccontextmanager
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from shared.config import settings
from shared.models import HealthResponse
from shared.utils import setup_logging
from .assignment_routes import router as assignment_router
from .utilizacion import router as utilizacion_router

# Setup logging
logger = setup_logging("api-gateway", settings.LOG_LEVEL)


@asynccontextmanager
async def ciclo(app: FastAPI):
    """Logs when the gateway starts and stops"""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Optimizer Service: {settings.OPTIMIZER_SERVICE_URL}")
    logger.info("API Gateway is ready")
    yield
    logger.info("Shutting down API Gateway")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=ciclo,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(assignment_router, prefix="/api", tags=["Asignación por OR"])
app.include_router(utilizacion_router, prefix="/api", tags=["Utilización de técnicos"])


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check for the gateway (./iniciar.sh waits for it)"""
    return HealthResponse(status="healthy", service="api-gateway", version=settings.VERSION)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
        "api": "/api"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )

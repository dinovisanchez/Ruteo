"""Configuration settings for Route Optimizer services"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Project metadata
    PROJECT_NAME: str = "Route Optimizer"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Microservices-based route optimization system for field crews"

    # Service URLs
    DATA_SERVICE_URL: str = os.getenv("DATA_SERVICE_URL", "http://localhost:8001")
    DISTANCE_SERVICE_URL: str = os.getenv("DISTANCE_SERVICE_URL", "http://localhost:8002")
    OPTIMIZER_SERVICE_URL: str = os.getenv("OPTIMIZER_SERVICE_URL", "http://localhost:8003")

    # Redis configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    CACHE_TTL: int = 3600  # 1 hour in seconds

    # File upload configuration
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS: List[str] = [".xlsx", ".xls", ".csv"]

    # CORS configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://frontend:3000"
    ]

    # Optimization defaults
    DEFAULT_WORK_HOURS: float = 8.0
    DEFAULT_SPEED_KMH: float = 30.0
    DEFAULT_START_TIME: str = "08:00"
    DEFAULT_END_TIME: str = "17:00"

    # GPS validation (Colombia boundaries)
    MIN_LATITUDE: float = -4.2
    MAX_LATITUDE: float = 13.4
    MIN_LONGITUDE: float = -81.8
    MAX_LONGITUDE: float = -66.9

    # Optimization parameters
    MAX_ACTIVITIES_PER_CREW: int = 20
    MIN_ACTIVITIES_PER_CREW: int = 1
    OPTIMIZATION_TIMEOUT_SECONDS: int = 300  # 5 minutes

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance"""
    return settings

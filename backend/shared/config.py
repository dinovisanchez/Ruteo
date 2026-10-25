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
    # The dev server moves to 3001, 3002... when 3000 is busy; accept any local port
    CORS_ORIGIN_REGEX: str = r"http://(localhost|127\.0\.0\.1)(:\d+)?"

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

    # Metabase: de dónde salen las OTs. Autenticación con API key o con usuario/contraseña
    METABASE_URL: str = ""
    METABASE_API_KEY: str = ""
    METABASE_USERNAME: str = ""
    METABASE_PASSWORD: str = ""
    METABASE_CARD_ID: str = ""  # Id de la pregunta por defecto (el número en /question/123-...)
    # JSON opcional campo → columna de Metabase, ej. {"codigo_bia": "OT", "or_operador": "Operador"}
    METABASE_COLUMN_MAP: str = ""

    # Catálogo de bases y contratistas (hoja "Data Contratista")
    CONTRATISTAS_CSV_URL: str = ""  # CSV publicado de Google Sheets; si falla se usa el archivo local
    CONTRATISTAS_CSV_PATH: str = ""  # Por defecto backend/data/contratistas.csv
    # Técnicos y contratistas por OR que se editan desde la app
    ASIGNACION_CONFIG_PATH: str = ""  # Por defecto backend/data/asignacion.json

    # Geocodificación (Nominatim) para OTs que llegan sin GPS
    GEOCODING_ENABLED: bool = True
    GEOCODING_MAX_POR_CONSULTA: int = 30

    # Trazado de las rutas por la red vial (OSRM); vacío = líneas rectas en el mapa
    OSRM_URL: str = "https://router.project-osrm.org"
    # El servidor público de OSRM pide máximo una consulta por segundo
    OSRM_PAUSA_SEGUNDOS: float = 1.0

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # El .env puede traer variables de otros componentes (ej. REACT_APP_*)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance"""
    return settings

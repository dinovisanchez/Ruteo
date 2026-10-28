"""Configuration of Ruteo's backend: read from backend/.env"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Project metadata
    PROJECT_NAME: str = "Ruteo"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Plan del día de las OTs: técnicos de Bia y contratistas por OR"

    # The gateway asks the optimizer for each plan
    OPTIMIZER_SERVICE_URL: str = os.getenv("OPTIMIZER_SERVICE_URL", "http://localhost:8003")

    # Excel/CSV upload: largest file accepted
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB

    # CORS configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://frontend:3000"
    ]
    # The dev server moves to 3001, 3002... when 3000 is busy; accept any local port
    CORS_ORIGIN_REGEX: str = r"http://(localhost|127\.0\.0\.1)(:\d+)?"
    # Names the gateway answers to: a web page that points another domain at this computer
    # (DNS rebinding) gets refused instead of using the Metabase key
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "api-gateway"]

    # GPS validation (Colombia boundaries)
    MIN_LATITUDE: float = -4.2
    MAX_LATITUDE: float = 13.4
    MIN_LONGITUDE: float = -81.8
    MAX_LONGITUDE: float = -66.9

    # Zona horaria de las OTs: «hoy» y las horas de visita de Metabase se leen en esta zona
    ZONA_HORARIA: str = "America/Bogota"

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

    # Geocodificación para OTs que llegan sin GPS: Nominatim (gratis, 1 consulta por segundo) o, con una
    # llave de la API Geocoding de Google, Google (entiende mejor las direcciones de Colombia; cobra por uso)
    GEOCODING_ENABLED: bool = True
    GEOCODING_MAX_POR_CONSULTA: int = 30
    GOOGLE_GEOCODING_API_KEY: str = ""

    # Trazado de las rutas por la red vial (OSRM); vacío = líneas rectas en el mapa
    OSRM_URL: str = "https://router.project-osrm.org"
    # Si el principal no responde se usa este (el OSRM de FOSSGIS que usa openstreetmap.org)
    OSRM_URL_RESPALDO: str = "https://routing.openstreetmap.de/routed-car"
    # El servidor público de OSRM pide máximo una consulta por segundo
    OSRM_PAUSA_SEGUNDOS: float = 1.0

    # El .env puede traer variables de otros componentes (ej. REACT_APP_*) o de versiones anteriores
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance"""
    return settings

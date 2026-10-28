"""Pruebas del backend: sin red, sin el .env real y con la configuración en una carpeta temporal"""
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# Antes de importar la app: la configuración se lee al importar
_CARPETA = Path(tempfile.mkdtemp(prefix="ruteo-pruebas-"))
os.environ.update({
    "ASIGNACION_CONFIG_PATH": str(_CARPETA / "asignacion.json"),
    "GEOCODING_ENABLED": "false",
    "OSRM_URL": "",
    "OSRM_URL_RESPALDO": "",
    "METABASE_URL": "http://metabase.prueba",
    "METABASE_API_KEY": "clave-de-prueba",
    "METABASE_CARD_ID": "44",
})

import httpx  # noqa: E402

from shared.models import Activity, GPSCoordinates, Tecnico  # noqa: E402


def dia(desfase: int = 0) -> str:
    """Hoy más `desfase` días, YYYY-MM-DD: las pruebas no dependen de la fecha en que corren"""
    return (date.today() + timedelta(days=desfase)).isoformat()


def ot(codigo: str, lat: float = 4.65, lon: float = -74.08, **campos) -> Activity:
    """Una OT en Bogotá con GPS; los demás campos se pasan por nombre"""
    datos = dict(servicio="visita", nombre=codigo, direccion="Calle 1", ciudad="Bogotá", departamento="Bogotá D.C.",
                 or_operador="Enel", gps=f"{lat},{lon}", coordinates=GPSCoordinates(latitude=lat, longitude=lon))
    datos.update(campos)
    return Activity(codigo_bia=codigo, **datos)


def tecnico(id_: str, nombre: str, base: str = "bia-bogota") -> Tecnico:
    return Tecnico(id=id_, nombre=nombre, base_id=base)


@pytest.fixture
def cliente(monkeypatch):
    """El gateway con el optimizador en el mismo proceso, como lo usa el navegador (Host: localhost)"""
    from fastapi.testclient import TestClient
    from api_gateway import assignment_routes
    from api_gateway.main import app
    from services.optimizer_service.main import app as optimizador

    class AlOptimizador(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.ASGITransport(app=optimizador)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(assignment_routes.httpx, "AsyncClient", AlOptimizador)
    return TestClient(app, base_url="http://localhost")

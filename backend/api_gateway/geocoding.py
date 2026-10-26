"""Geocodificación de OTs sin GPS con Nominatim (OpenStreetMap), con caché en disco"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from datetime import date
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from shared.catalogo import normalizar_texto
from shared.config import settings
from shared.models import Activity, GPSCoordinates
from shared.utils import setup_logging, validate_gps_colombia

logger = setup_logging("api-gateway", settings.LOG_LEVEL)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim exige un User-Agent que identifique la aplicación y máximo 1 consulta por segundo
USER_AGENT = "Ruteo-Bia/1.0"
PAUSA_SEGUNDOS = 1.1
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocache.json"

_cache: Optional[Dict[str, Optional[List[float]]]] = None


def _leer_cache() -> Dict[str, Optional[List[float]]]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = {}
    return _cache


def _guardar_cache() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporal = CACHE_PATH.with_suffix(".tmp")
    temporal.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    temporal.replace(CACHE_PATH)


def _consultas(actividad: Activity) -> List[str]:
    """Primero la dirección completa; si no aparece, el municipio (ubicación aproximada)"""
    municipio = ", ".join(p.strip() for p in [actividad.ciudad, actividad.departamento, "Colombia"] if p and p.strip())
    consultas = []
    if actividad.direccion.strip():
        consultas.append(f"{actividad.direccion.strip()}, {municipio}")
    if actividad.ciudad.strip():
        consultas.append(municipio)
    return consultas


async def _buscar(client: httpx.AsyncClient, consulta: str) -> Optional[GPSCoordinates]:
    respuesta = await client.get(
        NOMINATIM_URL,
        params={"q": consulta, "format": "json", "limit": 1, "countrycodes": "co"},
        headers={"User-Agent": USER_AGENT},
    )
    respuesta.raise_for_status()
    resultados = respuesta.json()
    if not resultados:
        return None
    lat, lon = float(resultados[0]["lat"]), float(resultados[0]["lon"])
    return GPSCoordinates(latitude=lat, longitude=lon) if validate_gps_colombia(lat, lon)[0] else None


async def geocodificar(actividades: List[Activity]) -> Tuple[int, List[str]]:
    """Completa las coordenadas de las OTs sin GPS a partir de su dirección o municipio.

    Modifica las actividades en sitio y las marca como aproximadas. Respeta el
    límite de consultas por llamada; las que quedan pendientes se resuelven en
    las siguientes (el caché guarda lo ya buscado). Devuelve (geocodificadas, avisos).
    """
    pendientes = [a for a in actividades if a.coordinates is None and _consultas(a)]
    if not pendientes or not settings.GEOCODING_ENABLED:
        return 0, []
    # Primero las que entran al plan (pendientes y asignadas de hoy en adelante); el historial después
    hoy = date.today().isoformat()
    pendientes.sort(key=lambda a: 0 if a.situacion == "pendiente" else (1 if (a.fecha_visita or "") >= hoy else 2))

    cache = _leer_cache()
    resueltas = 0
    consultas_red = 0
    avisos: List[str] = []
    cambio_cache = False
    red_disponible = True

    async with httpx.AsyncClient(timeout=15.0) as client:
        for actividad in pendientes:
            for consulta in _consultas(actividad):
                clave = normalizar_texto(consulta)
                if clave not in cache:
                    if not red_disponible or consultas_red >= settings.GEOCODING_MAX_POR_CONSULTA:
                        break
                    if consultas_red:
                        await asyncio.sleep(PAUSA_SEGUNDOS)
                    consultas_red += 1
                    try:
                        coords = await _buscar(client, consulta)
                    except httpx.HTTPError as e:
                        avisos.append(f"No se pudo geocodificar (Nominatim no respondió): {e}")
                        red_disponible = False
                        break
                    cache[clave] = [coords.latitude, coords.longitude] if coords else None
                    cambio_cache = True
                if cache[clave]:
                    lat, lon = cache[clave]
                    actividad.coordinates = GPSCoordinates(latitude=lat, longitude=lon)
                    actividad.gps = f"{lat},{lon}"
                    actividad.coordenadas_aproximadas = True
                    resueltas += 1
                    break

    if cambio_cache:
        _guardar_cache()
    sin_resolver = [a for a in pendientes if a.coordinates is None]
    no_encontradas = sum(1 for a in sin_resolver if all(normalizar_texto(c) in cache for c in _consultas(a)))
    if no_encontradas:
        avisos.append(f"{no_encontradas} OTs sin GPS no se encontraron ni por dirección ni por municipio")
    if len(sin_resolver) > no_encontradas:
        avisos.append(
            f"{len(sin_resolver) - no_encontradas} OTs sin GPS quedan pendientes de geocodificar; "
            "vuelve a traer las OTs para continuar"
        )
    return resueltas, avisos

"""Trazado de las rutas por la red vial con OSRM, para dibujarlas en el mapa"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import time
from typing import Dict, List, Optional, Tuple

import httpx

from shared.config import settings

MAX_CACHE = 500

_cache: Dict[str, Tuple[List[List[float]], float]] = {}
_turno: Optional[asyncio.Lock] = None
_ultima_consulta = 0.0


async def trazar(client: httpx.AsyncClient, puntos: List[List[float]]) -> Optional[Tuple[List[List[float]], float]]:
    """Geometría [[lat, lon], ...] y km por vía de una ruta que pasa por `puntos` en ese orden.

    None si OSRM no encuentra ruta. Lanza httpx.HTTPError si OSRM no responde.
    """
    global _turno, _ultima_consulta
    coordenadas = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in puntos)
    if coordenadas in _cache:
        return _cache[coordenadas]

    # El candado se crea aquí para que quede en el event loop del servidor
    if _turno is None:
        _turno = asyncio.Lock()
    async with _turno:
        espera = settings.OSRM_PAUSA_SEGUNDOS - (time.monotonic() - _ultima_consulta)
        if espera > 0:
            await asyncio.sleep(espera)
        try:
            respuesta = await client.get(
                f"{settings.OSRM_URL.rstrip('/')}/route/v1/driving/{coordenadas}",
                params={"overview": "full", "geometries": "geojson"},
            )
        finally:
            _ultima_consulta = time.monotonic()

    if respuesta.status_code != 200:
        return None
    datos = respuesta.json()
    if datos.get("code") != "Ok" or not datos.get("routes"):
        return None
    ruta = datos["routes"][0]
    resultado = (
        [[lat, lon] for lon, lat in ruta["geometry"]["coordinates"]],
        round(ruta["distance"] / 1000, 2),
    )
    if len(_cache) >= MAX_CACHE:
        _cache.clear()
    _cache[coordenadas] = resultado
    return resultado

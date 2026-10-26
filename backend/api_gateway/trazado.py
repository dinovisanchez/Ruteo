"""Rutas por la red vial con OSRM: el trazado para el mapa y los tiempos entre puntos"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import time
from typing import Dict, List, Optional, Tuple

import httpx

from shared.config import settings
from shared.models import MatrizVial
from shared.utils import setup_logging

logger = setup_logging("api-gateway", settings.LOG_LEVEL)

MAX_CACHE = 500
# El servidor público de OSRM acepta hasta 100 coordenadas por consulta de tabla
MAX_PUNTOS_TABLA = 100
MAX_PARES = 200_000
# Tras un error de conexión no se insiste por un rato, para no demorar cada recálculo
PAUSA_SI_FALLA_SEGUNDOS = 120

_cache: Dict[str, Tuple[List[List[float]], float]] = {}
# (origen, destino) como "lon,lat" → (km, minutos) por las vías; None si OSRM no encontró ruta
_pares: Dict[Tuple[str, str], Tuple[Optional[float], Optional[float]]] = {}
_turno: Optional[asyncio.Lock] = None
_ultima_consulta = 0.0
_sin_osrm_hasta = 0.0


def _coordenada(lat: float, lon: float) -> str:
    return f"{lon:.5f},{lat:.5f}"


async def _consultar(client: httpx.AsyncClient, ruta: str, params: Dict[str, str]) -> Optional[dict]:
    """GET a OSRM respetando la pausa entre consultas; None si OSRM responde con error"""
    global _turno, _ultima_consulta
    # El candado se crea aquí para que quede en el event loop del servidor
    if _turno is None:
        _turno = asyncio.Lock()
    async with _turno:
        espera = settings.OSRM_PAUSA_SEGUNDOS - (time.monotonic() - _ultima_consulta)
        if espera > 0:
            await asyncio.sleep(espera)
        try:
            respuesta = await client.get(f"{settings.OSRM_URL.rstrip('/')}{ruta}", params=params)
        finally:
            _ultima_consulta = time.monotonic()
    if respuesta.status_code != 200:
        return None
    datos = respuesta.json()
    return datos if datos.get("code") == "Ok" else None


async def trazar(client: httpx.AsyncClient, puntos: List[List[float]]) -> Optional[Tuple[List[List[float]], float]]:
    """Geometría [[lat, lon], ...] y km por vía de una ruta que pasa por `puntos` en ese orden.

    None si OSRM no encuentra ruta. Lanza httpx.HTTPError si OSRM no responde.
    """
    coordenadas = ";".join(_coordenada(lat, lon) for lat, lon in puntos)
    if coordenadas in _cache:
        return _cache[coordenadas]

    datos = await _consultar(
        client, f"/route/v1/driving/{coordenadas}", {"overview": "full", "geometries": "geojson"}
    )
    if not datos or not datos.get("routes"):
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


async def _completar_pares(client: httpx.AsyncClient, origenes: List[str], destinos: List[str]) -> bool:
    if all((a, b) in _pares for a in origenes for b in destinos if a != b):
        return True
    coordenadas = list(dict.fromkeys(origenes + destinos))
    params = {"annotations": "duration,distance"}
    if coordenadas != origenes or coordenadas != destinos:
        params["sources"] = ";".join(str(coordenadas.index(a)) for a in origenes)
        params["destinations"] = ";".join(str(coordenadas.index(b)) for b in destinos)
    datos = await _consultar(client, f"/table/v1/driving/{';'.join(coordenadas)}", params)
    if not datos:
        return False
    for i, a in enumerate(origenes):
        for j, b in enumerate(destinos):
            segundos = datos["durations"][i][j]
            metros = (datos.get("distances") or [[None] * len(destinos)] * len(origenes))[i][j]
            _pares[(a, b)] = (
                round(metros / 1000, 3) if metros is not None else None,
                round(segundos / 60, 2) if segundos is not None else None,
            )
    return True


async def matriz_vial(puntos: List[List[float]]) -> Tuple[Optional[MatrizVial], Optional[str]]:
    """Km y minutos por las vías entre todos los puntos [[lat, lon], ...] (sin repetir).

    Devuelve (matriz, aviso); sin OSRM la matriz es None y el optimizador usa línea recta.
    """
    global _sin_osrm_hasta
    if not settings.OSRM_URL or len(puntos) < 2:
        return None, None
    if time.monotonic() < _sin_osrm_hasta:
        return None, f"OSRM no respondió hace poco ({settings.OSRM_URL}): tiempos estimados en línea recta"
    unicos: Dict[str, List[float]] = {}
    for lat, lon in puntos:
        unicos.setdefault(_coordenada(lat, lon), [lat, lon])
    claves = list(unicos)

    if len(_pares) > MAX_PARES:
        _pares.clear()
    # Si son muchos puntos, la tabla se pide por bloques (origen × destino)
    tamano = len(claves) if len(claves) <= MAX_PUNTOS_TABLA else MAX_PUNTOS_TABLA // 2
    bloques = [claves[i:i + tamano] for i in range(0, len(claves), tamano)]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            for origenes in bloques:
                for destinos in bloques:
                    if not await _completar_pares(client, origenes, destinos):
                        return None, "OSRM no devolvió los tiempos por vía: se estimaron en línea recta"
    except httpx.HTTPError as e:
        logger.warning(f"OSRM no respondió ({settings.OSRM_URL}): {e}")
        _sin_osrm_hasta = time.monotonic() + PAUSA_SI_FALLA_SEGUNDOS
        return None, f"No se pudo consultar OSRM en {settings.OSRM_URL}: tiempos estimados en línea recta"

    def valor(a: str, b: str, campo: int) -> Optional[float]:
        return 0.0 if a == b else _pares[(a, b)][campo]

    return MatrizVial(
        puntos=[unicos[c] for c in claves],
        km=[[valor(a, b, 0) for b in claves] for a in claves],
        minutos=[[valor(a, b, 1) for b in claves] for a in claves],
    ), None

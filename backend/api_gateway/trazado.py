"""Rutas por la red vial con OSRM: el trazado para el mapa y los tiempos entre puntos.

Se prueba primero OSRM_URL y, si no responde, OSRM_URL_RESPALDO. El servidor que
respondió la última vez se usa primero en la siguiente consulta.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import time
from typing import Dict, List, Optional, Set, Tuple

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
TIMEOUT = httpx.Timeout(20.0, connect=5.0)

_cache: Dict[str, Tuple[List[List[float]], float]] = {}
_en_curso: Dict[str, "asyncio.Future"] = {}
# (origen, destino) como "lon,lat" → (km, minutos) por las vías; None si OSRM no encontró ruta
_pares: Dict[Tuple[str, str], Tuple[Optional[float], Optional[float]]] = {}
_turno: Optional[asyncio.Lock] = None
_ultima_consulta = 0.0
_sin_osrm_hasta = 0.0
_preferido = 0
_tareas: Set["asyncio.Task"] = set()
ultimo_error: Optional[str] = None


def servidores() -> List[str]:
    urls = [settings.OSRM_URL, settings.OSRM_URL_RESPALDO]
    return list(dict.fromkeys(u.strip().rstrip("/") for u in urls if u and u.strip()))


def _coordenada(lat: float, lon: float) -> str:
    return f"{lon:.5f},{lat:.5f}"


def _describir(error: Exception) -> str:
    texto = str(error) or error.__class__.__name__
    return texto if len(texto) < 160 else texto[:157] + "..."


async def _consultar(client: httpx.AsyncClient, ruta: str, params: Dict[str, str]) -> Optional[dict]:
    """GET a OSRM respetando la pausa entre consultas; prueba cada servidor hasta que uno responda.

    Devuelve None si ninguno respondió bien; el motivo queda en `ultimo_error`.
    """
    global _turno, _ultima_consulta, _sin_osrm_hasta, _preferido, ultimo_error
    lista = servidores()
    if not lista:
        ultimo_error = "OSRM_URL está vacío"
        return None
    if time.monotonic() < _sin_osrm_hasta:
        return None
    # El candado se crea aquí para que quede en el event loop del servidor
    if _turno is None:
        _turno = asyncio.Lock()
    orden = lista[_preferido:] + lista[:_preferido] if _preferido < len(lista) else lista
    errores = []
    sin_conexion = 0
    for servidor in orden:
        async with _turno:
            espera = settings.OSRM_PAUSA_SEGUNDOS - (time.monotonic() - _ultima_consulta)
            if espera > 0:
                await asyncio.sleep(espera)
            try:
                respuesta = await client.get(f"{servidor}{ruta}", params=params)
            except httpx.HTTPError as e:
                sin_conexion += 1
                errores.append(f"{servidor}: {_describir(e)}")
                continue
            finally:
                _ultima_consulta = time.monotonic()
        if respuesta.status_code != 200:
            errores.append(f"{servidor}: HTTP {respuesta.status_code}")
            continue
        datos = respuesta.json()
        if datos.get("code") != "Ok":
            errores.append(f"{servidor}: {datos.get('code')} {datos.get('message', '')}".strip())
            continue
        _preferido = lista.index(servidor)
        ultimo_error = None
        return datos
    ultimo_error = "; ".join(errores)
    logger.warning(f"OSRM no respondió: {ultimo_error}")
    if sin_conexion == len(orden):
        _sin_osrm_hasta = time.monotonic() + PAUSA_SI_FALLA_SEGUNDOS
    return None


async def _trazar_sin_cache(client: httpx.AsyncClient, coordenadas: str) -> Optional[Tuple[List[List[float]], float]]:
    datos = await _consultar(
        client, f"/route/v1/driving/{coordenadas}", {"overview": "full", "geometries": "geojson"}
    )
    if not datos or not datos.get("routes"):
        return None
    ruta = datos["routes"][0]
    return (
        [[lat, lon] for lon, lat in ruta["geometry"]["coordinates"]],
        round(ruta["distance"] / 1000, 2),
    )


async def trazar(client: httpx.AsyncClient, puntos: List[List[float]]) -> Optional[Tuple[List[List[float]], float]]:
    """Geometría [[lat, lon], ...] y km por vía de una ruta que pasa por `puntos` en ese orden.

    None si no se pudo trazar (el motivo queda en `ultimo_error`). Si la misma ruta ya
    se está trazando (por ejemplo, la precarga después de asignar), espera ese resultado.
    """
    coordenadas = ";".join(_coordenada(lat, lon) for lat, lon in puntos)
    if coordenadas in _cache:
        return _cache[coordenadas]
    if coordenadas in _en_curso:
        return await asyncio.shield(_en_curso[coordenadas])

    futuro = asyncio.get_running_loop().create_future()
    _en_curso[coordenadas] = futuro
    resultado = None
    try:
        resultado = await _trazar_sin_cache(client, coordenadas)
        if resultado:
            if len(_cache) >= MAX_CACHE:
                _cache.clear()
            _cache[coordenadas] = resultado
        return resultado
    finally:
        # Quien espera la misma ruta recibe el resultado aunque esta consulta falle
        _en_curso.pop(coordenadas, None)
        futuro.set_result(resultado)


def precargar(rutas: List[List[List[float]]]) -> None:
    """Traza en segundo plano las rutas recién asignadas, para que el mapa las tenga listas"""
    async def tarea():
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for puntos in rutas:
                if len(puntos) >= 2:
                    await trazar(client, puntos)

    if servidores() and rutas:
        nueva = asyncio.get_running_loop().create_task(tarea())
        _tareas.add(nueva)
        nueva.add_done_callback(_tareas.discard)


async def estado() -> Dict:
    """Prueba un trazado corto para saber si OSRM responde desde el backend"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        datos = await _consultar(
            client, "/route/v1/driving/-74.08443,4.68674;-74.06374,4.66587", {"overview": "false"}
        )
    lista = servidores()
    return {
        "ok": datos is not None,
        "servidor": lista[_preferido] if datos is not None and lista else None,
        "servidores": lista,
        "error": None if datos is not None else ultimo_error,
    }


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
    if not servidores() or len(puntos) < 2:
        return None, None
    unicos: Dict[str, List[float]] = {}
    for lat, lon in puntos:
        unicos.setdefault(_coordenada(lat, lon), [lat, lon])
    claves = list(unicos)

    if len(_pares) > MAX_PARES:
        _pares.clear()
    # Si son muchos puntos, la tabla se pide por bloques (origen × destino)
    tamano = len(claves) if len(claves) <= MAX_PUNTOS_TABLA else MAX_PUNTOS_TABLA // 2
    bloques = [claves[i:i + tamano] for i in range(0, len(claves), tamano)]
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        for origenes in bloques:
            for destinos in bloques:
                if not await _completar_pares(client, origenes, destinos):
                    motivo = ultimo_error or "OSRM no respondió hace poco"
                    return None, f"El servidor no obtuvo los tiempos por vía ({motivo})"

    def valor(a: str, b: str, campo: int) -> Optional[float]:
        return 0.0 if a == b else _pares[(a, b)][campo]

    return MatrizVial(
        puntos=[unicos[c] for c in claves],
        km=[[valor(a, b, 0) for b in claves] for a in claves],
        minutos=[[valor(a, b, 1) for b in claves] for a in claves],
    ), None

"""Geocodificación de OTs sin GPS con Nominatim (OpenStreetMap), con caché en disco"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from datetime import date
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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

# Direcciones que se buscan en segundo plano después de cada extracción (Nominatim: 1 por segundo)
MAX_SEGUNDO_PLANO = 200

_cache: Optional[Dict[str, Optional[List[float]]]] = None
_refinando = False
_tareas: Set["asyncio.Task"] = set()


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


def _consultas(actividad: Activity) -> Tuple[Optional[str], Optional[str]]:
    """(dirección completa, municipio): la segunda es el respaldo, con ubicación aproximada"""
    municipio = ", ".join(p.strip() for p in [actividad.ciudad, actividad.departamento, "Colombia"] if p and p.strip())
    direccion = f"{actividad.direccion.strip()}, {municipio}" if actividad.direccion.strip() else None
    return direccion, (municipio if actividad.ciudad.strip() else None)


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


def _ubicar(actividad: Activity, coords: List[float], por_municipio: bool) -> None:
    actividad.coordinates = GPSCoordinates(latitude=coords[0], longitude=coords[1])
    actividad.gps = f"{coords[0]},{coords[1]}"
    actividad.coordenadas_aproximadas = True
    actividad.ubicacion_municipio = por_municipio


async def _refinar(consultas: List[str]) -> None:
    """Busca en segundo plano las direcciones que faltan; quedan en el caché para la próxima extracción"""
    global _refinando
    cache = _leer_cache()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for numero, consulta in enumerate(consultas, start=1):
                clave = normalizar_texto(consulta)
                if clave in cache:
                    continue
                await asyncio.sleep(PAUSA_SEGUNDOS)
                try:
                    coords = await _buscar(client, consulta)
                except httpx.HTTPError as e:
                    logger.warning(f"Geocodificación en segundo plano detenida: {e}")
                    break
                cache[clave] = [coords.latitude, coords.longitude] if coords else None
                if numero % 20 == 0:
                    _guardar_cache()
    finally:
        _guardar_cache()
        _refinando = False


async def geocodificar(actividades: List[Activity]) -> Tuple[int, List[str]]:
    """Ubica las OTs sin GPS: por dirección si ya se conoce y, si no, por su municipio.

    Los municipios son pocos y se buscan enseguida, así ninguna OT se queda sin ubicación.
    Con el resto del cupo de consultas se buscan las direcciones de las OTs más importantes
    (pendientes y de hoy en adelante); las demás se buscan en segundo plano y quedan en el
    caché para la próxima extracción. Todas se marcan como aproximadas.
    Devuelve (ubicadas, avisos).
    """
    global _refinando
    pendientes = [a for a in actividades if a.coordinates is None and any(_consultas(a))]
    if not pendientes or not settings.GEOCODING_ENABLED:
        return 0, []
    # Primero las que entran al plan (pendientes y asignadas de hoy en adelante); el historial después
    hoy = date.today().isoformat()
    pendientes.sort(key=lambda a: 0 if a.situacion == "pendiente" else (1 if (a.fecha_visita or "") >= hoy else 2))

    cache = _leer_cache()
    avisos: List[str] = []
    cambio_cache = False

    def aplicar_cache(actividad: Activity) -> bool:
        """Ubica la OT con lo que ya está en el caché: dirección primero, municipio después"""
        direccion, municipio = _consultas(actividad)
        for consulta in (direccion, municipio):
            if consulta and cache.get(normalizar_texto(consulta)):
                _ubicar(actividad, cache[normalizar_texto(consulta)], por_municipio=consulta != direccion)
                return consulta == direccion
        return False

    exactas = {id(a) for a in pendientes if aplicar_cache(a)}
    municipios = list(dict.fromkeys(
        m for a in pendientes if a.coordinates is None
        for m in [_consultas(a)[1]] if m and normalizar_texto(m) not in cache
    ))
    direcciones = list(dict.fromkeys(
        d for a in pendientes if id(a) not in exactas
        for d in [_consultas(a)[0]] if d and normalizar_texto(d) not in cache
    ))

    consultas_red = 0
    red_disponible = True
    async with httpx.AsyncClient(timeout=15.0) as client:
        for consulta in municipios + direcciones:
            if consultas_red >= settings.GEOCODING_MAX_POR_CONSULTA:
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
            cache[normalizar_texto(consulta)] = [coords.latitude, coords.longitude] if coords else None
            cambio_cache = True
    for actividad in pendientes:
        aplicar_cache(actividad)
    if cambio_cache:
        _guardar_cache()

    faltan = [d for d in direcciones if normalizar_texto(d) not in cache]
    if faltan and red_disponible and not _refinando:
        _refinando = True
        tarea = asyncio.get_running_loop().create_task(_refinar(faltan[:MAX_SEGUNDO_PLANO]))
        _tareas.add(tarea)
        tarea.add_done_callback(_tareas.discard)

    ubicadas = sum(1 for a in pendientes if a.coordinates is not None)
    sin_ubicar = len(pendientes) - ubicadas
    if faltan:
        avisos.append(
            f"{len(faltan)} OTs están ubicadas por su municipio mientras se busca la dirección exacta; "
            "vuelve a extraer en unos minutos para precisarlas"
        )
    if sin_ubicar:
        avisos.append(f"{sin_ubicar} OTs sin GPS no se encontraron ni por dirección ni por municipio")
    return ubicadas, avisos

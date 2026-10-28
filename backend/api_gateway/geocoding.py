"""Geocodificación de OTs sin GPS, con caché en disco.

Por defecto con Nominatim (OpenStreetMap, gratis, máximo 1 consulta por segundo). Si backend/.env trae
GOOGLE_GEOCODING_API_KEY se usa Google, que entiende mejor las direcciones de Colombia.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

import httpx

from shared.catalogo import normalizar_texto
from shared.config import settings
from shared.models import Activity, GPSCoordinates
from shared.utils import hoy as fecha_de_hoy, setup_logging, validate_gps_colombia

logger = setup_logging("api-gateway", settings.LOG_LEVEL)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GOOGLE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
# Nominatim exige un User-Agent que identifique la aplicación y máximo 1 consulta por segundo
USER_AGENT = "Ruteo-Bia/1.0"
PAUSA_SEGUNDOS = 1.1
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocache.json"

# Direcciones que se buscan en segundo plano después de cada extracción (Nominatim: 1 por segundo)
MAX_SEGUNDO_PLANO = 200
# Con Google no hay pausa: en una extracción se buscan hasta estas direcciones
MAX_GOOGLE = 500
# Una dirección que no se encontró se vuelve a buscar pasados estos días
DIAS_REINTENTO = 7
# Nominatim: desde este place_rank el resultado es una casa o un edificio; menos es la calle o el municipio
RANGO_DIRECCION = 28

_cache: Optional[Dict[str, Any]] = None
_refinando = False
_tareas: Set["asyncio.Task"] = set()
# Una sola fila para Nominatim: la extracción y el segundo plano comparten la pausa entre consultas
_turno: Optional[asyncio.Lock] = None
_ultima_consulta = 0.0


class Hallazgo(NamedTuple):
    lat: float
    lon: float
    preciso: bool  # la casa o el edificio; si no, el centro de la calle o del municipio


def proveedor() -> str:
    return "google" if settings.GOOGLE_GEOCODING_API_KEY else "nominatim"


def _leer_cache() -> Dict[str, Any]:
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


# Tipos de vía como se escriben en Colombia → como los nombra el mapa. El orden importa: «AV CRA» antes que «AV»
_TIPOS_VIA = [
    (r"(?:AVENIDA|AVDA|AV)\.?\s*(?:CARRERA|KRA|CRA|KR|CR)\.?", "Avenida Carrera"),
    (r"(?:AVENIDA|AVDA|AV)\.?\s*(?:CALLE|CLL|CL)\.?", "Avenida Calle"),
    (r"AK\.?", "Avenida Carrera"),
    (r"AC\.?", "Avenida Calle"),
    (r"(?:CALLE|CLL|CL|C)\.?", "Calle"),
    (r"(?:CARRERA|KRA|CRA|KR|CR)\.?", "Carrera"),
    (r"(?:DIAGONAL|DIAG|DG)\.?", "Diagonal"),
    (r"(?:TRANSVERSAL|TRANSV|TV|TR)\.?", "Transversal"),
    (r"(?:AVENIDA|AVDA|AV)\.?", "Avenida"),
]
# Número de la vía con letra, BIS y cuadrante: «58», «58A», «10 BIS», «10 Sur»
_VIA = r"\d+\s?[A-Z]?(?:\s+BIS)?(?:\s+(?:SUR|ESTE|NORTE|OESTE))?"


def normalizar_direccion(texto: str) -> str:
    """Una dirección colombiana como la entiende el mapa: «Cl. 58 #10-32 Apto 3» → «Calle 58 10-32».

    Expande el tipo de vía, quita «#» y «No.», y deja la dirección hasta el número de la casa (sin
    apartamento, barrio ni local). Lo que no empieza por un tipo de vía (una vereda, un sitio) queda igual.
    """
    direccion = " ".join(texto.split())
    for patron, nombre in _TIPOS_VIA:
        tipo = re.match(rf"^{patron}\s*(?=\d)", direccion, flags=re.IGNORECASE)
        if tipo:
            direccion = f"{nombre} {direccion[tipo.end():]}"
            break
    else:
        return direccion
    # «Calle 58 # 10-32», «Calle 58 No. 10 32», «Calle 58 10 32» → «Calle 58 10-32»
    numero = re.match(
        rf"^(.*?\s{_VIA})\s*(?:#|N[OoºÚú°]\.?|NUM(?:ERO)?\.?)?\s*(\d+\s?[A-Z]?)\s*(?:-|\s)\s*(\d+)\b",
        direccion, flags=re.IGNORECASE,
    )
    if numero:
        return f"{numero.group(1).strip()} {numero.group(2).replace(' ', '')}-{numero.group(3)}"
    return direccion


def _consultas(actividad: Activity) -> Tuple[Optional[str], Optional[str]]:
    """(dirección completa, municipio): la segunda es el respaldo, con ubicación aproximada"""
    municipio = ", ".join(p.strip() for p in [actividad.ciudad, actividad.departamento, "Colombia"] if p and p.strip())
    calle = normalizar_direccion(actividad.direccion.strip()) if actividad.direccion.strip() else ""
    direccion = f"{calle}, {municipio}" if calle else None
    return direccion, (municipio if actividad.ciudad.strip() else None)


async def _esperar_turno() -> None:
    """Nominatim pide máximo una consulta por segundo, entre todas las búsquedas de la app"""
    global _turno, _ultima_consulta
    if _turno is None:
        _turno = asyncio.Lock()
    async with _turno:
        espera = PAUSA_SEGUNDOS - (time.monotonic() - _ultima_consulta)
        if espera > 0:
            await asyncio.sleep(espera)
        _ultima_consulta = time.monotonic()


def _respuesta_rara(origen: str, error: Exception) -> httpx.HTTPError:
    # Una página de error o un aviso de límite en vez de resultados: se trata como si no respondiera
    return httpx.DecodingError(f"{origen} respondió algo que no son resultados: {error}")


async def _buscar_nominatim(client: httpx.AsyncClient, consulta: str) -> Optional[Hallazgo]:
    await _esperar_turno()
    respuesta = await client.get(
        NOMINATIM_URL,
        params={"q": consulta, "format": "jsonv2", "limit": 1, "countrycodes": "co"},
        headers={"User-Agent": USER_AGENT},
    )
    respuesta.raise_for_status()
    try:
        resultados = respuesta.json()
        if not resultados:
            return None
        primero = resultados[0]
        lat, lon = float(primero["lat"]), float(primero["lon"])
        rango = primero.get("place_rank")
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise _respuesta_rara("Nominatim", e) from e
    return Hallazgo(lat, lon, rango is None or int(rango) >= RANGO_DIRECCION)


async def _buscar_google(client: httpx.AsyncClient, consulta: str) -> Optional[Hallazgo]:
    respuesta = await client.get(GOOGLE_URL, params={
        "address": consulta, "components": "country:CO", "language": "es", "key": settings.GOOGLE_GEOCODING_API_KEY,
    })
    respuesta.raise_for_status()
    try:
        datos = respuesta.json()
        estado = datos.get("status")
        if estado == "ZERO_RESULTS":
            return None
        if estado != "OK":
            # REQUEST_DENIED (llave mala), OVER_QUERY_LIMIT…: no es «no encontrada», es que Google no sirvió
            raise httpx.HTTPError(f"Google respondió {estado}: {datos.get('error_message', '')}".strip())
        geometria = datos["results"][0]["geometry"]
        lat, lon = float(geometria["location"]["lat"]), float(geometria["location"]["lng"])
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        raise _respuesta_rara("Google", e) from e
    return Hallazgo(lat, lon, geometria.get("location_type") in ("ROOFTOP", "RANGE_INTERPOLATED"))


async def _buscar(client: httpx.AsyncClient, consulta: str) -> Optional[Hallazgo]:
    """Busca una dirección o un municipio en Colombia; None si no se encontró"""
    hallazgo = await (_buscar_google if proveedor() == "google" else _buscar_nominatim)(client, consulta)
    if hallazgo and not validate_gps_colombia(hallazgo.lat, hallazgo.lon)[0]:
        return None
    return hallazgo


def _guardar(cache: Dict[str, Any], consulta: str, hallazgo: Optional[Hallazgo]) -> None:
    if hallazgo is None:
        cache[normalizar_texto(consulta)] = {"sin": fecha_de_hoy().isoformat(), "por": proveedor()}
    else:
        cache[normalizar_texto(consulta)] = [hallazgo.lat, hallazgo.lon] + ([] if hallazgo.preciso else ["aprox"])


def _guardado(cache: Dict[str, Any], consulta: Optional[str]) -> Optional[Hallazgo]:
    valor = cache.get(normalizar_texto(consulta)) if consulta else None
    if isinstance(valor, list) and len(valor) >= 2:
        return Hallazgo(float(valor[0]), float(valor[1]), len(valor) < 3)
    return None


def _por_buscar(cache: Dict[str, Any], consulta: str) -> bool:
    """No está en el caché, o no se encontró hace más de DIAS_REINTENTO días o con otro proveedor"""
    valor = cache.get(normalizar_texto(consulta), "falta")
    if isinstance(valor, list):
        return False
    if isinstance(valor, dict) and valor.get("por") == proveedor():
        try:
            return date.fromisoformat(valor.get("sin", "")) < fecha_de_hoy() - timedelta(days=DIAS_REINTENTO)
        except ValueError:
            return True
    # Sin buscar, o un «no encontrada» de una versión anterior (sin fecha) o de otro proveedor
    return True


def _ubicar(actividad: Activity, hallazgo: Hallazgo, impreciso: bool) -> None:
    actividad.coordinates = GPSCoordinates(latitude=hallazgo.lat, longitude=hallazgo.lon)
    actividad.gps = f"{hallazgo.lat},{hallazgo.lon}"
    actividad.coordenadas_aproximadas = True
    actividad.ubicacion_imprecisa = impreciso


async def _refinar(consultas: List[str]) -> None:
    """Busca en segundo plano las direcciones que faltan; quedan en el caché para la próxima extracción"""
    global _refinando
    cache = _leer_cache()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for numero, consulta in enumerate(consultas, start=1):
                if not _por_buscar(cache, consulta):
                    continue
                try:
                    hallazgo = await _buscar(client, consulta)
                except httpx.HTTPError as e:
                    logger.warning(f"Geocodificación en segundo plano detenida: {e}")
                    break
                _guardar(cache, consulta, hallazgo)
                if numero % 20 == 0:
                    _guardar_cache()
    finally:
        _guardar_cache()
        _refinando = False


async def geocodificar(actividades: List[Activity]) -> Tuple[int, List[str]]:
    """Ubica las OTs sin GPS: por dirección si ya se conoce y, si no, por su municipio.

    Los municipios son pocos y se buscan enseguida, así ninguna OT se queda sin ubicación.
    Con el resto del cupo de consultas se buscan las direcciones de las OTs más importantes
    (pendientes y de hoy en adelante); con Nominatim las demás se buscan en segundo plano y
    quedan en el caché para la próxima extracción. Todas se marcan como aproximadas, y como
    imprecisas (no cuentan como cerca de nada) las que solo dan la calle o el municipio.
    Devuelve (ubicadas, avisos).
    """
    global _refinando
    pendientes = [a for a in actividades if a.coordinates is None and any(_consultas(a))]
    if not pendientes or not settings.GEOCODING_ENABLED:
        return 0, []
    # Primero las que entran al plan (pendientes y asignadas de hoy en adelante); el historial después
    hoy = fecha_de_hoy().isoformat()
    pendientes.sort(key=lambda a: 0 if a.situacion == "pendiente" else (1 if (a.fecha_visita or "") >= hoy else 2))

    cache = _leer_cache()
    avisos: List[str] = []
    cambio_cache = False

    def aplicar_cache(actividad: Activity) -> bool:
        """Ubica la OT con lo que ya está en el caché: dirección primero, municipio después.
        True si su dirección ya se buscó y se encontró (aunque sea solo la calle)."""
        direccion, municipio = _consultas(actividad)
        # Las versiones anteriores guardaban la dirección tal como venía: sirve mientras se busca la nueva
        anterior = f"{actividad.direccion.strip()}, {municipio}" if actividad.direccion.strip() and municipio else None
        por_direccion = _guardado(cache, direccion) or _guardado(cache, anterior)
        if por_direccion:
            _ubicar(actividad, por_direccion, impreciso=not por_direccion.preciso)
            return True
        por_municipio = _guardado(cache, municipio)
        if por_municipio:
            _ubicar(actividad, por_municipio, impreciso=True)
        return False

    resueltas = {id(a) for a in pendientes if aplicar_cache(a)}
    municipios = list(dict.fromkeys(
        m for a in pendientes if a.coordinates is None
        for m in [_consultas(a)[1]] if m and _por_buscar(cache, m)
    ))
    direcciones = list(dict.fromkeys(
        d for a in pendientes if id(a) not in resueltas
        for d in [_consultas(a)[0]] if d and _por_buscar(cache, d)
    ))

    cupo = MAX_GOOGLE if proveedor() == "google" else settings.GEOCODING_MAX_POR_CONSULTA
    consultas_red = 0
    red_disponible = True
    async with httpx.AsyncClient(timeout=15.0) as client:
        for consulta in municipios + direcciones:
            if consultas_red >= cupo:
                break
            consultas_red += 1
            try:
                hallazgo = await _buscar(client, consulta)
            except httpx.HTTPError as e:
                avisos.append(f"No se pudo geocodificar ({'Google' if proveedor() == 'google' else 'Nominatim'} no respondió): {e}")
                red_disponible = False
                break
            _guardar(cache, consulta, hallazgo)
            cambio_cache = True
    for actividad in pendientes:
        aplicar_cache(actividad)
    if cambio_cache:
        _guardar_cache()

    faltan = [d for d in direcciones if _por_buscar(cache, d)]
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

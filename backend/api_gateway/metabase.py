"""Lectura de OTs desde una pregunta (card) de Metabase"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from shared.catalogo import normalizar_texto, parse_coordenadas
from shared.config import settings
from shared.models import Activity, GPSCoordinates
from shared.utils import setup_logging, validate_gps_colombia

logger = setup_logging("api-gateway", settings.LOG_LEVEL)

# Nombres de columna que se reconocen automáticamente para cada campo de la OT
ALIAS_COLUMNAS: Dict[str, List[str]] = {
    # El código CO (Bia Code) va primero: es la llave que usa el resto del sistema
    "codigo_bia": ["bia code", "co", "codigo bia", "ot", "orden", "orden de trabajo", "orden trabajo", "numero ot",
                   "no ot", "id ot", "codigo ot", "codigo", "frontera", "codigo frontera"],
    "servicio": ["tipo de ot", "tipo ot", "tipo de orden", "servicio", "tipo servicio", "tipo de servicio",
                 "actividad", "tipo actividad",
                 "tipo de actividad", "maniobra", "tipo maniobra", "tipo"],
    "nombre": ["nombre", "cliente", "nombre cliente", "nombre del cliente", "razon social"],
    "direccion": ["direccion", "direccion ot", "direccion cliente", "address"],
    "ciudad": ["ciudad", "municipio", "city"],
    "departamento": ["departamento", "depto", "dpto"],
    "or_operador": ["or operador", "or", "operador de red", "operador red", "operador"],
    "gps": ["gps", "geolocalizacion", "coordenadas", "ubicacion", "lat lon", "latlon"],
    "latitud": ["latitud", "lat", "latitude"],
    "longitud": ["longitud", "lon", "lng", "long", "longitude"],
}
SERVICIO_POR_DEFECTO = "default"


class MetabaseError(Exception):
    """Error de configuración o de comunicación con Metabase, con mensaje para el usuario"""


def _clave_columna(nombre: str) -> str:
    return normalizar_texto(nombre).replace("_", " ")


def estado() -> Dict[str, Any]:
    """Qué tan configurada está la conexión, sin exponer credenciales"""
    if settings.METABASE_API_KEY:
        auth = "api_key"
    elif settings.METABASE_USERNAME and settings.METABASE_PASSWORD:
        auth = "usuario"
    else:
        auth = None
    return {
        "configurado": bool(settings.METABASE_URL and auth),
        "servidor": urlparse(settings.METABASE_URL).netloc or None,
        "autenticacion": auth,
        "card_id": settings.METABASE_CARD_ID or None,
    }


_token_sesion: Optional[str] = None


async def _encabezados(client: httpx.AsyncClient, renovar: bool = False) -> Dict[str, str]:
    global _token_sesion
    if settings.METABASE_API_KEY:
        return {"x-api-key": settings.METABASE_API_KEY}
    if not (settings.METABASE_USERNAME and settings.METABASE_PASSWORD):
        raise MetabaseError(
            "Falta configurar la autenticación de Metabase: METABASE_API_KEY o METABASE_USERNAME/METABASE_PASSWORD"
        )
    if _token_sesion is None or renovar:
        respuesta = await client.post(
            f"{settings.METABASE_URL.rstrip('/')}/api/session",
            json={"username": settings.METABASE_USERNAME, "password": settings.METABASE_PASSWORD},
        )
        if respuesta.status_code != 200:
            raise MetabaseError(f"Metabase rechazó el usuario/contraseña (HTTP {respuesta.status_code})")
        _token_sesion = respuesta.json()["id"]
    return {"X-Metabase-Session": _token_sesion}


async def consultar_pregunta(card_id: str) -> List[Dict[str, Any]]:
    """Ejecuta la pregunta y devuelve sus filas como diccionarios {columna: valor}"""
    if not settings.METABASE_URL:
        raise MetabaseError("Falta configurar METABASE_URL")
    if not str(card_id).strip().isdigit():
        raise MetabaseError(f"El id de la pregunta debe ser un número, llegó '{card_id}'")

    url = f"{settings.METABASE_URL.rstrip('/')}/api/card/{str(card_id).strip()}/query/json"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            respuesta = await client.post(url, headers=await _encabezados(client))
            if respuesta.status_code == 401 and not settings.METABASE_API_KEY:
                respuesta = await client.post(url, headers=await _encabezados(client, renovar=True))
    except httpx.RequestError as e:
        raise MetabaseError(f"No se pudo conectar con Metabase en {settings.METABASE_URL}: {e}")

    if respuesta.status_code in (401, 403):
        raise MetabaseError(f"Metabase no autorizó la consulta de la pregunta {card_id} (HTTP {respuesta.status_code})")
    if respuesta.status_code == 404:
        raise MetabaseError(f"La pregunta {card_id} no existe en Metabase")
    if respuesta.status_code not in (200, 202):
        raise MetabaseError(f"Metabase respondió HTTP {respuesta.status_code}: {respuesta.text[:300]}")

    filas = respuesta.json()
    if isinstance(filas, dict):
        # Metabase devuelve un objeto (no una lista) cuando la consulta falla
        raise MetabaseError(f"La pregunta {card_id} falló en Metabase: {filas.get('error') or filas}")
    return filas


def resolver_mapeo(columnas: List[str], mapeo_manual: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Campo de la OT → nombre de columna en Metabase.

    El mapeo manual (METABASE_COLUMN_MAP) manda; el resto se detecta por alias.
    """
    mapeo: Dict[str, str] = {}
    por_clave = {_clave_columna(c): c for c in columnas}
    for campo, columna in (mapeo_manual or {}).items():
        if columna in columnas:
            mapeo[campo] = columna
        elif _clave_columna(columna) in por_clave:
            mapeo[campo] = por_clave[_clave_columna(columna)]
    usadas = set(mapeo.values())
    for campo, alias in ALIAS_COLUMNAS.items():
        if campo in mapeo:
            continue
        for nombre in [campo.replace("_", " ")] + alias:
            columna = por_clave.get(nombre)
            if columna and columna not in usadas:
                mapeo[campo] = columna
                usadas.add(columna)
                break
    return mapeo


def _mapeo_configurado() -> Dict[str, str]:
    if not settings.METABASE_COLUMN_MAP.strip():
        return {}
    try:
        mapeo = json.loads(settings.METABASE_COLUMN_MAP)
    except json.JSONDecodeError as e:
        raise MetabaseError(f"METABASE_COLUMN_MAP no es un JSON válido: {e}")
    if not isinstance(mapeo, dict):
        raise MetabaseError("METABASE_COLUMN_MAP debe ser un objeto JSON {campo: columna}")
    return {str(k): str(v) for k, v in mapeo.items()}


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _numero(valor: Any) -> Optional[float]:
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = _texto(valor).replace(",", ".")
    if texto.count(".") > 1:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _coordenadas_fila(fila: Dict[str, Any], mapeo: Dict[str, str]) -> Optional[GPSCoordinates]:
    if "gps" in mapeo:
        coords = parse_coordenadas(_texto(fila.get(mapeo["gps"])))
        if coords:
            return coords
    if "latitud" in mapeo and "longitud" in mapeo:
        lat, lon = _numero(fila.get(mapeo["latitud"])), _numero(fila.get(mapeo["longitud"]))
        if lat is not None and lon is not None and validate_gps_colombia(lat, lon)[0]:
            return GPSCoordinates(latitude=lat, longitude=lon)
    return None


def filas_a_actividades(
    filas: List[Dict[str, Any]],
    mapeo_manual: Optional[Dict[str, str]] = None,
) -> Tuple[List[Activity], Dict[str, str], List[str]]:
    """Convierte las filas de Metabase en OTs. Devuelve (actividades, mapeo usado, avisos).

    Las OTs sin coordenadas se devuelven igual (coordinates=None) para geocodificarlas.
    """
    columnas = list(filas[0].keys()) if filas else []
    mapeo = resolver_mapeo(columnas, mapeo_manual if mapeo_manual is not None else _mapeo_configurado())
    faltantes = [c for c in ("codigo_bia", "or_operador") if c not in mapeo]
    if filas and faltantes:
        raise MetabaseError(
            f"No encontré las columnas para {', '.join(faltantes)} en la pregunta. "
            f"Columnas disponibles: {', '.join(columnas)}. "
            "Renómbralas en Metabase o defínelas en METABASE_COLUMN_MAP."
        )
    tiene_ubicacion = "gps" in mapeo or ("latitud" in mapeo and "longitud" in mapeo) or "direccion" in mapeo
    if filas and not tiene_ubicacion:
        raise MetabaseError(
            "La pregunta no tiene columnas de ubicación (GPS, Latitud/Longitud o Dirección). "
            f"Columnas disponibles: {', '.join(columnas)}"
        )

    avisos: List[str] = []
    actividades: List[Activity] = []
    vistos = set()
    duplicadas = 0
    for numero, fila in enumerate(filas, start=1):
        codigo = _texto(fila.get(mapeo["codigo_bia"]))
        if not codigo:
            avisos.append(f"Fila {numero}: sin código de OT; se omite")
            continue
        if codigo in vistos:
            duplicadas += 1
            continue
        vistos.add(codigo)

        coords = _coordenadas_fila(fila, mapeo)
        actividades.append(Activity(
            codigo_bia=codigo,
            servicio=_texto(fila.get(mapeo.get("servicio", ""))).lower() or SERVICIO_POR_DEFECTO,
            gps=f"{coords.latitude},{coords.longitude}" if coords else "",
            nombre=_texto(fila.get(mapeo.get("nombre", ""))),
            direccion=_texto(fila.get(mapeo.get("direccion", ""))),
            ciudad=_texto(fila.get(mapeo.get("ciudad", ""))),
            departamento=_texto(fila.get(mapeo.get("departamento", ""))),
            or_operador=_texto(fila.get(mapeo["or_operador"])) or "Sin OR",
            coordinates=coords,
        ))
    if duplicadas:
        avisos.append(f"{duplicadas} filas repetidas (mismo código de OT) se tomaron una sola vez")
    return actividades, mapeo, avisos

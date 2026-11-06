"""Lectura de OTs desde una pregunta (card) de Metabase"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import itertools
import json
import re
from collections import Counter
from datetime import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from dateutil import parser as dateutil_parser

from shared.catalogo import normalizar_texto, parse_coordenadas
from shared.config import settings
from shared.models import Activity, GPSCoordinates
from shared.utils import hoy, setup_logging, validate_gps_colombia

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
    # Para distinguir dos OTs del mismo CO
    "orden_trabajo": ["orden de trabajo", "orden trabajo", "numero ot", "id ot", "codigo ot", "ot"],
    # Asignación ya hecha en Metabase
    "situacion": ["situacion"],
    "estado_app": ["estado app", "status app"],
    # El estado de la OT en Olibia: solo se usa para dejar fuera las vencidas
    "estado": ["estado ot", "estado de la ot", "estado visita", "estado de la visita"],
    "fecha_visita": ["fecha de la visita", "fecha visita", "fecha"],
    "asignado_a": ["electricistas asignados", "electricistas", "tecnicos asignados", "tecnico asignado"],
    "contratista_asignado": ["contratista asignado", "contratista"],
    "electricista_id": ["id electricista", "id del electricista", "electrician id", "electrician"],
    # Quién creó la OT y cuándo
    "creado_por": ["creado por", "creada por", "creador", "creado por usuario", "usuario creador", "created by",
                   "creada por usuario", "autor"],
    "fecha_creacion": ["fecha de creacion", "fecha creacion", "creado el", "creada el", "created at",
                       "fecha de registro"],
    # La duración de una instalación depende del tipo de medida
    "tipo_medida": ["tipo de medida", "tipo medida", "medida", "measurement type", "measurement type id"],
    # Para unir la pregunta de desplazamientos: el id de la visita en la app de técnicos
    "id_visita": ["id visita", "id de la visita", "visit id", "visita id"],
    # Dónde y cuándo el técnico dio «Desplazamiento OK» en Olibia
    "desplazamiento_gps": ["gps desplazamiento", "gps desplazamiento ok", "ubicacion desplazamiento",
                           "ubicacion desplazamiento ok", "coordenadas desplazamiento", "coordenadas desplazamiento ok",
                           "desplazamiento ok gps", "desplazamiento ok ubicacion", "desplazamiento ok coordenadas"],
    "desplazamiento_latitud": ["latitud desplazamiento", "latitud desplazamiento ok", "lat desplazamiento",
                               "desplazamiento ok latitud", "desplazamiento ok lat"],
    "desplazamiento_longitud": ["longitud desplazamiento", "longitud desplazamiento ok", "lon desplazamiento",
                                "lng desplazamiento", "desplazamiento ok longitud", "desplazamiento ok lon"],
    "desplazamiento_fecha": ["fecha desplazamiento", "fecha desplazamiento ok", "hora desplazamiento",
                             "hora desplazamiento ok", "desplazamiento ok fecha", "desplazamiento ok hora",
                             "desplazamiento ok"],
}
SERVICIO_POR_DEFECTO = "default"

# Columnas de la pregunta de desplazamientos (los IN_ROUTE de electrician_status_tracking)
ALIAS_DESPLAZAMIENTOS: Dict[str, List[str]] = {
    "id_visita": ["id visita", "id de la visita", "visit id", "visita id"],
    "orden_trabajo": ["orden de trabajo", "orden trabajo", "card id"],
    "codigo_bia": ["bia code", "codigo bia", "internal bia code", "co"],
    "gps": ["gps desplazamiento", "ubicacion desplazamiento", "ubicacion desplazamiento ok", "ubicacion", "coordenadas"],
    "latitud": ["latitud desplazamiento", "latitude", "lat"],
    "longitud": ["longitud desplazamiento", "longitude", "lon", "lng"],
    "fecha": ["fecha desplazamiento", "hora desplazamiento", "hora marcado", "hora", "created at app", "created at"],
    # Cuándo y dónde marcó que llegó a la dirección (IN_ADDRESS)
    "llegada": ["fecha llegada", "hora llegada", "llegada", "llegada al sitio", "fecha llegada sitio"],
    "llegada_gps": ["gps llegada", "ubicacion llegada", "coordenadas llegada"],
    "llegada_latitud": ["latitud llegada", "lat llegada"],
    "llegada_longitud": ["longitud llegada", "lon llegada", "lng llegada"],
}

# Tipo de medida (como viene de Olibia o en español) → como se nombra en el tipo de OT
_MEDIDAS = {
    "direct": "directa", "directa": "directa",
    "semi direct": "semidirecta", "semidirect": "semidirecta", "semidirecta": "semidirecta", "semi directa": "semidirecta",
    "indirect": "indirecta", "indirecta": "indirecta",
}


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
            # Sin formato: fechas en ISO y números sin separadores de miles
            datos = {"format_rows": "false"}
            respuesta = await client.post(url, headers=await _encabezados(client), data=datos)
            if respuesta.status_code == 401 and not settings.METABASE_API_KEY:
                respuesta = await client.post(url, headers=await _encabezados(client, renovar=True), data=datos)
    except httpx.RequestError as e:
        raise MetabaseError(f"No se pudo conectar con Metabase en {settings.METABASE_URL}: {e}")

    if respuesta.status_code in (401, 403):
        raise MetabaseError(f"Metabase no autorizó la consulta de la pregunta {card_id} (HTTP {respuesta.status_code})")
    if respuesta.status_code == 404:
        raise MetabaseError(f"La pregunta {card_id} no existe en Metabase")
    if respuesta.status_code not in (200, 202):
        raise MetabaseError(f"Metabase respondió HTTP {respuesta.status_code}: {respuesta.text[:300]}")

    try:
        filas = respuesta.json()
    except ValueError:
        raise MetabaseError(
            f"Metabase respondió algo que no son filas de la pregunta {card_id} (¿se cortó la respuesta?). Intenta de nuevo."
        )
    if isinstance(filas, dict):
        # Metabase devuelve un objeto (no una lista) cuando la consulta falla
        raise MetabaseError(f"La pregunta {card_id} falló en Metabase: {filas.get('error') or filas}")
    return filas


def resolver_mapeo(columnas: List[str], mapeo_manual: Optional[Dict[str, str]] = None,
                   alias_columnas: Optional[Dict[str, List[str]]] = None) -> Dict[str, str]:
    """Campo de la OT → nombre de columna en Metabase.

    El mapeo manual (METABASE_COLUMN_MAP) manda; el resto se detecta por alias (los de la pregunta de
    OTs, u otros como los de la pregunta de desplazamientos).
    """
    mapeo: Dict[str, str] = {}
    por_clave = {_clave_columna(c): c for c in columnas}
    for campo, columna in (mapeo_manual or {}).items():
        if columna in columnas:
            mapeo[campo] = columna
        elif _clave_columna(columna) in por_clave:
            mapeo[campo] = por_clave[_clave_columna(columna)]
    usadas = set(mapeo.values())
    for campo, alias in (alias_columnas or ALIAS_COLUMNAS).items():
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


def _coordenadas_fila(fila: Dict[str, Any], mapeo: Dict[str, str], prefijo: str = "") -> Optional[GPSCoordinates]:
    """Las coordenadas de la fila: la OT, o con prefijo «desplazamiento_» las del desplazamiento OK"""
    gps, latitud, longitud = f"{prefijo}gps", f"{prefijo}latitud", f"{prefijo}longitud"
    if gps in mapeo:
        coords = parse_coordenadas(_texto(fila.get(mapeo[gps])))
        if coords:
            return coords
    if latitud in mapeo and longitud in mapeo:
        lat, lon = _numero(fila.get(mapeo[latitud])), _numero(fila.get(mapeo[longitud]))
        if lat is not None and lon is not None and validate_gps_colombia(lat, lon)[0]:
            return GPSCoordinates(latitude=lat, longitude=lon)
    return None


def _desplazamiento_en(fila: Dict[str, Any], mapeo: Dict[str, str]) -> Optional[str]:
    """Cuándo dio el técnico «Desplazamiento OK»: «YYYY-MM-DD HH:MM» o solo la fecha"""
    if "desplazamiento_fecha" not in mapeo:
        return None
    fecha, hora = _momento(fila.get(mapeo["desplazamiento_fecha"]))
    return f"{fecha} {hora}" if fecha and hora else fecha


# Valores de «Situación» (los de la pregunta recomendada y sus variantes) y de «Estado app» de Olibia.
# Se comparan completos: «No asignada» no es «asignada», «Cancelada» no es «pendiente».
SITUACIONES = {
    "pendiente por asignar": "pendiente", "por asignar": "pendiente", "pendiente": "pendiente", "sin asignar": "pendiente",
    "asignada": "asignada", "asignado": "asignada", "reasignada": "asignada", "reasignado": "asignada",
    "en ejecucion": "asignada", "lista para ejecutar": "asignada", "programada": "asignada",
    "cerrada": "cerrada", "cerrado": "cerrada", "completada": "cerrada", "ejecutada": "cerrada",
    "cierre exitoso": "cerrada", "cierre fallido": "cerrada",
    "cancelada": "descartada", "cancelado": "descartada", "anulada": "descartada", "rechazada": "descartada",
}
ESTADOS_APP = {
    "pending assignment": "pendiente",
    "assigned": "asignada", "reassigned": "asignada", "accepted": "asignada", "scheduled": "asignada",
    "in progress": "asignada", "on the way": "asignada", "started": "asignada",
    "completed": "cerrada", "finished": "cerrada", "closed": "cerrada", "done": "cerrada", "failed": "cerrada",
    "cancelled": "descartada", "canceled": "descartada", "rejected": "descartada", "deleted": "descartada",
}


# Vencidas en Olibia («Vencida», «Cierre vencido», «Vencimiento», «Expirada», EXPIRED, OVERDUE…): no
# entran, como las canceladas. Se buscan en Situación, Estado, Estado app y cualquier columna cuyo
# nombre diga estado, status o situación.
PALABRAS_VENCIDA = ("vencid", "vencim", "expir", "caducad", "overdue")
NOMBRES_COLUMNA_ESTADO = ("estado", "status", "situacion")
NO_ENTRAN = ("descartada", "vencida")


def _clave_estado(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalizar_texto(texto)).strip()


def _columnas_estado(mapeo: Dict[str, str], columnas: List[str]) -> List[str]:
    """Las columnas que dicen el estado de la OT: las reconocidas y cualquier otra que lo diga en el nombre"""
    propias = [mapeo[c] for c in ("situacion", "estado", "estado_app") if c in mapeo]
    otras = [c for c in columnas if c not in propias and any(n in _clave_columna(c) for n in NOMBRES_COLUMNA_ESTADO)]
    return propias + otras


def _valor_vencido(fila: Dict[str, Any], columnas_estado: List[str]) -> Optional[str]:
    """El valor que dice que la OT está vencida en Olibia, o None"""
    for columna in columnas_estado:
        texto = _texto(fila.get(columna))
        if texto and any(p in _clave_estado(texto) for p in PALABRAS_VENCIDA):
            return texto
    return None


def _estado(fila: Dict[str, Any], mapeo: Dict[str, str]) -> Tuple[str, Optional[str]]:
    """(estado, valor que no se reconoció) según «Situación» o, si no la trae, «Estado app».

    El estado es "pendiente", "asignada", "cerrada" (ya se hizo: cuenta como asignada) o "descartada"
    (cancelada o rechazada: no entra); las vencidas se apartan antes (ver _valor_vencido). Un archivo
    sin columnas de estado trae OTs por asignar; un valor que no se reconoce se toma como por asignar,
    para que se vea, y se avisa.
    """
    desconocido = None
    for campo, valores in (("situacion", SITUACIONES), ("estado_app", ESTADOS_APP)):
        if campo not in mapeo:
            continue
        texto = _texto(fila.get(mapeo[campo]))
        if _clave_estado(texto) in valores:
            return valores[_clave_estado(texto)], None
        desconocido = desconocido or (texto or None)
    return "pendiente", desconocido


def _momento(valor: Any) -> Tuple[Optional[str], Optional[str]]:
    """(fecha YYYY-MM-DD, hora HH:MM) en la hora de Colombia de lo que mande Metabase o un archivo.

    Con desfase o en UTC (…Z) se pasa a la hora de Colombia; sin desfase ya es hora local. Medianoche
    es una fecha sin hora y se toma tal cual. En texto, el día va primero (29/10/2026). Lo que no es
    una fecha (por ejemplo «Semana 3») da (None, None).
    """
    texto = _texto(valor)
    if not texto:
        return None, None
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", texto):
            momento = dateutil_parser.isoparse(texto)
        else:
            momento = dateutil_parser.parse(texto, dayfirst=True)
    except (ValueError, OverflowError):
        return None, None
    if momento.time() == time(0, 0):
        return momento.date().isoformat(), None
    if momento.tzinfo is not None:
        momento = momento.astimezone(ZoneInfo(settings.ZONA_HORARIA))
    return momento.date().isoformat(), momento.strftime("%H:%M")


def _fecha(valor: Any) -> Optional[str]:
    return _momento(valor)[0]


def _hora(valor: Any) -> Optional[str]:
    return _momento(valor)[1]


def _servicio(fila: Dict[str, Any], mapeo: Dict[str, str]) -> str:
    """Tipo de OT; las instalaciones llevan el tipo de medida ("Instalación semidirecta")"""
    servicio = _texto(fila.get(mapeo.get("servicio", ""))) or SERVICIO_POR_DEFECTO
    if "tipo_medida" in mapeo and normalizar_texto(servicio) == "instalacion":
        medida = _MEDIDAS.get(re.sub(r"[^a-z]+", " ", normalizar_texto(_texto(fila.get(mapeo["tipo_medida"])))).strip())
        if medida:
            return f"{servicio} {medida}"
    return servicio


def filas_a_actividades(
    filas: List[Dict[str, Any]],
    mapeo_manual: Optional[Dict[str, str]] = None,
) -> Tuple[List[Activity], Dict[str, str], List[str]]:
    """Convierte las filas de Metabase en OTs. Devuelve (actividades, mapeo usado, avisos).

    Las OTs sin coordenadas se devuelven igual (coordinates=None) para geocodificarlas.
    """
    columnas = list(filas[0].keys()) if filas else []
    mapeo = resolver_mapeo(columnas, mapeo_manual if mapeo_manual is not None else _mapeo_configurado())
    if filas and "or_operador" not in mapeo:
        raise MetabaseError(
            "No encontré la columna del OR en la pregunta. "
            f"Columnas disponibles: {', '.join(columnas)}. "
            "Renómbrala como 'OR' en Metabase o defínela en METABASE_COLUMN_MAP."
        )
    tiene_ubicacion = "gps" in mapeo or ("latitud" in mapeo and "longitud" in mapeo) or "direccion" in mapeo
    if filas and not tiene_ubicacion:
        raise MetabaseError(
            "La pregunta no tiene columnas de ubicación (GPS, Latitud/Longitud o Dirección). "
            f"Columnas disponibles: {', '.join(columnas)}"
        )

    avisos: List[str] = []
    if filas and "codigo_bia" not in mapeo:
        avisos.append(
            "La pregunta no tiene columna de código (Bia Code u OT); cada fila se numeró como OT-1, OT-2, ..."
        )
    # Vencida en cualquiera de las columnas de estado: no entra, aunque la Situación diga por asignar
    columnas_estado = _columnas_estado(mapeo, columnas)
    estados: Dict[int, Tuple[str, Optional[str]]] = {}
    valores_vencida: Counter = Counter()
    for numero, fila in enumerate(filas, start=1):
        valor = _valor_vencido(fila, columnas_estado)
        if valor:
            estados[numero] = ("vencida", None)
            valores_vencida[valor] += 1
        else:
            estados[numero] = _estado(fila, mapeo)
    descartadas = sum(1 for estado, _ in estados.values() if estado == "descartada")
    vencidas = sum(valores_vencida.values())
    # Por asignar con la fecha de visita ya pasada: también vencidas, no aplican
    hoy_iso = hoy().isoformat()
    pasadas = 0
    if "fecha_visita" in mapeo:
        for numero, fila in enumerate(filas, start=1):
            fecha = _fecha(fila.get(mapeo["fecha_visita"]))
            if estados[numero][0] == "pendiente" and fecha and fecha < hoy_iso:
                estados[numero] = ("vencida", None)
                pasadas += 1
    desconocidos = Counter(valor for _, valor in estados.values() if valor)
    if descartadas:
        avisos.append(f"OTs canceladas o rechazadas que no se cargan: {descartadas}")
    if vencidas:
        valores = ", ".join(f"«{v}» ({n})" for v, n in valores_vencida.most_common(4))
        avisos.append(f"OTs vencidas en Olibia que no se cargan: {vencidas} ({valores})")
    if pasadas:
        avisos.append(f"OTs por asignar con la fecha de visita ya pasada (vencidas), que no se cargan: {pasadas}")
    if desconocidos:
        valores = ", ".join(f"«{v}» ({n})" for v, n in desconocidos.most_common(4))
        avisos.append(f"Estados que Ruteo no conoce, tomados como por asignar: {valores}. Revisa la pregunta")
    codigos, avisos_filas = _codigos_por_fila(filas, mapeo, estados)
    avisos.extend(avisos_filas)
    actividades: List[Activity] = []
    fechas_raras = 0
    for numero, fila in enumerate(filas, start=1):
        codigo = codigos.get(numero)
        if not codigo:
            continue
        estado = estados[numero][0]
        valor_fecha = fila.get(mapeo["fecha_visita"]) if "fecha_visita" in mapeo else None
        fecha_visita, hora_visita = _momento(valor_fecha)
        if _texto(valor_fecha) and not fecha_visita:
            fechas_raras += 1
        coords = _coordenadas_fila(fila, mapeo)
        actividades.append(Activity(
            codigo_bia=codigo,
            servicio=_servicio(fila, mapeo),
            gps=f"{coords.latitude},{coords.longitude}" if coords else "",
            nombre=_texto(fila.get(mapeo.get("nombre", ""))),
            direccion=_texto(fila.get(mapeo.get("direccion", ""))),
            ciudad=_texto(fila.get(mapeo.get("ciudad", ""))),
            departamento=_texto(fila.get(mapeo.get("departamento", ""))),
            or_operador=_texto(fila.get(mapeo["or_operador"])) or "Sin OR",
            coordinates=coords,
            extras=dict(fila),
            situacion="pendiente" if estado == "pendiente" else "asignada",
            cerrada=estado == "cerrada",
            fecha_visita=fecha_visita,
            hora_visita=hora_visita,
            asignado_a=(_texto(fila.get(mapeo["asignado_a"])) or None) if "asignado_a" in mapeo else None,
            electricista_id=(_texto(fila.get(mapeo["electricista_id"])) or None) if "electricista_id" in mapeo else None,
            contratista_asignado=(
                (_texto(fila.get(mapeo["contratista_asignado"])) or None) if "contratista_asignado" in mapeo else None
            ),
            creado_por=(_texto(fila.get(mapeo["creado_por"])) or None) if "creado_por" in mapeo else None,
            fecha_creacion=_fecha(fila.get(mapeo["fecha_creacion"])) if "fecha_creacion" in mapeo else None,
            desplazamiento_ok=_coordenadas_fila(fila, mapeo, "desplazamiento_"),
            desplazamiento_ok_en=_desplazamiento_en(fila, mapeo),
        ))
    if fechas_raras:
        avisos.append(f"Fechas de visita que no se entendieron (quedaron sin fecha): {fechas_raras}")
    if len(actividades) != len(filas):
        avisos.insert(0, f"Metabase trajo {len(filas)} filas y quedaron {len(actividades)} OTs")
    return actividades, mapeo, avisos


def _llave(valor: Any) -> str:
    """Un id para unir dos preguntas: 123, 123.0 y «123» son el mismo"""
    texto = _texto(valor)
    return texto[:-2] if texto.endswith(".0") and texto[:-2].isdigit() else texto


def hora_desplazamiento(valor: Any) -> Tuple[Optional[str], Optional[str]]:
    """(fecha, hora) en Colombia de un desplazamiento. La app de técnicos guarda la hora en UTC y Metabase
    la manda sin zona («2026-11-05T19:27:12.035»): sin zona se toma como UTC (DESPLAZAMIENTOS_EN_UTC)"""
    texto = _texto(valor)
    if (settings.DESPLAZAMIENTOS_EN_UTC and re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", texto)
            and not re.search(r"(Z|[+-]\d{2}:?\d{2})$", texto)):
        texto += "Z"
    return _momento(texto)


def unir_desplazamientos(actividades: List[Activity], mapeo: Dict[str, str], filas: List[Dict[str, Any]]) -> List[str]:
    """Pone en cada OT dónde y cuándo el técnico dio «Desplazamiento OK», según la pregunta de
    desplazamientos (los IN_ROUTE de la app de técnicos). Se unen por «Id visita» o, si esa pregunta no
    lo trae, por la orden de trabajo o el código; vale el último de cada visita. Devuelve avisos.
    """
    if not filas:
        return []
    columnas = resolver_mapeo(list(filas[0].keys()), {}, ALIAS_DESPLAZAMIENTOS)
    llaves = [campo for campo in ("id_visita", "orden_trabajo", "codigo_bia") if campo in columnas and campo in mapeo]
    if not llaves:
        return ["La pregunta de desplazamientos no se puede unir con las OTs: agrega «Id visita» a las dos preguntas"]
    if "gps" not in columnas and not ("latitud" in columnas and "longitud" in columnas):
        return ["La pregunta de desplazamientos no trae la ubicación: le faltan las columnas de latitud y longitud"]

    def momento(fila: Dict[str, Any], campo: str) -> Optional[str]:
        fecha, hora = hora_desplazamiento(fila.get(columnas[campo])) if campo in columnas else (None, None)
        return f"{fecha} {hora}" if fecha and hora else fecha

    ultimos: Dict[Tuple[str, str], Tuple[str, GPSCoordinates, Optional[str], Optional[str], Optional[GPSCoordinates]]] = {}
    for fila in filas:
        coords = _coordenadas_fila(fila, columnas)
        if not coords:
            continue
        cuando, llegada = momento(fila, "fecha"), momento(fila, "llegada")
        sitio = _coordenadas_fila(fila, columnas, "llegada_")
        for campo in llaves:
            valor = _llave(fila.get(columnas[campo]))
            if valor and ((campo, valor) not in ultimos or (cuando or "") > ultimos[(campo, valor)][0]):
                ultimos[(campo, valor)] = (cuando or "", coords, cuando, llegada, sitio)

    unidas = 0
    for actividad in actividades:
        if actividad.desplazamiento_ok:
            continue  # La pregunta de OTs ya lo trae
        for campo in llaves:
            encontrado = ultimos.get((campo, _llave(actividad.extras.get(mapeo[campo]))))
            if encontrado:
                actividad.desplazamiento_ok, actividad.desplazamiento_ok_en = encontrado[1], encontrado[2]
                actividad.llegada_sitio_en, actividad.llegada_sitio = encontrado[3], encontrado[4]
                unidas += 1
                break
    if ultimos and not unidas:
        return [f"La pregunta de desplazamientos trajo {len(filas)} filas, pero ninguna es de las OTs cargadas: revisa "
                "que las dos tengan el mismo «Id visita»"]
    return []


def _ejemplos(codigos: List[str]) -> str:
    distintos = list(dict.fromkeys(codigos))
    return ", ".join(distintos[:3]) + ("…" if len(distintos) > 3 else "")


def _codigos_por_fila(
    filas: List[Dict[str, Any]], mapeo: Dict[str, str], estados: Dict[int, Tuple[str, Optional[str]]],
) -> Tuple[Dict[int, str], List[str]]:
    """Número de fila → código con el que entra al plan; las filas que no entran no aparecen.

    Cada fila es una visita y una OT (mismo código y misma orden) puede traer varias: la vigente es
    la que sigue por asignar o, si ninguna, la más reciente, y usa el código tal cual. Las visitas
    anteriores ya asignadas o cerradas entran aparte con su fecha (ocuparon a su técnico ese día);
    las anteriores que dicen «por asignar» quedaron atrás con la nueva visita y no cuentan. Dos OTs
    distintas con el mismo código se distinguen con el número de la orden. Las canceladas y las
    vencidas no entran.
    """
    avisos: List[str] = []
    ots: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for numero, fila in enumerate(filas, start=1):
        if estados[numero][0] in NO_ENTRAN:
            continue
        codigo = _texto(fila.get(mapeo["codigo_bia"])) if "codigo_bia" in mapeo else f"OT-{numero}"
        if not codigo:
            avisos.append(f"Fila {numero}: sin código de OT; se omite")
            continue
        orden = _texto(fila.get(mapeo["orden_trabajo"])) if "orden_trabajo" in mapeo else ""
        fecha, hora = _momento(fila.get(mapeo["fecha_visita"]) if "fecha_visita" in mapeo else None)
        ots.setdefault((codigo, orden), []).append({
            "numero": numero,
            "fecha": fecha or "",
            "hora": hora or "",
            "pendiente": estados[numero][0] == "pendiente",
        })

    repetidas = 0
    viejas: List[str] = []
    vigentes: Dict[Tuple[str, str], Dict[str, Any]] = {}
    anteriores: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for clave, visitas in ots.items():
        unicas: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for visita in visitas:
            momento = (visita["fecha"], visita["hora"])
            if momento in unicas:
                repetidas += 1
                # Entre copias de la misma visita vale la que dice «por asignar»
                if not visita["pendiente"]:
                    continue
            unicas[momento] = visita
        # Primero la que sigue por asignar, luego la más reciente; las sin fecha al final
        ordenadas = sorted(unicas.values(), key=lambda v: (v["pendiente"], v["fecha"], v["hora"]), reverse=True)
        vigentes[clave] = ordenadas[0]
        anteriores[clave] = []
        for visita in ordenadas[1:]:
            if visita["pendiente"]:
                viejas.append(clave[0])
            else:
                anteriores[clave].append(visita)

    codigos: Dict[int, str] = {}
    usados = set()

    def usar(numero: int, candidatos: List[str]) -> str:
        extras = (f"{candidatos[-1]} #{n}" for n in itertools.count(2))
        codigo = next(c for c in itertools.chain(candidatos, extras) if c not in usados)
        usados.add(codigo)
        codigos[numero] = codigo
        return codigo

    # Si dos OTs comparten código, lo lleva tal cual la que sigue por asignar o la más reciente
    con_fecha: List[str] = []
    for clave in sorted(vigentes, key=lambda c: (vigentes[c]["pendiente"], vigentes[c]["fecha"], vigentes[c]["hora"]),
                        reverse=True):
        codigo, orden = clave
        propio = usar(vigentes[clave]["numero"], [codigo, f"{codigo} / OT {orden}"] if orden else [codigo])
        for visita in anteriores[clave]:
            fecha = visita["fecha"] or "sin fecha"
            con_fecha.append(usar(visita["numero"], [f"{propio} · {fecha}", f"{propio} · {fecha} {visita['hora']}".strip()]))

    if repetidas:
        avisos.append(f"Filas repetidas (misma OT y misma visita) que cuentan una sola vez: {repetidas}")
    if viejas:
        avisos.append(
            "Visitas anteriores de OTs que siguen por asignar, que no cuentan aparte porque vale la más reciente: "
            f"{len(viejas)} ({_ejemplos(viejas)})"
        )
    if con_fecha:
        avisos.append(
            "Visitas anteriores ya asignadas o cerradas, que aparecen con su fecha junto al código: "
            f"{len(con_fecha)} ({_ejemplos(con_fecha)})"
        )
    return codigos, avisos

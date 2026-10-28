"""Lectura de OTs desde una pregunta (card) de Metabase"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import itertools
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from dateutil import parser as dateutil_parser

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
    # Para distinguir dos OTs del mismo CO
    "orden_trabajo": ["orden de trabajo", "orden trabajo", "numero ot", "id ot", "codigo ot", "ot"],
    # Asignación ya hecha en Metabase
    "situacion": ["situacion"],
    "estado_app": ["estado app", "status app"],
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
}
SERVICIO_POR_DEFECTO = "default"

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


def _situacion(fila: Dict[str, Any], mapeo: Dict[str, str]) -> str:
    """'pendiente' o 'asignada', según la columna Situación o el estado de la app de campo"""
    if "situacion" in mapeo:
        valor = normalizar_texto(_texto(fila.get(mapeo["situacion"])))
        if "pendiente" in valor:
            return "pendiente"
        # Las cerradas también cuentan como asignadas: ocuparon tiempo de su técnico ese día
        if "asignad" in valor or "cerrad" in valor:
            return "asignada"
    if "estado_app" in mapeo:
        valor = normalizar_texto(_texto(fila.get(mapeo["estado_app"])))
        return "pendiente" if valor in ("", "pending_assignment", "pending assignment") else "asignada"
    return "pendiente"


def _cerrada(fila: Dict[str, Any], mapeo: Dict[str, str]) -> bool:
    """La visita ya se hizo: la columna Situación dice «Cerrada»"""
    return "situacion" in mapeo and "cerrad" in normalizar_texto(_texto(fila.get(mapeo["situacion"])))


def _hora(valor: Any) -> Optional[str]:
    """HH:MM de una fecha con hora (ISO o texto); None si no trae hora o es medianoche"""
    coincidencia = re.search(r"[T ](\d{1,2}):(\d{2})", _texto(valor))
    if not coincidencia or (coincidencia.group(1) in ("0", "00") and coincidencia.group(2) == "00"):
        return None
    return f"{int(coincidencia.group(1)):02d}:{coincidencia.group(2)}"


def _fecha(valor: Any) -> Optional[str]:
    """Fecha YYYY-MM-DD a partir de lo que mande Metabase (ISO o texto con formato)"""
    texto = _texto(valor)
    if not texto:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", texto):
        return texto[:10]
    try:
        return dateutil_parser.parse(texto, fuzzy=True).date().isoformat()
    except (ValueError, OverflowError):
        return None


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
    codigos, avisos_filas = _codigos_por_fila(filas, mapeo)
    avisos.extend(avisos_filas)
    actividades: List[Activity] = []
    for numero, fila in enumerate(filas, start=1):
        codigo = codigos.get(numero)
        if not codigo:
            continue
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
            situacion=_situacion(fila, mapeo),
            cerrada=_cerrada(fila, mapeo),
            fecha_visita=_fecha(fila.get(mapeo["fecha_visita"])) if "fecha_visita" in mapeo else None,
            hora_visita=_hora(fila.get(mapeo["fecha_visita"])) if "fecha_visita" in mapeo else None,
            asignado_a=(_texto(fila.get(mapeo["asignado_a"])) or None) if "asignado_a" in mapeo else None,
            electricista_id=(_texto(fila.get(mapeo["electricista_id"])) or None) if "electricista_id" in mapeo else None,
            contratista_asignado=(
                (_texto(fila.get(mapeo["contratista_asignado"])) or None) if "contratista_asignado" in mapeo else None
            ),
            creado_por=(_texto(fila.get(mapeo["creado_por"])) or None) if "creado_por" in mapeo else None,
            fecha_creacion=_fecha(fila.get(mapeo["fecha_creacion"])) if "fecha_creacion" in mapeo else None,
        ))
    if len(actividades) != len(filas):
        avisos.insert(0, f"Metabase trajo {len(filas)} filas y quedaron {len(actividades)} OTs")
    return actividades, mapeo, avisos


def _ejemplos(codigos: List[str]) -> str:
    distintos = list(dict.fromkeys(codigos))
    return ", ".join(distintos[:3]) + ("…" if len(distintos) > 3 else "")


def _codigos_por_fila(filas: List[Dict[str, Any]], mapeo: Dict[str, str]) -> Tuple[Dict[int, str], List[str]]:
    """Número de fila → código con el que entra al plan; las filas que no entran no aparecen.

    Cada fila es una visita y una OT (mismo código y misma orden) puede traer varias: la vigente es
    la que sigue por asignar o, si ninguna, la más reciente, y usa el código tal cual. Las visitas
    anteriores ya asignadas o cerradas entran aparte con su fecha (ocuparon a su técnico ese día);
    las anteriores que dicen «por asignar» quedaron atrás con la nueva visita y no cuentan. Dos OTs
    distintas con el mismo código se distinguen con el número de la orden.
    """
    avisos: List[str] = []
    ots: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for numero, fila in enumerate(filas, start=1):
        codigo = _texto(fila.get(mapeo["codigo_bia"])) if "codigo_bia" in mapeo else f"OT-{numero}"
        if not codigo:
            avisos.append(f"Fila {numero}: sin código de OT; se omite")
            continue
        orden = _texto(fila.get(mapeo["orden_trabajo"])) if "orden_trabajo" in mapeo else ""
        valor = fila.get(mapeo["fecha_visita"]) if "fecha_visita" in mapeo else None
        ots.setdefault((codigo, orden), []).append({
            "numero": numero,
            "fecha": _fecha(valor) or "",
            "hora": _hora(valor) or "",
            "pendiente": _situacion(fila, mapeo) == "pendiente",
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

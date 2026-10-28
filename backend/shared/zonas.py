"""Zonas de los equipos Bia y del tránsito (data/zonas_bia.json)

- equipos: qué OTs atiende cada equipo de técnicos Bia (por OR y zona).
- transito: zonas donde los desplazamientos tardan más.
"""
import json
from pathlib import Path
from typing import List, Optional, Tuple

from .models import CoberturaEquipo, GPSCoordinates, OperadorRed, Zona, ZonaTransito
from .operadores import clave, normalizar_departamento, resolver_or
from .utils import haversine_distance

DEFAULT_ZONAS_PATH = Path(__file__).resolve().parent.parent / "data" / "zonas_bia.json"


def cargar_zonas(path: Optional[str] = None) -> Tuple[List[CoberturaEquipo], List[ZonaTransito]]:
    ruta = Path(path) if path else DEFAULT_ZONAS_PATH
    if not ruta.exists():
        return [], []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return (
        [CoberturaEquipo(**e) for e in datos.get("equipos", [])],
        [ZonaTransito(**z) for z in datos.get("transito", [])],
    )


def _km(lat: float, lon: float, punto: GPSCoordinates) -> float:
    return haversine_distance(GPSCoordinates(latitude=lat, longitude=lon), punto)


def en_zona(zona: Zona, ciudad: str, departamento: str, punto: Optional[GPSCoordinates]) -> bool:
    """La OT está en la zona si su municipio está en la lista o si cae dentro del radio"""
    if clave(ciudad) in {clave(m) for m in zona.municipios}:
        if not (zona.departamento and departamento) or (
            normalizar_departamento(zona.departamento) == normalizar_departamento(departamento)
        ):
            return True
    return punto is not None and _km(zona.latitud, zona.longitud, punto) <= zona.radio_km


def atiende_or(cobertura: CoberturaEquipo, nombre_or: str, operadores: List[OperadorRed]) -> bool:
    operador = resolver_or(nombre_or, operadores)
    nombres = {clave(nombre_or)} | ({clave(operador.nombre)} if operador else set())
    return bool(nombres & {clave(o) for o in cobertura.ors})


def recargo_transito(zonas: List[ZonaTransito], punto: GPSCoordinates) -> Optional[ZonaTransito]:
    """Zona de tránsito donde cae el punto (la de mayor recargo si hay varias)"""
    dentro = [z for z in zonas if _km(z.latitud, z.longitud, punto) <= z.radio_km]
    return max(dentro, key=lambda z: (z.recargo_pct, z.minutos_extra)) if dentro else None

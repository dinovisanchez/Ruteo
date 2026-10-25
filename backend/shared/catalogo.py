"""Catálogo de sedes operativas: bases de Bia y sedes de contratistas.

Lee el CSV exportado de la hoja "Data Contratista" (mismos encabezados).
Las coordenadas salen de la columna "Geolocalizacion" ("lat, lon"); las
columnas Latitud/Longitud de la hoja vienen con el formato de números
dañado, así que solo se usan si falta la geolocalización.
"""
import csv
import io
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from .models import GPSCoordinates, SedeOperativa
from .utils import validate_gps_colombia

DEFAULT_CATALOGO_PATH = Path(__file__).resolve().parent.parent / "data" / "contratistas.csv"

_SUFIJO_LEGAL = re.compile(r"[\s,]+(s\.?\s?a\.?\s?s\.?|s\.?\s?a\.?|ltda\.?)\s*$", re.IGNORECASE)

# Encabezado normalizado de la hoja → campo interno
_COLUMNAS = {
    "razon social": "razon_social",
    "nit": "nit",
    "ciudad": "ciudad",
    "departamento": "departamento",
    "actividad economica": "tipo",
    "direccion": "direccion",
    "geolocalizacion": "geolocalizacion",
    "latitud": "latitud",
    "longitud": "longitud",
}


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples"""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar_texto(texto)).strip("-")


def nombre_empresa(razon_social: str) -> str:
    """Razón social sin el sufijo societario (S.A.S, SAS, S.A, LTDA)"""
    return _SUFIJO_LEGAL.sub("", razon_social.strip()).strip()


def clave_empresa(razon_social: str) -> str:
    return slug(nombre_empresa(razon_social))


def parse_coordenadas(texto: str) -> Optional[GPSCoordinates]:
    """Convierte "lat, lon" en coordenadas; None si no es válido o cae fuera de Colombia"""
    partes = [p.strip() for p in str(texto or "").split(",")]
    if len(partes) != 2:
        return None
    try:
        lat, lon = float(partes[0]), float(partes[1])
    except ValueError:
        return None
    valido, _ = validate_gps_colombia(lat, lon)
    return GPSCoordinates(latitude=lat, longitude=lon) if valido else None


def _coordenada_decimal(texto: str) -> Optional[float]:
    """Acepta "6,2089578" o "6.2089578"; rechaza valores con separadores de miles"""
    valor = str(texto or "").strip().replace(",", ".")
    if valor.count(".") > 1:
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def parse_catalogo_csv(texto: str) -> Tuple[List[SedeOperativa], List[str]]:
    """Devuelve (sedes, avisos). Las filas sin ubicación válida se omiten con un aviso."""
    lector = csv.DictReader(io.StringIO(texto.lstrip("﻿")))
    columnas = {
        col: _COLUMNAS[normalizar_texto(col)]
        for col in (lector.fieldnames or [])
        if normalizar_texto(col) in _COLUMNAS
    }
    if "razon_social" not in columnas.values():
        raise ValueError("El CSV del catálogo no tiene la columna 'Razón social'")

    sedes: List[SedeOperativa] = []
    avisos: List[str] = []
    ids_usados: Dict[str, int] = {}

    for numero, fila_cruda in enumerate(lector, start=2):
        fila = {campo: (fila_cruda.get(col) or "").strip() for col, campo in columnas.items()}
        razon_social = fila.get("razon_social", "")
        if not razon_social:
            continue

        coords = parse_coordenadas(fila.get("geolocalizacion", ""))
        if coords is None:
            lat = _coordenada_decimal(fila.get("latitud", ""))
            lon = _coordenada_decimal(fila.get("longitud", ""))
            if lat is not None and lon is not None and validate_gps_colombia(lat, lon)[0]:
                coords = GPSCoordinates(latitude=lat, longitude=lon)
        ciudad = fila.get("ciudad", "")
        if coords is None:
            avisos.append(f"Fila {numero}: {razon_social} ({ciudad or 'sin ciudad'}) no tiene ubicación válida; se omite")
            continue

        tipo = "base" if normalizar_texto(fila.get("tipo", "")) == "base" else "contratista"
        empresa_id = clave_empresa(razon_social)
        ciudad_principal = re.sub(r"\bd\.?\s?c\.?$", "", ciudad.split(",")[0], flags=re.IGNORECASE)
        sede_id = empresa_id if tipo == "base" else f"{empresa_id}-{slug(ciudad_principal)}"
        ids_usados[sede_id] = ids_usados.get(sede_id, 0) + 1
        if ids_usados[sede_id] > 1:
            sede_id = f"{sede_id}-{ids_usados[sede_id]}"

        sedes.append(SedeOperativa(
            id=sede_id,
            empresa_id=empresa_id,
            empresa=nombre_empresa(razon_social),
            nit=fila.get("nit") or None,
            tipo=tipo,
            ciudad=ciudad,
            departamento=fila.get("departamento", ""),
            direccion=fila.get("direccion", ""),
            coordinates=coords,
        ))

    return sedes, avisos


def cargar_catalogo(path: Optional[str] = None, url: Optional[str] = None) -> Tuple[List[SedeOperativa], List[str]]:
    """Carga el catálogo desde una URL CSV (hoja publicada) o desde el archivo local.

    Si la URL falla se usa el archivo local y se agrega un aviso.
    """
    avisos: List[str] = []
    if url:
        try:
            respuesta = httpx.get(url, timeout=20.0, follow_redirects=True)
            respuesta.raise_for_status()
            sedes, avisos_csv = parse_catalogo_csv(respuesta.text)
            return sedes, avisos_csv
        except Exception as e:
            avisos.append(f"No se pudo leer el catálogo desde la URL ({e}); se usa el archivo local")

    ruta = Path(path) if path else DEFAULT_CATALOGO_PATH
    sedes, avisos_csv = parse_catalogo_csv(ruta.read_text(encoding="utf-8"))
    return sedes, avisos + avisos_csv

"""OTs desde un archivo Excel o CSV: sus filas se leen igual que las de la pregunta de Metabase"""
import io
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

EXTENSIONES = (".xlsx", ".csv")


class ArchivoError(Exception):
    """El archivo no se pudo leer, con mensaje para el usuario"""


def _valor(valor: Any) -> Any:
    """Celdas vacías como None y fechas como texto ISO, como llegan de Metabase"""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor is pd.NaT:
        return None
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, str):
        return valor.strip() or None
    return valor


def _leer_csv(contenido: bytes) -> pd.DataFrame:
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel en Windows guarda los CSV en latin-1
        texto = contenido.decode("latin-1")
    # Coma o punto y coma (Excel en español); todo como texto para no perder ceros a la izquierda
    return pd.read_csv(io.StringIO(texto), sep=None, engine="python", dtype=str)


def leer_filas(nombre: str, contenido: bytes) -> List[Dict[str, Any]]:
    """Filas del archivo como diccionarios {columna: valor}"""
    extension = Path(nombre).suffix.lower()
    if extension not in EXTENSIONES:
        raise ArchivoError(f"Formato no soportado: usa un archivo {' o '.join(EXTENSIONES)} (un .xls se guarda como .xlsx)")
    try:
        tabla = _leer_csv(contenido) if extension == ".csv" else pd.read_excel(io.BytesIO(contenido))
    except Exception as e:
        raise ArchivoError(f"No se pudo leer {nombre}: {e}")
    tabla = tabla.dropna(how="all")
    if tabla.empty:
        raise ArchivoError(f"{nombre} no tiene filas")
    return [{str(columna).strip(): _valor(valor) for columna, valor in fila.items()}
            for fila in tabla.to_dict(orient="records")]

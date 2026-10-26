"""Operadores de Red (OR) de Colombia y los departamentos que atiende cada uno.

El catálogo está en data/operadores_red.csv. Sirve para que, sin una lista
manual de contratistas por OR, una OT vaya a los contratistas con sede en los
departamentos donde opera su OR.
"""
import csv
import re
from pathlib import Path
from typing import List, Optional

from .catalogo import normalizar_texto
from .models import OperadorRed

DEFAULT_OPERADORES_PATH = Path(__file__).resolve().parent.parent / "data" / "operadores_red.csv"

_SINONIMOS_DEPARTAMENTO = {
    "bogota d c": "bogota",
    "bogota dc": "bogota",
    "bogota distrito capital": "bogota",
    "distrito capital": "bogota",
    "santafe de bogota": "bogota",
    "valle": "valle del cauca",
    "guajira": "la guajira",
    "norte santander": "norte de santander",
    "san andres": "san andres y providencia",
    "san andres providencia y santa catalina": "san andres y providencia",
}


def clave(texto: str) -> str:
    """Minúsculas, sin tildes y solo letras y números separados por un espacio"""
    return re.sub(r"[^a-z0-9]+", " ", normalizar_texto(texto)).strip()


def normalizar_departamento(texto: str) -> str:
    k = re.sub(r"^(departamento|depto|dpto)( del?)? ", "", clave(texto))
    return _SINONIMOS_DEPARTAMENTO.get(k, k)


def cargar_operadores(path: Optional[str] = None) -> List[OperadorRed]:
    ruta = Path(path) if path else DEFAULT_OPERADORES_PATH
    operadores = []
    with ruta.open(encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            nombre = (fila.get("OR") or "").strip()
            if not nombre:
                continue
            operadores.append(OperadorRed(
                nombre=nombre,
                alias=[a.strip() for a in (fila.get("Alias") or "").split("|") if a.strip()],
                departamentos=[d.strip() for d in (fila.get("Departamentos") or "").split("|") if d.strip()],
                notas=(fila.get("Notas") or "").strip(),
            ))
    return operadores


def resolver_or(nombre: str, operadores: List[OperadorRed]) -> Optional[OperadorRed]:
    """Encuentra el OR del catálogo aunque el nombre venga distinto ("AIR-E S.A.S. E.S.P.", "Enel Colombia")"""
    buscado = clave(nombre)
    if not buscado:
        return None
    for operador in operadores:
        if buscado in {clave(operador.nombre), *(clave(a) for a in operador.alias)}:
            return operador
    # El nombre trae texto de más: gana el alias más largo que aparezca como palabras completas
    mejor, largo = None, 0
    for operador in operadores:
        for alias in [operador.nombre, *operador.alias]:
            a = clave(alias)
            if len(a) >= 3 and f" {a} " in f" {buscado} " and len(a) > largo:
                mejor, largo = operador, len(a)
    return mejor

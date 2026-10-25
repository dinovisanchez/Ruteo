"""Muestra las columnas de una tabla de Metabase y busca en qué tablas hay direcciones o coordenadas.

Usa METABASE_URL y la API key (o usuario/contraseña) de backend/.env; no imprime credenciales.

Uso, desde la carpeta backend con el .venv activo:
    python -m scripts.explorar_metabase --tabla 22375
    python -m scripts.explorar_metabase --tabla 22375 --buscar
    python -m scripts.explorar_metabase --base 2344 --buscar
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import httpx

from shared.catalogo import normalizar_texto
from shared.config import settings

# Fragmentos de nombre de columna que suelen indicar ubicación
PISTAS_UBICACION = ["direcc", "address", "latitud", "longitud", "latitude", "longitude", "gps", "coorden", "geoloc"]


def _cliente() -> httpx.Client:
    if not settings.METABASE_URL:
        sys.exit("Falta METABASE_URL en backend/.env")
    cliente = httpx.Client(base_url=settings.METABASE_URL.rstrip("/"), timeout=60.0)
    if settings.METABASE_API_KEY:
        cliente.headers["x-api-key"] = settings.METABASE_API_KEY
    elif settings.METABASE_USERNAME and settings.METABASE_PASSWORD:
        respuesta = cliente.post(
            "/api/session",
            json={"username": settings.METABASE_USERNAME, "password": settings.METABASE_PASSWORD},
        )
        if respuesta.status_code != 200:
            sys.exit(f"Metabase rechazó el usuario/contraseña (HTTP {respuesta.status_code})")
        cliente.headers["X-Metabase-Session"] = respuesta.json()["id"]
    else:
        sys.exit("Falta METABASE_API_KEY (o METABASE_USERNAME/METABASE_PASSWORD) en backend/.env")
    return cliente


def _get(cliente: httpx.Client, ruta: str) -> dict:
    respuesta = cliente.get(ruta)
    if respuesta.status_code != 200:
        sys.exit(f"Metabase respondió HTTP {respuesta.status_code} en {ruta}: {respuesta.text[:300]}")
    return respuesta.json()


def mostrar_tabla(cliente: httpx.Client, tabla_id: int) -> int:
    """Imprime las columnas de la tabla y devuelve el id de su base de datos"""
    tabla = _get(cliente, f"/api/table/{tabla_id}/query_metadata")
    print(f"Tabla {tabla_id}: {tabla.get('schema')}.{tabla.get('name')} ({tabla.get('display_name')}) · base {tabla.get('db_id')}")
    for campo in tabla.get("fields", []):
        print(f"  {campo['name']:40s} {campo.get('display_name', ''):40s} {campo.get('base_type', '')}")
    return tabla.get("db_id")


def buscar_ubicacion(cliente: httpx.Client, base_id: int) -> None:
    metadata = _get(cliente, f"/api/database/{base_id}/metadata")
    encontrados = []
    for tabla in metadata.get("tables", []):
        for campo in tabla.get("fields", []):
            nombre = normalizar_texto(campo["name"])
            if any(pista in nombre for pista in PISTAS_UBICACION):
                encontrados.append((tabla["id"], f"{tabla.get('schema')}.{tabla['name']}", campo["name"]))
    print(f"\nColumnas de ubicación en la base {base_id} ({len(encontrados)}):")
    for tabla_id, tabla, campo in sorted(encontrados, key=lambda e: (e[1], e[2])):
        print(f"  tabla {tabla_id:<8} {tabla:50s} {campo}")
    if not encontrados:
        print("  (ninguna; puede que la API key no tenga permiso sobre todas las tablas)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tabla", type=int, help="Id de la tabla (source-table en la URL de la pregunta)")
    parser.add_argument("--base", type=int, help="Id de la base de datos (database en la URL de la pregunta)")
    parser.add_argument("--buscar", action="store_true", help="Buscar columnas de dirección o coordenadas en la base")
    args = parser.parse_args()
    if not args.tabla and not args.base:
        parser.error("Indica --tabla, --base o ambos")

    with _cliente() as cliente:
        base_id = args.base
        if args.tabla:
            base_id = base_id or mostrar_tabla(cliente, args.tabla)
        if args.buscar:
            buscar_ubicacion(cliente, base_id)


if __name__ == "__main__":
    main()

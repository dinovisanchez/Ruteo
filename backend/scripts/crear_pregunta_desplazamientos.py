"""Crea en Metabase la pregunta de desplazamientos de Ruteo: dónde y cuándo cada técnico dio
«Desplazamiento OK» (IN_ROUTE en electrician_status_tracking, en la base de la app de técnicos).

Usa METABASE_URL y la API key de backend/.env. No imprime credenciales ni datos de técnicos: solo
cuántas filas trae, las horas de los últimos desplazamientos (para revisar la zona horaria) y
cuántas OTs de la pregunta de Ruteo se pueden unir.

Uso, desde la carpeta backend:
    .venv/bin/python -m scripts.crear_pregunta_desplazamientos           # la crea y la prueba
    .venv/bin/python -m scripts.crear_pregunta_desplazamientos --sql     # solo el SQL, para pegarlo a mano
    .venv/bin/python -m scripts.crear_pregunta_desplazamientos --revisar 12345   # prueba una ya creada
    .venv/bin/python -m scripts.crear_pregunta_desplazamientos --actualizar 12345  # le pone el SQL de ahora
    .venv/bin/python -m scripts.crear_pregunta_desplazamientos --tabla otro_esquema.electrician_status_tracking
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Any, Dict, List, Optional

import httpx

from api_gateway.metabase import ALIAS_COLUMNAS, ALIAS_DESPLAZAMIENTOS, _llave, hora_desplazamiento, resolver_mapeo
from scripts.explorar_metabase import _cliente
from shared.config import settings

BASE_APP_TECNICOS = 496
NOMBRE = "Ruteo · Desplazamientos OK (IN_ROUTE)"

SQL = """-- Ruteo · Desplazamientos: el último «Desplazamiento OK» (IN_ROUTE) de cada visita, con su ubicación.
-- Ruteo la une a sus OTs por «Id visita». Las horas van en UTC, como las guarda la app de técnicos: Ruteo las
-- pasa a la hora de Colombia.
-- «Fecha llegada»: cuándo marcó que llegó a la dirección (IN_ADDRESS) después de ese desplazamiento.
SELECT DISTINCT ON (t.visit_id)
  t.visit_id                                AS "Id visita",
  COALESCE(t.created_at_app, t.created_at)  AS "Fecha desplazamiento",
  t.latitude                                AS "Latitud desplazamiento",
  t.longitude                               AS "Longitud desplazamiento",
  llegada.hora                              AS "Fecha llegada"
FROM __TABLA__ t
LEFT JOIN LATERAL (
  SELECT MIN(COALESCE(a.created_at_app, a.created_at)) AS hora
  FROM __TABLA__ a
  WHERE a.visit_id = t.visit_id
    AND a.deleted_at IS NULL
    AND a.electrician_status = 'IN_ADDRESS'
    AND COALESCE(a.created_at_app, a.created_at) >= COALESCE(t.created_at_app, t.created_at)
) llegada ON true
WHERE t.deleted_at IS NULL
  AND t.electrician_status = 'IN_ROUTE'
  AND t.latitude IS NOT NULL AND t.latitude <> 0
  AND COALESCE(t.created_at_app, t.created_at) >= CURRENT_DATE - INTERVAL '__DIAS__ days'
ORDER BY t.visit_id, COALESCE(t.created_at_app, t.created_at) DESC
"""


# En Bia está en la base 496 (prod-electrician-visits), esquema public
TABLA = "public.electrician_status_tracking"


def sql(dias: int, tabla: str = TABLA) -> str:
    if not all(parte.replace("_", "").isalnum() for parte in tabla.split(".")):
        sys.exit(f"Nombre de tabla no válido: {tabla} (usa esquema.tabla, solo letras, números y _)")
    return SQL.replace("__DIAS__", str(int(dias))).replace("__TABLA__", tabla)


def crear(cliente: httpx.Client, base: int, dias: int, coleccion: Optional[int], tabla: str) -> int:
    pregunta = {
        "name": NOMBRE,
        "description": "La usa Ruteo para mostrar en cada CO dónde y cuándo el técnico dio «Desplazamiento OK».",
        "display": "table",
        "visualization_settings": {},
        "dataset_query": {"type": "native", "database": base, "native": {"query": sql(dias, tabla), "template-tags": {}}},
        "collection_id": coleccion,
    }
    respuesta = cliente.post("/api/card", json=pregunta)
    if respuesta.status_code in (401, 403):
        sys.exit("La API key no puede crear preguntas en Metabase. Créala a mano: corre este comando con --sql, pega "
                 f"el SQL en una pregunta nueva de SQL nativo sobre la base {base} y luego pruébala con --revisar <número>.")
    if respuesta.status_code not in (200, 202):
        sys.exit(f"Metabase no creó la pregunta (HTTP {respuesta.status_code}): {respuesta.text[:300]}")
    return respuesta.json()["id"]


def actualizar(cliente: httpx.Client, card_id: str, base: int, dias: int, tabla: str) -> None:
    """Le pone el SQL de ahora a una pregunta ya creada, sin cambiarle el número"""
    consulta = {"type": "native", "database": base, "native": {"query": sql(dias, tabla), "template-tags": {}}}
    respuesta = cliente.put(f"/api/card/{card_id}", json={"dataset_query": consulta})
    if respuesta.status_code in (401, 403):
        sys.exit(f"La API key no puede editar la pregunta {card_id}. Edítala a mano: pega el SQL de --sql en ella.")
    if respuesta.status_code not in (200, 202):
        sys.exit(f"Metabase no actualizó la pregunta {card_id} (HTTP {respuesta.status_code}): {respuesta.text[:300]}")


def filas_de(cliente: httpx.Client, card_id: Any) -> List[Dict[str, Any]]:
    respuesta = cliente.post(f"/api/card/{card_id}/query/json", data={"format_rows": "false"})
    if respuesta.status_code not in (200, 202):
        sys.exit(f"La pregunta {card_id} no respondió (HTTP {respuesta.status_code}): {respuesta.text[:300]}")
    filas = respuesta.json()
    if isinstance(filas, dict):
        sys.exit(f"La pregunta {card_id} falló en Metabase: {filas.get('error') or filas}")
    return filas


def revisar(cliente: httpx.Client, card_id: Any) -> None:
    filas = filas_de(cliente, card_id)
    print(f"La pregunta {card_id} trae {len(filas)} desplazamientos.")
    if not filas:
        print("  Sin filas: revisa que la base sea la de la app de técnicos y que haya desplazamientos en esos días.")
        return
    columnas = resolver_mapeo(list(filas[0].keys()), {}, ALIAS_DESPLAZAMIENTOS)
    faltan = [c for c in ("id_visita", "latitud", "longitud") if c not in columnas]
    if faltan:
        print(f"  Le faltan columnas que Ruteo necesita: {', '.join(faltan)}. Usa el SQL de --sql.")
        return
    if "llegada" in columnas:
        con_llegada = sum(1 for f in filas if f.get(columnas["llegada"]))
        print(f"  {con_llegada} {'tiene' if con_llegada == 1 else 'tienen'} la hora de llegada a la dirección (IN_ADDRESS).")
    if "fecha" in columnas:
        horas = sorted((str(f.get(columnas["fecha"])) for f in filas if f.get(columnas["fecha"])), reverse=True)[:3]
        print("  Horas de los últimos desplazamientos: como las manda Metabase → como las muestra Ruteo (hora de")
        print("  Colombia). Compáralas con un desplazamiento que conozcas:")
        for hora in horas:
            fecha, en_colombia = hora_desplazamiento(hora)
            print(f"    {hora}  →  {fecha} {en_colombia or ''}")

    # ¿Se une con la pregunta de Ruteo?
    if not settings.METABASE_CARD_ID:
        print("  (Sin METABASE_CARD_ID en backend/.env no puedo revisar la unión con la pregunta de Ruteo.)")
        return
    ots = filas_de(cliente, settings.METABASE_CARD_ID)
    mapeo = resolver_mapeo(list(ots[0].keys()) if ots else [], {}, ALIAS_COLUMNAS)
    if "id_visita" not in mapeo:
        print(f"  La pregunta de Ruteo ({settings.METABASE_CARD_ID}) no tiene la columna «Id visita»: agrégala con el id")
        print("  de la visita de la app de técnicos (el mismo visit_id) y vuelve a correr --revisar.")
        return
    visitas = {_llave(f.get(columnas["id_visita"])) for f in filas}
    unidas = sum(1 for f in ots if _llave(f.get(mapeo["id_visita"])) in visitas)
    print(f"  {unidas} de las {len(ots)} filas de la pregunta de Ruteo tienen su desplazamiento.")
    if not unidas:
        print("  Ninguna coincide: revisa que «Id visita» de la pregunta de Ruteo sea el mismo visit_id de la app de técnicos.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sql", action="store_true", help="Solo mostrar el SQL de la pregunta")
    parser.add_argument("--revisar", metavar="ID", help="Probar una pregunta de desplazamientos ya creada")
    parser.add_argument("--actualizar", metavar="ID", help="Ponerle el SQL de ahora a una pregunta ya creada (mismo número)")
    parser.add_argument("--base", type=int, default=BASE_APP_TECNICOS, help=f"Base de la app de técnicos ({BASE_APP_TECNICOS})")
    parser.add_argument("--dias", type=int, default=7, help="Cuántos días atrás trae (7)")
    parser.add_argument("--coleccion", type=int, help="Id de la colección donde guardarla (por defecto, la raíz)")
    parser.add_argument("--tabla", default=TABLA,
                        help=f"La tabla de estados de los técnicos, con su esquema si hace falta ({TABLA})")
    args = parser.parse_args()

    if args.sql:
        print(sql(args.dias, args.tabla))
        return
    with _cliente() as cliente:
        if args.revisar:
            revisar(cliente, args.revisar)
            return
        if args.actualizar:
            actualizar(cliente, args.actualizar, args.base, args.dias, args.tabla)
            print(f"Actualicé la pregunta {args.actualizar}: ahora trae también la hora de llegada a la dirección.\n")
            revisar(cliente, args.actualizar)
            return
        card_id = crear(cliente, args.base, args.dias, args.coleccion, args.tabla)
        print(f"Creé la pregunta «{NOMBRE}» con el número {card_id}.\n")
        revisar(cliente, card_id)
        print(f"\nPon en backend/.env (y en Render → Environment):  METABASE_DESPLAZAMIENTOS_CARD_ID={card_id}")
        print("y vuelve a correr ./iniciar.sh.")


if __name__ == "__main__":
    main()

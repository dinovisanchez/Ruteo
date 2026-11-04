"""El gateway de punta a punta: Metabase (simulado) → OTs → plan del día, archivo, utilización y seguridad"""
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api_gateway import metabase
from conftest import dia

BOGOTA = {"Ciudad": "Bogotá", "Departamento": "Bogotá D.C."}


def fila(codigo, situacion, fecha, lat, lon, **extra):
    datos = {"Bia Code": codigo, "Orden de trabajo": hash(codigo) % 100000, "Situación": situacion,
             "Fecha de la visita": fecha, "OR": "ENEL COLOMBIA S.A. E.S.P.", "Dirección": f"Calle {codigo}",
             "Tipo de OT": "Visita previa", "Latitud": lat, "Longitud": lon,
             # Metabase manda todas las columnas en cada fila, vacías si no aplican
             "Electricistas asignados": None, "Contratista asignado": None, **BOGOTA}
    datos.update(extra)
    return datos


FILAS = [
    fila("PEND1", "Pendiente por asignar", f"{dia(0)}T09:00:00", 4.680, -74.050),
    fila("PEND2", "Pendiente por asignar", None, 4.6805, -74.0505),
    fila("ASIG1", "Asignada", f"{dia(0)}T10:00:00", 4.681, -74.051,
         **{"Electricistas asignados": "CARLOS ANDRES SALAS", "Contratista asignado": "Bia Energy"}),
    fila("CONTR", "Asignada", f"{dia(0)}T11:00:00", 4.650, -74.090,
         **{"Electricistas asignados": "Carla Salas", "Contratista asignado": "MONTAJES MTE S.A.S"}),
    fila("CERR", "Cerrada", f"{dia(0)}T07:00:00", 4.640, -74.080,
         **{"Electricistas asignados": "Juan Reyes", "Contratista asignado": "Bia Energy"}),
]


@pytest.fixture
def con_metabase(monkeypatch, cliente):
    async def pregunta(card_id):
        return [dict(f) for f in FILAS]

    monkeypatch.setattr(metabase, "consultar_pregunta", pregunta)
    return cliente


def test_salud_y_host_permitido(cliente):
    assert cliente.get("/api/health").json()["status"] == "healthy"
    # Otro nombre de servidor (DNS rebinding) no llega a la app
    assert TestClient(cliente.app, base_url="http://malicioso.example").get("/api/health").status_code == 400


def test_ots_desde_metabase(con_metabase):
    datos = con_metabase.get("/api/metabase/ots").json()
    ots = {a["codigo_bia"]: a for a in datos["actividades"]}
    assert sorted(ots) == ["ASIG1", "CERR", "CONTR", "PEND1", "PEND2"]
    assert ots["CERR"]["cerrada"] and ots["PEND1"]["hora_visita"] == "09:00"
    assert datos["ors"] == {"ENEL COLOMBIA S.A. E.S.P.": 5}


def _plan(cliente, actividades, tecnicos_ids, **extra):
    pedido = {"modo": "automatico", "actividades": actividades, "tecnicos_ids": tecnicos_ids, "dia": dia(0), **extra}
    respuesta = cliente.post("/api/asignar", json=pedido)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_plan_del_dia(con_metabase):
    actividades = con_metabase.get("/api/metabase/ots").json()["actividades"]
    tecnicos = {t["nombre"]: t["id"] for t in con_metabase.get("/api/asignacion/config").json()["tecnicos"]}
    bogota = [tecnicos["Carlos Salas"], tecnicos["Juan Jaramillo"]]
    resultado = _plan(con_metabase, actividades, bogota)
    decisiones = {d["codigo_bia"]: d for d in resultado["decisiones"]}
    # Las pendientes quedan sugeridas y siguen pendientes; la de Carlos se queda con él
    assert decisiones["PEND1"]["situacion"] == "pendiente" and decisiones["PEND1"]["enviar_a"] != "sin_asignar"
    assert decisiones["ASIG1"]["fijada"] and "Carlos Salas" in decisiones["ASIG1"]["responsable"]
    # La del contratista no se le cuenta a Carlos Salas aunque «Carla Salas» se parezca
    assert decisiones["CONTR"]["enviar_a"] in ("contratista", "externo")
    assert "Carlos" not in (decisiones["CONTR"]["responsable"] or "")
    # Juan Reyes (de la cerrada) no está disponible: no se reasigna
    assert decisiones["CERR"]["enviar_a"] == "externo" and "no se reasigna" in decisiones["CERR"]["motivo"]
    # Las dos pendientes están a ~70 m de la de Carlos: van con él
    assert decisiones["PEND1"]["responsable"] == decisiones["ASIG1"]["responsable"]
    assert decisiones["PEND2"]["responsable"] == decisiones["ASIG1"]["responsable"]


def test_lote_sin_cerradas(con_metabase):
    actividades = con_metabase.get("/api/metabase/ots").json()["actividades"]
    tecnicos = [t["id"] for t in con_metabase.get("/api/asignacion/config").json()["tecnicos"]]
    pedido = {"modo": "automatico", "actividades": actividades, "tecnicos_ids": tecnicos, "dia": dia(0)}
    solo_cerrada = con_metabase.post("/api/asignar/lote", json={**pedido, "codigos": ["CERR"]})
    assert solo_cerrada.status_code == 400
    propuesta = con_metabase.post("/api/asignar/lote", json={**pedido, "codigos": ["PEND1", "CERR"]}).json()
    codigos = [c for g in propuesta["grupos"] for c in g["codigos"]] + [s["codigo"] for s in propuesta["sin_tecnico"]]
    assert codigos == ["PEND1"]


def test_archivo_csv_con_punto_y_coma_y_tildes(cliente):
    texto = "Bia Code;OR;Dirección;Ciudad;Situación;Fecha de la visita;Latitud;Longitud\n" \
            f"CO01;Enel;Calle 1;Bogotá;Pendiente por asignar;{dia(1)};4.65;-74.08\n" \
            "CO02;Enel;Calle 2;Bogotá;Asignada;;4.66;-74.07\n"
    respuesta = cliente.post("/api/upload", files={"file": ("ots.csv", texto.encode("latin-1"), "text/csv")})
    assert respuesta.status_code == 200, respuesta.text
    ots = {a["codigo_bia"]: a for a in respuesta.json()["actividades"]}
    assert ots["CO01"]["fecha_visita"] == dia(1) and ots["CO01"]["ciudad"] == "Bogotá"
    assert ots["CO02"]["situacion"] == "asignada" and ots["CO02"]["coordinates"]["latitude"] == 4.66


def test_archivo_excel_con_fechas_y_celdas_vacias(cliente):
    tabla = pd.DataFrame({
        "Bia Code": ["CO10", "CO11"], "OR": ["Air-e", "Air-e"], "Dirección": ["Cra 1", None],
        "Ciudad": ["Barranquilla", "Barranquilla"], "Fecha de la visita": [pd.Timestamp(f"{dia(2)} 14:30"), pd.NaT],
        "GPS": ["10.97, -74.79", "10.98,-74.80"],
    })
    archivo = io.BytesIO()
    tabla.to_excel(archivo, index=False)
    respuesta = cliente.post("/api/upload", files={"file": ("ots.xlsx", archivo.getvalue(), "application/octet-stream")})
    assert respuesta.status_code == 200, respuesta.text
    ots = {a["codigo_bia"]: a for a in respuesta.json()["actividades"]}
    assert (ots["CO10"]["fecha_visita"], ots["CO10"]["hora_visita"]) == (dia(2), "14:30")
    assert ots["CO11"]["fecha_visita"] is None and ots["CO11"]["direccion"] == ""


def test_archivo_no_soportado_o_sin_or(cliente):
    assert cliente.post("/api/upload", files={"file": ("ots.xls", b"x", "application/octet-stream")}).status_code == 422
    sin_or = cliente.post("/api/upload", files={"file": ("ots.csv", b"Bia Code,Direccion\nCO1,Calle 1\n", "text/csv")})
    assert sin_or.status_code == 422 and "OR" in sin_or.json()["detail"]


def test_utilizacion_de_la_semana(con_metabase):
    actividades = con_metabase.get("/api/metabase/ots").json()["actividades"]
    respuesta = con_metabase.post("/api/utilizacion", json={
        "actividades": [a for a in actividades if a["situacion"] == "asignada"], "desde": dia(-6), "hasta": dia(0),
    })
    assert respuesta.status_code == 200, respuesta.text
    por_tecnico = {t["nombre"]: t for t in respuesta.json()["tecnicos"]}
    # La OT de Carlos cuenta para él; la del contratista no le suma a nadie de Bia
    assert por_tecnico["Carlos Salas"]["usado_min"] > 0
    assert por_tecnico["Juan Reyes"]["usado_min"] > 0  # la cerrada ocupó su tiempo

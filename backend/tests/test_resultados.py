"""Resultados para los KRs: lo que sugirió Ruteo frente a lo que quedó asignado en Metabase"""
from api_gateway import resultados
from conftest import dia, ot
from shared.models import DecisionOT


def decision(codigo, enviar_a, responsable_id, responsable, situacion="pendiente"):
    return DecisionOT(codigo_bia=codigo, enviar_a=enviar_a, responsable_id=responsable_id, responsable=responsable,
                      situacion=situacion, motivo="prueba")


def test_compara_lo_sugerido_con_lo_asignado(cliente, monkeypatch, tmp_path):
    monkeypatch.setattr(resultados, "RUTA", tmp_path / "sugerencias.json")
    tecnicos = {t["nombre"]: t["id"] for t in cliente.get("/api/asignacion/config").json()["tecnicos"]}
    carlos, juan = tecnicos["Carlos Salas"], tecnicos["Juan Jaramillo"]
    montajes = next(s for s in cliente.get("/api/catalogo").json()["sedes"]
                    if s["tipo"] == "contratista" and "MONTAJES" in s["empresa"].upper())
    guardadas = resultados.registrar(dia(0), [
        decision("ACEPTA", "tecnico", carlos, "Carlos Salas"),
        decision("CAMBIA", "tecnico", carlos, "Carlos Salas"),
        decision("CONTR", "contratista", f"{montajes['id']}#1", "MONTAJES · Cuadrilla 1"),
        decision("SIGUE", "tecnico", juan, "Juan Jaramillo"),
        decision("SE_FUE", "tecnico", juan, "Juan Jaramillo"),
        # No cuentan: ya asignada en Metabase y sin destino
        decision("YA", "tecnico", carlos, "Carlos Salas", situacion="asignada"),
        decision("NADIE", "sin_asignar", None, None),
    ], {"CAMBIA": f"tecnico:{carlos}"})
    assert guardadas == 5
    # Un plan de un día pasado es consulta: no se guarda
    assert resultados.registrar(dia(-1), [decision("VIEJA", "tecnico", carlos, "Carlos Salas")], {}) == 0

    # Lo que trae ahora Metabase
    ahora = [
        ot("ACEPTA", situacion="asignada", fecha_visita=dia(0), asignado_a="CARLOS ANDRES SALAS", contratista_asignado="Bia Energy"),
        ot("CAMBIA", situacion="asignada", fecha_visita=dia(0), asignado_a="Juan Jaramillo", contratista_asignado="Bia Energy"),
        ot("CONTR", situacion="asignada", fecha_visita=dia(0), asignado_a="Pedro", contratista_asignado=montajes["empresa"]),
        ot("SIGUE", situacion="pendiente"),
    ]
    respuesta = cliente.post("/api/resultados", json={
        "actividades": [a.model_dump(mode="json") for a in ahora], "desde": dia(-7), "hasta": dia(0)})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["total"] == {"sugeridas": 5, "aceptadas": 2, "cambiadas": 1, "pendientes": 1, "sin_dato": 1,
                              "editadas": 1, "aceptacion": round(2 / 3, 4)}
    assert datos["por_destino"]["contratista"]["aceptadas"] == 1
    assert datos["cambiadas"] == [{"dia": dia(0), "codigo": "CAMBIA", "sugerido": "Carlos Salas", "quedo": "Juan Jaramillo",
                                   "editada": True}]
    assert [d["dia"] for d in datos["por_dia"]] == [dia(0)]


def test_un_plan_recalculado_deja_la_ultima_sugerencia(monkeypatch, tmp_path):
    monkeypatch.setattr(resultados, "RUTA", tmp_path / "sugerencias.json")
    resultados.registrar(dia(1), [decision("X", "tecnico", "t1", "Ana")], {})
    primera = resultados._leer()[f"{dia(1)}|X"]["primera_vez"]
    resultados.registrar(dia(1), [decision("X", "tecnico", "t2", "Luis")], {})
    guardada = resultados._leer()[f"{dia(1)}|X"]
    assert (guardada["ids"], guardada["nombre"], guardada["primera_vez"]) == (["t2"], "Luis", primera)


def test_el_plan_guarda_sus_sugerencias(cliente, monkeypatch, tmp_path):
    monkeypatch.setattr(resultados, "RUTA", tmp_path / "sugerencias.json")
    tecnicos = [t["id"] for t in cliente.get("/api/asignacion/config").json()["tecnicos"]]
    actividades = [ot(f"P{k}", 4.68 + k * .01, -74.05, fecha_visita=dia(0)).model_dump(mode="json") for k in range(3)]
    respuesta = cliente.post("/api/asignar", json={"modo": "automatico", "actividades": actividades,
                                                   "tecnicos_ids": tecnicos, "dia": dia(0)})
    assert respuesta.status_code == 200, respuesta.text
    assert sorted(s["codigo"] for s in resultados._leer().values()) == ["P0", "P1", "P2"]

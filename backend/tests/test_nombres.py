"""Quién hace cada OT: técnicos de Bia por su nombre en Metabase, nunca los electricistas de un contratista"""
import pytest

from api_gateway import assignment_routes as rutas
from conftest import ot, tecnico
from shared.models import AsignacionConfig

TECNICOS = [tecnico("t-daniel", "Daniel Rodriguez"), tecnico("t-mario", "Mario Perez"), tecnico("t-juan", "Juan Reyes"),
            tecnico("t-carlos", "Carlos Salas"), tecnico("t-jorge", "Jorge Gelver"), tecnico("t-jona", "Jonathan Rudas")]


@pytest.mark.parametrize("texto, esperados", [
    ("DANIELA RODRIGUEZ", []),
    ("María Pérez", []),
    ("Juliana Gómez", []),
    ("Juan Carlos Reyes Ortiz", ["Juan Reyes"]),
    ("CARLOS ANDRES SALAS, Juan Reyes", ["Carlos Salas", "Juan Reyes"]),
    ("JORGE GELVEZ", ["Jorge Gelver"]),
    ("Jhonatan Rudas", ["Jonathan Rudas"]),
    ('["Daniel Rodríguez"]', ["Daniel Rodriguez"]),
    ("", []),
])
def test_tecnicos_mencionados(texto, esperados):
    assert [t.nombre for t in rutas.tecnicos_mencionados(texto, TECNICOS)] == esperados


def test_una_ot_de_contratista_no_es_de_ningun_tecnico_de_bia():
    contratista = ot("C1", situacion="asignada", asignado_a="Daniel Rodriguez", contratista_asignado="ELECPROYECTOS")
    assert rutas.responsables(contratista, TECNICOS, {}) == []


def test_contratista_vacio_o_bia_si_busca_tecnicos():
    for contratista in (None, "", "Bia Energy", "BIA"):
        actividad = ot("B1", situacion="asignada", asignado_a="Carlos Salas", contratista_asignado=contratista)
        assert [t.id for t in rutas.responsables(actividad, TECNICOS, {})] == ["t-carlos"]


def test_ids_aprendidos(monkeypatch):
    monkeypatch.setattr(rutas, "guardar_config", lambda config: None)
    contratista = ot("C1", situacion="asignada", asignado_a="Daniel Rodriguez", contratista_asignado="ELECPROYECTOS",
                     electricista_id="777")
    bia = ot("B1", situacion="asignada", asignado_a="Carlos Salas", contratista_asignado="Bia Energy", electricista_id="555")
    sin_contratista = ot("V1", situacion="asignada", asignado_a="Juan Reyes", electricista_id="666")
    # 777 se había aprendido mal de una OT de contratista y 555 estaba equivocado: se corrigen solos
    config = AsignacionConfig(tecnicos=TECNICOS, ids_electricistas={"777": "t-daniel", "555": "t-mario"})
    assert rutas.aprender_ids([contratista, bia, sin_contratista], config) == {"555": "t-carlos", "666": "t-juan"}


def test_un_id_equivocado_no_le_gana_al_nombre():
    actividad = ot("B2", situacion="asignada", asignado_a="Carlos Salas", contratista_asignado="Bia", electricista_id="999")
    assert [t.id for t in rutas.responsables(actividad, TECNICOS, {"999": "t-daniel"})] == ["t-carlos"]


def test_el_id_pone_primero_al_principal_y_cuenta_solo_las_personas_del_tipo():
    actividad = ot("B3", situacion="asignada", asignado_a="Carlos Salas, Juan Reyes", contratista_asignado="Bia",
                   electricista_id="42")
    assert [t.id for t in rutas.responsables(actividad, TECNICOS, {"42": "t-juan"})] == ["t-juan"]
    actividad.personas_requeridas = 2
    assert [t.id for t in rutas.responsables(actividad, TECNICOS, {"42": "t-juan"})] == ["t-juan", "t-carlos"]

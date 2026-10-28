"""Qué OTs entran en el plan de un día y a quién quedan fijadas"""
from api_gateway import assignment_routes as rutas
from conftest import dia, ot, tecnico

CARLOS, JUAN = tecnico("t-carlos", "Carlos Salas"), tecnico("t-juan", "Juan Reyes")
TECNICOS = [CARLOS, JUAN]


def plan(actividades, dia_plan, ediciones=None, disponibles=TECNICOS):
    del_dia, fijas, externas, notas, _, metricas = rutas.plan_del_dia(
        actividades, dia_plan, ediciones or {}, TECNICOS, disponibles, [])
    return [a.codigo_bia for a in del_dia], fijas, externas, notas, metricas


def test_un_dia_tiene_las_ots_de_esa_fecha_y_hoy_suma_vencidas_y_sin_fecha():
    actividades = [
        ot("HOY", fecha_visita=dia(0)), ot("MANANA", fecha_visita=dia(1)), ot("VENCIDA", fecha_visita=dia(-2)),
        ot("SIN_FECHA"), ot("ASIG_MANANA", situacion="asignada", fecha_visita=dia(1), asignado_a="Carlos Salas"),
    ]
    hoy, _, _, notas, _ = plan(actividades, dia(0))
    assert sorted(hoy) == ["HOY", "SIN_FECHA", "VENCIDA"]
    assert notas["VENCIDA"] == f"Pendiente desde el {dia(-2)}"
    manana, fijas, _, _, metricas = plan(actividades, dia(1))
    assert sorted(manana) == ["ASIG_MANANA", "MANANA"]
    assert fijas == {"ASIG_MANANA": "tecnico:t-carlos"}
    assert metricas["pendientes_otros_dias"] == 3


def test_asignada_a_tecnico_no_disponible_se_reasigna():
    actividades = [ot("A1", situacion="asignada", fecha_visita=dia(0), asignado_a="Carlos Salas", contratista_asignado="Bia")]
    _, fijas, externas, notas, _ = plan(actividades, dia(0), disponibles=[JUAN])
    assert fijas == {} and externas == {} and "la app la reasigna" in notas["A1"]


def test_cerrada_no_se_reasigna_ni_se_edita():
    cerrada = ot("CERR", situacion="asignada", cerrada=True, fecha_visita=dia(0), asignado_a="Carlos Salas",
                 contratista_asignado="Bia Energy")
    # Carlos no está hoy: se queda con él como externa, aunque alguien pida reasignarla
    _, fijas, externas, notas, _ = plan([cerrada], dia(0), {"CERR": "auto"}, disponibles=[JUAN])
    assert externas == {"CERR": "Carlos Salas (cerrada)"} and "CERR" not in fijas
    assert "no se reasigna" in notas["CERR"]
    # Carlos está: entra en su ruta; una edición a mano no la mueve
    _, fijas, _, _, _ = plan([cerrada], dia(0), {"CERR": "tecnico:t-juan"})
    assert fijas == {"CERR": "tecnico:t-carlos"}


def test_ot_de_contratista_desconocido_es_externa_aunque_el_nombre_se_parezca():
    actividad = ot("C1", situacion="asignada", fecha_visita=dia(0), asignado_a="Carlos Salas", contratista_asignado="ELECTRO X")
    _, fijas, externas, _, _ = plan([actividad], dia(0))
    assert fijas == {} and externas == {"C1": "Carlos Salas (ELECTRO X)"}


def test_bia_sin_registrar_se_avisa():
    actividad = ot("B1", situacion="asignada", fecha_visita=dia(0), asignado_a="Pedro Nuevo", contratista_asignado="Bia")
    _, _, externas, _, metricas = plan([actividad], dia(0))
    assert externas["B1"] == "Pedro Nuevo (Bia, sin registrar en la app)"
    assert metricas["bia_sin_registrar"] == ["Pedro Nuevo"]


def test_edicion_a_mano_manda():
    actividades = [ot("P1", fecha_visita=dia(0)), ot("A1", situacion="asignada", fecha_visita=dia(0), asignado_a="Carlos Salas")]
    _, fijas, _, notas, _ = plan(actividades, dia(0), {"P1": "tecnico:t-juan", "A1": "auto"})
    assert fijas == {"P1": "tecnico:t-juan"}
    assert notas["P1"] == "Editada a mano" and "la app la reasigna" in notas["A1"]

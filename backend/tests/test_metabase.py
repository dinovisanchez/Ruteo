"""Filas de la pregunta de Metabase → OTs: columnas, situación, visitas de una misma OT"""
from api_gateway import metabase
from conftest import dia

P, A, C = "Pendiente por asignar", "Asignada", "Cerrada"


def fila(codigo, orden, fecha, situacion, **extra):
    datos = {"Bia Code": codigo, "Orden de trabajo": orden, "Situación": situacion, "Fecha de la visita": fecha,
             "OR": "ENEL", "Dirección": "Calle 1", "Ciudad": "Bogotá"}
    datos.update(extra)
    return datos


def leer(filas):
    actividades, _, avisos = metabase.filas_a_actividades(filas, {})
    return {a.codigo_bia: a for a in actividades}, avisos


def test_columnas_en_espanol_se_reconocen():
    ots, _ = leer([fila("CO1", 1, f"{dia(1)}T09:30:00-05:00", A, **{
        "Electricistas asignados": "Carlos Salas", "Contratista asignado": "Bia Energy", "Id electricista": "77",
        "Tipo de OT": "Normalización", "Creado por": "Ana", "Fecha de creación": f"{dia(-2)}T08:00:00",
        "Latitud": 4.6, "Longitud": -74.1})])
    a = ots["CO1"]
    assert (a.situacion, a.fecha_visita, a.hora_visita) == ("asignada", dia(1), "09:30")
    assert (a.asignado_a, a.contratista_asignado, a.electricista_id) == ("Carlos Salas", "Bia Energy", "77")
    assert (a.servicio, a.or_operador, a.creado_por, a.fecha_creacion) == ("Normalización", "ENEL", "Ana", dia(-2))
    assert a.coordinates.latitude == 4.6 and not a.cerrada


def test_cerrada_cuenta_como_asignada_y_se_marca():
    ots, _ = leer([fila("CO1", 1, dia(-1), C)])
    assert ots["CO1"].situacion == "asignada" and ots["CO1"].cerrada


def test_la_visita_vigente_lleva_el_codigo():
    # Una OT con dos visitas viejas que dicen «por asignar» y la nueva: solo cuenta la nueva
    ots, avisos = leer([fila("CO1", 111, dia(-15), P), fila("CO1", 111, dia(-8), P), fila("CO1", 111, dia(2), P)])
    assert list(ots) == ["CO1"] and ots["CO1"].fecha_visita == dia(2)
    assert any("no cuentan aparte" in a for a in avisos)


def test_visitas_anteriores_cerradas_entran_con_su_fecha():
    ots, _ = leer([fila("CO2", 222, dia(-10), C, **{"Electricistas asignados": "Ana"}), fila("CO2", 222, dia(1), P)])
    assert ots["CO2"].situacion == "pendiente" and ots["CO2"].fecha_visita == dia(1)
    assert ots[f"CO2 · {dia(-10)}"].cerrada


def test_pendiente_sin_fecha_es_la_vigente_frente_a_una_cerrada():
    ots, _ = leer([fila("CO3", 333, dia(-5), C), fila("CO3", 333, None, P)])
    assert ots["CO3"].fecha_visita is None and ots["CO3"].situacion == "pendiente"
    assert f"CO3 · {dia(-5)}" in ots


def test_filas_repetidas_cuentan_una_vez():
    ots, avisos = leer([fila("CO4", 444, f"{dia(1)}T09:00", P), fila("CO4", 444, f"{dia(1)}T09:00", P)])
    assert list(ots) == ["CO4"]
    assert any("una sola vez" in a for a in avisos)
    assert any("trajo 2 filas y quedaron 1 OTs" in a for a in avisos)


def test_dos_ots_con_el_mismo_codigo_se_distinguen_por_la_orden():
    ots, _ = leer([fila("CO5", 1, dia(0), A), fila("CO5", 2, dia(3), P)])
    # La que sigue por asignar se queda con el código tal cual
    assert ots["CO5"].situacion == "pendiente" and ots["CO5 / OT 1"].situacion == "asignada"


def test_sin_columna_de_orden_se_queda_la_visita_nueva():
    filas = [{k: v for k, v in f.items() if k != "Orden de trabajo"}
             for f in (fila("CO6", 0, dia(-9), P), fila("CO6", 0, dia(1), P))]
    ots, _ = leer(filas)
    assert list(ots) == ["CO6"] and ots["CO6"].fecha_visita == dia(1)


def test_una_fila_por_ot_no_genera_avisos():
    ots, avisos = leer([fila(f"CO7{i}", i, dia(1), P) for i in range(4)])
    assert len(ots) == 4 and avisos == []


def test_sin_columna_de_or_falla_con_mensaje():
    try:
        metabase.filas_a_actividades([{"Bia Code": "CO1", "Dirección": "x"}], {})
    except metabase.MetabaseError as e:
        assert "OR" in str(e)
    else:
        raise AssertionError("debió fallar")

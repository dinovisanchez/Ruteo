"""Filas de la pregunta de Metabase → OTs: columnas, situación, visitas de una misma OT"""
import pytest

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


@pytest.mark.parametrize("valor, esperado", [
    ("2026-10-29T12:00:00-05:00", ("2026-10-29", "12:00")),
    ("2026-10-29T17:00:00Z", ("2026-10-29", "12:00")),           # UTC → hora de Colombia
    ("2026-10-30T03:00:00Z", ("2026-10-29", "22:00")),           # en UTC ya es otro día
    ("2026-10-29T09:30:00.000-0500", ("2026-10-29", "09:30")),
    ("2026-10-29 09:30:00", ("2026-10-29", "09:30")),           # sin desfase: ya es hora local
    ("2026-10-29T00:00:00Z", ("2026-10-29", None)),               # medianoche es una fecha sin hora
    ("2026-10-29", ("2026-10-29", None)),
    ("03/11/2026", ("2026-11-03", None)),                         # en texto el día va primero
    ("13/11/2026 14:30", ("2026-11-13", "14:30")),
    ("Semana 3", (None, None)),
    ("", (None, None)),
])
def test_fechas_y_horas_en_hora_de_colombia(valor, esperado):
    assert metabase._momento(valor) == esperado


def test_una_fecha_que_no_se_entiende_se_avisa():
    _, avisos = leer([fila("CO1", 1, "Semana 3", P)])
    assert any("no se entendieron" in a for a in avisos)


@pytest.mark.parametrize("situacion, esperado", [
    ("Pendiente por asignar", ("pendiente", False)),
    ("Asignada", ("asignada", False)),
    ("REASIGNADA", ("asignada", False)),
    ("Cerrada", ("asignada", True)),
    ("Cierre Fallido", ("asignada", True)),
    # Antes «No asignada» contaba como asignada y «Cancelada» como pendiente
    ("No asignada", ("pendiente", False)),
    ("Desasignada", ("pendiente", False)),
])
def test_situacion_por_valor_exacto(situacion, esperado):
    ots, _ = leer([fila("CO1", 1, dia(1), situacion)])
    assert (ots["CO1"].situacion, ots["CO1"].cerrada) == esperado


@pytest.mark.parametrize("estado_app, esperado", [
    ("PENDING_ASSIGNMENT", ("pendiente", False)),
    ("ASSIGNED", ("asignada", False)),
    ("REASSIGNED", ("asignada", False)),
    ("COMPLETED", ("asignada", True)),
    ("", ("pendiente", False)),
])
def test_sin_situacion_manda_el_estado_app(estado_app, esperado):
    datos = {k: v for k, v in fila("CO1", 1, dia(1), P).items() if k != "Situación"}
    ots, _ = leer([{**datos, "Estado app": estado_app}])
    assert (ots["CO1"].situacion, ots["CO1"].cerrada) == esperado


def test_canceladas_no_entran_y_lo_desconocido_se_avisa():
    ots, avisos = leer([fila("CO1", 1, dia(1), "Cancelada"), fila("CO2", 2, dia(1), "No asignada"),
                        fila("CO3", 3, dia(1), "No asignada"), fila("CO4", 4, dia(1), P)])
    assert sorted(ots) == ["CO2", "CO3", "CO4"]
    assert "OTs canceladas o rechazadas que no se cargan: 1" in avisos
    assert any("«No asignada» (2)" in a and "por asignar" in a for a in avisos)


def test_una_visita_cancelada_no_le_quita_el_codigo_a_la_vigente():
    ots, _ = leer([fila("CO1", 1, dia(3), "Cancelada"), fila("CO1", 1, dia(1), P)])
    assert list(ots) == ["CO1"] and ots["CO1"].fecha_visita == dia(1)


def test_un_archivo_sin_columnas_de_estado_trae_pendientes():
    actividades, _, avisos = metabase.filas_a_actividades([{"Bia Code": "X1", "OR": "Enel", "Dirección": "Calle 1"}], {})
    assert actividades[0].situacion == "pendiente" and avisos == []

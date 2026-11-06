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
    # Una OT con una visita vencida, otra anterior que dice «por asignar» y la nueva: solo cuenta la nueva
    ots, avisos = leer([fila("CO1", 111, dia(-15), P), fila("CO1", 111, dia(1), P), fila("CO1", 111, dia(2), P)])
    assert list(ots) == ["CO1"] and ots["CO1"].fecha_visita == dia(2)
    assert any("no cuentan aparte" in a for a in avisos)
    assert "OTs por asignar con la fecha de visita ya pasada (vencidas), que no se cargan: 1" in avisos


def test_las_pendientes_con_la_fecha_pasada_no_aplican():
    ots, avisos = leer([fila("CO1", 1, dia(-1), P), fila("CO2", 2, f"{dia(0)}T07:00:00", P), fila("CO3", 3, None, P),
                        fila("CO4", 4, dia(-1), A), fila("CO5", 5, dia(-1), C)])
    # Las de hoy (aunque la hora ya haya pasado) y las sin fecha sí; las asignadas y cerradas de otros días también
    assert sorted(ots) == ["CO2", "CO3", "CO4", "CO5"]
    assert "OTs por asignar con la fecha de visita ya pasada (vencidas), que no se cargan: 1" in avisos


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


def test_las_vencidas_en_olibia_no_entran_aunque_digan_por_asignar():
    def con_estados(codigo, situacion, estado, estado_app="PENDING_ASSIGNMENT", fecha=dia(-3)):
        return fila(codigo, int(codigo[2:]), fecha, situacion, Estado=estado, **{"Estado app": estado_app})

    ots, avisos = leer([
        con_estados("CO1", P, "Vencida"),
        con_estados("CO2", P, "Cierre vencido"),
        con_estados("CO3", P, "Por asignar", "EXPIRED"),
        con_estados("CO4", "Vencida", ""),
        con_estados("CO5", P, "Por asignar", fecha=dia(1)),
        con_estados("CO6", A, "Asignada", "ASSIGNED", dia(1)),
    ])
    assert sorted(ots) == ["CO5", "CO6"]
    aviso = next(a for a in avisos if a.startswith("OTs vencidas en Olibia que no se cargan: 4"))
    # Dice qué valores quitó, para revisarlo contra Olibia
    assert "«Vencida» (2)" in aviso and "«Cierre vencido» (1)" in aviso and "«EXPIRED» (1)" in aviso
    assert not any("no conoce" in a for a in avisos)


@pytest.mark.parametrize("columna, valor", [
    ("Estado", "Expirada"),
    ("Estado", "VENCIMIENTO SLA"),
    ("Estado", "Caducada"),
    ("Estado app", "OVERDUE_ASSIGNMENT"),
    # Una columna de estado con otro nombre también cuenta
    ("Estado Olibia", "Vencida"),
    ("status_visita", "expired"),
])
def test_las_vencidas_se_reconocen_escritas_de_varias_formas(columna, valor):
    def con(codigo, texto):
        return fila(codigo, int(codigo[2:]), dia(1), P, **{columna: texto})
    ots, avisos = leer([con("CO1", valor), con("CO2", "Por asignar")])
    assert sorted(ots) == ["CO2"]
    assert any(a.startswith("OTs vencidas en Olibia que no se cargan: 1") and f"«{valor}»" in a for a in avisos)


def test_una_visita_vencida_no_le_quita_el_codigo_a_la_nueva():
    ots, _ = leer([fila("CO1", 1, dia(-2), P, Estado="Vencida"), fila("CO1", 1, dia(2), P, Estado="Por asignar")])
    assert list(ots) == ["CO1"] and ots["CO1"].fecha_visita == dia(2)


def test_una_visita_cancelada_no_le_quita_el_codigo_a_la_vigente():
    ots, _ = leer([fila("CO1", 1, dia(3), "Cancelada"), fila("CO1", 1, dia(1), P)])
    assert list(ots) == ["CO1"] and ots["CO1"].fecha_visita == dia(1)


def test_un_archivo_sin_columnas_de_estado_trae_pendientes():
    actividades, _, avisos = metabase.filas_a_actividades([{"Bia Code": "X1", "OR": "Enel", "Dirección": "Calle 1"}], {})
    assert actividades[0].situacion == "pendiente" and avisos == []


def test_ubicacion_y_hora_del_desplazamiento_ok():
    ots, _ = leer([
        fila("CO1", 1, dia(0), A, **{"Latitud desplazamiento": "4,6790", "Longitud desplazamiento": -74.047,
                                     "Fecha desplazamiento": f"{dia(0)}T13:52:00Z"}),
        # Sin datos del desplazamiento, o con coordenadas fuera de Colombia: no hay ubicación
        fila("CO2", 2, dia(0), A, **{"Latitud desplazamiento": None, "Longitud desplazamiento": None,
                                     "Fecha desplazamiento": None}),
        fila("CO3", 3, dia(0), A, **{"Latitud desplazamiento": 40.4, "Longitud desplazamiento": -3.7,
                                     "Fecha desplazamiento": dia(0)}),
    ])
    co1 = ots["CO1"]
    assert (co1.desplazamiento_ok.latitude, co1.desplazamiento_ok.longitude) == (4.679, -74.047)
    # En UTC se pasa a la hora de Colombia
    assert co1.desplazamiento_ok_en == f"{dia(0)} 08:52"
    assert ots["CO2"].desplazamiento_ok is None and ots["CO2"].desplazamiento_ok_en is None
    assert ots["CO3"].desplazamiento_ok is None and ots["CO3"].desplazamiento_ok_en == dia(0)


def test_desplazamiento_ok_en_una_sola_columna_de_gps():
    ots, _ = leer([fila("CO1", 1, dia(0), A, **{"GPS desplazamiento OK": "4.6790, -74.0470"})])
    assert (ots["CO1"].desplazamiento_ok.latitude, ots["CO1"].desplazamiento_ok.longitude) == (4.679, -74.047)
    # La ubicación de la OT no se confunde con la del desplazamiento
    assert ots["CO1"].coordinates is None


def test_la_hora_del_desplazamiento_sin_zona_es_utc(monkeypatch):
    from shared.config import settings
    # Así llega de la app de técnicos: UTC, con milésimas y sin zona
    assert metabase.hora_desplazamiento("2026-11-05T19:27:12.035") == ("2026-11-05", "14:27")
    assert metabase.hora_desplazamiento("2026-11-05 02:10:00") == ("2026-11-04", "21:10")
    # Con zona se respeta la que trae
    assert metabase.hora_desplazamiento("2026-11-05T19:27:00Z") == ("2026-11-05", "14:27")
    assert metabase.hora_desplazamiento("2026-11-05T14:27:00-05:00") == ("2026-11-05", "14:27")
    assert metabase.hora_desplazamiento(None) == (None, None)
    # Si la pregunta ya las trae en hora de Colombia
    monkeypatch.setattr(settings, "DESPLAZAMIENTOS_EN_UTC", False)
    assert metabase.hora_desplazamiento("2026-11-05T14:27:12") == ("2026-11-05", "14:27")

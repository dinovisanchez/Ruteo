"""Motor de asignación: cerca → libre → menor UTR, OTs juntas a 2 km y propuesta por lote"""
import random

import pytest

import services.optimizer_service.assignment as motor
from conftest import ot, tecnico
from shared.catalogo import cargar_catalogo
from shared.models import AssignmentRequest, JornadaConfig, ServiceTime

SEDES, _ = cargar_catalogo()
CARLOS_DIANA_EDGAR = [tecnico("carlos", "Carlos"), tecnico("diana", "Diana"), tecnico("edgar", "Edgar")]
# Carlos lleva poco en la semana; Diana y Edgar bastante
PREVIO = {"carlos": 300, "diana": 1500, "edgar": 1400}


def jornada(radio=2.0, **campos):
    return JornadaConfig(radio_grupo_km=radio, tiempos_servicio=[
        ServiceTime(servicio="visita", duracion_minutos=60), ServiceTime(servicio="normalizacion", duracion_minutos=120),
        ServiceTime(servicio="instalacion", duracion_minutos=120), ServiceTime(servicio="larga", duracion_minutos=300),
    ], **campos)


def pedido(actividades, tecnicos=CARLOS_DIANA_EDGAR, fijas=None, previo=PREVIO, **campos):
    return AssignmentRequest(modo="inhouse", actividades=actividades, sedes=SEDES, tecnicos=tecnicos, fijas=fijas or {},
                             uso_previo=previo or {}, disponible_previo=2016 if previo else 0,
                             jornada=campos.pop("jornada", jornada()), **campos)


def responsables(resultado):
    return {p.actividad.codigo_bia: r.responsable for r in resultado.rutas for p in r.ruta.paradas}


NORTE = ot("NORTE", 4.750, -74.050)      # de Carlos
SUR_DIANA = ot("SUR-D", 4.570, -74.120)  # de Diana
SUR = ot("SUR", 4.5755, -74.1165)        # libre, a ~0,7 km de la de Diana
OESTE = ot("OESTE", 4.660, -74.185)      # libre, lejos de todos
ESTE = ot("ESTE", 4.700, -74.020)
FIJAS = {"NORTE": "tecnico:carlos", "SUR-D": "tecnico:diana"}


def test_cerca_le_gana_a_la_menor_utr_y_libre_va_antes_que_menor_utr():
    resultado = motor.asignar(pedido([NORTE, SUR_DIANA, SUR, OESTE], fijas=FIJAS))
    de = responsables(resultado)
    assert de["SUR"] == "Diana"   # cerca de la de Diana, aunque Carlos tenga menos UTR
    assert de["OESTE"] == "Edgar"  # nadie la tiene cerca y Edgar no tiene OTs
    motivos = {d.codigo_bia: d.motivo for d in resultado.decisiones}
    assert "km de otras OTs de Diana" in motivos["SUR"]


def test_si_todos_tienen_ots_lejos_va_al_de_menor_utr():
    resultado = motor.asignar(pedido([NORTE, SUR_DIANA, ESTE, OESTE], fijas={**FIJAS, "ESTE": "tecnico:edgar"}))
    assert responsables(resultado)["OESTE"] == "Carlos"


def test_propuesta_por_lote_sigue_las_mismas_reglas():
    base = pedido([NORTE, SUR_DIANA, SUR, OESTE], fijas=FIJAS)
    por_codigo = {c: g for g in motor.repartir_lote(base, ["SUR", "OESTE"])["grupos"] for c in g["codigos"]}
    assert (por_codigo["SUR"]["tecnico"], por_codigo["SUR"]["regla"]) == ("Diana", motor.REGLA_CERCA)
    assert (por_codigo["OESTE"]["tecnico"], por_codigo["OESTE"]["regla"]) == ("Edgar", motor.REGLA_LIBRE)
    # Con lo que el plan ya le da a Edgar (la del este), la del oeste va a Carlos
    otro = base.model_copy(update={"actividades": [NORTE, SUR_DIANA, ESTE, OESTE]})
    grupo = motor.repartir_lote(otro, ["OESTE"], {"ESTE": "edgar"})["grupos"][0]
    assert (grupo["tecnico"], grupo["regla"]) == ("Carlos", motor.REGLA_MENOR_UTR)


@pytest.fixture
def cuatro():
    return [tecnico(f"t{i}", n) for i, n in enumerate(["Ana", "Luis", "Sara", "Pedro"])]


def test_ots_cercanas_van_juntas(cuatro):
    azar = random.Random(3)
    grupo_a = [ot(f"A{k}", 4.700 + azar.uniform(-.003, .003), -74.050 + azar.uniform(-.003, .003)) for k in range(3)]
    grupo_b = [ot(f"B{k}", 4.600 + azar.uniform(-.003, .003), -74.150 + azar.uniform(-.003, .003)) for k in range(2)]
    sueltas = [ot("S0", 4.75, -74.10), ot("S1", 4.55, -74.08), ot("S2", 4.66, -74.20)]
    previo = {"t0": 1500, "t1": 1400, "t2": 300, "t3": 1450}
    resultado = motor.asignar(pedido(grupo_a + grupo_b + sueltas, tecnicos=cuatro, previo=previo))
    de = responsables(resultado)
    assert len({de[c] for c in ["A0", "A1", "A2"]}) == 1 and len({de[c] for c in ["B0", "B1"]}) == 1
    assert resultado.metricas["ots_agrupadas"] == 5
    motivos = {d.codigo_bia: d.motivo for d in resultado.decisiones}
    assert "Va junto con" in motivos["A0"] and "Va junto con" not in motivos["S0"]
    # Con «cerca» en 0 no se junta nada
    sin = motor.asignar(pedido(grupo_a + grupo_b + sueltas, tecnicos=cuatro, previo=previo, jornada=jornada(0)))
    assert sin.metricas["ots_agrupadas"] == 0


def test_un_grupo_que_no_cabe_en_una_jornada_se_parte(cuatro):
    azar = random.Random(5)
    grandes = [ot(f"G{k}", 4.680 + azar.uniform(-.004, .004), -74.080 + azar.uniform(-.004, .004), servicio="normalizacion")
               for k in range(8)]
    resultado = motor.asignar(pedido(grandes, tecnicos=cuatro, previo=None))
    assert not resultado.sin_asignar
    assert all(r.ruta.tiempo_total_minutos <= 8 * 60 for r in resultado.rutas)


def test_ot_de_dos_personas_fijada_sale_en_pareja(cuatro):
    dos = [ot("P0", 4.65, -74.06, servicio="instalacion", personas_requeridas=2)]
    dos += [ot(f"U{k}", 4.62 + k * .01, -74.1) for k in range(3)]
    resultado = motor.asignar(pedido(dos, tecnicos=cuatro, fijas={"P0": "tecnico:t0"}, previo=None))
    ruta = next(r for r in resultado.rutas if any(p.actividad.codigo_bia == "P0" for p in r.ruta.paradas))
    assert ruta.personas == 2 and "Ana" in ruta.responsable


def test_si_el_grupo_no_cabe_se_separa_y_se_reintenta(monkeypatch):
    llamadas = []
    original = motor._resolver_vrp

    def espia(actividades, *args, **kwargs):
        llamadas.append(len(actividades))
        return original(actividades, *args, **kwargs)

    monkeypatch.setattr(motor, "_resolver_vrp", espia)
    base = next(s for s in SEDES if s.id == "bia-bogota").coordinates
    # Una OT fija de 5 h deja ~2 h: la pareja (2 × 90 min) no cabe junta, una sola sí
    fija = ot("F0", base.latitude + .005, base.longitude, servicio="larga")
    par = [ot(f"P{k}", base.latitude + .01 + k * .003, base.longitude) for k in range(2)]
    j = JornadaConfig(horas_laborales=8, radio_grupo_km=2, tiempos_servicio=[
        ServiceTime(servicio="visita", duracion_minutos=90), ServiceTime(servicio="larga", duracion_minutos=300)])
    resultado = motor.asignar(pedido([fija] + par, tecnicos=[tecnico("t0", "Ana")], fijas={"F0": "tecnico:t0"},
                                     previo=None, jornada=j))
    asignadas = [p.actividad.codigo_bia for r in resultado.rutas for p in r.ruta.paradas]
    assert llamadas == [2, 3]  # primero la pareja como un solo nodo, luego separada
    assert "F0" in asignadas and len([c for c in asignadas if c.startswith("P")]) == 1


def test_ubicadas_solo_por_municipio_no_cuentan_como_cerca():
    centro = dict(lat=4.6097, lon=-74.0817, ubicacion_imprecisa=True)
    actividades = [ot("M0", **centro), ot("M1", **centro), ot("D0", 4.640, -74.065)]
    grupos = motor.grupos_cercanos([0, 1, 2], actividades, {0: 1, 1: 1, 2: 1}, 2.0, 400, {},
                                   motor.Distancias(jornada()))
    assert sorted(map(sorted, grupos)) == [[0], [1], [2]]

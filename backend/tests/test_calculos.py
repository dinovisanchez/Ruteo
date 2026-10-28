"""Cálculos del plan: UTR sin contar dos veces, tope de OTs por ruta con grupos y parejas en el lote"""
import services.optimizer_service.assignment as motor
from conftest import dia, ot, tecnico
from shared.catalogo import cargar_catalogo
from shared.models import AssignmentRequest, JornadaConfig, ServiceTime

SEDES, _ = cargar_catalogo()
JORNADA = dict(radio_grupo_km=2, tiempos_servicio=[ServiceTime(servicio="visita", duracion_minutos=45)])


def test_una_ot_reasignada_por_el_plan_cuenta_solo_para_quien_la_hace(cliente):
    tecnicos = {t["nombre"]: t["id"] for t in cliente.get("/api/asignacion/config").json()["tecnicos"]}
    carlos, juan = tecnicos["Carlos Salas"], tecnicos["Juan Jaramillo"]
    # En Metabase es de Carlos; el plan del día se la dio a Juan
    actividad = ot("X1", situacion="asignada", fecha_visita=dia(0), asignado_a="Carlos Salas",
                   contratista_asignado="Bia Energy").model_dump(mode="json")
    respuesta = cliente.post("/api/utilizacion", json={
        "actividades": [actividad], "desde": dia(0), "hasta": dia(0),
        "plan": {"dia": dia(0), "rutas": [
            {"tecnicos_ids": [juan], "servicio_min": 60, "viaje_min": 30, "km": 12, "codigos": ["X1"]}]},
    })
    assert respuesta.status_code == 200, respuesta.text
    usado = {t["id"]: t["usado_min"] for t in respuesta.json()["tecnicos"]}
    assert usado[juan] == 90 and usado[carlos] == 0
    assert respuesta.json()["equipo"]["usado_min"] == 90


def test_el_tope_de_ots_por_ruta_cuenta_cada_ot_de_un_grupo():
    # Cuatro OTs a menos de 1 km (un grupo) y tope de 2 OTs por ruta
    cuatro = [ot(f"G{k}", 4.680 + k * .002, -74.080) for k in range(4)]
    resultado = motor.asignar(AssignmentRequest(
        modo="inhouse", actividades=cuatro, sedes=SEDES, tecnicos=[tecnico("t0", "Ana"), tecnico("t1", "Luis")],
        jornada=JornadaConfig(capacidad_maxima_actividades=2, **JORNADA)))
    assert all(len(r.ruta.paradas) <= 2 for r in resultado.rutas), [len(r.ruta.paradas) for r in resultado.rutas]
    assert sum(len(r.ruta.paradas) for r in resultado.rutas) == 4


def _lote(tecnicos):
    dos = ot("P2", 4.65, -74.06, personas_requeridas=2)
    pedido = AssignmentRequest(modo="inhouse", actividades=[dos], sedes=SEDES, tecnicos=tecnicos,
                               jornada=JornadaConfig(**JORNADA))
    return motor.repartir_lote(pedido, ["P2"])


def test_una_ot_de_dos_personas_en_el_lote_necesita_pareja_en_el_equipo():
    solo = _lote([tecnico("t0", "Ana")])
    assert solo["grupos"] == []
    assert "no hay otro técnico disponible para la pareja" in solo["sin_tecnico"][0]["motivo"]
    pareja = _lote([tecnico("t0", "Ana"), tecnico("t1", "Luis")])
    assert pareja["grupos"][0]["personas"] == 2 and pareja["grupos"][0]["tecnico"] in ("Ana", "Luis")
    # Un técnico de otro equipo no sirve de pareja
    lejos = _lote([tecnico("t0", "Ana"), tecnico("t9", "Jorge", base="bia-barranquilla")])
    assert lejos["grupos"] == []

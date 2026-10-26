"""Utilización (UTR) de los técnicos Bia: horas usadas en OTs y desplazamientos frente a las horas disponibles.

Las horas disponibles salen de la jornada semanal (42 h por defecto) repartida en los días
laborables de la semana. Las horas usadas de cada técnico en un día son la duración de sus
OTs según el tipo, más el desplazamiento base → OTs → base de ese día.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collections import Counter
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from shared.distancias import Distancias
from shared.models import Activity, GPSCoordinates, JornadaConfig, ServiceTime, ZonaTransito
from shared.utils import get_service_time
from shared.catalogo import normalizar_texto
from .assignment_routes import aprender_ids, es_de_bia, leer_config, obtener_catalogo, obtener_zonas, responsables

router = APIRouter()

# Desplazamiento de una OT sin ubicación cuando ninguna OT de ese día tiene ubicación
MINUTOS_VIAJE_SIN_UBICACION = 25
# Un tramo más largo que esto en la ruta de un día es casi siempre una dirección mal ubicada
MAX_KM_TRAMO = 200
MAX_DIAS = 93


class RutaPlan(BaseModel):
    """Ruta de una cuadrilla en el plan calculado (con las OTs sugeridas)"""
    tecnicos_ids: List[str]
    servicio_min: int
    viaje_min: int
    km: float = 0
    codigos: List[str]


class PlanDelDia(BaseModel):
    dia: date
    rutas: List[RutaPlan]


class UtilizacionRequest(BaseModel):
    actividades: List[Activity]
    desde: date
    hasta: date
    horas_semana: float = Field(default=42, gt=0, le=80)
    dias_semana: int = Field(default=5, ge=1, le=7)  # Lunes a viernes = 5; lunes a sábado = 6
    tiempos_servicio: List[ServiceTime] = Field(default_factory=list)
    # Tipo de OT → personas que necesita: cuántos de los electricistas listados cuentan
    personas_por_tipo: Dict[str, int] = Field(default_factory=dict)
    transito: List[ZonaTransito] = Field(default_factory=list)
    jornada: JornadaConfig = Field(default_factory=JornadaConfig)
    # Si viene, ese día cada técnico cuenta con su ruta del plan (asignadas + sugeridas), más las
    # OTs que Metabase le asigna y que la ruta no incluye (por ejemplo, sin ubicación)
    plan: Optional[PlanDelDia] = None


def minutos_de_viaje(
    ots: List[Activity],
    base: Optional[GPSCoordinates],
    dist: Distancias,
    retorno: bool,
) -> Tuple[int, float, bool]:
    """Desplazamiento del día: base → OTs (por hora de visita; si no hay, por cercanía) → base.

    Las OTs sin ubicación, o a más de MAX_KM_TRAMO de su tramo anterior (ubicación errada), suman
    el promedio de los demás tramos. Devuelve (minutos, km, estimado).
    """
    ubicadas = [a for a in ots if a.coordinates is not None]
    if base is not None:
        ubicadas = [a for a in ubicadas if dist.km(base, a.coordinates) <= MAX_KM_TRAMO]
    if any(a.hora_visita for a in ubicadas):
        orden = sorted(ubicadas, key=lambda a: a.hora_visita or "99:99")
    else:
        orden, restantes, posicion = [], list(ubicadas), base
        while restantes:
            siguiente = min(restantes, key=lambda a: dist.km(posicion, a.coordinates)) if posicion else restantes[0]
            restantes.remove(siguiente)
            orden.append(siguiente)
            posicion = siguiente.coordinates

    tramos: List[float] = []
    kms: List[float] = []
    posicion = base
    destinos = [a.coordinates for a in orden] + ([base] if retorno and base is not None and orden else [])
    for destino in destinos:
        if posicion is not None:
            tramos.append(dist.minutos(posicion, destino))
            kms.append(dist.km(posicion, destino))
        posicion = destino

    sin_ubicacion = len(ots) - len(ubicadas)
    if sin_ubicacion:
        tramos += [sum(tramos) / len(tramos) if tramos else MINUTOS_VIAJE_SIN_UBICACION] * sin_ubicacion
        kms += [sum(kms) / len(kms) if kms else 0] * sin_ubicacion
    return int(round(sum(tramos))), round(sum(kms), 1), sin_ubicacion > 0


@router.post("/utilizacion", response_model=dict)
async def utilizacion(request: UtilizacionRequest):
    """UTR de cada técnico Bia y del equipo entre `desde` y `hasta`, con el detalle por día"""
    if request.hasta < request.desde:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La fecha final es anterior a la inicial")
    if (request.hasta - request.desde).days >= MAX_DIAS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El periodo puede ser de máximo 3 meses")

    config = leer_config()
    tecnicos = [t for t in config.tecnicos if t.activo]
    personas = {normalizar_texto(k): v for k, v in request.personas_por_tipo.items()}
    for actividad in request.actividades:
        actividad.personas_requeridas = max(1, personas.get(normalizar_texto(actividad.servicio), 1))
    ids = aprender_ids(request.actividades, config)
    sedes = {s.id: s for s in obtener_catalogo()["sedes"]}
    coberturas, transito = obtener_zonas()
    equipo_de_base = {c.base_id: c.equipo for c in coberturas}
    jornada = request.jornada.model_copy(update={"zonas_transito": request.transito or transito})
    dist = Distancias(jornada)
    servicios = {st.servicio: st.duracion_minutos for st in request.tiempos_servicio}

    desde, hasta = request.desde.isoformat(), request.hasta.isoformat()
    dia_plan = request.plan.dia.isoformat() if request.plan and desde <= request.plan.dia.isoformat() <= hasta else None

    # OTs de cada técnico por día, según los electricistas asignados en Metabase
    carga: Dict[str, Dict[str, List[Activity]]] = {}
    sin_registrar: Counter = Counter()
    for actividad in request.actividades:
        fecha = actividad.fecha_visita
        if actividad.situacion != "asignada" or not fecha or not desde <= fecha <= hasta:
            continue
        if actividad.coordinates is None and actividad.gps:
            try:
                actividad.parse_coordinates()
            except ValueError:
                pass
        mencionados = responsables(actividad, tecnicos, ids)
        if not mencionados:
            if actividad.asignado_a and es_de_bia(actividad.contratista_asignado):
                sin_registrar[actividad.asignado_a] += 1
            continue
        for tecnico in mencionados:
            carga.setdefault(tecnico.id, {}).setdefault(fecha, []).append(actividad)

    def servicio_de(ots: List[Activity]) -> int:
        return sum(get_service_time(a.servicio, servicios) for a in ots)

    # El día del plan, cada técnico cuenta con su ruta calculada (asignadas + sugeridas)
    plan: Dict[str, RutaPlan] = {}
    for ruta in (request.plan.rutas if dia_plan else []):
        for tecnico_id in ruta.tecnicos_ids:
            plan[tecnico_id] = ruta

    fechas = [request.desde + timedelta(days=i) for i in range((request.hasta - request.desde).days + 1)]
    laborables = {f.isoformat() for f in fechas if f.weekday() < request.dias_semana}
    minutos_dia = request.horas_semana / request.dias_semana * 60

    por_dia = {
        f.isoformat(): {"fecha": f.isoformat(), "laborable": f.isoformat() in laborables, "usado_min": 0}
        for f in fechas
    }
    ots_por_dia: Dict[str, Set[str]] = {f: set() for f in por_dia}
    filas = []
    for tecnico in tecnicos:
        base = sedes.get(tecnico.base_id)
        dias = []
        cargas = dict(carga.get(tecnico.id, {}))
        if tecnico.id in plan:
            cargas.setdefault(dia_plan, [])
        for fecha, ots in sorted(cargas.items()):
            if fecha == dia_plan and tecnico.id in plan:
                ruta = plan[tecnico.id]
                # Sus OTs de Metabase que la ruta no trae (sin ubicación): servicio + viaje promedio de la ruta
                fuera = [a for a in ots if a.codigo_bia not in set(ruta.codigos)]
                promedio = ruta.viaje_min / len(ruta.codigos) if ruta.codigos else MINUTOS_VIAJE_SIN_UBICACION
                dias.append({
                    "fecha": fecha,
                    "ots": len(ruta.codigos) + len(fuera),
                    "servicio_min": ruta.servicio_min + servicio_de(fuera),
                    "viaje_min": int(round(ruta.viaje_min + promedio * len(fuera))),
                    "km": round(ruta.km, 1),
                    "viaje_estimado": bool(fuera),
                    "plan": True,
                    "codigos": list(ruta.codigos) + [a.codigo_bia for a in fuera],
                })
                ots_por_dia[fecha].update(ruta.codigos)
                ots_por_dia[fecha].update(a.codigo_bia for a in fuera)
                continue
            viaje, km, estimado = minutos_de_viaje(ots, base.coordinates if base else None, dist, jornada.incluir_retorno)
            dias.append({"fecha": fecha, "ots": len(ots), "servicio_min": servicio_de(ots), "viaje_min": viaje,
                         "km": km, "viaje_estimado": estimado, "plan": False,
                         "codigos": [a.codigo_bia for a in ots]})
            ots_por_dia[fecha].update(a.codigo_bia for a in ots)
        for d in dias:
            por_dia[d["fecha"]]["usado_min"] += d["servicio_min"] + d["viaje_min"]

        disponible = minutos_dia * len(laborables)
        usado = sum(d["servicio_min"] + d["viaje_min"] for d in dias)
        filas.append({
            "id": tecnico.id,
            "nombre": tecnico.nombre,
            "equipo": equipo_de_base.get(tecnico.base_id) or (base.empresa if base else tecnico.base_id),
            "ots": sum(d["ots"] for d in dias),
            "servicio_min": sum(d["servicio_min"] for d in dias),
            "viaje_min": sum(d["viaje_min"] for d in dias),
            "km": round(sum(d["km"] for d in dias), 1),
            "usado_min": usado,
            "disponible_min": round(disponible),
            "utr": round(usado / disponible, 4) if disponible else None,
            "dias_con_ots": len(dias),
            "viaje_estimado": any(d["viaje_estimado"] for d in dias),
            "dias": dias,
        })

    for fecha, d in por_dia.items():
        d["ots"] = len(ots_por_dia[fecha])
        d["disponible_min"] = round(minutos_dia * len(tecnicos)) if d["laborable"] else 0
        d["utr"] = round(d["usado_min"] / d["disponible_min"], 4) if d["disponible_min"] else None

    usado_total = sum(f["usado_min"] for f in filas)
    disponible_total = sum(f["disponible_min"] for f in filas)
    return {
        "desde": desde,
        "hasta": hasta,
        "horas_semana": request.horas_semana,
        "dias_semana": request.dias_semana,
        "horas_dia": round(minutos_dia / 60, 2),
        "dias_laborables": len(laborables),
        "dia_plan": dia_plan,
        "tecnicos": filas,
        "por_dia": list(por_dia.values()),
        "equipo": {
            "ots": len(set().union(*ots_por_dia.values())) if ots_por_dia else 0,
            "usado_min": usado_total,
            "disponible_min": disponible_total,
            "utr": round(usado_total / disponible_total, 4) if disponible_total else None,
        },
        "sin_registrar": [{"nombre": n, "ots": c} for n, c in sin_registrar.most_common()],
    }

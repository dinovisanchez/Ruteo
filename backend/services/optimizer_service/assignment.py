"""Asignación de OTs: técnicos in-house (VRP con varias bases) o contratista más cercano por OR"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import math
from typing import Dict, List, Optional, Tuple

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from shared.models import (
    Activity,
    ActividadSinAsignar,
    AssignmentRequest,
    AssignmentResult,
    CrewRoute,
    GPSCoordinates,
    JornadaConfig,
    OpcionContratista,
    RecomendacionContratista,
    RouteStop,
    RutaAsignada,
    SedeOperativa,
    Tecnico,
)
from shared.catalogo import normalizar_texto
from shared.config import settings
from shared.utils import (
    add_minutes_to_time,
    calculate_utilization,
    get_service_time,
    setup_logging,
)
from ..distance_service.calculator import haversine_distance

logger = setup_logging("optimizer-service", settings.LOG_LEVEL)

# Costo de dejar una OT sin asignar; muy por encima de cualquier ruta real (en minutos)
PENALIZACION_SIN_ASIGNAR = 1_000_000
# Peso de la ruta más larga en el objetivo: reparte la carga entre técnicos/cuadrillas
PESO_RUTA_MAS_LARGA = 10
# Costo por minuto que una ruta supera la carga promedio de su base (segunda pasada)
PESO_EXCESO_META = 20
MAX_ALTERNATIVAS = 3


class Distancias:
    """Distancia por vía aproximada: línea recta × factor vial, a velocidad promedio"""

    def __init__(self, jornada: JornadaConfig):
        self.factor = jornada.factor_vial
        self.velocidad = jornada.velocidad_promedio_kmh

    def km(self, a: GPSCoordinates, b: GPSCoordinates) -> float:
        return haversine_distance(a, b) * self.factor

    def minutos(self, a: GPSCoordinates, b: GPSCoordinates) -> int:
        return int(math.ceil(self.km(a, b) / self.velocidad * 60))


def _tiempos_servicio(jornada: JornadaConfig) -> Dict[str, int]:
    return {st.servicio: st.duracion_minutos for st in jornada.tiempos_servicio}


def _resolver_vrp(
    actividades: List[Activity],
    inicios: List[GPSCoordinates],
    jornada: JornadaConfig,
    dist: Distancias,
    limite_segundos: int,
    metas: Optional[List[Optional[int]]] = None,
    personas_vehiculo: Optional[List[int]] = None,
) -> Tuple[List[List[int]], List[int], List[int]]:
    """Reparte las actividades entre vehículos que salen de `inicios`.

    Cada vehículo tiene la jornada como tope de tiempo (viaje + servicio). Las
    actividades que no caben quedan descartadas. `metas` penaliza los minutos
    que cada vehículo pasa de su meta. Con `personas_vehiculo`, una OT solo va
    a vehículos (cuadrillas) con al menos las personas que requiere. Devuelve
    (rutas, descartadas, minutos por vehículo), con índices sobre `actividades`.
    """
    n, m = len(actividades), len(inicios)
    if n == 0:
        return [[] for _ in range(m)], [], [0] * m

    servicios = _tiempos_servicio(jornada)
    max_minutos = int(jornada.horas_laborales * 60)

    # Nodos: 0..m-1 bases, m..m+n-1 actividades, m+n fin libre (cuando no hay retorno)
    puntos = list(inicios) + [a.coordinates for a in actividades]
    fin_libre = m + n
    total_nodos = m + n + (0 if jornada.incluir_retorno else 1)
    viaje = [[0] * total_nodos for _ in range(total_nodos)]
    for i in range(m + n):
        for j in range(m + n):
            if i != j:
                viaje[i][j] = dist.minutos(puntos[i], puntos[j])
    servicio_nodo = [0] * m + [get_service_time(a.servicio, servicios) for a in actividades] + [0]

    finales = list(range(m)) if jornada.incluir_retorno else [fin_libre] * m
    manager = pywrapcp.RoutingIndexManager(total_nodos, m, list(range(m)), finales)
    routing = pywrapcp.RoutingModel(manager)

    def costo_viaje(desde, hasta):
        return viaje[manager.IndexToNode(desde)][manager.IndexToNode(hasta)]

    def tiempo_total(desde, hasta):
        nodo = manager.IndexToNode(desde)
        return viaje[nodo][manager.IndexToNode(hasta)] + servicio_nodo[nodo]

    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(costo_viaje))
    routing.AddDimension(routing.RegisterTransitCallback(tiempo_total), 0, max_minutos, True, "Tiempo")
    dimension_tiempo = routing.GetDimensionOrDie("Tiempo")
    dimension_tiempo.SetGlobalSpanCostCoefficient(PESO_RUTA_MAS_LARGA)
    for vehiculo, meta in enumerate(metas or []):
        if meta is not None:
            dimension_tiempo.SetCumulVarSoftUpperBound(routing.End(vehiculo), meta, PESO_EXCESO_META)

    if jornada.capacidad_maxima_actividades:
        def demanda(indice):
            return 1 if manager.IndexToNode(indice) >= m and manager.IndexToNode(indice) < m + n else 0
        routing.AddDimensionWithVehicleCapacity(
            routing.RegisterUnaryTransitCallback(demanda),
            0,
            [jornada.capacidad_maxima_actividades] * m,
            True,
            "Actividades",
        )

    for nodo in range(m, m + n):
        indice = manager.NodeToIndex(nodo)
        routing.AddDisjunction([indice], PENALIZACION_SIN_ASIGNAR)
        if personas_vehiculo:
            requeridas = actividades[nodo - m].personas_requeridas
            permitidos = [v for v in range(m) if personas_vehiculo[v] >= requeridas]
            if len(permitidos) < m:
                routing.SetAllowedVehiclesForIndex(permitidos, indice)

    parametros = pywrapcp.DefaultRoutingSearchParameters()
    parametros.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    parametros.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    parametros.time_limit.seconds = limite_segundos

    solucion = routing.SolveWithParameters(parametros)
    if not solucion:
        logger.warning("El solver no encontró solución; todas las actividades quedan sin asignar")
        return [[] for _ in range(m)], list(range(n)), [0] * m

    rutas: List[List[int]] = []
    asignadas = set()
    for vehiculo in range(m):
        ruta = []
        indice = routing.Start(vehiculo)
        while not routing.IsEnd(indice):
            nodo = manager.IndexToNode(indice)
            if m <= nodo < m + n:
                ruta.append(nodo - m)
                asignadas.add(nodo - m)
            indice = solucion.Value(routing.NextVar(indice))
        rutas.append(ruta)

    minutos = [solucion.Value(dimension_tiempo.CumulVar(routing.End(v))) for v in range(m)]
    descartadas = [i for i in range(n) if i not in asignadas]
    return rutas, descartadas, minutos


def _resolver_balanceado(
    actividades: List[Activity],
    inicios: List[GPSCoordinates],
    grupos: List[str],
    jornada: JornadaConfig,
    dist: Distancias,
    limite_segundos: int,
    personas_vehiculo: Optional[List[int]] = None,
) -> Tuple[List[List[int]], List[int]]:
    """Como `_resolver_vrp`, pero reparte la carga entre los vehículos de un mismo grupo (base).

    Primero resuelve sin metas; luego vuelve a resolver con la carga promedio de
    cada grupo como meta. Se queda con la segunda solución si no deja más OTs
    sin asignar.
    """
    rutas, descartadas, minutos = _resolver_vrp(
        actividades, inicios, jornada, dist, limite_segundos, personas_vehiculo=personas_vehiculo
    )
    por_grupo: Dict[str, List[int]] = {}
    for vehiculo, grupo in enumerate(grupos):
        por_grupo.setdefault(grupo, []).append(vehiculo)
    if all(len(vehiculos) < 2 for vehiculos in por_grupo.values()):
        return rutas, descartadas

    metas: List[Optional[int]] = [None] * len(inicios)
    for vehiculos in por_grupo.values():
        if len(vehiculos) >= 2:
            meta = math.ceil(sum(minutos[v] for v in vehiculos) / len(vehiculos))
            for v in vehiculos:
                metas[v] = meta
    rutas_b, descartadas_b, _ = _resolver_vrp(
        actividades, inicios, jornada, dist, limite_segundos, metas, personas_vehiculo
    )
    if len(descartadas_b) <= len(descartadas):
        return rutas_b, descartadas_b
    return rutas, descartadas


def _limite_solver(num_actividades: int) -> int:
    return min(10, 1 + num_actividades // 15)


def construir_ruta(
    cuadrilla_id: int,
    actividades: List[Activity],
    inicio: GPSCoordinates,
    jornada: JornadaConfig,
    dist: Distancias,
) -> CrewRoute:
    """Calcula horarios y totales de una ruta que sale de `inicio` y visita las actividades en orden"""
    servicios = _tiempos_servicio(jornada)
    paradas: List[RouteStop] = []
    hora = jornada.horario_inicio
    posicion = inicio
    distancia_total = 0.0
    trabajo = 0
    desplazamiento = 0

    for secuencia, actividad in enumerate(actividades, start=1):
        km = dist.km(posicion, actividad.coordinates)
        minutos_viaje = dist.minutos(posicion, actividad.coordinates)
        minutos_servicio = get_service_time(actividad.servicio, servicios)
        llegada = add_minutes_to_time(hora, minutos_viaje)
        salida = add_minutes_to_time(llegada, minutos_servicio)
        paradas.append(RouteStop(
            secuencia=secuencia,
            actividad=actividad,
            hora_llegada_estimada=llegada,
            hora_salida_estimada=salida,
            distancia_desde_anterior_km=round(km, 2),
            tiempo_desplazamiento_minutos=minutos_viaje,
        ))
        distancia_total += km
        trabajo += minutos_servicio
        desplazamiento += minutos_viaje
        posicion = actividad.coordinates
        hora = salida

    if jornada.incluir_retorno and paradas:
        distancia_total += dist.km(posicion, inicio)
        minutos_retorno = dist.minutos(posicion, inicio)
        desplazamiento += minutos_retorno
        hora = add_minutes_to_time(hora, minutos_retorno)

    disponible = int(jornada.horas_laborales * 60)
    return CrewRoute(
        cuadrilla_id=cuadrilla_id,
        paradas=paradas,
        distancia_total_km=round(distancia_total, 2),
        tiempo_total_minutos=trabajo + desplazamiento,
        tiempo_trabajo_minutos=trabajo,
        tiempo_desplazamiento_minutos=desplazamiento,
        hora_inicio=jornada.horario_inicio,
        hora_fin=hora,
        utilization_percent=round(calculate_utilization(trabajo, desplazamiento, disponible), 2),
        # Se compara el tiempo transcurrido, no la hora del reloj (que da la vuelta a las 24 h)
        viable=trabajo + desplazamiento <= disponible,
    )


def _separar_sin_coordenadas(actividades: List[Activity]) -> Tuple[List[Activity], List[ActividadSinAsignar]]:
    con_coordenadas, sin_coordenadas = [], []
    for actividad in actividades:
        if actividad.coordinates is None and actividad.gps:
            try:
                actividad.parse_coordinates()
            except ValueError:
                pass
        if actividad.coordinates is None:
            sin_coordenadas.append(ActividadSinAsignar(actividad=actividad, motivo="La OT no tiene coordenadas"))
        else:
            con_coordenadas.append(actividad)
    return con_coordenadas, sin_coordenadas


def armar_cuadrillas(
    tecnicos: List[Tecnico],
    manuales: List[List[str]],
    actividades: List[Activity],
    sedes: Dict[str, SedeOperativa],
    jornada: JornadaConfig,
) -> List[List[Tecnico]]:
    """Agrupa a los técnicos seleccionados en cuadrillas de 1 o 2 personas.

    Las cuadrillas manuales se respetan; el resto de técnicos sale solo. Sin
    cuadrillas manuales, en cada base se forman las parejas que pide el trabajo
    de las OTs de 2 o más personas (asignando cada OT a la base más cercana).
    """
    por_id = {t.id: t for t in tecnicos}
    if manuales:
        cuadrillas = [[por_id[i] for i in grupo if i in por_id] for grupo in manuales]
        cuadrillas = [c for c in cuadrillas if c]
        usados = {t.id for c in cuadrillas for t in c}
        return cuadrillas + [[t] for t in tecnicos if t.id not in usados]

    por_base: Dict[str, List[Tecnico]] = {}
    for tecnico in tecnicos:
        por_base.setdefault(tecnico.base_id, []).append(tecnico)

    servicios = _tiempos_servicio(jornada)
    minutos_pareja: Dict[str, int] = {base: 0 for base in por_base}
    for actividad in actividades:
        if actividad.personas_requeridas < 2:
            continue
        base = min(por_base, key=lambda b: haversine_distance(sedes[b].coordinates, actividad.coordinates))
        minutos_pareja[base] += get_service_time(actividad.servicio, servicios)

    max_minutos = int(jornada.horas_laborales * 60)
    cuadrillas: List[List[Tecnico]] = []
    for base, grupo in por_base.items():
        # El 1,25 cubre los desplazamientos, igual que la estimación de cuadrillas de contratistas
        parejas = min(len(grupo) // 2, math.ceil(minutos_pareja[base] * 1.25 / max_minutos))
        cuadrillas += [grupo[2 * k:2 * k + 2] for k in range(parejas)]
        cuadrillas += [[t] for t in grupo[2 * parejas:]]
    return cuadrillas


def _costo_cuadrilla(cuadrilla: List[Tecnico]) -> Optional[float]:
    costos = [t.costo_dia for t in cuadrilla if t.costo_dia is not None]
    return float(sum(costos)) if costos else None


def asignar_inhouse(request: AssignmentRequest) -> AssignmentResult:
    """Reparte las OTs entre cuadrillas de los técnicos seleccionados, cada una saliendo de su base"""
    sedes = {s.id: s for s in request.sedes}
    tecnicos = [t for t in request.tecnicos if t.base_id in sedes]
    if not tecnicos:
        raise ValueError("Selecciona al menos un técnico con una base válida")

    actividades, sin_asignar = _separar_sin_coordenadas(request.actividades)
    cuadrillas = armar_cuadrillas(tecnicos, request.cuadrillas, actividades, sedes, request.jornada)
    max_personas = max(len(c) for c in cuadrillas)
    atendibles = [a for a in actividades if a.personas_requeridas <= max_personas]
    sin_asignar += [
        ActividadSinAsignar(
            actividad=a,
            motivo=f"Requiere {a.personas_requeridas} personas y no hay una cuadrilla de ese tamaño",
        )
        for a in actividades if a.personas_requeridas > max_personas
    ]

    dist = Distancias(request.jornada)
    rutas_idx, descartadas = _resolver_balanceado(
        atendibles,
        [sedes[c[0].base_id].coordinates for c in cuadrillas],
        [c[0].base_id for c in cuadrillas],
        request.jornada,
        dist,
        _limite_solver(len(atendibles)),
        personas_vehiculo=[len(c) for c in cuadrillas],
    )

    rutas: List[RutaAsignada] = []
    for numero, (cuadrilla, indices) in enumerate(zip(cuadrillas, rutas_idx), start=1):
        if not indices:
            continue
        sede = sedes[cuadrilla[0].base_id]
        rutas.append(RutaAsignada(
            responsable_id="+".join(t.id for t in cuadrilla),
            responsable=" + ".join(t.nombre for t in cuadrilla),
            tipo="tecnico",
            sede=sede,
            ruta=construir_ruta(numero, [atendibles[i] for i in indices], sede.coordinates, request.jornada, dist),
            integrantes=[t.nombre for t in cuadrilla],
            personas=len(cuadrilla),
            costo=_costo_cuadrilla(cuadrilla),
        ))

    sin_asignar += [
        ActividadSinAsignar(
            actividad=atendibles[i],
            motivo="No cabe en la jornada de los técnicos seleccionados",
        )
        for i in descartadas
    ]
    extra = {
        "tecnicos_seleccionados": len(tecnicos),
        "cuadrillas_armadas": len(cuadrillas),
        "parejas": sum(1 for c in cuadrillas if len(c) >= 2),
        "cuadrillas_manuales": bool(request.cuadrillas),
    }
    return _resultado("inhouse", request, rutas, [], sin_asignar, extra)


def recomendar_contratista(
    actividad: Activity,
    sedes_contratistas: List[SedeOperativa],
    or_contratistas: Dict[str, List[str]],
    dist: Distancias,
) -> RecomendacionContratista:
    """Elige la sede más cercana entre los contratistas que atienden el OR de la OT.

    Si el OR no tiene contratistas definidos se elige entre todos.
    """
    empresas_or = set(or_contratistas.get(normalizar_texto(actividad.or_operador), []))
    candidatas = [s for s in sedes_contratistas if s.empresa_id in empresas_or]
    criterio = "lista_or"
    if not candidatas:
        candidatas = sedes_contratistas
        criterio = "sin_lista_or"

    # Una opción por empresa: su sede más cercana a la OT
    mejor_por_empresa: Dict[str, OpcionContratista] = {}
    for sede in candidatas:
        km = round(dist.km(sede.coordinates, actividad.coordinates), 2)
        actual = mejor_por_empresa.get(sede.empresa_id)
        if actual is None or km < actual.distancia_km:
            mejor_por_empresa[sede.empresa_id] = OpcionContratista(
                sede_id=sede.id, empresa=sede.empresa, ciudad=sede.ciudad, distancia_km=km
            )
    opciones = sorted(mejor_por_empresa.values(), key=lambda o: o.distancia_km)

    return RecomendacionContratista(
        codigo_bia=actividad.codigo_bia,
        or_operador=actividad.or_operador,
        elegido=opciones[0] if opciones else None,
        criterio=criterio,
        alternativas=opciones[1:1 + MAX_ALTERNATIVAS],
    )


def _ordenar_por_cercania(actividades: List[Activity], inicio: GPSCoordinates, dist: Distancias) -> List[Activity]:
    """Orden de visita por vecino más cercano partiendo de `inicio`"""
    pendientes = list(actividades)
    orden = []
    posicion = inicio
    while pendientes:
        siguiente = min(pendientes, key=lambda a: dist.km(posicion, a.coordinates))
        pendientes.remove(siguiente)
        orden.append(siguiente)
        posicion = siguiente.coordinates
    return orden


def _planificar_sede(
    actividades: List[Activity],
    sede: SedeOperativa,
    jornada: JornadaConfig,
    dist: Distancias,
) -> Tuple[List[List[Activity]], List[Activity]]:
    """Arma las cuadrillas mínimas para que las OTs de una sede quepan en la jornada.

    Devuelve (rutas, lejanas): las lejanas no caben en una jornada ni solas
    (ir, atender y volver supera las horas laborales) y van en un viaje aparte.
    """
    servicios = _tiempos_servicio(jornada)
    max_minutos = int(jornada.horas_laborales * 60)

    def minutos_solo(actividad: Activity) -> int:
        ida = dist.minutos(sede.coordinates, actividad.coordinates)
        vuelta = ida if jornada.incluir_retorno else 0
        return ida + get_service_time(actividad.servicio, servicios) + vuelta

    caben = [a for a in actividades if minutos_solo(a) <= max_minutos]
    lejanas = [a for a in actividades if minutos_solo(a) > max_minutos]
    if not caben:
        return [], lejanas

    servicio_total = sum(get_service_time(a.servicio, servicios) for a in caben)
    cuadrillas = max(1, math.ceil(servicio_total * 1.25 / max_minutos))
    if jornada.capacidad_maxima_actividades:
        cuadrillas = max(cuadrillas, math.ceil(len(caben) / jornada.capacidad_maxima_actividades))

    limite = _limite_solver(len(caben))
    while True:
        # Búsqueda corta: aquí solo interesa si caben todas, la ruta fina se arma después
        rutas_idx, descartadas, _ = _resolver_vrp(
            caben, [sede.coordinates] * cuadrillas, jornada, dist, min(3, limite)
        )
        if not descartadas or cuadrillas >= len(caben):
            break
        asignadas = len(caben) - len(descartadas)
        por_cuadrilla = max(1, asignadas // cuadrillas)
        cuadrillas = min(len(caben), cuadrillas + max(1, math.ceil(len(descartadas) / por_cuadrilla)))
    if cuadrillas > 1 and not descartadas:
        rutas_idx, descartadas = _resolver_balanceado(
            caben, [sede.coordinates] * cuadrillas, [sede.id] * cuadrillas, jornada, dist, limite
        )

    rutas = [[caben[i] for i in indices] for indices in rutas_idx if indices]
    # Con una cuadrilla por OT todas caben, así que aquí no deberían quedar descartadas
    rutas += [[caben[i]] for i in descartadas]
    return rutas, lejanas


def asignar_contratistas(request: AssignmentRequest) -> AssignmentResult:
    """Recomienda el contratista de cada OT y arma las rutas de cada sede elegida"""
    sedes_contratistas = [s for s in request.sedes if s.tipo == "contratista"]
    if not sedes_contratistas:
        raise ValueError("El catálogo no tiene sedes de contratistas")
    sedes = {s.id: s for s in sedes_contratistas}
    or_contratistas = {normalizar_texto(k): v for k, v in request.or_contratistas.items()}

    actividades, sin_asignar = _separar_sin_coordenadas(request.actividades)
    dist = Distancias(request.jornada)

    recomendaciones = []
    por_sede: Dict[str, List[Activity]] = {}
    for actividad in actividades:
        recomendacion = recomendar_contratista(actividad, sedes_contratistas, or_contratistas, dist)
        recomendaciones.append(recomendacion)
        por_sede.setdefault(recomendacion.elegido.sede_id, []).append(actividad)

    rutas: List[RutaAsignada] = []
    for sede_id, actividades_sede in por_sede.items():
        sede = sedes[sede_id]
        rutas_sede, lejanas = _planificar_sede(actividades_sede, sede, request.jornada, dist)
        for numero, ruta in enumerate(rutas_sede, start=1):
            rutas.append(RutaAsignada(
                responsable_id=f"{sede.id}#{numero}",
                responsable=f"{sede.empresa} ({sede.ciudad}) · Cuadrilla {numero}",
                tipo="contratista",
                sede=sede,
                ruta=construir_ruta(numero, ruta, sede.coordinates, request.jornada, dist),
                personas=max(a.personas_requeridas for a in ruta),
            ))
        # Las lejanas también son de este contratista: van juntas en un viaje que supera la jornada
        if lejanas:
            numero = len(rutas_sede) + 1
            rutas.append(RutaAsignada(
                responsable_id=f"{sede.id}#viaje",
                responsable=f"{sede.empresa} ({sede.ciudad}) · Viaje de más de una jornada",
                tipo="contratista",
                sede=sede,
                ruta=construir_ruta(
                    numero, _ordenar_por_cercania(lejanas, sede.coordinates, dist),
                    sede.coordinates, request.jornada, dist,
                ),
                personas=max(a.personas_requeridas for a in lejanas),
            ))

    por_contratista: Dict[str, int] = {}
    for recomendacion in recomendaciones:
        por_contratista[recomendacion.elegido.empresa] = por_contratista.get(recomendacion.elegido.empresa, 0) + 1
    extra = {
        "ots_por_contratista": por_contratista,
        "ots_sin_lista_or": sum(1 for r in recomendaciones if r.criterio == "sin_lista_or"),
    }
    return _resultado("contratistas", request, rutas, recomendaciones, sin_asignar, extra)


def _resultado(
    modo: str,
    request: AssignmentRequest,
    rutas: List[RutaAsignada],
    recomendaciones: List[RecomendacionContratista],
    sin_asignar: List[ActividadSinAsignar],
    extra: Dict,
) -> AssignmentResult:
    distancia = round(sum(r.ruta.distancia_total_km for r in rutas), 2)
    asignadas = sum(len(r.ruta.paradas) for r in rutas)
    costos = [r.costo for r in rutas if r.costo is not None]
    metricas = {
        "ots_asignadas": asignadas,
        "costo_total": round(sum(costos), 2) if costos else None,
        "ots_sin_asignar": len(sin_asignar),
        "rutas": len(rutas),
        "rutas_no_viables": sum(1 for r in rutas if not r.ruta.viable),
        "factor_vial": request.jornada.factor_vial,
        **extra,
    }
    return AssignmentResult(
        modo=modo,
        total_actividades=len(request.actividades),
        rutas=rutas,
        recomendaciones=recomendaciones,
        sin_asignar=sin_asignar,
        distancia_total_km=distancia,
        viable_en_un_dia=all(r.ruta.viable for r in rutas) and not sin_asignar,
        metricas=metricas,
    )


def asignar(request: AssignmentRequest) -> AssignmentResult:
    if request.modo == "inhouse":
        return asignar_inhouse(request)
    return asignar_contratistas(request)

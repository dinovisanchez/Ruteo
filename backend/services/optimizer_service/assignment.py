"""Asignación de OTs: técnicos in-house (VRP con varias bases) o contratista más cercano por OR"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import math
from typing import Dict, List, Optional, Set, Tuple

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from shared.models import (
    Activity,
    ActividadSinAsignar,
    DecisionOT,
    AssignmentRequest,
    AssignmentResult,
    CoberturaEquipo,
    CrewRoute,
    GPSCoordinates,
    JornadaConfig,
    OperadorRed,
    OpcionContratista,
    RecomendacionContratista,
    RouteStop,
    RutaAsignada,
    SedeOperativa,
    Tecnico,
)
from shared.operadores import clave, normalizar_departamento, resolver_or
from shared.distancias import Distancias
from shared.zonas import atiende_or, en_zona
from shared.config import settings
from shared.utils import (
    add_minutes_to_time,
    calculate_utilization,
    get_service_time,
    haversine_distance,
    setup_logging,
)

logger = setup_logging("optimizer-service", settings.LOG_LEVEL)

# Costo de dejar una OT sin asignar; muy por encima de cualquier ruta real (en minutos)
PENALIZACION_SIN_ASIGNAR = 1_000_000
# Una OT fijada a un técnico se descarta solo si no queda otra salida
PENALIZACION_FIJADA = PENALIZACION_SIN_ASIGNAR * 100
# Peso de la ruta más larga en el objetivo: reparte la carga entre técnicos/cuadrillas
PESO_RUTA_MAS_LARGA = 10
# Costo por minuto que una ruta supera la carga promedio de su base (segunda pasada)
PESO_EXCESO_META = 20
MAX_ALTERNATIVAS = 3
# Un grupo de OTs cercanas no pasa de esta parte de la jornada, para que quepa con el viaje desde la base
FRACCION_GRUPO = 0.6
# En el motivo se nombran hasta estas OTs del grupo
MAX_NOMBRADAS = 3


def _tiempos_servicio(jornada: JornadaConfig) -> Dict[str, int]:
    return {st.servicio: st.duracion_minutos for st in jornada.tiempos_servicio}


def _resolver_vrp(
    actividades: List[Activity],
    inicios: List[GPSCoordinates],
    jornada: JornadaConfig,
    dist: Distancias,
    limite_segundos: int,
    metas: Optional[List[Optional[int]]] = None,
    permitidos: Optional[List[Optional[List[int]]]] = None,
    fijadas: Optional[Set[int]] = None,
    servicio_nodos: Optional[List[int]] = None,
) -> Tuple[List[List[int]], List[int], List[int]]:
    """Reparte las actividades entre vehículos que salen de `inicios`.

    Cada vehículo tiene la jornada como tope de tiempo (viaje + servicio). Las
    actividades que no caben quedan descartadas. `metas` penaliza los minutos
    que cada vehículo pasa de su meta. `permitidos[i]` limita la actividad i a
    esos vehículos (None = cualquiera) y las `fijadas` se descartan de últimas.
    `servicio_nodos` reemplaza los minutos de servicio de cada actividad (un grupo
    de OTs cercanas viaja como una sola). Devuelve (rutas, descartadas, minutos
    por vehículo), con índices sobre `actividades`.
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
    minutos_servicio = servicio_nodos if servicio_nodos is not None else [
        get_service_time(a.servicio, servicios) for a in actividades
    ]
    servicio_nodo = [0] * m + list(minutos_servicio) + [0]

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
        fijada = fijadas is not None and nodo - m in fijadas
        routing.AddDisjunction([indice], PENALIZACION_FIJADA if fijada else PENALIZACION_SIN_ASIGNAR)
        if permitidos and permitidos[nodo - m] is not None:
            routing.SetAllowedVehiclesForIndex(permitidos[nodo - m], indice)

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
    permitidos: Optional[List[Optional[List[int]]]] = None,
    fijadas: Optional[Set[int]] = None,
) -> Tuple[List[List[int]], List[int]]:
    """Como `_resolver_vrp`, pero reparte la carga entre los vehículos de un mismo grupo (base).

    Primero resuelve sin metas; luego vuelve a resolver con la carga promedio del grupo
    como meta de cada vehículo. Se queda con la segunda solución si no deja más OTs sin
    asignar. Lo usan las cuadrillas de un contratista.
    """
    rutas, descartadas, minutos = _resolver_vrp(
        actividades, inicios, jornada, dist, limite_segundos, permitidos=permitidos, fijadas=fijadas
    )
    por_grupo: Dict[str, List[int]] = {}
    for vehiculo, grupo in enumerate(grupos):
        por_grupo.setdefault(grupo, []).append(vehiculo)
    if all(len(vehiculos) < 2 for vehiculos in por_grupo.values()):
        return rutas, descartadas

    metas: List[Optional[int]] = [None] * len(inicios)
    for vehiculos in por_grupo.values():
        if len(vehiculos) < 2:
            continue
        total = sum(minutos[v] for v in vehiculos)
        for v in vehiculos:
            metas[v] = math.ceil(total / len(vehiculos))
    rutas_b, descartadas_b, _ = _resolver_vrp(
        actividades, inicios, jornada, dist, limite_segundos, metas, permitidos, fijadas
    )
    if len(descartadas_b) <= len(descartadas):
        return rutas_b, descartadas_b
    return rutas, descartadas


def _orden_cercania(indices: List[int], actividades: List[Activity], inicio: GPSCoordinates, dist: Distancias) -> List[int]:
    """Índices en orden de visita por vecino más cercano partiendo de `inicio`"""
    pendientes, orden, posicion = list(indices), [], inicio
    while pendientes:
        siguiente = min(pendientes, key=lambda i: dist.km(posicion, actividades[i].coordinates))
        pendientes.remove(siguiente)
        orden.append(siguiente)
        posicion = actividades[siguiente].coordinates
    return orden


def _minutos_grupo(grupo: List[int], actividades: List[Activity], servicios: Dict[str, int], dist: Distancias) -> int:
    """Servicio de todas las OTs del grupo más el viaje entre ellas, empezando por la primera"""
    orden = [grupo[0]] + _orden_cercania(grupo[1:], actividades, actividades[grupo[0]].coordinates, dist)
    viaje = sum(dist.minutos(actividades[a].coordinates, actividades[b].coordinates) for a, b in zip(orden, orden[1:]))
    return viaje + sum(get_service_time(actividades[i].servicio, servicios) for i in grupo)


def _precisa(actividad: Activity) -> bool:
    """Tiene GPS o se ubicó por su dirección (no solo por el centro de su municipio)"""
    return not actividad.ubicacion_municipio


def grupos_cercanos(
    indices: List[int],
    actividades: List[Activity],
    claves: Dict[int, object],
    radio_km: float,
    tope_minutos: int,
    servicios: Dict[str, int],
    dist: Distancias,
) -> List[List[int]]:
    """Junta las OTs que están a `radio_km` o menos (por carretera) para que las haga una sola cuadrilla.

    Solo se juntan OTs con la misma `clave` (las mismas cuadrillas posibles). Cada grupo crece
    alrededor de la OT con más vecinas, de la más cercana a la más lejana, sin pasar de
    `tope_minutos` de trabajo más viaje entre ellas. Las OTs sin vecinas quedan solas.
    El primer índice de cada grupo es la OT del centro.
    """
    if radio_km <= 0 or len(indices) < 2:
        return [[i] for i in indices]
    km = lambda a, b: dist.km(actividades[a].coordinates, actividades[b].coordinates)
    # Las ubicadas solo por su municipio están todas en el centro: no se sabe si están cerca
    vecinas = {
        i: [j for j in indices if j != i and claves.get(j) == claves.get(i) and _precisa(actividades[i])
            and _precisa(actividades[j]) and km(i, j) <= radio_km]
        for i in indices
    }
    restantes = set(indices)
    grupos: List[List[int]] = []
    while restantes:
        centro = max(sorted(restantes), key=lambda i: sum(1 for j in vecinas[i] if j in restantes))
        grupo = [centro]
        minutos = get_service_time(actividades[centro].servicio, servicios)
        for j in sorted((j for j in vecinas[centro] if j in restantes), key=lambda j: km(centro, j)):
            extra = get_service_time(actividades[j].servicio, servicios) + dist.minutos(
                actividades[grupo[-1]].coordinates, actividades[j].coordinates
            )
            if minutos + extra <= tope_minutos:
                grupo.append(j)
                minutos += extra
        restantes -= set(grupo)
        grupos.append(grupo)
    return grupos


REGLA_CERCA, REGLA_LIBRE, REGLA_MENOR_UTR, REGLA_NO_CABE = 1, 2, 3, 4


def repartir_por_reglas(
    nodos: List[List[int]],
    actividades: List[Activity],
    permitidos: List[Optional[List[int]]],
    fijos: Set[int],
    inicios: List[GPSCoordinates],
    previos: Optional[List[float]],
    jornada: JornadaConfig,
    dist: Distancias,
) -> Dict[int, Dict]:
    """A qué cuadrilla va cada grupo libre de OTs (`nodos`, índices sobre `actividades`), en este orden:

    1. Cerca: si el grupo está a `radio_grupo_km` o menos de las OTs que una cuadrilla ya tiene
       ese día, va a la más cercana, aunque otra lleve menos carga en la semana.
    2. Libre: si no, a una cuadrilla que todavía no tiene OTs ese día (la de menor carga).
    3. Si todas tienen OTs y están lejos, a la de menor carga en la semana (`previos` + el día).

    Solo cuentan las cuadrillas donde el grupo cabe en la jornada. Se decide primero lo más
    claro: lo cercano (de lo más cerca a lo más lejos) y luego los grupos más grandes; cada
    decisión cuenta para las siguientes. `fijos` son grupos ya fijados a su única cuadrilla
    permitida. Devuelve por grupo {"vehiculo", "regla", "km", "antes", "despues", "opciones"}
    (minutos de carga antes y después); si no cabe en ninguna, la regla es REGLA_NO_CABE y el
    vehículo es el de menor carga.
    """
    servicios = _tiempos_servicio(jornada)
    m = len(inicios)
    max_minutos = int(jornada.horas_laborales * 60)
    radio = jornada.radio_grupo_km
    centros = [actividades[nodo[0]] for nodo in nodos]
    minutos = [_minutos_grupo(nodo, actividades, servicios, dist) for nodo in nodos]
    previo = list(previos) if previos else [0.0] * m

    # Ruta tentativa de cada cuadrilla: lo fijado, en orden de cercanía desde su base
    paradas: List[List[int]] = [[] for _ in range(m)]
    for n in fijos:
        paradas[permitidos[n][0] if permitidos[n] else 0].append(n)
    paradas = [_orden_cercania(paradas[v], centros, inicios[v], dist) for v in range(m)]

    def minutos_ruta(v: int) -> int:
        puntos = [inicios[v]] + [centros[n].coordinates for n in paradas[v]]
        if jornada.incluir_retorno and paradas[v]:
            puntos.append(inicios[v])
        return sum(dist.minutos(a, b) for a, b in zip(puntos, puntos[1:])) + sum(minutos[n] for n in paradas[v])

    carga = [minutos_ruta(v) for v in range(m)]

    def km_entre(a: int, b: int) -> float:
        return min((dist.km(actividades[i].coordinates, actividades[j].coordinates)
                    for i in nodos[a] for j in nodos[b] if _precisa(actividades[i]) and _precisa(actividades[j])),
                   default=math.inf)

    def insercion(v: int, n: int) -> Tuple[int, int]:
        """Dónde menos desvía el grupo en la ruta de v, y cuánto queda la carga de v"""
        ruta, c = paradas[v], centros[n].coordinates
        puntos = [inicios[v]] + [centros[r].coordinates for r in ruta]
        mejor = None
        for pos in range(len(ruta) + 1):
            anterior = puntos[pos]
            if pos < len(ruta):
                siguiente = puntos[pos + 1]
                desvio = dist.minutos(anterior, c) + dist.minutos(c, siguiente) - dist.minutos(anterior, siguiente)
            elif jornada.incluir_retorno:
                vuelta = dist.minutos(anterior, inicios[v]) if ruta else 0
                desvio = dist.minutos(anterior, c) + dist.minutos(c, inicios[v]) - vuelta
            else:
                desvio = dist.minutos(anterior, c)
            if mejor is None or desvio < mejor[1]:
                mejor = (pos, desvio)
        return mejor[0], carga[v] + mejor[1] + minutos[n]

    pendientes = [n for n in range(len(nodos)) if n not in fijos]
    cerca = {(n, v): min((km_entre(n, r) for r in paradas[v]), default=math.inf) for n in pendientes for v in range(m)}

    def opcion(n: int, v: int) -> Tuple[Tuple, int, int]:
        pos, nueva = insercion(v, n)
        km = cerca[(n, v)]
        if nueva > max_minutos:
            clave: Tuple = (REGLA_NO_CABE, previo[v] + carga[v])
        elif radio > 0 and km <= radio:
            clave = (REGLA_CERCA, km)
        elif not paradas[v]:
            clave = (REGLA_LIBRE, previo[v] + carga[v], dist.km(inicios[v], centros[n].coordinates))
        else:
            clave = (REGLA_MENOR_UTR, previo[v] + carga[v], km)
        return clave + (v,), pos, nueva

    def permitido(n: int, v: int) -> bool:
        return permitidos[n] is None or v in permitidos[n]

    opciones = {(n, v): opcion(n, v) for n in pendientes for v in range(m) if permitido(n, v)}

    def decision(n: int, elegida: Tuple[Tuple, int, int]) -> Dict:
        v = elegida[0][-1]
        return {
            "vehiculo": v,
            "regla": elegida[0][0],
            "km": cerca[(n, v)],
            "antes": previo[v] + carga[v],
            "despues": previo[v] + elegida[2],
            "opciones": [
                {"vehiculo": o[0][-1], "regla": o[0][0], "km": cerca[(n, o[0][-1])],
                 "carga": previo[o[0][-1]] + carga[o[0][-1]], "cabe": o[0][0] != REGLA_NO_CABE}
                for o in sorted(opciones[(n, w)] for w in range(m) if (n, w) in opciones)
            ],
        }

    decididos: Dict[int, Dict] = {}
    por_decidir = set(pendientes)
    while por_decidir:
        mejor = None
        for n in por_decidir:
            propias = [opciones[(n, v)] for v in range(m) if (n, v) in opciones]
            if not propias:
                continue
            elegida = min(propias)
            regla = elegida[0][0]
            if regla == REGLA_NO_CABE:
                continue
            prioridad = (regla, elegida[0][1] if regla == REGLA_CERCA else -minutos[n], n)
            if mejor is None or prioridad < mejor[0]:
                mejor = (prioridad, n, elegida)
        if mejor is None:
            break
        _, n, elegida = mejor
        decididos[n] = decision(n, elegida)
        v, pos, nueva = elegida[0][-1], elegida[1], elegida[2]
        paradas[v].insert(pos, n)
        carga[v] = nueva
        por_decidir.discard(n)
        for otro in por_decidir:
            cerca[(otro, v)] = min(cerca[(otro, v)], km_entre(otro, n))
            if (otro, v) in opciones:
                opciones[(otro, v)] = opcion(otro, v)
    # Los que no caben en ninguna jornada: la cuadrilla de menor carga, para quien lo quiera forzar
    for n in por_decidir:
        propias = [opciones[(n, v)] for v in range(m) if (n, v) in opciones]
        if propias:
            decididos[n] = decision(n, min(propias))
    return decididos


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
    fijas: List[List[str]],
    actividades: List[Activity],
    sedes: Dict[str, SedeOperativa],
    jornada: JornadaConfig,
    bases_permitidas: Optional[Dict[str, Set[str]]] = None,
    con_pareja: Optional[Set[str]] = None,
) -> List[List[Tecnico]]:
    """Agrupa a los técnicos disponibles en cuadrillas de 1 o 2 personas.

    Las cuadrillas fijas (armadas a mano o que ya salen juntas en Metabase) se
    respetan. Con el resto, en cada base se forman las parejas que pide el
    trabajo de las OTs de 2 o más personas (asignando cada OT a la base más
    cercana), descontando las parejas fijas de esa base. Los técnicos de
    `con_pareja` (tienen fijada una OT de 2 personas) no salen solos.
    """
    con_pareja = con_pareja or set()
    por_id = {t.id: t for t in tecnicos}
    cuadrillas = [[por_id[i] for i in grupo if i in por_id] for grupo in fijas]
    cuadrillas = [c for c in cuadrillas if c]
    usados = {t.id for c in cuadrillas for t in c}

    por_base: Dict[str, List[Tecnico]] = {}
    for tecnico in tecnicos:
        if tecnico.id not in usados:
            por_base.setdefault(tecnico.base_id, []).append(tecnico)
    if not por_base:
        return cuadrillas

    servicios = _tiempos_servicio(jornada)
    bases = list(dict.fromkeys(t.base_id for t in tecnicos))
    minutos_pareja: Dict[str, int] = {base: 0 for base in bases}
    for actividad in actividades:
        if actividad.personas_requeridas < 2:
            continue
        permitidas = (bases_permitidas or {}).get(actividad.codigo_bia)
        candidatas = [b for b in bases if not permitidas or b in permitidas] or bases
        base = min(candidatas, key=lambda b: haversine_distance(sedes[b].coordinates, actividad.coordinates))
        minutos_pareja[base] += get_service_time(actividad.servicio, servicios)

    max_minutos = int(jornada.horas_laborales * 60)
    for base, grupo in por_base.items():
        # Quien no puede salir solo va primero, así queda en una pareja
        grupo = [t for t in grupo if t.id in con_pareja] + [t for t in grupo if t.id not in con_pareja]
        # El 1,25 cubre los desplazamientos, igual que la estimación de cuadrillas de contratistas
        necesarias = math.ceil(minutos_pareja[base] * 1.25 / max_minutos)
        armadas = sum(1 for c in cuadrillas if len(c) >= 2 and c[0].base_id == base)
        minimas = math.ceil(sum(1 for t in grupo if t.id in con_pareja) / 2)
        parejas = max(0, min(len(grupo) // 2, max(necesarias - armadas, minimas)))
        cuadrillas += [grupo[2 * k:2 * k + 2] for k in range(parejas)]
        cuadrillas += [[t] for t in grupo[2 * parejas:]]
    return cuadrillas


def _costo_cuadrilla(cuadrilla: List[Tecnico]) -> Optional[float]:
    costos = [t.costo_dia for t in cuadrilla if t.costo_dia is not None]
    return float(sum(costos)) if costos else None


def _insertar_donde_menos_desvia(
    ruta: List[int],
    i: int,
    actividades: List[Activity],
    inicio: GPSCoordinates,
    dist: Distancias,
) -> None:
    """Mete la actividad i en la posición de la ruta que menos kilómetros agrega"""
    puntos = [inicio] + [actividades[j].coordinates for j in ruta]
    nuevo = actividades[i].coordinates

    def desvio(posicion: int) -> float:
        anterior = puntos[posicion]
        if posicion + 1 == len(puntos):
            return dist.km(anterior, nuevo)
        siguiente = puntos[posicion + 1]
        return dist.km(anterior, nuevo) + dist.km(nuevo, siguiente) - dist.km(anterior, siguiente)

    ruta.insert(min(range(len(ruta) + 1), key=desvio), i)


def _razon_regla(decidido: Dict, nombre: str) -> str:
    """Por qué el grupo le tocó a esa cuadrilla, para el motivo de la decisión"""
    if decidido["regla"] == REGLA_CERCA:
        return f"Está a {decidido['km']:.1f} km de otras OTs de {nombre} hoy"
    if decidido["regla"] == REGLA_LIBRE:
        return f"{nombre} no tenía OTs hoy y nadie más tiene OTs cerca"
    return f"Todos tienen OTs lejos de esta: va a {nombre}, con la menor carga de la semana"


def _asignar_inhouse(
    actividades: List[Activity],
    fijas: Dict[str, str],
    tecnicos: List[Tecnico],
    request: AssignmentRequest,
    dist: Distancias,
    bases_permitidas: Optional[Dict[str, Set[str]]] = None,
) -> Tuple[List[RutaAsignada], List[ActividadSinAsignar], Dict]:
    """Reparte las OTs entre cuadrillas de los técnicos disponibles, cada una saliendo de su base.

    `fijas` (OT → id de técnico) obliga a que la OT vaya a la cuadrilla de ese
    técnico; si no cabe en su jornada igual se le deja, y la ruta muestra el exceso.
    `bases_permitidas` (OT → bases) limita la OT a las cuadrillas del equipo que la cubre.
    """
    sedes = {s.id: s for s in request.sedes}
    bases_permitidas = bases_permitidas or {}
    libres = [a for a in actividades if a.codigo_bia not in fijas]
    personas_de = {a.codigo_bia: a.personas_requeridas for a in actividades}
    con_pareja = {t for codigo, t in fijas.items() if personas_de.get(codigo, 1) >= 2}
    cuadrillas = armar_cuadrillas(
        tecnicos, request.cuadrillas, libres, sedes, request.jornada, bases_permitidas, con_pareja
    )
    cuadrilla_de = {t.id: v for v, c in enumerate(cuadrillas) for t in c}
    personas = [len(c) for c in cuadrillas]
    grupos = [c[0].base_id for c in cuadrillas]

    atendibles: List[Activity] = []
    permitidos: List[List[int]] = []
    sin_asignar: List[ActividadSinAsignar] = []
    for actividad in actividades:
        tecnico_id = fijas.get(actividad.codigo_bia)
        if tecnico_id is not None:
            lista = [cuadrilla_de[tecnico_id]]
        else:
            permitidas = bases_permitidas.get(actividad.codigo_bia)
            lista = [
                v for v, p in enumerate(personas)
                if p >= actividad.personas_requeridas and (not permitidas or grupos[v] in permitidas)
            ]
            if not lista:
                sin_asignar.append(ActividadSinAsignar(
                    actividad=actividad,
                    motivo=f"Requiere {actividad.personas_requeridas} personas y no hay una cuadrilla de ese tamaño",
                ))
                continue
        atendibles.append(actividad)
        permitidos.append(lista)
    fijadas = {i for i, a in enumerate(atendibles) if a.codigo_bia in fijas}
    inicios = [sedes[c[0].base_id].coordinates for c in cuadrillas]
    # Lo que cada cuadrilla ya trabajó en la semana (promedio de sus integrantes)
    previos = [
        sum(request.uso_previo.get(t.id, 0) for t in c) / len(c) for c in cuadrillas
    ] if request.uso_previo else None

    servicios = _tiempos_servicio(request.jornada)
    tope_grupo = int(request.jornada.horas_laborales * 60 * FRACCION_GRUPO)
    # OT → las otras OTs cercanas que van con ella en la misma ruta, y por qué regla le tocó
    # a esa cuadrilla (para el motivo)
    juntas: Dict[str, List[str]] = {}
    razones: Dict[str, str] = {}

    def resolver(indices: List[int], vehiculos: List[int]) -> Tuple[Dict[int, List[int]], List[int]]:
        """Resuelve solo esas actividades con esas cuadrillas; índices sobre `atendibles`.

        Las OTs libres cercanas entre sí viajan como un solo punto, así las hace una sola
        cuadrilla; si un grupo no cabe en ninguna, se separa y se vuelve a resolver.
        """
        rutas = {v: [] for v in vehiculos}
        juntas.clear()
        razones.clear()
        if not vehiculos:
            return rutas, list(indices)
        posicion = {v: k for k, v in enumerate(vehiculos)}
        sub, sub_permitidos, sin_cuadrilla = [], [], []
        for i in indices:
            lista = [posicion[v] for v in permitidos[i] if v in posicion]
            if not lista:
                sin_cuadrilla.append(i)
                continue
            sub.append(i)
            sub_permitidos.append(lista if len(lista) < len(vehiculos) else None)
        acts = [atendibles[i] for i in sub]
        fijas_sub = {k for k, i in enumerate(sub) if i in fijadas}
        libres_sub = [k for k in range(len(sub)) if k not in fijas_sub]
        claves = {k: tuple(sub_permitidos[k]) if sub_permitidos[k] is not None else None for k in libres_sub}
        nodos = [[k] for k in sorted(fijas_sub)] + grupos_cercanos(
            libres_sub, acts, claves, request.jornada.radio_grupo_km, tope_grupo, servicios, dist
        )
        intentos = 2
        for intento in range(intentos):
            permitidos_nodo = [sub_permitidos[nodo[0]] for nodo in nodos]
            fijos_nodo = {n for n, nodo in enumerate(nodos) if nodo[0] in fijas_sub}
            # Cada grupo libre a su cuadrilla por las reglas (cerca, libre, menor UTR);
            # el solver solo ordena cada ruta y revisa que quepa en la jornada
            decididos = repartir_por_reglas(
                nodos, acts, permitidos_nodo, fijos_nodo, [inicios[v] for v in vehiculos],
                [previos[v] for v in vehiculos] if previos else None, request.jornada, dist,
            )
            elegidos = {n: d["vehiculo"] for n, d in decididos.items() if d["regla"] != REGLA_NO_CABE}
            rutas_nodos, descartados, _ = _resolver_vrp(
                [acts[nodo[0]] for nodo in nodos],
                [inicios[v] for v in vehiculos],
                request.jornada,
                dist,
                _limite_solver(len(nodos)),
                permitidos=[[elegidos[n]] if n in elegidos else permitidos_nodo[n] for n in range(len(nodos))],
                fijadas=fijos_nodo,
                servicio_nodos=[_minutos_grupo(nodo, acts, servicios, dist) for nodo in nodos],
            )
            sueltos = [n for n in descartados if len(nodos[n]) > 1]
            # En el último intento los grupos que no caben se quedan sin asignar enteros
            if not sueltos or intento == intentos - 1:
                break
            nodos = [nodo for n, nodo in enumerate(nodos) if n not in sueltos] + [
                [k] for n in sueltos for k in nodos[n]
            ]
        for k, ruta in enumerate(rutas_nodos):
            orden: List[int] = []
            punto = inicios[vehiculos[k]]
            nombre = " + ".join(t.nombre for t in cuadrillas[vehiculos[k]])
            for n in ruta:
                if elegidos.get(n) == k:
                    texto = _razon_regla(decididos[n], nombre)
                    for j in nodos[n]:
                        razones[acts[j].codigo_bia] = texto
                miembros = _orden_cercania(nodos[n], acts, punto, dist)
                orden += miembros
                punto = acts[miembros[-1]].coordinates
                if len(miembros) > 1:
                    codigos = [acts[j].codigo_bia for j in miembros]
                    for codigo in codigos:
                        juntas[codigo] = [c for c in codigos if c != codigo]
            rutas[vehiculos[k]] = [sub[j] for j in orden]
        descartadas_sub = [k for n in descartados for k in nodos[n]]
        return rutas, sin_cuadrilla + [sub[j] for j in descartadas_sub]

    todas = list(range(len(cuadrillas)))
    rutas_idx, descartadas = resolver(list(range(len(atendibles))), todas)
    # Una cuadrilla con OTs fijadas que no caben en su jornada se queda solo con esas;
    # las demás OTs se reparten entre las otras cuadrillas
    excedidas = {permitidos[i][0] for i in descartadas if i in fijadas}
    if excedidas:
        restantes = [i for i in range(len(atendibles)) if not (i in fijadas and permitidos[i][0] in excedidas)]
        rutas_idx, descartadas = resolver(restantes, [v for v in todas if v not in excedidas])
        for vehiculo in excedidas:
            propias = [i for i in fijadas if permitidos[i][0] == vehiculo]
            orden = _ordenar_por_cercania([atendibles[i] for i in propias], inicios[vehiculo], dist)
            rutas_idx[vehiculo] = [propias[[atendibles[i] for i in propias].index(a)] for a in orden]
    for i in descartadas:
        if i in fijadas:
            vehiculo = permitidos[i][0]
            _insertar_donde_menos_desvia(rutas_idx[vehiculo], i, atendibles, inicios[vehiculo], dist)

    rutas: List[RutaAsignada] = []
    for numero, cuadrilla in enumerate(cuadrillas, start=1):
        indices = rutas_idx[numero - 1]
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
            motivo="No cabe en la jornada de los técnicos disponibles",
        )
        for i in descartadas if i not in fijadas
    ]
    extra = {
        "tecnicos_seleccionados": len(tecnicos),
        "cuadrillas_armadas": len(cuadrillas),
        "parejas": sum(1 for c in cuadrillas if len(c) >= 2),
        "cuadrillas_manuales": bool(request.cuadrillas),
        "ots_agrupadas": len(juntas),
        "radio_grupo_km": request.jornada.radio_grupo_km,
        "juntas": dict(juntas),
        "razones": dict(razones),
    }
    return rutas, sin_asignar, extra


def _candidatas_contratista(
    actividad: Activity,
    sedes_contratistas: List[SedeOperativa],
    or_contratistas: Dict[str, List[str]],
    operadores: List[OperadorRed],
    empresa_fija: Optional[str] = None,
) -> Tuple[List[SedeOperativa], str, Optional[OperadorRed], Optional[str]]:
    """Sedes que pueden atender la OT, en este orden de preferencia:

    0. Las del contratista al que quedó fijada la OT.
    1. La lista manual de contratistas de su OR.
    2. Las sedes en los departamentos que atiende su OR (catálogo de OR).
    3. Si el OR no está en el catálogo, las sedes en el departamento de la OT.
    4. Todas, si ninguna de las anteriores tiene sedes.

    Devuelve (sedes, criterio, OR del catálogo, zona considerada).
    """
    operador = resolver_or(actividad.or_operador, operadores)
    if empresa_fija:
        candidatas = [s for s in sedes_contratistas if s.empresa_id == empresa_fija]
        if candidatas:
            return candidatas, "fijada", operador, None

    lista = or_contratistas.get(clave(actividad.or_operador)) or (
        or_contratistas.get(clave(operador.nombre)) if operador else None
    )
    if lista:
        candidatas = [s for s in sedes_contratistas if s.empresa_id in set(lista)]
        if candidatas:
            return candidatas, "lista_or", operador, None

    if operador and operador.departamentos:
        zona = ", ".join(operador.departamentos)
        departamentos = {normalizar_departamento(d) for d in operador.departamentos}
        candidatas = [s for s in sedes_contratistas if normalizar_departamento(s.departamento) in departamentos]
        if candidatas:
            return candidatas, "departamento_or", operador, zona
    elif actividad.departamento:
        zona = actividad.departamento
        departamento = normalizar_departamento(actividad.departamento)
        candidatas = [s for s in sedes_contratistas if normalizar_departamento(s.departamento) == departamento]
        if candidatas:
            return candidatas, "departamento_ot", operador, zona
    else:
        zona = None

    return sedes_contratistas, "sin_lista_or", operador, zona


def recomendar_contratista(
    actividad: Activity,
    sedes_contratistas: List[SedeOperativa],
    or_contratistas: Dict[str, List[str]],
    dist: Distancias,
    operadores: Optional[List[OperadorRed]] = None,
    empresa_fija: Optional[str] = None,
) -> RecomendacionContratista:
    """Elige la sede más cercana entre los contratistas que pueden atender el OR de la OT"""
    candidatas, criterio, operador, zona = _candidatas_contratista(
        actividad, sedes_contratistas, or_contratistas, operadores or [], empresa_fija
    )

    # Una opción por empresa: su sede más cercana a la OT
    mejor_por_empresa: Dict[str, OpcionContratista] = {}
    for sede in candidatas:
        km = round(dist.km(sede.coordinates, actividad.coordinates), 2)
        actual = mejor_por_empresa.get(sede.empresa_id)
        if actual is None or km < actual.distancia_km:
            mejor_por_empresa[sede.empresa_id] = OpcionContratista(
                sede_id=sede.id, empresa_id=sede.empresa_id, empresa=sede.empresa, ciudad=sede.ciudad,
                distancia_km=km,
            )
    opciones = sorted(mejor_por_empresa.values(), key=lambda o: o.distancia_km)

    return RecomendacionContratista(
        codigo_bia=actividad.codigo_bia,
        or_operador=actividad.or_operador,
        elegido=opciones[0] if opciones else None,
        criterio=criterio,
        or_canonico=operador.nombre if operador else None,
        zona=zona,
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


def _asignar_contratistas(
    actividades: List[Activity],
    fijas: Dict[str, str],
    request: AssignmentRequest,
    dist: Distancias,
) -> Tuple[List[RutaAsignada], List[RecomendacionContratista], Dict]:
    """Recomienda el contratista de cada OT y arma las rutas de cada sede elegida.

    `fijas` (OT → id de empresa) limita la OT a las sedes de ese contratista.
    """
    sedes_contratistas = [s for s in request.sedes if s.tipo == "contratista"]
    if not sedes_contratistas:
        raise ValueError("El catálogo no tiene sedes de contratistas")
    sedes = {s.id: s for s in sedes_contratistas}
    or_contratistas = {clave(k): v for k, v in request.or_contratistas.items()}

    recomendaciones = []
    por_sede: Dict[str, List[Activity]] = {}
    for actividad in actividades:
        recomendacion = recomendar_contratista(
            actividad, sedes_contratistas, or_contratistas, dist, request.operadores,
            fijas.get(actividad.codigo_bia),
        )
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
    return rutas, recomendaciones, extra


def _motivo_contratista(
    recomendacion: Optional[RecomendacionContratista],
    actividad: Activity,
    sede: SedeOperativa,
    km: float,
) -> str:
    nombre_or = (recomendacion.or_canonico if recomendacion else None) or actividad.or_operador
    criterio = recomendacion.criterio if recomendacion else "lista_or"
    if criterio == "fijada":
        return f"Fijada a {sede.empresa}; sale de su sede más cercana ({km:g} km)"
    if criterio == "lista_or":
        return f"Contratista definido para {nombre_or}, el más cercano ({km:g} km)"
    if criterio == "departamento_or":
        return (
            f"{nombre_or} opera en {recomendacion.zona}; contratista con sede en {sede.departamento}, "
            f"el más cercano ({km:g} km)"
        )
    if criterio == "departamento_ot":
        return (
            f"{actividad.or_operador} no está en el catálogo de OR; contratista con sede en "
            f"{recomendacion.zona}, el más cercano ({km:g} km)"
        )
    zona = f" ({recomendacion.zona})" if recomendacion and recomendacion.zona else ""
    return f"Ningún contratista tiene sede en la zona de {nombre_or}{zona}; el más cercano de todos ({km:g} km)"


def _decisiones(
    request: AssignmentRequest,
    rutas: List[RutaAsignada],
    recomendaciones: List[RecomendacionContratista],
    sin_asignar: List[ActividadSinAsignar],
    motivos_previos: Dict[str, str],
    fijadas: Set[str],
    sin_ubicacion: Optional[List[DecisionOT]] = None,
) -> List[DecisionOT]:
    """Una decisión por OT: a quién enviarla y por qué, en el orden en que llegaron"""
    dist = Distancias(request.jornada, request.matriz)
    por_codigo = {r.codigo_bia: r for r in recomendaciones}
    decisiones: Dict[str, DecisionOT] = {}

    for asignada in rutas:
        sede = asignada.sede
        for parada in asignada.ruta.paradas:
            actividad = parada.actividad
            km = round(dist.km(sede.coordinates, actividad.coordinates), 1)
            if asignada.tipo == "contratista":
                motivo = _motivo_contratista(por_codigo.get(actividad.codigo_bia), actividad, sede, km)
                if not asignada.ruta.viable:
                    motivo += ". La ruta supera la jornada: requiere viaje"
            else:
                if actividad.codigo_bia in fijadas:
                    motivo = f"Fijada a {asignada.responsable}; a {km:g} km de {sede.empresa}"
                else:
                    motivo = f"A {km:g} km de {sede.empresa}; cabe en la jornada de {asignada.responsable}"
                    if request.uso_previo and request.disponible_previo:
                        integrantes = asignada.responsable_id.split("+")
                        uso = sum(request.uso_previo.get(i, 0) for i in integrantes) / len(integrantes)
                        motivo += f", que lleva {round(uso / request.disponible_previo * 100)} % de UTR en la semana"
                if not asignada.ruta.viable:
                    motivo += ". Su ruta pasa de la jornada: revisa la carga de este técnico"
            decisiones[actividad.codigo_bia] = DecisionOT(
                codigo_bia=actividad.codigo_bia,
                enviar_a=asignada.tipo,
                responsable_id=asignada.responsable_id,
                responsable=asignada.responsable,
                sede=f"{sede.empresa} ({sede.ciudad})",
                distancia_base_km=km,
                hora_llegada=parada.hora_llegada_estimada,
                motivo=motivo,
            )

    for decision in sin_ubicacion or []:
        decisiones[decision.codigo_bia] = decision

    for item in sin_asignar:
        decisiones[item.actividad.codigo_bia] = DecisionOT(
            codigo_bia=item.actividad.codigo_bia, enviar_a="sin_asignar", motivo=item.motivo
        )

    for codigo, responsable in request.externas.items():
        decisiones[codigo] = DecisionOT(
            codigo_bia=codigo,
            enviar_a="externo",
            responsable=responsable,
            # Con nota (por ejemplo, cerrada por un técnico que hoy no está) la nota ya dice por qué
            motivo=("Se deja como está y no entra en las rutas" if codigo in request.notas
                    else "Su responsable no está en la app: se deja como está y no entra en las rutas"),
        )

    resultado = []
    for actividad in request.actividades:
        decision = decisiones.get(actividad.codigo_bia)
        if decision is None:
            continue
        previos = [t for t in (request.notas.get(actividad.codigo_bia), motivos_previos.get(actividad.codigo_bia)) if t]
        if previos:
            decision.motivo = ". ".join(previos + [decision.motivo])
        decision.situacion = actividad.situacion
        decision.fijada = actividad.codigo_bia in fijadas or actividad.codigo_bia in request.externas
        resultado.append(decision)
    return resultado


def _resultado(
    request: AssignmentRequest,
    rutas: List[RutaAsignada],
    recomendaciones: List[RecomendacionContratista],
    sin_asignar: List[ActividadSinAsignar],
    extra: Dict,
    motivos_previos: Dict[str, str],
    fijadas: Set[str],
    sin_ubicacion: Optional[List[DecisionOT]] = None,
) -> AssignmentResult:
    distancia = round(sum(r.ruta.distancia_total_km for r in rutas), 2)
    asignadas = sum(len(r.ruta.paradas) for r in rutas)
    costos = [r.costo for r in rutas if r.costo is not None]
    metricas = {
        "ots_asignadas": asignadas,
        "ots_con_tecnicos": sum(len(r.ruta.paradas) for r in rutas if r.tipo == "tecnico"),
        "ots_con_contratistas": sum(len(r.ruta.paradas) for r in rutas if r.tipo == "contratista"),
        "ots_externas": sum(1 for a in request.actividades if a.codigo_bia in request.externas),
        "ots_fijadas": len(fijadas),
        "ots_ya_asignadas": sum(1 for a in request.actividades if a.situacion == "asignada"),
        "ots_pendientes": sum(1 for a in request.actividades if a.situacion == "pendiente"),
        "costo_total": round(sum(costos), 2) if costos else None,
        "ots_sin_asignar": len(sin_asignar),
        "rutas": len(rutas),
        "rutas_no_viables": sum(1 for r in rutas if not r.ruta.viable),
        "factor_vial": request.jornada.factor_vial,
        **extra,
    }
    return AssignmentResult(
        modo=request.modo,
        total_actividades=len(request.actividades),
        rutas=rutas,
        decisiones=_decisiones(request, rutas, recomendaciones, sin_asignar, motivos_previos, fijadas, sin_ubicacion),
        recomendaciones=recomendaciones,
        sin_asignar=sin_asignar,
        distancia_total_km=distancia,
        viable_en_un_dia=all(r.ruta.viable for r in rutas) and not sin_asignar,
        metricas=metricas,
    )


def _equipos_que_cubren(actividad: Activity, request: AssignmentRequest) -> List[CoberturaEquipo]:
    """Equipos Bia que atienden el OR de la OT en la zona donde está"""
    return [
        c for c in request.coberturas
        if atiende_or(c, actividad.or_operador, request.operadores) and (
            not c.zonas or any(
                en_zona(z, actividad.ciudad, actividad.departamento, actividad.coordinates) for z in c.zonas
            )
        )
    ]


def _fuera_de_cobertura(actividad: Activity, equipos: List[CoberturaEquipo], request: AssignmentRequest) -> str:
    if equipos:
        return f"{equipos[0].equipo} no tiene técnicos disponibles"
    del_or = [c for c in request.coberturas if atiende_or(c, actividad.or_operador, request.operadores)]
    if del_or:
        zonas = ", ".join(z.nombre for z in del_or[0].zonas)
        return f"{actividad.ciudad or 'La OT'} está fuera de la zona del {del_or[0].equipo} ({zonas})"
    operador = resolver_or(actividad.or_operador, request.operadores)
    return f"Ningún equipo Bia atiende {operador.nombre if operador else actividad.or_operador}"


def _agregar_motivo(motivos: Dict[str, str], codigo: str, texto: str) -> None:
    motivos[codigo] = f"{motivos[codigo]}. {texto}" if codigo in motivos else texto


def asignar(request: AssignmentRequest) -> AssignmentResult:
    """Decide a quién enviar cada OT y arma las rutas.

    - `externas`: ya tienen un responsable que no está en la app; no se enrutan.
    - `fijas`: van al técnico (si está disponible) o al contratista indicado.
    - El resto según el modo: "automatico" deja a los técnicos las que están en el
      radio de una base y caben en su jornada, y manda las demás al contratista más
      cercano de su OR; "inhouse" solo usa técnicos y "contratistas" solo contratistas.
    """
    sedes = {s.id: s for s in request.sedes}
    tecnicos = [t for t in request.tecnicos if t.base_id in sedes]
    disponibles = {t.id for t in tecnicos}
    empresas = {s.empresa_id for s in request.sedes if s.tipo == "contratista"}
    dist = Distancias(request.jornada, request.matriz)

    actividades, sin_coordenadas = _separar_sin_coordenadas(
        [a for a in request.actividades if a.codigo_bia not in request.externas]
    )
    motivos_previos: Dict[str, str] = {}
    fijas_tecnico: Dict[str, str] = {}
    fijas_empresa: Dict[str, str] = {}
    fijadas: Set[str] = set()

    # Sin ubicación no hay ruta posible, pero la OT fijada a alguien sigue siendo de esa persona
    sin_asignar: List[ActividadSinAsignar] = []
    sin_ubicacion: List[DecisionOT] = []
    nombre_tecnico = {t.id: t.nombre for t in tecnicos}
    nombre_empresa = {s.empresa_id: s.empresa for s in request.sedes if s.tipo == "contratista"}
    for item in sin_coordenadas:
        codigo = item.actividad.codigo_bia
        tipo, _, destino = request.fijas.get(codigo, "").partition(":")
        if tipo == "tecnico" and destino in nombre_tecnico:
            enviar_a, responsable = "tecnico", nombre_tecnico[destino]
        elif tipo == "empresa" and destino in nombre_empresa:
            enviar_a, responsable = "contratista", nombre_empresa[destino]
        else:
            sin_asignar.append(item)
            continue
        fijadas.add(codigo)
        sin_ubicacion.append(DecisionOT(
            codigo_bia=codigo,
            enviar_a=enviar_a,
            responsable_id=destino,
            responsable=responsable,
            motivo=f"Fijada a {responsable}. No tiene ubicación: no entra en la ruta ni en el mapa",
        ))
    para_tecnicos: List[Activity] = []
    para_contratistas: List[Activity] = []
    libres: List[Activity] = []
    bases_permitidas: Dict[str, Set[str]] = {}
    for actividad in actividades:
        codigo = actividad.codigo_bia
        tipo, _, destino = request.fijas.get(codigo, "").partition(":")
        if tipo == "tecnico" and destino in disponibles:
            fijas_tecnico[codigo] = destino
            para_tecnicos.append(actividad)
        elif tipo == "empresa" and destino in empresas:
            fijas_empresa[codigo] = destino
            para_contratistas.append(actividad)
        elif tipo == "contratista":
            _agregar_motivo(motivos_previos, codigo, "Enviada a contratista a mano")
            para_contratistas.append(actividad)
        else:
            if tipo == "tecnico":
                _agregar_motivo(motivos_previos, codigo, "El técnico fijado no está disponible")
            elif tipo == "empresa":
                _agregar_motivo(motivos_previos, codigo, "El contratista fijado no está en el catálogo")
            libres.append(actividad)
            continue
        fijadas.add(codigo)

    extra: Dict = {"tecnicos_disponibles": len(tecnicos), "reparto_por_semana": bool(request.uso_previo)}
    if request.modo == "contratistas":
        para_contratistas += libres
    elif request.modo == "inhouse":
        if not tecnicos:
            raise ValueError("Selecciona al menos un técnico con una base válida")
        para_tecnicos += libres
        # Si un equipo con técnicos disponibles cubre la OT, va a ese equipo
        for actividad in libres:
            bases = {c.base_id for c in _equipos_que_cubren(actividad, request)} & {t.base_id for t in tecnicos}
            if bases:
                bases_permitidas[actividad.codigo_bia] = bases
    elif not tecnicos:
        for actividad in libres:
            _agregar_motivo(motivos_previos, actividad.codigo_bia, "No hay técnicos disponibles")
        para_contratistas += libres
    elif request.coberturas:
        # Cada OT va al equipo Bia que cubre su OR y su zona, si ese equipo tiene técnicos disponibles
        bases_con_tecnicos = {t.base_id for t in tecnicos}
        for actividad in libres:
            equipos = _equipos_que_cubren(actividad, request)
            con_tecnicos = {c.base_id for c in equipos if c.base_id in bases_con_tecnicos}
            if con_tecnicos:
                bases_permitidas[actividad.codigo_bia] = con_tecnicos
                equipo = next(c.equipo for c in equipos if c.base_id in con_tecnicos)
                _agregar_motivo(motivos_previos, actividad.codigo_bia, f"Le corresponde al {equipo}")
                para_tecnicos.append(actividad)
            else:
                _agregar_motivo(motivos_previos, actividad.codigo_bia, _fuera_de_cobertura(actividad, equipos, request))
                para_contratistas.append(actividad)
    else:
        radio = request.jornada.radio_inhouse_km
        extra["radio_inhouse_km"] = radio
        bases = [sedes[b] for b in dict.fromkeys(t.base_id for t in tecnicos)]
        for actividad in libres:
            base, km = min(((b, dist.km(b.coordinates, actividad.coordinates)) for b in bases), key=lambda x: x[1])
            if km <= radio:
                para_tecnicos.append(actividad)
            else:
                _agregar_motivo(
                    motivos_previos,
                    actividad.codigo_bia,
                    f"Está a {km:.0f} km de la base con técnicos disponibles más cercana ({base.ciudad}), "
                    f"fuera del radio de {radio:g} km",
                )
                para_contratistas.append(actividad)

    rutas: List[RutaAsignada] = []
    if para_tecnicos:
        rutas_tecnicos, sobrantes, extra_tecnicos = _asignar_inhouse(
            para_tecnicos, fijas_tecnico, tecnicos, request, dist, bases_permitidas
        )
        rutas += rutas_tecnicos
        radio = request.jornada.radio_grupo_km
        for codigo, texto in extra_tecnicos.pop("razones", {}).items():
            _agregar_motivo(motivos_previos, codigo, texto)
        for codigo, otras in extra_tecnicos.pop("juntas", {}).items():
            nombradas = ", ".join(otras[:MAX_NOMBRADAS]) + (f" y {len(otras) - MAX_NOMBRADAS} más" if len(otras) > MAX_NOMBRADAS else "")
            _agregar_motivo(motivos_previos, codigo, f"Va junto con {nombradas}: están a {radio:g} km o menos")
        extra.update(extra_tecnicos)
        if request.modo == "inhouse":
            sin_asignar += sobrantes
        else:
            # Lo que no cabe en la jornada de los técnicos pasa a contratistas
            for item in sobrantes:
                _agregar_motivo(motivos_previos, item.actividad.codigo_bia, item.motivo)
                para_contratistas.append(item.actividad)

    recomendaciones: List[RecomendacionContratista] = []
    if para_contratistas:
        rutas_contratistas, recomendaciones, extra_contratistas = _asignar_contratistas(
            para_contratistas, fijas_empresa, request, dist
        )
        rutas += rutas_contratistas
        extra.update(extra_contratistas)

    extra["ots_sin_ubicacion"] = len(sin_ubicacion)
    return _resultado(request, rutas, recomendaciones, sin_asignar, extra, motivos_previos, fijadas, sin_ubicacion)


def repartir_lote(request: AssignmentRequest, codigos: List[str], plan_actual: Optional[Dict[str, str]] = None) -> Dict:
    """Propuesta para un lote de OTs elegidas a mano, con las mismas reglas que el plan.

    Las que están a `radio_grupo_km` o menos entre sí (y las cubre el mismo equipo) forman un
    grupo. Cada grupo va, en este orden, al técnico que ya tiene OTs cerca ese día, a uno que
    todavía no tiene OTs, o al de menor UTR de la semana (`repartir_por_reglas`). Lo que cada
    técnico ya tiene ese día son sus OTs fijadas y las que le da el plan actual
    (`plan_actual`: OT → id de la cuadrilla, "t1+t2"), sin contar las del lote.
    """
    sedes = {s.id: s for s in request.sedes}
    tecnicos = [t for t in request.tecnicos if t.base_id in sedes]
    dist = Distancias(request.jornada, request.matriz)
    servicios = _tiempos_servicio(request.jornada)
    jornada_min = int(request.jornada.horas_laborales * 60)
    elegidas = set(codigos)
    indice = {t.id: v for v, t in enumerate(tecnicos)}

    for actividad in request.actividades:
        if actividad.coordinates is None and actividad.gps:
            try:
                actividad.parse_coordinates()
            except ValueError:
                pass
    por_codigo = {a.codigo_bia: a for a in request.actividades}
    lote = [a for a in request.actividades if a.codigo_bia in elegidas and a.coordinates is not None]
    sin_ubicacion = [a.codigo_bia for a in request.actividades if a.codigo_bia in elegidas and a.coordinates is None]

    # Lo que ya tiene cada técnico ese día, fuera del lote
    anclas: List[Tuple[Activity, int]] = []
    for codigo, valor in request.fijas.items():
        tipo, _, destino = valor.partition(":")
        actividad = por_codigo.get(codigo)
        if tipo == "tecnico" and destino in indice and codigo not in elegidas and actividad and actividad.coordinates:
            anclas.append((actividad, indice[destino]))
    for codigo, responsable in (plan_actual or {}).items():
        actividad = por_codigo.get(codigo)
        if codigo in elegidas or codigo in request.fijas or not actividad or actividad.coordinates is None:
            continue
        anclas += [(actividad, indice[i]) for i in responsable.split("+") if i in indice]

    bases_con_tecnicos = {t.base_id for t in tecnicos}
    actividades = [a for a, _ in anclas] + lote
    primero = len(anclas)
    cubre: Dict[int, List[int]] = {}
    for k, actividad in enumerate(lote, start=primero):
        bases = (
            {c.base_id for c in _equipos_que_cubren(actividad, request)} & bases_con_tecnicos
            if request.coberturas else bases_con_tecnicos
        )
        cubre[k] = [v for v, t in enumerate(tecnicos) if t.base_id in bases]
    grupos = grupos_cercanos(
        list(range(primero, len(actividades))), actividades, {k: tuple(v) for k, v in cubre.items()},
        request.jornada.radio_grupo_km, int(jornada_min * FRACCION_GRUPO), servicios, dist,
    )
    nodos = [[k] for k in range(primero)] + grupos
    permitidos: List[Optional[List[int]]] = [[v] for _, v in anclas] + [cubre[g[0]] for g in grupos]
    decididos = repartir_por_reglas(
        nodos, actividades, permitidos, set(range(primero)),
        [sedes[t.base_id].coordinates for t in tecnicos],
        [request.uso_previo.get(t.id, 0) for t in tecnicos], request.jornada, dist,
    )

    disponible = request.disponible_previo + jornada_min
    utr = lambda minutos: round(minutos / disponible, 4) if disponible else None
    km_o_nada = lambda km: None if km == math.inf else round(km, 1)
    propuesta: List[Dict] = []
    sin_tecnico: List[Dict] = []
    for n in range(primero, len(nodos)):
        grupo = nodos[n]
        codigos_grupo = [actividades[k].codigo_bia for k in grupo]
        decidido = decididos.get(n)
        if decidido is None:
            centro = actividades[grupo[0]]
            motivo = _fuera_de_cobertura(centro, _equipos_que_cubren(centro, request), request) \
                if tecnicos else "No hay técnicos disponibles"
            sin_tecnico += [{"codigo": c, "motivo": motivo} for c in codigos_grupo]
            continue
        elegido = tecnicos[decidido["vehiculo"]]
        propuesta.append({
            "codigos": codigos_grupo,
            "tecnico_id": elegido.id,
            "tecnico": elegido.nombre,
            "minutos": round(decidido["despues"] - decidido["antes"]),
            "km_max": round(max((dist.km(actividades[grupo[0]].coordinates, actividades[k].coordinates)
                                 for k in grupo[1:]), default=0), 1),
            "personas": max(actividades[k].personas_requeridas for k in grupo),
            "cabe": decidido["regla"] != REGLA_NO_CABE,
            "regla": decidido["regla"],
            "km_cerca": km_o_nada(decidido["km"]),
            "utr_antes": utr(decidido["antes"]),
            "utr_despues": utr(decidido["despues"]),
            "opciones": [
                {"tecnico_id": tecnicos[o["vehiculo"]].id, "tecnico": tecnicos[o["vehiculo"]].nombre,
                 "utr": utr(o["carga"]), "cabe": o["cabe"], "regla": o["regla"], "km_cerca": km_o_nada(o["km"])}
                for o in decidido["opciones"]
            ],
        })

    return {
        "radio_km": request.jornada.radio_grupo_km,
        "grupos": propuesta,
        "sin_tecnico": sin_tecnico,
        "sin_ubicacion": sin_ubicacion,
    }

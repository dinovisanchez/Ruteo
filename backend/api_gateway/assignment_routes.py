"""Rutas de asignación por OR: OTs desde Metabase, catálogo, configuración y asignación"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collections import Counter
from functools import lru_cache
from pathlib import Path
import csv
import re
from typing import Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from shared.catalogo import cargar_catalogo, nombre_empresa, normalizar_texto
from shared.operadores import cargar_operadores, clave, normalizar_departamento, resolver_or
from shared.zonas import cargar_zonas
from shared.config import settings
from shared.models import (
    Activity,
    AsignacionConfig,
    AssignmentRequest,
    AssignmentResult,
    JornadaConfig,
    MatrizVial,
    ModoAsignacion,
    OperadorRed,
    CoberturaEquipo,
    SedeOperativa,
    Tecnico,
    ZonaTransito,
)
from shared.utils import hoy as hoy_en_colombia, setup_logging
from . import metabase
from .archivo import ArchivoError, leer_filas
from .geocoding import geocodificar
from . import trazado

logger = setup_logging("api-gateway", settings.LOG_LEVEL)

router = APIRouter()

CONFIG_PATH = Path(settings.ASIGNACION_CONFIG_PATH) if settings.ASIGNACION_CONFIG_PATH else (
    Path(__file__).resolve().parent.parent / "data" / "asignacion.json"
)

TECNICOS_HOJA_PATH = Path(__file__).resolve().parent.parent / "data" / "tecnicos.csv"
# Nombre de la base en la pestaña "Tecnicos" de la hoja → base Bia del catálogo
BASES_POR_NOMBRE = {"costa": "bia-barranquilla", "caribe": "bia-barranquilla", "barranquilla": "bia-barranquilla",
                    "bogota": "bia-bogota"}

_catalogo: Optional[Dict] = None
_operadores: Optional[List[OperadorRed]] = None
_zonas: Optional[Tuple[List[CoberturaEquipo], List[ZonaTransito]]] = None


def obtener_catalogo(recargar: bool = False) -> Dict:
    global _catalogo
    if _catalogo is None or recargar:
        sedes, avisos = cargar_catalogo(settings.CONTRATISTAS_CSV_PATH or None, settings.CONTRATISTAS_CSV_URL or None)
        _catalogo = {"sedes": sedes, "avisos": avisos}
        logger.info(f"Catálogo cargado: {len(sedes)} sedes, {len(avisos)} avisos")
    return _catalogo


def obtener_operadores() -> List[OperadorRed]:
    global _operadores
    if _operadores is None:
        _operadores = cargar_operadores()
        logger.info(f"Catálogo de OR cargado: {len(_operadores)} operadores")
    return _operadores


def obtener_zonas() -> Tuple[List[CoberturaEquipo], List[ZonaTransito]]:
    """Cobertura de los equipos Bia y zonas de tránsito (data/zonas_bia.json)"""
    global _zonas
    if _zonas is None:
        _zonas = cargar_zonas()
        logger.info(f"Zonas cargadas: {len(_zonas[0])} equipos Bia, {len(_zonas[1])} zonas de tránsito")
    return _zonas


def tecnicos_de_la_hoja() -> List[Tecnico]:
    """Técnicos de la pestaña "Tecnicos" de la hoja (data/tecnicos.csv), con su base Bia"""
    if not TECNICOS_HOJA_PATH.exists():
        return []
    tecnicos = []
    with TECNICOS_HOJA_PATH.open(encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            nombre = (fila.get("Nombre") or "").strip()
            base_id = BASES_POR_NOMBRE.get(clave(fila.get("Base") or ""))
            if nombre and base_id:
                tecnicos.append(Tecnico(id=f"hoja-{clave(nombre).replace(' ', '-')}", nombre=nombre, base_id=base_id))
    return tecnicos


def leer_config() -> AsignacionConfig:
    """Configuración guardada; los técnicos de la hoja que aún no están se agregan solos (una vez)"""
    hoja = tecnicos_de_la_hoja()
    if not CONFIG_PATH.exists():
        return AsignacionConfig(tecnicos=hoja, hoja_importados=[t.id for t in hoja])
    config = AsignacionConfig.model_validate_json(CONFIG_PATH.read_text(encoding="utf-8"))
    registrados = {clave(t.nombre) for t in config.tecnicos} | {t.id for t in config.tecnicos}
    nuevos = [t for t in hoja if t.id not in config.hoja_importados and not {clave(t.nombre), t.id} & registrados]
    vistos = sorted(set(config.hoja_importados) | {t.id for t in hoja})
    if nuevos or vistos != sorted(config.hoja_importados):
        config.tecnicos += nuevos
        config.hoja_importados = vistos
        guardar_config(config)
        if nuevos:
            logger.info(f"Técnicos agregados desde la hoja: {', '.join(t.nombre for t in nuevos)}")
    return config


def guardar_config(config: AsignacionConfig) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporal = CONFIG_PATH.with_suffix(".tmp")
    temporal.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    temporal.replace(CONFIG_PATH)


def conteo_por_or(actividades: List[Activity]) -> Dict[str, int]:
    return dict(Counter(a.or_operador for a in actividades).most_common())


class OTsResponse(BaseModel):
    card_id: Optional[str] = None  # Vacío cuando las OTs vienen de un archivo
    total_filas: int
    actividades: List[Activity]
    columnas: List[str]
    mapeo: Dict[str, str]
    ors: Dict[str, int]
    geocodificadas: int
    sin_coordenadas: int
    avisos: List[str]


class AsignarRequest(BaseModel):
    modo: ModoAsignacion = "automatico"
    actividades: List[Activity]
    or_filtro: List[str] = Field(default_factory=list)  # Vacío = todos los OR
    tecnicos_ids: List[str] = Field(default_factory=list)
    # Parejas armadas a mano (ids de técnicos); vacío = la app sugiere las cuadrillas
    cuadrillas: List[List[str]] = Field(default_factory=list)
    # Tipo de OT → personas que necesita; los tipos que no aparecen necesitan 1
    personas_por_tipo: Dict[str, int] = Field(default_factory=dict)
    # Día del plan (YYYY-MM-DD; vacío = hoy): entran las OTs ya asignadas para ese día y las pendientes
    dia: Optional[str] = None
    # Ediciones a mano: OT → "tecnico:<id>", "empresa:<id>", "contratista" o "auto" (que decida la app)
    fijas: Dict[str, str] = Field(default_factory=dict)
    # Zonas de tránsito con el recargo editado en la app; vacío = las de data/zonas_bia.json
    transito: List[ZonaTransito] = Field(default_factory=list)
    # Tiempos por las vías que trae el navegador cuando el backend no llega a OSRM
    matriz: Optional[MatrizVial] = None
    # Carga de cada técnico en la semana antes de este día, para repartir de forma pareja
    uso_previo: Dict[str, float] = Field(default_factory=dict)
    disponible_previo: float = 0
    jornada: JornadaConfig = Field(default_factory=JornadaConfig)


class TrazadoRuta(BaseModel):
    id: str
    puntos: List[List[float]]  # [[lat, lon], ...] en orden de visita, empezando por la base


class TrazadoRequest(BaseModel):
    rutas: List[TrazadoRuta]


def _como_suena(palabra: str) -> str:
    """Quita diferencias de ortografía que no cambian el sonido: Jhonatan = Jonathan, Gelvez ~ Gelver"""
    palabra = re.sub(r"c([ei])", r"s\1", palabra).replace("h", "").replace("v", "b").replace("z", "s").replace("y", "i")
    return re.sub(r"(.)\1+", r"\1", palabra)


def _parecidas(a: str, b: str) -> bool:
    """Misma palabra al oído, o una letra distinta en palabras de 5 o más letras ("gelver" / "gelvez")"""
    a, b = _como_suena(a), _como_suena(b)
    if a == b:
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    anterior = list(range(len(b) + 1))
    for i, letra_a in enumerate(a, start=1):
        actual = [i]
        for j, letra_b in enumerate(b, start=1):
            actual.append(min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + (letra_a != letra_b)))
        anterior = actual
    return anterior[-1] <= 1


# Separa las personas en "Electricistas asignados" ("Carlos Salas, Juan Reyes", '["A", "B"]', "A y B")
SEPARADOR_PERSONAS = re.compile(r"[,;|/\n\[\]\"]+| y ", flags=re.IGNORECASE)


def tecnicos_mencionados(texto: Optional[str], tecnicos: List[Tecnico]) -> List[Tecnico]:
    """Técnicos de la app que aparecen en "Electricistas asignados" de Metabase.

    Cada persona del texto ("CARLOS ANDRÉS SALAS, Juan Reyes") coincide con el técnico cuyas
    palabras del nombre están todas en ella, sin importar mayúsculas ni tildes. El nombre de pila
    tiene que sonar igual (Daniel no es Daniela, Mario no es María); en los apellidos se acepta una
    letra distinta ("Gelver" / "Gelvez").
    """
    return [tecnicos[i] for i in _mencionados(texto or "", tuple(t.nombre for t in tecnicos))]


@lru_cache(maxsize=8192)
def _mencionados(texto: str, nombres: Tuple[str, ...]) -> Tuple[int, ...]:
    """Índices de `nombres` que aparecen en `texto`; los nombres se repiten mucho, así que se guardan"""
    encontrados: List[int] = []
    for persona in SEPARADOR_PERSONAS.split(texto):
        palabras = clave(persona).split()
        if not palabras:
            continue
        for indice, nombre_tecnico in enumerate(nombres):
            nombre = clave(nombre_tecnico).split()
            if (
                nombre and indice not in encontrados
                and any(_como_suena(nombre[0]) == _como_suena(p) for p in palabras)
                and all(any(_parecidas(n, p) for p in palabras) for n in nombre[1:])
            ):
                encontrados.append(indice)
    return tuple(encontrados)


def _personas_de_bia(actividad: Activity) -> bool:
    """Las personas de la OT pueden ser técnicos de Bia: su contratista es Bia o no viene.

    Si la OT es de un contratista, sus electricistas son del contratista aunque se llamen parecido
    a alguien de Bia.
    """
    return not (actividad.contratista_asignado or "").strip() or es_de_bia(actividad.contratista_asignado)


def aprender_ids(actividades: List[Activity], config: AsignacionConfig) -> Dict[str, str]:
    """Id del electricista en Olibia → técnico, aprendido de las OTs de Bia con un solo electricista reconocido.

    Se guarda en la configuración para usarlo en las OTs que listan a varias personas. Si una OT
    nueva contradice lo guardado, manda la OT; los ids que aparecen en OTs de contratistas no son
    de técnicos de Bia y se borran.
    """
    ids = dict(config.ids_electricistas)
    for actividad in actividades:
        if not actividad.electricista_id:
            continue
        if not _personas_de_bia(actividad):
            ids.pop(actividad.electricista_id, None)
            continue
        personas = [p for p in SEPARADOR_PERSONAS.split(actividad.asignado_a or "") if clave(p)]
        mencionados = tecnicos_mencionados(actividad.asignado_a, config.tecnicos)
        if len(personas) == 1 and len(mencionados) == 1:
            ids[actividad.electricista_id] = mencionados[0].id
    if ids != config.ids_electricistas:
        config.ids_electricistas = ids
        guardar_config(config)
    return ids


def responsables(actividad: Activity, tecnicos: List[Tecnico], ids: Dict[str, str]) -> List[Tecnico]:
    """Técnicos de Bia que hacen la OT: el de "Id electricista" primero y solo tantos como pide su tipo.

    "Electricistas asignados" puede traer a más personas de las que fueron (por ejemplo, tras una
    reasignación); así una OT de 1 persona no se le cuenta a dos técnicos. Las OTs de contratistas
    no son de ningún técnico de Bia.
    """
    if not _personas_de_bia(actividad):
        return []
    mencionados = tecnicos_mencionados(actividad.asignado_a, tecnicos)
    principal = next((t for t in tecnicos if t.id == ids.get(actividad.electricista_id or "")), None)
    # El id solo ordena a los que ya nombra la OT, o ubica a quien no se reconoce por el nombre
    if principal and (not mencionados or principal in mencionados):
        mencionados = [principal] + [t for t in mencionados if t.id != principal.id]
    return mencionados[:max(1, actividad.personas_requeridas)]


def es_de_bia(contratista: Optional[str]) -> bool:
    """El "Contratista asignado" de Metabase es Bia (técnicos propios)"""
    return "bia" in clave(contratista or "").split()


def empresa_mencionada(texto: Optional[str], sedes: List[SedeOperativa]) -> Optional[str]:
    """Id de la empresa contratista que corresponde al "Contratista asignado" de Metabase"""
    palabras = set(clave(nombre_empresa(texto or "")).split())
    if not palabras:
        return None
    empresas = {s.empresa_id: set(clave(s.empresa).split()) for s in sedes if s.tipo == "contratista"}
    # El texto trae el nombre completo de la empresa (gana el más largo) o una parte que solo una tiene
    contenidas = sorted(((len(p), e) for e, p in empresas.items() if p and p <= palabras), reverse=True)
    if contenidas:
        return contenidas[0][1]
    contienen = [e for e, p in empresas.items() if palabras <= p]
    return contienen[0] if len(contienen) == 1 else None


def plan_del_dia(
    actividades: List[Activity],
    dia: str,
    ediciones: Dict[str, str],
    tecnicos: List[Tecnico],
    disponibles: List[Tecnico],
    sedes: List[SedeOperativa],
    ids_electricistas: Optional[Dict[str, str]] = None,
) -> Tuple[List[Activity], Dict[str, str], Dict[str, str], Dict[str, str], List[List[str]], Dict]:
    """OTs del día y a quién quedan fijadas.

    Entran las OTs con fecha de visita `dia`, asignadas o pendientes, igual que en Olibia. Solo
    el plan de hoy suma además las pendientes vencidas (su fecha ya pasó) y las pendientes sin
    fecha, para que no queden sin planear. Una asignada queda
    fijada a su técnico si está disponible (si no, la app la reasigna), a su contratista
    si está en el catálogo, o como externa si su responsable no está en la app. Las
    ediciones a mano mandan sobre lo que dice Metabase.

    Devuelve (actividades, fijas, externas, notas, parejas de Metabase, métricas).
    """
    ids_disponibles = {t.id for t in disponibles}
    del_dia: List[Activity] = []
    fijas: Dict[str, str] = {}
    externas: Dict[str, str] = {}
    notas: Dict[str, str] = {}
    parejas: List[List[str]] = []
    sin_registrar: Dict[str, int] = {}
    otros_dias = sin_fecha = pendientes_otros_dias = 0
    hoy = hoy_en_colombia().isoformat()

    for actividad in actividades:
        codigo = actividad.codigo_bia
        fecha = actividad.fecha_visita
        if actividad.situacion == "asignada" and fecha != dia:
            if fecha:
                otros_dias += 1
            else:
                sin_fecha += 1
            continue
        if actividad.situacion == "pendiente" and fecha != dia:
            # Otro día solo muestra lo que tiene esa fecha; hoy suma las vencidas y las sin fecha
            if dia != hoy or (fecha and fecha > hoy):
                pendientes_otros_dias += 1
                continue
            notas[codigo] = f"Pendiente desde el {fecha}" if fecha else "Pendiente sin fecha de visita"
        del_dia.append(actividad)

        # Una visita cerrada ya se hizo: no se edita ni se vuelve a mandar
        edicion = None if actividad.cerrada else ediciones.get(codigo)
        if edicion and edicion != "auto":
            fijas[codigo] = edicion
            if edicion != "contratista":
                notas[codigo] = "Editada a mano"
            continue
        if actividad.situacion != "asignada":
            continue
        responsable = actividad.asignado_a or actividad.contratista_asignado
        if edicion == "auto":
            notas[codigo] = f"Estaba asignada a {responsable or 'otro responsable'}; la app la reasigna"
            continue

        mencionados = responsables(actividad, tecnicos, ids_electricistas or {})
        if mencionados:
            en_turno = [t for t in mencionados if t.id in ids_disponibles]
            if en_turno:
                fijas[codigo] = f"tecnico:{en_turno[0].id}"
                notas[codigo] = f"Asignada en Metabase a {actividad.asignado_a}"
                if len(en_turno) >= 2:
                    parejas.append([t.id for t in en_turno[:2]])
            else:
                nombres = ", ".join(t.nombre for t in mencionados)
                if actividad.cerrada:
                    externas[codigo] = f"{nombres} (cerrada)"
                    notas[codigo] = f"Cerrada por {nombres}, que no está disponible hoy: no se reasigna"
                else:
                    notas[codigo] = f"Estaba asignada a {nombres}, que no está disponible; la app la reasigna"
            continue
        empresa = empresa_mencionada(actividad.contratista_asignado, sedes)
        if empresa:
            fijas[codigo] = f"empresa:{empresa}"
            notas[codigo] = f"Asignada en Metabase a {actividad.contratista_asignado}"
            continue
        if actividad.asignado_a and es_de_bia(actividad.contratista_asignado):
            # Técnico de Bia que no está en la lista de la app: no es externo, falta registrarlo
            responsable = f"{actividad.asignado_a} (Bia, sin registrar en la app)"
            sin_registrar[actividad.asignado_a] = sin_registrar.get(actividad.asignado_a, 0) + 1
        elif actividad.asignado_a and actividad.contratista_asignado:
            responsable = f"{actividad.asignado_a} ({actividad.contratista_asignado})"
        externas[codigo] = responsable or "Responsable sin registrar en Metabase"

    metricas = {
        "dia": dia,
        "ots_otros_dias": otros_dias,
        "asignadas_sin_fecha": sin_fecha,
        "pendientes_otros_dias": pendientes_otros_dias,
        "bia_sin_registrar": sorted(sin_registrar),
    }
    return del_dia, fijas, externas, notas, parejas, metricas


def pregunta_predeterminada() -> Optional[str]:
    """La pregunta guardada en la app manda sobre METABASE_CARD_ID del .env"""
    return leer_config().card_id or settings.METABASE_CARD_ID or None


@router.get("/metabase/estado", response_model=dict)
async def metabase_estado():
    """Estado de la conexión con Metabase (sin credenciales)"""
    return {**metabase.estado(), "card_id": pregunta_predeterminada()}


@router.get("/metabase/ots", response_model=OTsResponse)
async def metabase_ots(card_id: Optional[str] = None):
    """
    Trae las OTs de una pregunta de Metabase y las convierte al formato del optimizador.
    Las OTs sin GPS se geocodifican a partir de su dirección.
    """
    card = card_id or pregunta_predeterminada()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Indica el número de la pregunta de Metabase y guárdalo como predeterminado",
        )
    try:
        filas = await metabase.consultar_pregunta(card)
        actividades, mapeo, avisos = metabase.filas_a_actividades(filas)
    except metabase.MetabaseError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    geocodificadas, avisos_geo = await geocodificar(actividades)
    logger.info(f"Metabase pregunta {card}: {len(filas)} filas, {len(actividades)} OTs, {geocodificadas} geocodificadas")
    return OTsResponse(
        card_id=str(card),
        total_filas=len(filas),
        actividades=actividades,
        columnas=list(filas[0].keys()) if filas else [],
        mapeo=mapeo,
        ors=conteo_por_or(actividades),
        geocodificadas=geocodificadas,
        sin_coordenadas=sum(1 for a in actividades if a.coordinates is None),
        avisos=avisos + avisos_geo,
    )


@router.post("/upload", response_model=OTsResponse)
async def subir_archivo(file: UploadFile = File(...)):
    """
    OTs desde un Excel (.xlsx) o CSV: se leen con las mismas columnas que la pregunta de Metabase
    (Bia Code, OR, Dirección, Ciudad, Situación, Fecha de la visita...) y las que no traen GPS se
    geocodifican. El archivo no se guarda.
    """
    contenido = await file.read(settings.MAX_UPLOAD_SIZE + 1)
    if len(contenido) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo pasa de {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MB",
        )
    try:
        filas = leer_filas(file.filename or "", contenido)
        actividades, mapeo, avisos = metabase.filas_a_actividades(filas)
    except (ArchivoError, metabase.MetabaseError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not actividades:
        raise HTTPException(status_code=422, detail="El archivo no tiene OTs con código")
    geocodificadas, avisos_geo = await geocodificar(actividades)
    logger.info(f"Archivo {file.filename}: {len(filas)} filas, {len(actividades)} OTs, {geocodificadas} geocodificadas")
    return OTsResponse(
        total_filas=len(filas),
        actividades=actividades,
        columnas=list(filas[0].keys()),
        mapeo=mapeo,
        ors=conteo_por_or(actividades),
        geocodificadas=geocodificadas,
        sin_coordenadas=sum(1 for a in actividades if a.coordinates is None),
        avisos=avisos + avisos_geo,
    )


@router.get("/catalogo", response_model=dict)
async def catalogo(recargar: bool = False):
    """Bases de Bia y sedes de contratistas con su ubicación"""
    try:
        datos = obtener_catalogo(recargar)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error leyendo el catálogo: {e}")
    sedes: List[SedeOperativa] = datos["sedes"]
    empresas = {}
    for sede in sedes:
        if sede.tipo == "contratista":
            empresas.setdefault(sede.empresa_id, {"id": sede.empresa_id, "nombre": sede.empresa, "sedes": []})
            empresas[sede.empresa_id]["sedes"].append(sede.ciudad)
    return {
        "sedes": [s.model_dump(mode="json") for s in sedes],
        "empresas": sorted(empresas.values(), key=lambda e: e["nombre"]),
        "avisos": datos["avisos"],
    }


@router.get("/operadores", response_model=dict)
async def operadores(nombres: List[str] = Query(default=[])):
    """
    Catálogo de Operadores de Red con los departamentos que atienden y los contratistas
    con sede en esos departamentos. Con `nombres`, dice a qué OR del catálogo corresponde
    cada nombre que aparece en las OTs.
    """
    sedes = [s for s in obtener_catalogo()["sedes"] if s.tipo == "contratista"]
    catalogo_or = obtener_operadores()

    def empresas_en(departamentos: List[str]) -> List[str]:
        claves = {normalizar_departamento(d) for d in departamentos}
        return list(dict.fromkeys(s.empresa_id for s in sedes if normalizar_departamento(s.departamento) in claves))

    resueltos = {}
    for nombre in nombres:
        operador = resolver_or(nombre, catalogo_or)
        resueltos[nombre] = operador.nombre if operador else None

    return {
        "operadores": [
            {**op.model_dump(), "empresas_auto": empresas_en(op.departamentos)}
            for op in catalogo_or
        ],
        "resueltos": resueltos,
    }


@router.get("/zonas", response_model=dict)
async def zonas():
    """Qué OTs atiende cada equipo Bia (por OR y zona) y el recargo de tránsito de cada zona"""
    coberturas, transito = obtener_zonas()
    return {
        "equipos": [c.model_dump() for c in coberturas],
        "transito": [z.model_dump() for z in transito],
    }


@router.get("/tecnicos/hoja", response_model=List[Tecnico])
async def tecnicos_hoja():
    """Técnicos de la pestaña "Tecnicos" de la hoja, listos para agregar"""
    return tecnicos_de_la_hoja()


@router.get("/asignacion/config", response_model=AsignacionConfig)
async def obtener_config():
    """Técnicos in-house y contratistas por OR"""
    return leer_config()


@router.put("/asignacion/config", response_model=AsignacionConfig)
async def actualizar_config(config: AsignacionConfig):
    """Guarda técnicos in-house y contratistas por OR"""
    sedes = {s.id for s in obtener_catalogo()["sedes"]}
    empresas = {s.empresa_id for s in obtener_catalogo()["sedes"] if s.tipo == "contratista"}
    if config.card_id is not None:
        config.card_id = config.card_id.strip() or None
        if config.card_id and not config.card_id.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La pregunta de Metabase debe ser el número que aparece en /question/123-...",
            )
    ids = [t.id for t in config.tecnicos]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hay técnicos con el mismo id")
    for tecnico in config.tecnicos:
        if tecnico.base_id not in sedes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La base '{tecnico.base_id}' del técnico {tecnico.nombre} no existe en el catálogo",
            )
    for nombre_or, lista in config.or_contratistas.items():
        desconocidas = [e for e in lista if e not in empresas]
        if desconocidas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Contratistas desconocidos para {nombre_or}: {', '.join(desconocidas)}",
            )
    # Se descartan los OR sin contratistas para que usen la regla "el más cercano de todos"
    config.or_contratistas = {k.strip(): v for k, v in config.or_contratistas.items() if k.strip() and v}
    guardar_config(config)
    return config


class LoteRequest(AsignarRequest):
    # OTs elegidas para asignar juntas
    codigos: List[str]
    # OT → cuadrilla ("t1+t2") en el plan que se está viendo: lo que cada técnico ya tiene ese día
    plan_actual: Dict[str, str] = Field(default_factory=dict)


async def _pedido_del_dia(
    request: AsignarRequest,
) -> Tuple[AssignmentRequest, Dict, JornadaConfig, List[List[float]], Optional[MatrizVial], Optional[str]]:
    """Arma el pedido al optimizador para el día: OTs del día, fijadas, cuadrillas, coberturas y tiempos.

    Devuelve (pedido, métricas del día, jornada, puntos, matriz por vías, aviso si no hay vías).
    """
    filtro = {normalizar_texto(o) for o in request.or_filtro}
    actividades = [a for a in request.actividades if not filtro or normalizar_texto(a.or_operador) in filtro]
    if not actividades:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay OTs para los OR seleccionados")

    config = leer_config()
    sedes = obtener_catalogo()["sedes"]
    por_id = {t.id: t for t in config.tecnicos}
    # Los técnicos disponibles también reciben las OTs fijadas a ellos en modo "solo contratistas"
    tecnicos = [por_id[i] for i in request.tecnicos_ids if i in por_id]
    if not tecnicos and request.modo == "inhouse":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selecciona al menos un técnico")

    # Las personas por tipo van antes del plan: deciden cuántos de los electricistas listados cuentan
    personas = {normalizar_texto(k): v for k, v in request.personas_por_tipo.items()}
    for actividad in actividades:
        actividad.personas_requeridas = max(1, personas.get(normalizar_texto(actividad.servicio), 1))

    dia = request.dia or hoy_en_colombia().isoformat()
    actividades, fijas, externas, notas, parejas, metricas_dia = plan_del_dia(
        actividades, dia, request.fijas, config.tecnicos, tecnicos, sedes, aprender_ids(actividades, config)
    )
    if not actividades:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No hay OTs pendientes ni asignadas para el {dia}",
        )

    # Parejas a mano primero; luego las que ya salen juntas en Metabase, si no chocan
    seleccionados = {t.id for t in tecnicos}
    cuadrillas = [[i for i in grupo if i in seleccionados] for grupo in request.cuadrillas]
    cuadrillas = [grupo for grupo in cuadrillas if grupo]
    for pareja in parejas:
        en_cuadrilla = {i for grupo in cuadrillas for i in grupo}
        if not en_cuadrilla & set(pareja):
            cuadrillas.append(pareja)

    coberturas, transito = obtener_zonas()
    jornada = request.jornada.model_copy(update={"zonas_transito": request.transito or transito})

    # Tiempos por las vías entre las OTs del día y todas las sedes (bases y contratistas)
    puntos = [[s.coordinates.latitude, s.coordinates.longitude] for s in sedes]
    for actividad in actividades:
        if actividad.coordinates is None and actividad.gps:
            try:
                actividad.parse_coordinates()
            except ValueError:
                pass
        if actividad.coordinates is not None:
            puntos.append([actividad.coordinates.latitude, actividad.coordinates.longitude])
    if request.matriz is not None:
        matriz, aviso_vias = request.matriz, None
    else:
        matriz, aviso_vias = await trazado.matriz_vial(puntos)

    pedido = AssignmentRequest(
        modo=request.modo,
        actividades=actividades,
        sedes=sedes,
        tecnicos=tecnicos,
        cuadrillas=cuadrillas,
        or_contratistas=config.or_contratistas,
        operadores=obtener_operadores(),
        fijas=fijas,
        externas=externas,
        notas=notas,
        coberturas=coberturas,
        matriz=matriz,
        uso_previo=request.uso_previo,
        disponible_previo=request.disponible_previo,
        jornada=jornada,
    )
    return pedido, metricas_dia, jornada, puntos, matriz, aviso_vias


async def _al_optimizador(ruta: str, cuerpo: Dict) -> Dict:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            respuesta = await client.post(f"{settings.OPTIMIZER_SERVICE_URL}{ruta}", json=cuerpo)
    except httpx.RequestError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Optimizer service unavailable: {e}")
    try:
        datos = respuesta.json()
    except ValueError:
        datos = None
    if respuesta.status_code != 200:
        detalle = datos.get("detail") if isinstance(datos, dict) else None
        raise HTTPException(
            status_code=respuesta.status_code if 400 <= respuesta.status_code < 600 else status.HTTP_502_BAD_GATEWAY,
            detail=detalle or respuesta.text[:300] or f"El optimizador respondió HTTP {respuesta.status_code}",
        )
    if not isinstance(datos, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="El optimizador respondió algo que no es JSON")
    return datos


@router.post("/asignar", response_model=AssignmentResult)
async def asignar(request: AsignarRequest):
    """
    Plan del día: toma las OTs pendientes y las ya asignadas para ese día (filtradas por OR)
    y decide a quién enviar cada una:
    - las asignadas se quedan con su técnico o contratista (si el técnico no está
      disponible, se reasignan); las ediciones a mano mandan sobre Metabase
    - las pendientes van a los técnicos disponibles o al contratista más cercano de su OR
    """
    pedido, metricas_dia, jornada, puntos, matriz, aviso_vias = await _pedido_del_dia(request)
    resultado = AssignmentResult(**await _al_optimizador("/assign", pedido.model_dump(mode="json")))
    resultado.metricas.update(metricas_dia)
    resultado.metricas["tiempos_por_vias"] = matriz is not None
    resultado.metricas["aviso_vias"] = aviso_vias
    resultado.metricas["transito"] = [
        {"nombre": z.nombre, "recargo_pct": z.recargo_pct, "minutos_extra": z.minutos_extra} for z in jornada.zonas_transito
    ]
    # El mapa pide estas mismas rutas; se trazan ya para que estén listas al abrirlo
    trazado.precargar([puntos_ruta(r, jornada.incluir_retorno) for r in resultado.rutas])
    return resultado


@router.post("/asignar/lote", response_model=dict)
async def asignar_lote(request: LoteRequest):
    """
    Propuesta para asignar varias OTs juntas: las que están cerca entre sí (radio_grupo_km,
    2 km por defecto) forman un grupo y cada grupo va al técnico disponible de su equipo con
    la UTR más baja de la semana. No cambia nada: la app aplica la propuesta como ediciones.
    """
    # Las visitas cerradas ya se hicieron: no entran en un lote
    cerradas = {a.codigo_bia for a in request.actividades if a.cerrada}
    codigos = [c for c in request.codigos if c not in cerradas]
    if not codigos:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Elige al menos una OT que no esté cerrada")
    pedido, _, _, _, _, _ = await _pedido_del_dia(request)
    return await _al_optimizador("/lote", {
        "pedido": pedido.model_dump(mode="json"), "codigos": codigos, "plan_actual": request.plan_actual,
    })


def puntos_ruta(asignada, incluir_retorno: bool) -> List[List[float]]:
    """Base, paradas y regreso, igual que los manda el mapa"""
    base = [asignada.sede.coordinates.latitude, asignada.sede.coordinates.longitude]
    paradas = [
        [p.actividad.coordinates.latitude, p.actividad.coordinates.longitude]
        for p in asignada.ruta.paradas if p.actividad.coordinates
    ]
    return [base, *paradas, base] if incluir_retorno and paradas else [base, *paradas]


@router.post("/rutas/trazado", response_model=dict)
async def trazado_rutas(request: TrazadoRequest):
    """
    Geometría por vías (OSRM) de cada ruta, para dibujarla en el mapa siguiendo las calles.
    Las rutas que no se pueden trazar no vienen en la respuesta: el mapa las deja en línea recta.
    """
    if not trazado.servidores():
        return {"rutas": {}, "aviso": "OSRM_URL está vacío en backend/.env"}
    rutas = {}
    async with httpx.AsyncClient(timeout=trazado.TIMEOUT) as client:
        for ruta in request.rutas:
            if len(ruta.puntos) < 2:
                continue
            trazo = await trazado.trazar(client, ruta.puntos)
            if trazo:
                rutas[ruta.id] = {"geometria": trazo[0], "km": trazo[1]}
    faltan = [r.id for r in request.rutas if len(r.puntos) >= 2 and r.id not in rutas]
    return {"rutas": rutas, "aviso": trazado.ultimo_error if faltan else None}


@router.get("/rutas/estado", response_model=dict)
async def estado_rutas():
    """¿El backend llega a OSRM? Prueba un trazado corto y dice qué servidor respondió o por qué falló"""
    return await trazado.estado()

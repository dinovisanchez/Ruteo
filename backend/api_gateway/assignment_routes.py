"""Rutas de asignación por OR: OTs desde Metabase, catálogo, configuración y asignación"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collections import Counter
from pathlib import Path
from typing import Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from shared.catalogo import cargar_catalogo, normalizar_texto
from shared.config import settings
from shared.models import (
    Activity,
    AsignacionConfig,
    AssignmentRequest,
    AssignmentResult,
    JornadaConfig,
    SedeOperativa,
)
from shared.utils import setup_logging
from . import metabase
from .geocoding import geocodificar

logger = setup_logging("api-gateway", settings.LOG_LEVEL)

router = APIRouter()

CONFIG_PATH = Path(settings.ASIGNACION_CONFIG_PATH) if settings.ASIGNACION_CONFIG_PATH else (
    Path(__file__).resolve().parent.parent / "data" / "asignacion.json"
)

_catalogo: Optional[Dict] = None


def obtener_catalogo(recargar: bool = False) -> Dict:
    global _catalogo
    if _catalogo is None or recargar:
        sedes, avisos = cargar_catalogo(settings.CONTRATISTAS_CSV_PATH or None, settings.CONTRATISTAS_CSV_URL or None)
        _catalogo = {"sedes": sedes, "avisos": avisos}
        logger.info(f"Catálogo cargado: {len(sedes)} sedes, {len(avisos)} avisos")
    return _catalogo


def leer_config() -> AsignacionConfig:
    if not CONFIG_PATH.exists():
        return AsignacionConfig()
    return AsignacionConfig.model_validate_json(CONFIG_PATH.read_text(encoding="utf-8"))


def guardar_config(config: AsignacionConfig) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporal = CONFIG_PATH.with_suffix(".tmp")
    temporal.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    temporal.replace(CONFIG_PATH)


def conteo_por_or(actividades: List[Activity]) -> Dict[str, int]:
    return dict(Counter(a.or_operador for a in actividades).most_common())


class OTsResponse(BaseModel):
    card_id: str
    total_filas: int
    actividades: List[Activity]
    columnas: List[str]
    mapeo: Dict[str, str]
    ors: Dict[str, int]
    geocodificadas: int
    sin_coordenadas: int
    avisos: List[str]


class AsignarRequest(BaseModel):
    modo: Literal["inhouse", "contratistas"]
    actividades: List[Activity]
    or_filtro: List[str] = Field(default_factory=list)  # Vacío = todos los OR
    tecnicos_ids: List[str] = Field(default_factory=list)
    jornada: JornadaConfig = Field(default_factory=JornadaConfig)


@router.get("/metabase/estado", response_model=dict)
async def metabase_estado():
    """Estado de la conexión con Metabase (sin credenciales)"""
    return metabase.estado()


@router.get("/metabase/ots", response_model=OTsResponse)
async def metabase_ots(card_id: Optional[str] = None):
    """
    Trae las OTs de una pregunta de Metabase y las convierte al formato del optimizador.
    Las OTs sin GPS se geocodifican a partir de su dirección.
    """
    card = card_id or settings.METABASE_CARD_ID
    if not card:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Indica el id de la pregunta de Metabase o configura METABASE_CARD_ID",
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


@router.get("/asignacion/config", response_model=AsignacionConfig)
async def obtener_config():
    """Técnicos in-house y contratistas por OR"""
    return leer_config()


@router.put("/asignacion/config", response_model=AsignacionConfig)
async def actualizar_config(config: AsignacionConfig):
    """Guarda técnicos in-house y contratistas por OR"""
    sedes = {s.id for s in obtener_catalogo()["sedes"]}
    empresas = {s.empresa_id for s in obtener_catalogo()["sedes"] if s.tipo == "contratista"}
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


@router.post("/asignar", response_model=AssignmentResult)
async def asignar(request: AsignarRequest):
    """
    Filtra las OTs por OR y las asigna:
    - inhouse: entre los técnicos seleccionados, cada uno saliendo de su base
    - contratistas: al contratista más cercano entre los que atienden el OR de cada OT
    """
    filtro = {normalizar_texto(o) for o in request.or_filtro}
    actividades = [a for a in request.actividades if not filtro or normalizar_texto(a.or_operador) in filtro]
    if not actividades:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay OTs para los OR seleccionados")

    config = leer_config()
    tecnicos = []
    if request.modo == "inhouse":
        por_id = {t.id: t for t in config.tecnicos}
        tecnicos = [por_id[i] for i in request.tecnicos_ids if i in por_id]
        if not tecnicos:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selecciona al menos un técnico")

    pedido = AssignmentRequest(
        modo=request.modo,
        actividades=actividades,
        sedes=obtener_catalogo()["sedes"],
        tecnicos=tecnicos,
        or_contratistas=config.or_contratistas,
        jornada=request.jornada,
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            respuesta = await client.post(
                f"{settings.OPTIMIZER_SERVICE_URL}/assign",
                json=pedido.model_dump(mode="json"),
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Optimizer service unavailable: {e}")
    if respuesta.status_code != 200:
        raise HTTPException(status_code=respuesta.status_code, detail=respuesta.json().get("detail", respuesta.text))
    return AssignmentResult(**respuesta.json())

"""Resultados de Ruteo para medirlo: qué sugirió cada día y qué quedó asignado en Metabase.

Cada plan de hoy o de un día próximo guarda sus sugerencias (las pendientes que manda a un técnico de
Bia o a un contratista) en data/sugerencias.json. /resultados las compara con las OTs que trae ahora
Metabase: aceptada (quedó con quien sugirió Ruteo), cambiada (quedó con otro), sigue por asignar, o
sin dato (ya no viene en la pregunta).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from shared.config import settings
from shared.models import Activity, DecisionOT
from shared.utils import hoy, setup_logging
from .assignment_routes import aprender_ids, empresa_mencionada, leer_config, obtener_catalogo, responsables

logger = setup_logging("api-gateway", settings.LOG_LEVEL)
router = APIRouter()

RUTA = Path(settings.RESULTADOS_PATH) if settings.RESULTADOS_PATH else (
    Path(__file__).resolve().parent.parent / "data" / "sugerencias.json"
)
# Lo más viejo se borra: alcanza para comparar varios meses
DIAS_GUARDADOS = 400


def _leer() -> Dict[str, Dict[str, Any]]:
    try:
        return json.loads(RUTA.read_text(encoding="utf-8")).get("sugerencias", {})
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return {}


def _guardar(sugerencias: Dict[str, Dict[str, Any]]) -> None:
    RUTA.parent.mkdir(parents=True, exist_ok=True)
    temporal = RUTA.with_suffix(".tmp")
    temporal.write_text(json.dumps({"sugerencias": sugerencias}, ensure_ascii=False), encoding="utf-8")
    temporal.replace(RUTA)


def registrar(dia: str, decisiones: List[DecisionOT], fijas: Dict[str, str]) -> int:
    """Guarda lo que el plan de `dia` sugiere para las OTs pendientes; vale lo último que se calculó.

    Solo cuentan los planes de hoy en adelante (los de días pasados son consulta). Devuelve cuántas
    sugerencias guardó.
    """
    if dia < hoy().isoformat():
        return 0
    catalogo = {s.id: s for s in obtener_catalogo()["sedes"]}
    sugerencias = _leer()
    ahora = datetime.now().isoformat(timespec="seconds")
    guardadas = 0
    for d in decisiones:
        if d.situacion != "pendiente" or d.enviar_a not in ("tecnico", "contratista") or not d.responsable_id:
            continue
        if d.enviar_a == "tecnico":
            destino = {"tipo": "tecnico", "ids": d.responsable_id.split("+"), "nombre": d.responsable}
        else:
            sede = catalogo.get(d.responsable_id.split("#")[0])
            destino = {"tipo": "contratista", "empresa_id": sede.empresa_id if sede else None,
                       "nombre": sede.empresa if sede else (d.sede or d.responsable)}
        clave = f"{dia}|{d.codigo_bia}"
        anterior = sugerencias.get(clave, {})
        sugerencias[clave] = {
            "dia": dia, "codigo": d.codigo_bia, **destino,
            "editada": bool(fijas.get(d.codigo_bia) and fijas[d.codigo_bia] != "auto"),
            "primera_vez": anterior.get("primera_vez", ahora), "ultima_vez": ahora,
        }
        guardadas += 1
    limite = (hoy() - timedelta(days=DIAS_GUARDADOS)).isoformat()
    _guardar({k: v for k, v in sugerencias.items() if v.get("dia", "") >= limite})
    return guardadas


class ResultadosRequest(BaseModel):
    # Las OTs que trae ahora Metabase (como en /utilizacion; sin `extras` basta)
    actividades: List[Activity] = Field(default_factory=list)
    desde: date
    hasta: date


def _quedo(actividad: Optional[Activity], tecnicos, ids, sedes) -> Dict[str, Any]:
    """Con quién quedó la OT en Metabase"""
    if actividad is None:
        return {"estado": "sin_dato"}
    if actividad.situacion == "pendiente":
        return {"estado": "pendiente"}
    de_bia = responsables(actividad, tecnicos, ids)
    if de_bia:
        return {"estado": "asignada", "tipo": "tecnico", "ids": [t.id for t in de_bia],
                "nombre": " + ".join(t.nombre for t in de_bia)}
    return {"estado": "asignada", "tipo": "contratista", "empresa_id": empresa_mencionada(actividad.contratista_asignado, sedes),
            "nombre": actividad.contratista_asignado or actividad.asignado_a or "Sin responsable en Metabase"}


def comparar(sugerencia: Dict[str, Any], quedo: Dict[str, Any]) -> str:
    """aceptada, cambiada, pendiente o sin_dato"""
    if quedo["estado"] != "asignada":
        return quedo["estado"]
    if sugerencia["tipo"] == "tecnico":
        return "aceptada" if quedo["tipo"] == "tecnico" and set(sugerencia["ids"]) & set(quedo["ids"]) else "cambiada"
    mismo = quedo["tipo"] == "contratista" and sugerencia.get("empresa_id") and sugerencia["empresa_id"] == quedo["empresa_id"]
    return "aceptada" if mismo else "cambiada"


def _porcentaje(parte: int, total: int) -> Optional[float]:
    return round(parte / total, 4) if total else None


@router.post("/resultados", response_model=dict)
async def resultados(request: ResultadosRequest):
    """Cuántas sugerencias de Ruteo entre `desde` y `hasta` quedaron así en Metabase, por día y por destino"""
    if request.hasta < request.desde:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La fecha final es anterior a la inicial")
    config = leer_config()
    tecnicos = [t for t in config.tecnicos if t.activo]
    ids = aprender_ids(request.actividades, config)
    sedes = obtener_catalogo()["sedes"]
    por_codigo = {a.codigo_bia: a for a in request.actividades}
    desde, hasta = request.desde.isoformat(), request.hasta.isoformat()

    filas = []
    for sugerencia in sorted(_leer().values(), key=lambda s: (s["dia"], s["codigo"])):
        if not desde <= sugerencia["dia"] <= hasta:
            continue
        quedo = _quedo(por_codigo.get(sugerencia["codigo"]), tecnicos, ids, sedes)
        filas.append({**sugerencia, "resultado": comparar(sugerencia, quedo), "quedo": quedo})

    def resumen(lista: List[Dict[str, Any]]) -> Dict[str, Any]:
        cuenta = Counter(f["resultado"] for f in lista)
        decididas = cuenta["aceptada"] + cuenta["cambiada"]
        return {
            "sugeridas": len(lista),
            "aceptadas": cuenta["aceptada"],
            "cambiadas": cuenta["cambiada"],
            "pendientes": cuenta["pendiente"],
            "sin_dato": cuenta["sin_dato"],
            "editadas": sum(1 for f in lista if f["editada"]),
            # De las que ya se asignaron, cuántas quedaron como dijo Ruteo
            "aceptacion": _porcentaje(cuenta["aceptada"], decididas),
        }

    dias = sorted({f["dia"] for f in filas})
    return {
        "desde": desde,
        "hasta": hasta,
        "total": resumen(filas),
        "por_destino": {tipo: resumen([f for f in filas if f["tipo"] == tipo]) for tipo in ("tecnico", "contratista")},
        "por_dia": [{"dia": d, **resumen([f for f in filas if f["dia"] == d])} for d in dias],
        "cambiadas": [
            {"dia": f["dia"], "codigo": f["codigo"], "sugerido": f["nombre"], "quedo": f["quedo"].get("nombre"),
             "editada": f["editada"]}
            for f in filas if f["resultado"] == "cambiada"
        ],
    }

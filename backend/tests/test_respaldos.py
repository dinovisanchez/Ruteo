"""Cuando OSRM, Nominatim, Metabase o el optimizador responden mal, la app sigue con un respaldo o un mensaje"""
import asyncio

import httpx
import pytest

from api_gateway import assignment_routes, geocoding, metabase, trazado
from shared.config import settings
from shared.models import MatrizVial


def respuesta(cuerpo, codigo=200, tipo="text/html"):
    return httpx.MockTransport(lambda req: httpx.Response(codigo, content=cuerpo.encode(), headers={"content-type": tipo}))


@pytest.fixture
def osrm(monkeypatch):
    monkeypatch.setattr(settings, "OSRM_URL", "http://uno")
    monkeypatch.setattr(settings, "OSRM_URL_RESPALDO", "http://dos")
    monkeypatch.setattr(settings, "OSRM_PAUSA_SEGUNDOS", 0)
    monkeypatch.setattr(trazado, "_sin_osrm_hasta", 0)
    monkeypatch.setattr(trazado, "_preferido", 0)
    monkeypatch.setattr(trazado, "_turno", None)


def test_osrm_con_pagina_de_error_usa_el_respaldo(osrm):
    def servidor(req):
        if req.url.host == "uno":
            return httpx.Response(200, content=b"<html>Rate limit</html>")
        return httpx.Response(200, json={"code": "Ok", "routes": []})

    async def consultar():
        async with httpx.AsyncClient(transport=httpx.MockTransport(servidor)) as cliente:
            return await trazado._consultar(cliente, "/route/v1/driving/1,1;2,2", {})

    assert asyncio.run(consultar()) == {"code": "Ok", "routes": []}


def test_osrm_sin_json_en_ningun_servidor_no_falla(osrm):
    async def consultar():
        async with httpx.AsyncClient(transport=respuesta("<html>x</html>")) as cliente:
            return await trazado._consultar(cliente, "/x", {})

    assert asyncio.run(consultar()) is None
    assert "no es de OSRM" in trazado.ultimo_error


def test_nominatim_con_pagina_de_error_es_un_error_de_red():
    async def buscar():
        async with httpx.AsyncClient(transport=respuesta("<html>bloqueado</html>")) as cliente:
            return await geocoding._buscar(cliente, "Calle 1, Bogotá")

    with pytest.raises(httpx.HTTPError):
        asyncio.run(buscar())


def _cliente_con(monkeypatch, modulo, transporte):
    original = httpx.AsyncClient

    class Falso(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transporte
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(modulo.httpx, "AsyncClient", Falso)


def test_metabase_con_respuesta_cortada_da_un_mensaje(monkeypatch):
    _cliente_con(monkeypatch, metabase, respuesta('[{"Bia Code": "CO1", ', 202, "application/json"))
    with pytest.raises(metabase.MetabaseError, match="se cortó"):
        asyncio.run(metabase.consultar_pregunta("44"))


def test_metabase_con_error_de_la_pregunta(monkeypatch):
    _cliente_con(monkeypatch, metabase, respuesta('{"error": "Column not found"}', 202, "application/json"))
    with pytest.raises(metabase.MetabaseError, match="Column not found"):
        asyncio.run(metabase.consultar_pregunta("44"))


def test_optimizador_con_error_en_texto_plano(monkeypatch):
    _cliente_con(monkeypatch, assignment_routes, respuesta("Internal Server Error", 500, "text/plain"))
    with pytest.raises(assignment_routes.HTTPException) as error:
        asyncio.run(assignment_routes._al_optimizador("/lote", {}))
    assert error.value.status_code == 500 and error.value.detail == "Internal Server Error"


def test_matriz_incompleta_se_rechaza():
    with pytest.raises(ValueError, match="2×2"):
        MatrizVial(puntos=[[4.6, -74.1], [4.7, -74.0]], km=[[0, 1], [1]], minutos=[[0, 1], [1, 0]])
    MatrizVial(puntos=[[4.6, -74.1], [4.7, -74.0]], km=[[0, 1], [1, 0]], minutos=[[0, 3], [3, 0]])

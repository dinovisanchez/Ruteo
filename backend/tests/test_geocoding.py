"""Ubicar OTs sin GPS: direcciones de Colombia, precisión del resultado, Google opcional y caché"""
import asyncio
import time

import httpx
import pytest

from api_gateway import geocoding
from conftest import dia, ot
from shared.config import settings


@pytest.mark.parametrize("direccion, esperada", [
    ("Cl. 58 #10-32", "Calle 58 10-32"),
    ("Carrera 44 # 14-95", "Carrera 44 14-95"),
    ("KR 13 NO 85 32 LA CABRERA", "Carrera 13 85-32"),
    ("CL 72 52 35", "Calle 72 52-35"),
    ("AK 7 # 32-16 Local 2", "Avenida Carrera 7 32-16"),
    ("Av. Calle 26 # 69-76", "Avenida Calle 26 69-76"),
    ("Calle 10 Sur # 5-20 Apto 301", "Calle 10 Sur 5-20"),
    ("TV 4 3 155 BRR LA DOLORES", "Transversal 4 3-155"),
    ("C 23 # 54 - 85 BRR LAS PALMAS", "Calle 23 54-85"),
    ("Dg 21 42 80", "Diagonal 21 42-80"),
    ("CRA 58A # 10B-32", "Carrera 58A 10B-32"),
    ("VDA SAN BENITO FCA MESITAS", "VDA SAN BENITO FCA MESITAS"),
])
def test_direcciones_de_colombia(direccion, esperada):
    assert geocoding.normalizar_direccion(direccion) == esperada


def test_la_consulta_usa_la_direccion_normalizada():
    direccion, municipio = geocoding._consultas(ot("X", direccion="Cl. 58 #10-32 Int 2", ciudad="Bogotá",
                                                  departamento="Bogotá D.C.", coordinates=None))
    assert direccion == "Calle 58 10-32, Bogotá, Bogotá D.C., Colombia"
    assert municipio == "Bogotá, Bogotá D.C., Colombia"


@pytest.fixture
def sin_estado(monkeypatch, tmp_path):
    """Caché vacío en una carpeta temporal y sin pausas"""
    monkeypatch.setattr(geocoding, "CACHE_PATH", tmp_path / "geocache.json")
    monkeypatch.setattr(geocoding, "_cache", {})
    monkeypatch.setattr(geocoding, "_turno", None)
    monkeypatch.setattr(geocoding, "_ultima_consulta", 0.0)
    monkeypatch.setattr(geocoding, "PAUSA_SEGUNDOS", 0)
    monkeypatch.setattr(settings, "GEOCODING_ENABLED", True)


def _buscar_con(respuesta_json):
    async def buscar():
        transporte = httpx.MockTransport(lambda req: httpx.Response(200, json=respuesta_json))
        async with httpx.AsyncClient(transport=transporte) as cliente:
            return await geocoding._buscar(cliente, "Calle 58 10-32, Bogotá")
    return asyncio.run(buscar())


@pytest.mark.parametrize("rango, preciso", [(30, True), (28, True), (26, False), (16, False), (None, True)])
def test_nominatim_calle_o_municipio_es_impreciso(sin_estado, rango, preciso):
    resultado = {"lat": "4.64", "lon": "-74.06"}
    if rango is not None:
        resultado["place_rank"] = rango
    assert _buscar_con([resultado]) == geocoding.Hallazgo(4.64, -74.06, preciso)


def test_fuera_de_colombia_no_cuenta(sin_estado):
    assert _buscar_con([{"lat": "40.4", "lon": "-3.7", "place_rank": 30}]) is None


@pytest.mark.parametrize("tipo, preciso", [("ROOFTOP", True), ("RANGE_INTERPOLATED", True),
                                           ("GEOMETRIC_CENTER", False), ("APPROXIMATE", False)])
def test_google_con_llave(sin_estado, monkeypatch, tipo, preciso):
    monkeypatch.setattr(settings, "GOOGLE_GEOCODING_API_KEY", "llave")
    respuesta = {"status": "OK", "results": [{"geometry": {"location": {"lat": 4.64, "lng": -74.06}, "location_type": tipo}}]}
    assert geocoding.proveedor() == "google"
    assert _buscar_con(respuesta) == geocoding.Hallazgo(4.64, -74.06, preciso)


def test_google_sin_resultados_y_con_llave_mala(sin_estado, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_GEOCODING_API_KEY", "llave")
    assert _buscar_con({"status": "ZERO_RESULTS", "results": []}) is None
    with pytest.raises(httpx.HTTPError, match="REQUEST_DENIED"):
        _buscar_con({"status": "REQUEST_DENIED", "error_message": "The provided API key is invalid."})


def test_no_encontradas_se_reintentan_a_los_7_dias(sin_estado, monkeypatch):
    cache = {}
    geocoding._guardar(cache, "Calle 1, Bogotá", None)
    assert not geocoding._por_buscar(cache, "Calle 1, Bogotá")
    cache["calle 1, bogota"] = {"sin": dia(-8), "por": "nominatim"}
    assert geocoding._por_buscar(cache, "Calle 1, Bogotá")
    # Lo que no encontró Nominatim se le pregunta a Google cuando hay llave
    cache["calle 1, bogota"] = {"sin": dia(0), "por": "nominatim"}
    monkeypatch.setattr(settings, "GOOGLE_GEOCODING_API_KEY", "llave")
    assert geocoding._por_buscar(cache, "Calle 1, Bogotá")
    # El formato anterior (None) también se vuelve a buscar; lo encontrado no
    assert geocoding._por_buscar({"calle 1, bogota": None}, "Calle 1, Bogotá")
    assert not geocoding._por_buscar({"calle 1, bogota": [4.6, -74.1]}, "Calle 1, Bogotá")


def test_geocodificar_marca_lo_impreciso(sin_estado, monkeypatch):
    respuestas = {
        "calle 58 10-32, bogota, bogota d.c., colombia": geocoding.Hallazgo(4.64, -74.06, True),
        "calle 80 20-10, bogota, bogota d.c., colombia": geocoding.Hallazgo(4.67, -74.07, False),  # solo la calle
        "bogota, bogota d.c., colombia": geocoding.Hallazgo(4.61, -74.08, False),
    }

    async def buscar(cliente, consulta):
        return respuestas.get(geocoding.normalizar_texto(consulta))

    monkeypatch.setattr(geocoding, "_buscar", buscar)
    exacta, calle, nada = (ot(c, direccion=d, coordinates=None, gps="", situacion="pendiente")
                           for c, d in (("E", "Cl. 58 #10-32"), ("C", "CL 80 20 10"), ("N", "Vereda El Sol")))
    ubicadas, _ = asyncio.run(geocoding.geocodificar([exacta, calle, nada]))
    assert ubicadas == 3
    assert (exacta.coordinates.latitude, exacta.ubicacion_imprecisa) == (4.64, False)
    assert (calle.coordinates.latitude, calle.ubicacion_imprecisa) == (4.67, True)
    assert (nada.coordinates.latitude, nada.ubicacion_imprecisa) == (4.61, True)  # el municipio
    # La segunda vez todo sale del caché, sin consultar
    monkeypatch.setattr(geocoding, "_buscar", None)
    otra = ot("E2", direccion="Calle 58 # 10-32", coordinates=None, gps="")
    assert asyncio.run(geocoding.geocodificar([otra])) == (1, [])


def test_nominatim_una_consulta_por_segundo_entre_todas(sin_estado, monkeypatch):
    monkeypatch.setattr(geocoding, "PAUSA_SEGUNDOS", 0.2)

    async def tres_a_la_vez():
        inicio = time.monotonic()
        await asyncio.gather(*(geocoding._esperar_turno() for _ in range(3)))
        return time.monotonic() - inicio

    # La primera sale enseguida; las otras dos esperan su turno
    assert asyncio.run(tres_a_la_vez()) >= 0.38

"""Servidor compartido: login con Google (solo cuentas de Bia) y configuración sin pisar cambios de otros"""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from api_gateway import acceso
from shared.config import settings

CLIENTE = "ruteo-prueba.apps.googleusercontent.com"
LLAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class LlavesFalsas:
    """En lugar de las llaves públicas de Google, la de la prueba"""
    def get_signing_key_from_jwt(self, token):
        return type("Llave", (), {"key": LLAVE.public_key()})()


def token(correo="ana@bia.app", verificado=True, audiencia=CLIENTE, vence_en=3600, emisor="https://accounts.google.com"):
    ahora = int(time.time())
    return jwt.encode({"email": correo, "email_verified": verificado, "aud": audiencia, "iss": emisor,
                       "iat": ahora, "exp": ahora + vence_en, "name": "Ana"}, LLAVE, algorithm="RS256")


@pytest.fixture
def con_login(monkeypatch, cliente):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENTE)
    monkeypatch.setattr(settings, "DOMINIOS_PERMITIDOS", ["bia.app"])
    monkeypatch.setattr(settings, "CORREOS_PERMITIDOS", [])
    monkeypatch.setattr(acceso, "_cliente_llaves", lambda: LlavesFalsas())
    return cliente


def pedir(cliente, valor=None):
    return cliente.get("/api/catalogo", headers={"Authorization": f"Bearer {valor}"} if valor else {})


def test_sin_client_id_no_hay_login(cliente):
    assert cliente.get("/api/auth/config").json() == {"modo": None, "google_client_id": None, "dominios": []}
    assert pedir(cliente).status_code == 200
    assert cliente.post("/api/auth/entrar", json={"clave": "x"}).status_code == 404


def test_con_login_pide_una_cuenta_de_bia(con_login):
    assert con_login.get("/api/auth/config").json() == {"modo": "google", "google_client_id": CLIENTE,
                                                        "dominios": ["bia.app"]}
    assert con_login.get("/api/health").status_code == 200
    assert pedir(con_login).status_code == 401
    assert pedir(con_login, token()).status_code == 200


@pytest.mark.parametrize("valor, codigo, texto", [
    (lambda: token(correo="ana@gmail.com"), 403, "solo para cuentas de bia.app"),
    (lambda: token(verificado=False), 403, "no tiene el correo verificado"),
    (lambda: token(vence_en=-60), 401, "venció"),
    (lambda: token(audiencia="otra-app"), 401, "no es válida"),
    (lambda: token(emisor="https://malicioso.example"), 401, "no es válida"),
    (lambda: "no-es-un-token", 401, "no es válida"),
])
def test_tokens_que_no_entran(con_login, valor, codigo, texto):
    respuesta = pedir(con_login, valor())
    assert respuesta.status_code == codigo and texto in respuesta.json()["detail"]


def test_un_correo_de_fuera_puede_entrar_si_se_permite(con_login, monkeypatch):
    monkeypatch.setattr(settings, "CORREOS_PERMITIDOS", ["Consultor@Gmail.com"])
    assert pedir(con_login, token(correo="consultor@gmail.com")).status_code == 200


def test_un_guardado_con_version_vieja_se_rechaza_y_lo_aprendido_se_conserva(cliente):
    from api_gateway import assignment_routes as rutas
    config = cliente.get("/api/asignacion/config").json()
    guardada = rutas.leer_config()
    guardada.ids_electricistas = {"E-1": config["tecnicos"][0]["id"]}
    rutas.guardar_config(guardada)  # lo aprende la app: no sube la versión
    primera = cliente.put("/api/asignacion/config", json={**config, "ids_electricistas": {}})
    assert primera.status_code == 200, primera.text
    assert primera.json()["version"] == config["version"] + 1
    assert primera.json()["ids_electricistas"] == {"E-1": config["tecnicos"][0]["id"]}
    # Otra pestaña con la configuración de antes
    vieja = cliente.put("/api/asignacion/config", json=config)
    assert vieja.status_code == 409 and "recarga la página" in vieja.json()["detail"]


def test_la_app_en_vercel_puede_llamar_a_la_api_y_otra_pagina_no(cliente):
    def permiso(origen):
        r = cliente.options("/api/health", headers={"Origin": origen, "Access-Control-Request-Method": "GET",
                                                     "Access-Control-Request-Headers": "authorization"})
        return r.headers.get("access-control-allow-origin")

    assert permiso("https://ruteo.vercel.app") == "https://ruteo.vercel.app"
    assert permiso("https://otra.example") == "https://otra.example"
    assert permiso("http://localhost:3000") == "http://localhost:3000"
    assert permiso("https://pagina-cualquiera.example") is None


CLAVE = "una-clave-larga-de-prueba"


@pytest.fixture
def con_clave(monkeypatch, cliente):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "CLAVE_ACCESO", CLAVE)
    monkeypatch.setattr(acceso, "_intentos", {})
    return cliente


def entrar(cliente, clave):
    return cliente.post("/api/auth/entrar", json={"clave": clave})


def test_con_clave_se_entra_sin_google(con_clave):
    assert con_clave.get("/api/auth/config").json() == {"modo": "clave", "google_client_id": None, "dominios": []}
    assert pedir(con_clave).status_code == 401
    equivocada = entrar(con_clave, "otra-clave-cualquiera")
    # 403 y no 401: la app toma un 401 como sesión vencida
    assert equivocada.status_code == 403 and "no es correcta" in equivocada.json()["detail"]
    respuesta = entrar(con_clave, CLAVE)
    assert respuesta.status_code == 200
    sesion = respuesta.json()["token"]
    assert pedir(con_clave, sesion).status_code == 200
    # La app muestra el nombre y sabe cuándo vence
    datos = jwt.decode(sesion, options={"verify_signature": False})
    assert datos["name"] == "Equipo Bia" and datos["exp"] - datos["iat"] == 12 * 3600


def test_una_sesion_de_clave_no_sirve_si_la_clave_cambia_o_vence(con_clave, monkeypatch):
    sesion = entrar(con_clave, CLAVE).json()["token"]
    monkeypatch.setattr(settings, "CLAVE_ACCESO", "la-clave-nueva-del-equipo")
    assert pedir(con_clave, sesion).status_code == 401
    vencida = jwt.encode({"iss": "ruteo", "aud": "ruteo", "iat": 1, "exp": 2}, acceso._llave_clave(), algorithm="HS256")
    respuesta = pedir(con_clave, vencida)
    assert respuesta.status_code == 401 and "venció" in respuesta.json()["detail"]
    # Ni un token firmado con otra llave ni uno de Google sirven en el modo de clave
    assert pedir(con_clave, jwt.encode({"iss": "ruteo", "aud": "ruteo", "iat": 1, "exp": 2**31}, "x" * 32,
                                       algorithm="HS256")).status_code == 401
    assert pedir(con_clave, token()).status_code == 401


def test_muchos_intentos_equivocados_hacen_esperar(con_clave):
    for _ in range(acceso.INTENTOS_MAX):
        assert entrar(con_clave, "no-es-la-clave").status_code == 403
    assert entrar(con_clave, CLAVE).status_code == 429

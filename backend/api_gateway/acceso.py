"""Acceso a Ruteo cuando corre en un servidor compartido.

Sin GOOGLE_CLIENT_ID ni CLAVE_ACCESO (en el Mac de cada coordinador) todo queda abierto como siempre.
Con GOOGLE_CLIENT_ID, cada llamada a /api necesita el token de «Iniciar sesión con Google» (un JWT
firmado por Google) de una cuenta verificada de los dominios permitidos (DOMINIOS_PERMITIDOS,
bia.app por defecto) o de CORREOS_PERMITIDOS. Sin Google Cloud, con CLAVE_ACCESO: quien escribe la
clave recibe una sesión de 12 horas firmada por el servidor (si la clave cambia, todas se cierran).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

from shared.config import settings

router = APIRouter()

CERTIFICADOS_GOOGLE = "https://www.googleapis.com/oauth2/v3/certs"
EMISORES_GOOGLE = ("accounts.google.com", "https://accounts.google.com")
# Sin token: el chequeo de salud (lo usa ./iniciar.sh y el servidor), la configuración del login y
# la entrada con la clave
ABIERTAS = ("/api/health", "/api/auth/config", "/api/auth/entrar")
# La sesión que da la clave de acceso
EMISOR_CLAVE = "ruteo"
HORAS_SESION_CLAVE = 12
# Intentos fallidos de la clave por dirección antes de esperar
INTENTOS_MAX = 10
VENTANA_INTENTOS = 15 * 60

_llaves: Optional[jwt.PyJWKClient] = None
_intentos: Dict[str, List[float]] = {}


def modo() -> Optional[str]:
    """«google», «clave» o None (sin login)"""
    if settings.GOOGLE_CLIENT_ID:
        return "google"
    if settings.CLAVE_ACCESO:
        return "clave"
    return None


def activo() -> bool:
    return modo() is not None


def _llave_clave() -> bytes:
    """Con qué se firman las sesiones de la clave: sale de la clave, así cambiarla las cierra todas"""
    return hashlib.sha256(b"ruteo-sesion:" + settings.CLAVE_ACCESO.encode("utf-8")).digest()


def _cliente_llaves() -> jwt.PyJWKClient:
    """Las llaves públicas de Google, guardadas en memoria (se renuevan solas cuando Google las cambia)"""
    global _llaves
    if _llaves is None:
        _llaves = jwt.PyJWKClient(CERTIFICADOS_GOOGLE, cache_keys=True, lifespan=6 * 3600)
    return _llaves


class AccesoNegado(Exception):
    """El token falta, no es válido o es de una cuenta que no puede entrar; el mensaje es para el usuario"""


def _verificar_clave(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, _llave_clave(), algorithms=["HS256"], audience=EMISOR_CLAVE, issuer=EMISOR_CLAVE,
                          options={"require": ["exp", "iat", "aud", "iss"]})
    except jwt.ExpiredSignatureError:
        raise AccesoNegado("La sesión venció: vuelve a escribir la clave")
    except (jwt.PyJWTError, ValueError) as e:
        raise AccesoNegado(f"La sesión no es válida: vuelve a entrar ({e.__class__.__name__})")


def verificar(token: str) -> Dict[str, Any]:
    """Los datos de la cuenta si el token es de Google, para esta app y de una cuenta permitida (o, en
    el modo de clave, si es una sesión que dio este servidor)"""
    if modo() == "clave":
        return _verificar_clave(token)
    try:
        llave = _cliente_llaves().get_signing_key_from_jwt(token)
        datos = jwt.decode(token, llave.key, algorithms=["RS256"], audience=settings.GOOGLE_CLIENT_ID,
                           issuer=list(EMISORES_GOOGLE), options={"require": ["exp", "iat", "aud", "iss", "email"]})
    except jwt.ExpiredSignatureError:
        raise AccesoNegado("La sesión venció: vuelve a iniciar sesión con Google")
    except (jwt.PyJWTError, ValueError) as e:
        raise AccesoNegado(f"La sesión no es válida: vuelve a iniciar sesión ({e.__class__.__name__})")
    correo = str(datos.get("email", "")).lower()
    if not datos.get("email_verified"):
        raise AccesoNegado("Esa cuenta de Google no tiene el correo verificado")
    dominio = correo.rsplit("@", 1)[-1]
    permitidos = {d.lower().lstrip("@") for d in settings.DOMINIOS_PERMITIDOS}
    if dominio not in permitidos and correo not in {c.lower() for c in settings.CORREOS_PERMITIDOS}:
        raise AccesoNegado(f"Ruteo es solo para cuentas de {', '.join(sorted(permitidos)) or 'la empresa'}")
    return datos


class ExigirCuenta:
    """Middleware: con el login activo, toda llamada a /api (salvo ABIERTAS) necesita una cuenta permitida"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not activo():
            return await self.app(scope, receive, send)
        ruta = scope.get("path", "")
        if not ruta.startswith("/api") or ruta in ABIERTAS or scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)
        encabezado = Request(scope).headers.get("authorization", "")
        if not encabezado.lower().startswith("bearer "):
            respuesta = JSONResponse({"detail": "Inicia sesión con tu cuenta de Google de Bia"}, status_code=401)
            return await respuesta(scope, receive, send)
        try:
            scope.setdefault("state", {})["cuenta"] = verificar(encabezado[7:].strip())
        except AccesoNegado as e:
            respuesta = JSONResponse({"detail": str(e)}, status_code=401 if "sesión" in str(e) else 403)
            return await respuesta(scope, receive, send)
        return await self.app(scope, receive, send)


@router.get("/auth/config", response_model=dict)
async def configuracion_acceso():
    """Si hay que iniciar sesión, cómo (Google o la clave) y con qué app de Google (el client id es público)"""
    return {
        "modo": modo(),
        "google_client_id": settings.GOOGLE_CLIENT_ID or None,
        "dominios": settings.DOMINIOS_PERMITIDOS if modo() == "google" else [],
    }


class EntrarRequest(BaseModel):
    clave: str


def _demasiados_intentos(origen: str, ahora: float) -> bool:
    if len(_intentos) > 10000:
        # Muchas direcciones distintas: se olvidan las que ya no cuentan
        for ip in [ip for ip, veces in _intentos.items() if not veces or ahora - veces[-1] > VENTANA_INTENTOS]:
            del _intentos[ip]
    recientes = [t for t in _intentos.get(origen, []) if ahora - t < VENTANA_INTENTOS]
    _intentos[origen] = recientes
    return len(recientes) >= INTENTOS_MAX


@router.post("/auth/entrar", response_model=dict)
async def entrar_con_clave(request: EntrarRequest, pedido: Request):
    """Con la clave de acceso correcta, una sesión de 12 horas. Una clave equivocada responde 403 (no
    401, que la app toma como sesión vencida) y tras varios intentos hay que esperar"""
    if modo() != "clave":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Este servidor no usa clave de acceso")
    origen = pedido.client.host if pedido.client else "?"
    ahora = time.time()
    if _demasiados_intentos(origen, ahora):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Demasiados intentos con una clave equivocada: espera 15 minutos")
    if not hmac.compare_digest(request.clave.encode("utf-8"), settings.CLAVE_ACCESO.encode("utf-8")):
        _intentos[origen].append(ahora)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La clave no es correcta")
    _intentos.pop(origen, None)
    token = jwt.encode({"iss": EMISOR_CLAVE, "aud": EMISOR_CLAVE, "name": "Equipo Bia", "iat": int(ahora),
                        "exp": int(ahora) + HORAS_SESION_CLAVE * 3600}, _llave_clave(), algorithm="HS256")
    return {"token": token}

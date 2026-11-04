"""Acceso con la cuenta de Google de Bia, para cuando Ruteo corre en un servidor compartido.

Sin GOOGLE_CLIENT_ID (en el Mac de cada coordinador) todo queda abierto como siempre. Con él, cada
llamada a /api necesita el token de «Iniciar sesión con Google» (un JWT firmado por Google) de una
cuenta verificada de los dominios permitidos (DOMINIOS_PERMITIDOS, bia.app por defecto) o de
CORREOS_PERMITIDOS.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from shared.config import settings

router = APIRouter()

CERTIFICADOS_GOOGLE = "https://www.googleapis.com/oauth2/v3/certs"
EMISORES_GOOGLE = ("accounts.google.com", "https://accounts.google.com")
# Sin token: el chequeo de salud (lo usa ./iniciar.sh y el servidor) y la configuración del login
ABIERTAS = ("/api/health", "/api/auth/config")

_llaves: Optional[jwt.PyJWKClient] = None


def activo() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID)


def _cliente_llaves() -> jwt.PyJWKClient:
    """Las llaves públicas de Google, guardadas en memoria (se renuevan solas cuando Google las cambia)"""
    global _llaves
    if _llaves is None:
        _llaves = jwt.PyJWKClient(CERTIFICADOS_GOOGLE, cache_keys=True, lifespan=6 * 3600)
    return _llaves


class AccesoNegado(Exception):
    """El token falta, no es válido o es de una cuenta que no puede entrar; el mensaje es para el usuario"""


def verificar(token: str) -> Dict[str, Any]:
    """Los datos de la cuenta si el token es de Google, para esta app y de una cuenta permitida"""
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
    """Si hay que iniciar sesión y con qué app de Google (el client id es público)"""
    return {
        "google_client_id": settings.GOOGLE_CLIENT_ID or None,
        "dominios": settings.DOMINIOS_PERMITIDOS if activo() else [],
    }

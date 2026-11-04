#!/bin/bash
# Ruteo en un servidor (o en el contenedor de Docker): el optimizador y el gateway, que también sirve la
# app compilada. Uso: ./servidor.sh   (la app compilada va en frontend/build o en FRONTEND_DIR)
# Variables: PORT (8000), PYTHON (python3), CLAVE_ACCESO o GOOGLE_CLIENT_ID (login), FRONTEND_URL (la app en
# Vercel u otra dirección), ALLOWED_HOSTS, METABASE_*... Sin login no arranca, salvo SIN_LOGIN=1.
set -e
cd "$(dirname "$0")/backend"
PYTHON="${PYTHON:-python3}"
if [ -n "$GOOGLE_CLIENT_ID" ]; then
  echo "Login con Google (cuentas de DOMINIOS_PERMITIDOS)"
elif [ -n "$CLAVE_ACCESO" ]; then
  if [ "${#CLAVE_ACCESO}" -lt 12 ]; then
    echo "CLAVE_ACCESO es muy corta: usa 12 caracteres o más (mejor una frase de varias palabras)."
    exit 1
  fi
  echo "Login con la clave de acceso"
elif [ "$SIN_LOGIN" = "1" ]; then
  echo "Aviso: SIN_LOGIN=1: no se pide iniciar sesión; cualquiera que llegue a esta dirección usa Ruteo"
else
  echo "Ruteo no arranca sin login: en un servidor, cualquiera que llegue a la dirección vería las OTs de"
  echo "Metabase (clientes y direcciones). Pon CLAVE_ACCESO (una clave de 12 caracteres o más que el equipo"
  echo "escribe al entrar) o GOOGLE_CLIENT_ID (login con Google); solo para probar en un equipo propio, SIN_LOGIN=1."
  exit 1
fi
"$PYTHON" -m uvicorn services.optimizer_service.main:app --host 127.0.0.1 --port 8003 &
"$PYTHON" -m uvicorn api_gateway.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*' &
# Si uno de los dos se cae, el script termina y el servidor (o Docker) lo vuelve a arrancar
wait -n 2>/dev/null || wait
exit $?

#!/bin/bash
# Ruteo en un servidor (o en el contenedor de Docker): el optimizador y el gateway, que también sirve la
# app compilada. Uso: ./servidor.sh   (la app compilada va en frontend/build o en FRONTEND_DIR)
# Variables: PORT (8000), PYTHON (python3), GOOGLE_CLIENT_ID (login con Google), FRONTEND_URL (la app en
# Vercel u otra dirección), ALLOWED_HOSTS, METABASE_*... Sin GOOGLE_CLIENT_ID no arranca, salvo SIN_LOGIN=1.
set -e
cd "$(dirname "$0")/backend"
PYTHON="${PYTHON:-python3}"
if [ -z "$GOOGLE_CLIENT_ID" ]; then
  if [ "$SIN_LOGIN" != "1" ]; then
    echo "Ruteo no arranca sin login: en un servidor, cualquiera que llegue a la dirección vería las OTs de"
    echo "Metabase (clientes y direcciones). Pon GOOGLE_CLIENT_ID (README, «En un servidor de Bia») o, solo"
    echo "para probar en un equipo propio, SIN_LOGIN=1."
    exit 1
  fi
  echo "Aviso: SIN_LOGIN=1: no se pide iniciar sesión; cualquiera que llegue a esta dirección usa Ruteo"
fi
"$PYTHON" -m uvicorn services.optimizer_service.main:app --host 127.0.0.1 --port 8003 &
"$PYTHON" -m uvicorn api_gateway.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*' &
# Si uno de los dos se cae, el script termina y el servidor (o Docker) lo vuelve a arrancar
wait -n 2>/dev/null || wait
exit $?

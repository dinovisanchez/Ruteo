#!/bin/bash
# Arranca Ruteo en este equipo: reinicia el backend (4 servicios) y abre el frontend.
# Uso: ./iniciar.sh   (Ctrl+C detiene todo)
set -e
RAIZ="$(cd "$(dirname "$0")" && pwd)"
LOGS="$RAIZ/logs"
PATRON_BACKEND="uvicorn (api_gateway|services)\..*:app"
mkdir -p "$LOGS"

# Detiene el backend que siga corriendo (por ejemplo, el de antes de un git pull)
pkill -f "$PATRON_BACKEND" 2>/dev/null || true

cd "$RAIZ/backend"
if [ ! -d .venv ]; then
  echo "Creando el entorno de Python (solo la primera vez)..."
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó backend/.env: completa METABASE_URL y METABASE_API_KEY (open -e backend/.env)."
fi

for servicio in \
  "services.data_service.main:app 8001" \
  "services.distance_service.main:app 8002" \
  "services.optimizer_service.main:app 8003" \
  "api_gateway.main:app 8000"; do
  set -- $servicio
  .venv/bin/uvicorn "$1" --port "$2" > "$LOGS/backend-$2.log" 2>&1 &
done
trap 'pkill -f "$PATRON_BACKEND" 2>/dev/null || true' EXIT

echo "Backend iniciado (registros en logs/). Abriendo el frontend en http://localhost:3000 ..."
cd "$RAIZ/frontend"
[ -d node_modules ] || npm install
npm start

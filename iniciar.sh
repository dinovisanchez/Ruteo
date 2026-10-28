#!/bin/bash
# Arranca Ruteo en este equipo: reinicia el backend (gateway y optimizador) y abre el frontend.
# Uso: ./iniciar.sh   (Ctrl+C detiene todo)
set -e
RAIZ="$(cd "$(dirname "$0")" && pwd)"
LOGS="$RAIZ/logs"
PATRON_BACKEND="uvicorn (api_gateway|services)\..*:app"
mkdir -p "$LOGS"

# Detiene el backend y el frontend de esta carpeta que sigan corriendo (por ejemplo, de antes de un git pull,
# incluidos los servicios de datos y distancias de versiones anteriores)
pkill -f "$PATRON_BACKEND" 2>/dev/null || true
pkill -f "$RAIZ/frontend/node_modules" 2>/dev/null || true
sleep 1

# Si otro programa ocupa los puertos del backend (por ejemplo, un backend viejo de otra carpeta), avisa y para
for puerto in 8000 8003; do
  ocupado=$(lsof -nP -iTCP:"$puerto" -sTCP:LISTEN 2>/dev/null | tail -n +2)
  if [ -n "$ocupado" ]; then
    pid=$(echo "$ocupado" | awk '{print $2}' | head -n 1)
    echo "El puerto $puerto está ocupado por otro programa (¿un backend viejo de otra carpeta?):"
    echo "$ocupado"
    echo "Ciérralo con:  kill $pid   y vuelve a ejecutar ./iniciar.sh"
    exit 1
  fi
done

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
  "services.optimizer_service.main:app 8003" \
  "api_gateway.main:app 8000"; do
  set -- $servicio
  .venv/bin/uvicorn "$1" --port "$2" > "$LOGS/backend-$2.log" 2>&1 &
done
trap 'pkill -f "$PATRON_BACKEND" 2>/dev/null || true' EXIT

# Espera a que el backend responda antes de abrir el frontend
echo "Iniciando el backend..."
for intento in $(seq 1 40); do
  if curl -s -o /dev/null http://localhost:8000/api/health; then
    break
  fi
  if [ "$intento" -eq 40 ]; then
    echo "El backend no respondió. Últimas líneas de logs/backend-8000.log:"
    tail -n 25 "$LOGS/backend-8000.log"
    exit 1
  fi
  sleep 1
done
if ! curl -s http://localhost:8000/api/metabase/estado | grep -q '"configurado":true'; then
  echo "Aviso: Metabase no está configurado. Completa METABASE_URL y METABASE_API_KEY en backend/.env (open -e backend/.env)."
fi

echo "Backend listo (registros en logs/). Abriendo el frontend: usa la dirección «Local:» que aparece abajo."
cd "$RAIZ/frontend"
# Instala o actualiza los paquetes cuando cambian las versiones fijadas (package-lock.json)
if [ ! -d node_modules ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
  npm install --no-audit --no-fund
fi
npm start

#!/bin/bash
# Corre las pruebas de Ruteo: backend (pytest), frontend (jest) y, si no se pide "rapido", las de
# navegador (Playwright, con Metabase simulado). Uso: ./probar.sh   o   ./probar.sh rapido
set -e
RAIZ="$(cd "$(dirname "$0")" && pwd)"

echo "== Backend"
cd "$RAIZ/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements-dev.txt
.venv/bin/python -m pytest -q

echo "== Frontend"
cd "$RAIZ/frontend"
if [ ! -d node_modules ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
  npm install --no-audit --no-fund
fi
CI=true npx react-scripts test --watchAll=false

[ "$1" = "rapido" ] && exit 0

echo "== Navegador"
for puerto in 3002 3010 8000 8003; do
  if lsof -nP -iTCP:"$puerto" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "El puerto $puerto está ocupado (¿Ruteo abierto con ./iniciar.sh?). Ciérralo y vuelve a correr ./probar.sh"
    exit 1
  fi
done
CI=true npm run build
cd "$RAIZ/e2e"
npm install --no-audit --no-fund
npx playwright install chromium
PYTHON="$RAIZ/backend/.venv/bin/python" npx playwright test

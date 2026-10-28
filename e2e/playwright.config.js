// Pruebas de navegador: levantan el Metabase simulado, el backend y el frontend compilado
// (npm run build en frontend/ antes) y prueban la app como la usa un coordinador.
const fs = require('fs');
const path = require('path');
const { defineConfig } = require('@playwright/test');

const RAIZ = path.resolve(__dirname, '..');
const SALIDA = path.join(__dirname, 'salida');
const CONFIG = path.join(SALIDA, 'asignacion.json');
// Python con las dependencias del backend: el de backend/.venv si existe (./iniciar.sh lo crea)
const VENV = path.join(RAIZ, 'backend', '.venv', 'bin', 'python');
const PYTHON = process.env.PYTHON || (fs.existsSync(VENV) ? VENV : 'python3');

// Cada corrida empieza con los técnicos de la hoja (los procesos de prueba no la borran)
if (!process.env.TEST_WORKER_INDEX) {
  fs.mkdirSync(SALIDA, { recursive: true });
  fs.rmSync(CONFIG, { force: true });
}

const entorno = {
  ...process.env,
  // El servidor y el navegador en la misma zona: "hoy" es el mismo día para los dos
  TZ: 'America/Bogota',
  METABASE_URL: 'http://localhost:3010',
  METABASE_API_KEY: 'test-key',
  METABASE_CARD_ID: '44',
  ASIGNACION_CONFIG_PATH: CONFIG,
  OSRM_URL: 'http://localhost:3010',
  OSRM_URL_RESPALDO: '',
  OSRM_PAUSA_SEGUNDOS: '0',
  GEOCODING_ENABLED: 'false',
};
// Los registros de cada servidor quedan en salida/<nombre>.log
const servidor = (nombre, comando, carpeta, url) => ({
  command: `${comando} > "${path.join(SALIDA, `${nombre}.log`)}" 2>&1`,
  cwd: carpeta,
  url,
  env: entorno,
  // Nunca reusa un servidor que ya esté corriendo: podría ser Ruteo con el Metabase real
  reuseExistingServer: false,
  timeout: 120000,
});

module.exports = defineConfig({
  testDir: './pruebas',
  // Cada plan tarda unos segundos en el optimizador
  timeout: 240000,
  expect: { timeout: 90000 },
  // Un solo navegador a la vez: todas las pruebas usan el mismo backend
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: 'salida/informe' }]] : 'list',
  outputDir: 'salida/resultados',
  use: {
    baseURL: 'http://localhost:3002',
    locale: 'es-CO',
    timezoneId: 'America/Bogota',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    servidor('metabase', `${PYTHON} -m uvicorn metabase_simulado:app --port 3010`, path.join(__dirname, 'servidor'),
      'http://localhost:3010/search?q=prueba'),
    servidor('optimizador', `${PYTHON} -m uvicorn services.optimizer_service.main:app --port 8003`,
      path.join(RAIZ, 'backend'), 'http://localhost:8003/health'),
    servidor('gateway', `${PYTHON} -m uvicorn api_gateway.main:app --port 8000`, path.join(RAIZ, 'backend'),
      'http://localhost:8000/api/health'),
    servidor('frontend', `${PYTHON} -m http.server 3002 --directory "${path.join(RAIZ, 'frontend', 'build')}"`, RAIZ,
      'http://localhost:3002'),
  ],
});

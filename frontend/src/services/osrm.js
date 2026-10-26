// Direct OSRM queries from the browser, used when the backend cannot reach OSRM
// (for example behind a proxy that only the browser knows about). Both public servers allow CORS.
const SERVIDORES = (process.env.REACT_APP_OSRM_URLS
  || 'https://router.project-osrm.org,https://routing.openstreetmap.de/routed-car')
  .split(',').map((s) => s.trim().replace(/\/$/, '')).filter(Boolean);

// The public servers ask for at most one request per second
const PAUSA_MS = 1000;
const MAX_PUNTOS_TABLA = 100;
// After every server failed to connect, do not try again for a while
const PAUSA_SI_FALLA_MS = 120000;

let ultimaConsulta = 0;
let preferido = 0;
let ultimoError = null;
let sinConexionHasta = 0;

// Why the last query failed, to show it on the map
export const errorOsrm = () => ultimoError;

const coordenada = ([lat, lon]) => `${lon.toFixed(5)},${lat.toFixed(5)}`;

const consultar = async (ruta) => {
  if (Date.now() < sinConexionHasta) return null;
  const orden = [...SERVIDORES.slice(preferido), ...SERVIDORES.slice(0, preferido)];
  const errores = [];
  let sinConexion = 0;
  for (const servidor of orden) {
    const espera = PAUSA_MS - (Date.now() - ultimaConsulta);
    if (espera > 0) await new Promise((resolve) => { setTimeout(resolve, espera); });
    ultimaConsulta = Date.now();
    try {
      const respuesta = await fetch(`${servidor}${ruta}`);
      if (!respuesta.ok) {
        errores.push(`${servidor}: HTTP ${respuesta.status}`);
        continue;
      }
      const datos = await respuesta.json();
      if (datos.code !== 'Ok') {
        errores.push(`${servidor}: ${datos.code}`);
        continue;
      }
      preferido = SERVIDORES.indexOf(servidor);
      ultimoError = null;
      return datos;
    } catch (error) {
      sinConexion += 1;
      errores.push(`${servidor}: ${error.message}`);
    }
  }
  ultimoError = errores.join('; ');
  if (sinConexion === orden.length) sinConexionHasta = Date.now() + PAUSA_SI_FALLA_MS;
  return null;
};

/**
 * Road geometry of a route through `puntos` ([[lat, lon], ...]) in that order
 * @returns {Promise<Object|null>} { geometria: [[lat, lon], ...], km } or null
 */
export const rutaPorVias = async (puntos) => {
  const datos = await consultar(`/route/v1/driving/${puntos.map(coordenada).join(';')}?overview=full&geometries=geojson`);
  const ruta = datos?.routes?.[0];
  if (!ruta) return null;
  return {
    geometria: ruta.geometry.coordinates.map(([lon, lat]) => [lat, lon]),
    km: Math.round(ruta.distance / 10) / 100,
  };
};

/**
 * Km and minutes by road between every pair of points, in the shape the backend expects
 * @param {number[][]} puntos - [[lat, lon], ...]
 * @returns {Promise<Object|null>} { puntos, km, minutos } or null if OSRM does not answer
 */
export const matrizPorVias = async (puntos) => {
  const unicos = [...new Map(puntos.map((p) => [coordenada(p), p])).values()];
  if (unicos.length < 2) return null;
  const n = unicos.length;
  const km = Array.from({ length: n }, () => Array(n).fill(null));
  const minutos = Array.from({ length: n }, () => Array(n).fill(null));
  // Large sets go in blocks (origin × destination) so no request passes the server's limit
  const tamano = n <= MAX_PUNTOS_TABLA ? n : MAX_PUNTOS_TABLA / 2;
  const bloques = [];
  for (let i = 0; i < n; i += tamano) bloques.push([...Array(Math.min(tamano, n - i)).keys()].map((k) => i + k));

  for (const origenes of bloques) {
    for (const destinos of bloques) {
      const indices = [...new Set([...origenes, ...destinos])];
      const params = new URLSearchParams({ annotations: 'duration,distance' });
      if (origenes !== destinos) {
        params.set('sources', origenes.map((i) => indices.indexOf(i)).join(';'));
        params.set('destinations', destinos.map((j) => indices.indexOf(j)).join(';'));
      }
      const datos = await consultar(`/table/v1/driving/${indices.map((i) => coordenada(unicos[i])).join(';')}?${params}`);
      if (!datos) return null;
      origenes.forEach((i, a) => destinos.forEach((j, b) => {
        const metros = datos.distances?.[a]?.[b];
        const segundos = datos.durations?.[a]?.[b];
        km[i][j] = i === j ? 0 : (metros === null || metros === undefined ? null : metros / 1000);
        minutos[i][j] = i === j ? 0 : (segundos === null || segundos === undefined ? null : segundos / 60);
      }));
    }
  }
  return { puntos: unicos, km, minutos };
};

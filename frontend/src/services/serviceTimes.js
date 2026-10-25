// Default minutes per OT type, the same values the proximity mode uses (App.js).
// Keys are normalized: lowercase, no accents.
const DEFAULT_SERVICE_MINUTES = {
  'visita previa': 90,
  'visita pre-venta': 90,
  'instalacion': 180,
  'desconexion': 30,
  'reconexion': 30,
  'normalizacion telemedida': 60,
  'normalizacion telemedidas': 60,
  'normalizacion medida': 120,
  'inspeccion de frontera': 120,
  'tlis': 30,
  'toma de lectura in situ': 30,
  'visita conjunta': 60,
  'legalizacion': 120,
  'verificacion consumo': 30,
  'emergencia': 120,
  'pqr': 60,
};

const FALLBACK_MINUTES = 60;

const normalize = (text) => String(text || '')
  .normalize('NFD')
  .replace(/[̀-ͯ]/g, '')
  .toLowerCase()
  .trim();

export const defaultServiceMinutes = (servicio) => DEFAULT_SERVICE_MINUTES[normalize(servicio)] || FALLBACK_MINUTES;

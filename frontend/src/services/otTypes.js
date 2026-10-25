// Defaults per OT type. Minutes are the same values the proximity mode uses (App.js);
// OT types that usually need two people go out as a pair.
// Keys are normalized: lowercase, no accents.
const DEFAULT_OT_TYPES = {
  'visita previa': { minutos: 90, personas: 1 },
  'visita pre-venta': { minutos: 90, personas: 1 },
  'instalacion': { minutos: 180, personas: 2 },
  'desconexion': { minutos: 30, personas: 1 },
  'reconexion': { minutos: 30, personas: 1 },
  'normalizacion telemedida': { minutos: 60, personas: 1 },
  'normalizacion telemedidas': { minutos: 60, personas: 1 },
  'normalizacion medida': { minutos: 120, personas: 2 },
  'inspeccion de frontera': { minutos: 120, personas: 1 },
  'tlis': { minutos: 30, personas: 1 },
  'toma de lectura in situ': { minutos: 30, personas: 1 },
  'visita conjunta': { minutos: 60, personas: 1 },
  'legalizacion': { minutos: 120, personas: 1 },
  'verificacion consumo': { minutos: 30, personas: 1 },
  'emergencia': { minutos: 120, personas: 2 },
  'pqr': { minutos: 60, personas: 1 },
};

const FALLBACK = { minutos: 60, personas: 1 };

export const normalizeText = (text) => String(text || '')
  .normalize('NFD')
  .replace(/[̀-ͯ]/g, '')
  .toLowerCase()
  .trim();

/**
 * Minutes and people for an OT type: what was saved in the app, otherwise the default
 * @param {string} servicio - OT type as it comes from Metabase
 * @param {Object} saved - config.tipos_ot ({ [type]: { minutos, personas } })
 */
export const otTypeSettings = (servicio, saved = {}) => {
  const key = normalizeText(servicio);
  const savedKey = Object.keys(saved).find((k) => normalizeText(k) === key);
  return { ...FALLBACK, ...(DEFAULT_OT_TYPES[key] || {}), ...(savedKey ? saved[savedKey] : {}) };
};

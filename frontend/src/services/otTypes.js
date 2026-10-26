// Defaults per OT type (average durations given by Bia operations).
// OT types that usually need two people go out as a pair.
// Keys are normalized: lowercase, no accents.
const DEFAULT_OT_TYPES = {
  'visita previa': { minutos: 60, personas: 1 },
  'visita pre-venta': { minutos: 60, personas: 1 },
  // Installations come with their measurement type; without it they count as direct
  'instalacion': { minutos: 120, personas: 2 },
  'instalacion directa': { minutos: 120, personas: 2 },
  'instalacion semidirecta': { minutos: 240, personas: 2 },
  'instalacion indirecta': { minutos: 360, personas: 2 },
  'desconexion': { minutos: 30, personas: 1 },
  'reconexion': { minutos: 30, personas: 1 },
  'normalizacion telemedida': { minutos: 60, personas: 1 },
  'normalizacion telemedidas': { minutos: 60, personas: 1 },
  'normalizacion medida': { minutos: 120, personas: 2 },
  'inspeccion de frontera': { minutos: 120, personas: 1 },
  'tlis': { minutos: 20, personas: 1 },
  'toma de lectura in situ': { minutos: 20, personas: 1 },
  'visita conjunta': { minutos: 60, personas: 1 },
  'legalizacion': { minutos: 120, personas: 1 },
  'verificacion consumo': { minutos: 30, personas: 1 },
  'emergencia': { minutos: 120, personas: 2 },
  'pqr': { minutos: 60, personas: 1 },
};

// Types not listed above, by what their name says
const DEFAULT_BY_NAME = [
  [(key) => key.includes('telemedida'), { minutos: 60, personas: 1 }],
  [(key) => key.startsWith('normalizacion'), { minutos: 120, personas: 1 }],
  [(key) => key.startsWith('instalacion'), { minutos: 120, personas: 2 }],
  [(key) => key.includes('toma de lectura'), { minutos: 20, personas: 1 }],
];

// Earlier defaults: a saved value equal to one of these was never edited, so the new default applies
const PREVIOUS_DEFAULTS = {
  'visita previa': { minutos: 90, personas: 1 },
  'visita pre-venta': { minutos: 90, personas: 1 },
  'instalacion': { minutos: 180, personas: 2 },
  'tlis': { minutos: 30, personas: 1 },
  'toma de lectura in situ': { minutos: 30, personas: 1 },
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
  const byName = DEFAULT_BY_NAME.find(([matches]) => matches(key));
  const savedKey = Object.keys(saved).find((k) => normalizeText(k) === key);
  const previous = PREVIOUS_DEFAULTS[key];
  const savedValue = savedKey && !(previous && saved[savedKey].minutos === previous.minutos
    && saved[savedKey].personas === previous.personas) ? saved[savedKey] : {};
  return { ...FALLBACK, ...(DEFAULT_OT_TYPES[key] || (byName ? byName[1] : {})), ...savedValue };
};

/**
 * Rules of the day plan that do not depend on the screen: which OTs enter a day, how pending OTs
 * are grouped, when the plan is outdated, and which decisions match the filters.
 */
import { normalizeText } from './otTypes';

// What the plan depends on from each OT: if Metabase changes any of it, the plan is outdated
export const firmaOts = (ots) => ots
  .map((a) => [a.codigo_bia, a.situacion, a.fecha_visita, a.hora_visita, a.asignado_a, a.contratista_asignado].join('~'))
  .sort()
  .join('|');
// A visit already closed (by the Situación column): it only counts for utilization
export const esCerrada = (a, columnaSituacion) => Boolean(
  a.cerrada || (columnaSituacion && normalizeText(String(a.extras?.[columnaSituacion] || '')).includes('cerrad')),
);
// Puts back the manual edits of `previas` (code → previous value, undefined = there was none)
export const restaurar = (actuales, previas) => {
  const next = { ...actuales };
  Object.entries(previas).forEach(([codigo, valor]) => {
    if (valor === undefined) delete next[codigo];
    else next[codigo] = valor;
  });
  return next;
};

/**
 * Whether an OT belongs to the plan of `dia`: the ones whose visit date is that day, assigned or
 * pending, as in Olibia. Only today's plan also takes the pending ones whose date already passed and
 * the undated pending ones, so they get planned. Assigned without a date also travel, so the server
 * can report them (they enter no plan).
 */
// Pending with its visit date already past: overdue, it does not apply (no plan, not in Falta por asignar).
// The backend no longer loads them; this covers the OTs already loaded when a new day starts
export const estaVencida = (a, hoy) => a.situacion === 'pendiente' && Boolean(a.fecha_visita) && a.fecha_visita < hoy;
export const entraEnElDia = (a, dia, hoy) => {
  if (estaVencida(a, hoy)) return false;
  if (a.fecha_visita === dia) return true;
  return !a.fecha_visita && (a.situacion === 'asignada' || dia === hoy);
};
// Pending OTs of any date (not overdue): today, the next days and those without a date
export const GRUPOS_PENDIENTES = { hoy: 0, proxima: 1, sin_fecha: 2 };
export const grupoPendiente = (fecha, hoy) => {
  if (!fecha) return 'sin_fecha';
  return fecha === hoy ? 'hoy' : 'proxima';
};
// Several people can be selected: the OT matches if it goes to any of them
export const matchesAssignee = (decision, values) => !values.length || values.some((value) => {
  if (value === 'sin') return decision.enviar_a === 'sin_asignar';
  const nombre = value.slice(2);
  if (value.startsWith('t:')) return decision.enviar_a === 'tecnico' && (decision.responsable || '').split(' + ').includes(nombre);
  if (value.startsWith('c:')) return decision.enviar_a === 'contratista' && (decision.responsable || '').startsWith(`${nombre} (`);
  return decision.enviar_a === 'externo' && decision.responsable === nombre;
});

const DESTINO_OLIBIA = { tecnico: 'Técnico Bia', contratista: 'Contratista' };

/**
 * What still has to be done in Olibia from the plan: the pending OTs Ruteo sends to someone and the
 * ones edited by hand (also reassigned assigned ones). Until Ruteo assigns in Olibia directly, this
 * list is copied into a sheet or downloaded.
 */
export const paraOlibia = (rows, fijas) => rows
  .filter(({ decision: d }) => (d.enviar_a === 'tecnico' || d.enviar_a === 'contratista')
    && (d.situacion === 'pendiente' || fijas[d.codigo_bia]))
  .map(({ decision: d, actividad: a }) => ({
    codigo: d.codigo_bia,
    fecha: a?.fecha_visita || '',
    hora: d.hora_llegada ? d.hora_llegada.slice(0, 5) : (a?.hora_visita || ''),
    ciudad: a?.ciudad || '',
    direccion: a?.direccion || '',
    destino: DESTINO_OLIBIA[d.enviar_a],
    responsable: d.responsable || '',
    cambio: d.situacion === 'asignada' ? `Reasignar (estaba con ${a?.asignado_a || a?.contratista_asignado || 'otro'})` : 'Asignar',
    editada: Boolean(fijas[d.codigo_bia]),
  }));

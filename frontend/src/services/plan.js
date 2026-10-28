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
export const entraEnElDia = (a, dia, hoy) => {
  if (a.fecha_visita === dia) return true;
  if (!a.fecha_visita) return a.situacion === 'asignada' || dia === hoy;
  return a.situacion === 'pendiente' && a.fecha_visita < hoy && dia === hoy;
};
// Pending OTs of any date: overdue first, then today, the next days and those without a date
export const GRUPOS_PENDIENTES = { vencida: 0, hoy: 1, proxima: 2, sin_fecha: 3 };
export const grupoPendiente = (fecha, hoy) => {
  if (!fecha) return 'sin_fecha';
  if (fecha < hoy) return 'vencida';
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

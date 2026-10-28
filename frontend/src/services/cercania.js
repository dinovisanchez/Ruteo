import { normalizeText } from './otTypes';

// Straight-line distance in km between two points {latitude, longitude}
export const kmEntre = (a, b) => {
  const rad = (grados) => (grados * Math.PI) / 180;
  const dLat = rad(b.latitude - a.latitude);
  const dLon = rad(b.longitude - a.longitude);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
};

// Located by GPS or by its exact address: the ones located only by their street or municipality are at its center
export const ubicacionPrecisa = (a) => Boolean(a?.coordinates) && !a.ubicacion_imprecisa;

// Who has an assigned OT, as Metabase says: the electricians and, if it is not Bia, the contractor
export const responsableMetabase = (a) => {
  const contratista = a.contratista_asignado && !normalizeText(a.contratista_asignado).split(/\s+/).includes('bia')
    ? a.contratista_asignado : null;
  return [a.asignado_a, contratista].filter(Boolean).join(' · ') || 'Sin responsable en Metabase';
};

/**
 * For each pending OT, the OTs already assigned in Metabase that are `radio` km or less away in a
 * straight line. Only the active ones count: with a visit today or later and not closed. Those of the
 * day the pending OT would be planned (its date, or today if it is overdue or undated) go first,
 * then by date and distance. Returns {codigo: [{actividad, km, mismoDia}]}, only for those with some.
 */
export const asignadasCerca = (ots, { hoy, radio, cerrada }) => {
  const activas = (ots || []).filter((a) => a.situacion === 'asignada' && ubicacionPrecisa(a)
    && a.fecha_visita && a.fecha_visita >= hoy && !cerrada(a));
  const resultado = {};
  (ots || []).forEach((p) => {
    if (p.situacion !== 'pendiente' || !ubicacionPrecisa(p)) return;
    const diaPlan = p.fecha_visita && p.fecha_visita > hoy ? p.fecha_visita : hoy;
    const cerca = activas
      .map((a) => ({ actividad: a, km: kmEntre(p.coordinates, a.coordinates), mismoDia: a.fecha_visita === diaPlan }))
      .filter((c) => c.km <= radio)
      .sort((x, y) => (Number(y.mismoDia) - Number(x.mismoDia))
        || x.actividad.fecha_visita.localeCompare(y.actividad.fecha_visita)
        || (x.km - y.km));
    if (cerca.length) resultado[p.codigo_bia] = cerca;
  });
  return resultado;
};

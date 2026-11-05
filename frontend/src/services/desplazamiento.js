import dayjs from 'dayjs';
import { kmEntre } from './cercania';

// Farther than this from the OT address, the «Desplazamiento OK» was given far from the visit
export const LEJOS_KM = 1;

/**
 * Where and when the technician gave «Desplazamiento OK» in Olibia, if Metabase brings it: when (only
 * the hour if it was the visit day), how far from the OT address and a Google Maps link.
 */
export const desplazamientoOk = (a) => {
  if (!a?.desplazamiento_ok && !a?.desplazamiento_ok_en) return null;
  const [fecha, hora] = (a.desplazamiento_ok_en || '').split(' ');
  let cuando = null;
  if (fecha && hora) cuando = fecha === a.fecha_visita ? hora : `${dayjs(fecha).format('D MMM')} ${hora}`;
  else if (fecha) cuando = dayjs(fecha).format('D MMM');
  const punto = a.desplazamiento_ok;
  const km = punto && a.coordinates ? Math.round(kmEntre(punto, a.coordinates) * 10) / 10 : null;
  return {
    cuando,
    km,
    lejos: km !== null && km > LEJOS_KM,
    // The OT was located by its street or municipality: the distance is approximate
    aproximada: Boolean(a.coordenadas_aproximadas || a.ubicacion_imprecisa),
    mapa: punto ? `https://www.google.com/maps?q=${punto.latitude},${punto.longitude}` : null,
  };
};

export const textoDesplazamiento = (d) => [
  `Desplazamiento OK${d.cuando ? ` ${d.cuando}` : ''}`,
  d.km !== null ? `a ${d.km.toLocaleString('es-CO')} km de la dirección${d.aproximada ? ' (ubicada aprox.)' : ''}` : null,
].filter(Boolean).join(' · ');

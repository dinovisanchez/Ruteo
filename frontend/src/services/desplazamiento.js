import dayjs from 'dayjs';
import { kmEntre } from './cercania';

// Farther than this from the OT address, the «Desplazamiento OK» was given far from the site
export const LEJOS_KM = 1;
// Longer than this between «Desplazamiento OK» and arriving is not a trip (forgotten marks): not counted
const MAX_MINUTOS = 8 * 60;

const hora = (momento, fechaVisita) => {
  const [fecha, hh] = (momento || '').split(' ');
  if (!fecha) return null;
  if (!hh) return dayjs(fecha).format('D MMM');
  return fecha === fechaVisita ? hh : `${dayjs(fecha).format('D MMM')} ${hh}`;
};

/**
 * Where and when the technician gave «Desplazamiento OK» in Olibia, if Metabase brings it: when (only
 * the hour if it was the visit day), how far from the OT address (straight line), when they marked
 * arriving at the address and how many minutes that took, and a Google Maps link.
 */
export const desplazamientoOk = (a) => {
  if (!a?.desplazamiento_ok && !a?.desplazamiento_ok_en) return null;
  const punto = a.desplazamiento_ok;
  const km = punto && a.coordinates ? Math.round(kmEntre(punto, a.coordinates) * 10) / 10 : null;
  const salio = a.desplazamiento_ok_en?.includes(' ') ? dayjs(a.desplazamiento_ok_en) : null;
  const llego = a.llegada_sitio_en?.includes(' ') ? dayjs(a.llegada_sitio_en) : null;
  const diferencia = salio && llego ? llego.diff(salio, 'minute') : null;
  return {
    cuando: hora(a.desplazamiento_ok_en, a.fecha_visita),
    km,
    lejos: km !== null && km > LEJOS_KM,
    // The OT was located by its street or municipality: the distance is approximate
    aproximada: Boolean(a.coordenadas_aproximadas || a.ubicacion_imprecisa),
    llegada: llego ? hora(a.llegada_sitio_en, a.fecha_visita) : null,
    minutos: diferencia !== null && diferencia >= 0 && diferencia <= MAX_MINUTOS ? diferencia : null,
    mapa: punto ? `https://www.google.com/maps?q=${punto.latitude},${punto.longitude}` : null,
  };
};

const formatoKm = (km) => km.toLocaleString('es-CO', { maximumFractionDigits: 1 });

export const textoDesplazamiento = (d) => [
  `Desplazamiento OK${d.cuando ? ` ${d.cuando}` : ''}`,
  d.km !== null ? `a ${formatoKm(d.km)} km del sitio${d.aproximada ? ' (ubicado aprox.)' : ''}` : null,
  d.llegada ? `llegó ${d.llegada}${d.minutos !== null ? ` (${d.minutos} min)` : ''}` : null,
].filter(Boolean).join(' · ');

const promedio = (valores) => (valores.length ? valores.reduce((s, v) => s + v, 0) / valores.length : null);

/**
 * From «Desplazamiento OK» to the site, on average: km (straight line from where it was given) and
 * minutes until marking the arrival, overall and per technician. `filas` are {actividad, responsable}.
 */
export const promediosDesplazamiento = (filas) => {
  const datos = filas
    .map(({ actividad, responsable }) => ({ d: desplazamientoOk(actividad), responsable }))
    .filter(({ d }) => d);
  const resumen = (lista) => {
    const kms = lista.map(({ d }) => d.km).filter((v) => v !== null);
    const minutos = lista.map(({ d }) => d.minutos).filter((v) => v !== null);
    return {
      ots: lista.length,
      km: promedio(kms),
      minutos: promedio(minutos),
      conTiempo: minutos.length,
    };
  };
  const nombres = [...new Set(datos.map(({ responsable }) => responsable || 'Sin responsable'))].sort();
  return {
    ...resumen(datos),
    porTecnico: nombres.map((nombre) => ({
      nombre,
      ...resumen(datos.filter(({ responsable }) => (responsable || 'Sin responsable') === nombre)),
    })),
  };
};

export const textoPromedios = (p) => [
  `Desplazamiento OK en ${p.ots} ${p.ots === 1 ? 'OT' : 'OTs'}`,
  p.km !== null ? `en promedio a ${formatoKm(p.km)} km del sitio` : null,
  p.minutos !== null ? `${Math.round(p.minutos)} min hasta llegar${p.conTiempo < p.ots ? ` (en ${p.conTiempo} con llegada)` : ''}` : null,
].filter(Boolean).join(' · ');

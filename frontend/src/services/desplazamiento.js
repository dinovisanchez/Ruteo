import dayjs from 'dayjs';
import { kmEntre } from './cercania';

// Closer than this to where they marked arriving, the «Desplazamiento OK» was opened already at the site
export const EN_SITIO_KM = 0.3;
// Faster than this from «Desplazamiento OK» to arriving does not add up (GPS or marks out of place)
const MAX_KMH = 90;
// Longer than this between «Desplazamiento OK» and arriving is not a trip (forgotten marks): not counted
const MAX_MINUTOS = 8 * 60;

const hora = (momento, fechaVisita) => {
  const [fecha, hh] = (momento || '').split(' ');
  if (!fecha) return null;
  if (!hh) return dayjs(fecha).format('D MMM');
  return fecha === fechaVisita ? hh : `${dayjs(fecha).format('D MMM')} ${hh}`;
};

/**
 * Where and when the technician gave «Desplazamiento OK» in Olibia, if Metabase brings it, and the trip
 * to the site. The site is where they marked arriving (IN_ADDRESS); without it, the OT address only if
 * it is exact (an address located by its street or municipality would give made-up km). Flags the trips
 * that do not add up: opened already at the site, or faster than 90 km/h.
 */
export const desplazamientoOk = (a) => {
  if (!a?.desplazamiento_ok && !a?.desplazamiento_ok_en) return null;
  const punto = a.desplazamiento_ok;
  const aproximada = Boolean(a.coordenadas_aproximadas || a.ubicacion_imprecisa);
  const sitio = a.llegada_sitio || (a.coordinates && !aproximada ? a.coordinates : null);
  const km = punto && sitio ? Math.round(kmEntre(punto, sitio) * 10) / 10 : null;
  const salio = a.desplazamiento_ok_en?.includes(' ') ? dayjs(a.desplazamiento_ok_en) : null;
  const llego = a.llegada_sitio_en?.includes(' ') ? dayjs(a.llegada_sitio_en) : null;
  const diferencia = salio && llego ? llego.diff(salio, 'minute') : null;
  const minutos = diferencia !== null && diferencia >= 0 && diferencia <= MAX_MINUTOS ? diferencia : null;
  const enSitio = km !== null && km < EN_SITIO_KM;
  const noCuadra = !enSitio && km !== null && minutos !== null && (minutos === 0 || (km / minutos) * 60 > MAX_KMH);
  return {
    cuando: hora(a.desplazamiento_ok_en, a.fecha_visita),
    km,
    // Measured to where they marked arriving (the real site) or to the OT address
    hastaLlegada: Boolean(a.llegada_sitio),
    sinKmPorDireccion: Boolean(punto && km === null && aproximada),
    enSitio,
    noCuadra,
    // Shown in orange and left out of the averages
    revisar: enSitio || noCuadra,
    llegada: llego ? hora(a.llegada_sitio_en, a.fecha_visita) : null,
    minutos,
    mapa: punto ? `https://www.google.com/maps?q=${punto.latitude},${punto.longitude}` : null,
  };
};

const formatoKm = (km) => km.toLocaleString('es-CO', { maximumFractionDigits: 1 });

const distancia = (d) => {
  if (d.enSitio) return 'abierto ya en el sitio';
  if (d.km !== null) return `a ${formatoKm(d.km)} km del sitio`;
  if (d.sinKmPorDireccion) return 'sin km: la dirección está ubicada aprox.';
  return null;
};

export const textoDesplazamiento = (d) => [
  `Desplazamiento OK${d.cuando ? ` ${d.cuando}` : ''}`,
  distancia(d),
  d.llegada ? `llegó ${d.llegada}${d.minutos !== null ? ` (${d.minutos} min)` : ''}` : null,
  d.noCuadra ? 'no cuadra' : null,
].filter(Boolean).join(' · ');

const promedio = (valores) => (valores.length ? valores.reduce((s, v) => s + v, 0) / valores.length : null);

/**
 * From «Desplazamiento OK» to the site, on average: km and minutes until marking the arrival, overall
 * and per technician. The ones that do not add up are counted apart and left out. `filas` are
 * {actividad, responsable}.
 */
export const promediosDesplazamiento = (filas) => {
  const datos = filas
    .map(({ actividad, responsable }) => ({ d: desplazamientoOk(actividad), responsable }))
    .filter(({ d }) => d);
  const resumen = (lista) => {
    const validos = lista.filter(({ d }) => !d.revisar);
    const kms = validos.map(({ d }) => d.km).filter((v) => v !== null);
    const minutos = validos.map(({ d }) => d.minutos).filter((v) => v !== null);
    return {
      ots: lista.length,
      km: promedio(kms),
      minutos: promedio(minutos),
      conTiempo: minutos.length,
      enSitio: lista.filter(({ d }) => d.enSitio).length,
      noCuadran: lista.filter(({ d }) => d.noCuadra).length,
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

export const textoPromedios = (p) => {
  const apartadas = [
    p.enSitio ? `${p.enSitio} abiertos ya en el sitio` : null,
    p.noCuadran ? `${p.noCuadran} que no cuadran` : null,
  ].filter(Boolean);
  return [
    `Desplazamiento OK en ${p.ots} ${p.ots === 1 ? 'OT' : 'OTs'}`,
    p.km !== null ? `en promedio a ${formatoKm(p.km)} km del sitio` : null,
    p.minutos !== null ? `${Math.round(p.minutos)} min hasta llegar` : null,
    apartadas.length ? `no cuentan: ${apartadas.join(' y ')}` : null,
  ].filter(Boolean).join(' · ');
};

import {
  asignadasCerca, kmEntre, responsableMetabase, ubicacionPrecisa,
} from './cercania';

const HOY = '2026-10-28';
const punto = (latitude, longitude) => ({ latitude, longitude });
const ot = (codigo, situacion, fecha, coords, extra = {}) => ({
  codigo_bia: codigo, situacion, fecha_visita: fecha, coordinates: coords, ...extra,
});
const sinCerradas = { hoy: HOY, radio: 2, cerrada: (a) => Boolean(a.cerrada) };

test('kmEntre mide en línea recta', () => {
  // Un grado de latitud son ~111 km
  expect(kmEntre(punto(4, -74), punto(5, -74))).toBeCloseTo(111.2, 0);
  expect(kmEntre(punto(4.6, -74.1), punto(4.6, -74.1))).toBe(0);
});

test('las asignadas cerca: el mismo día primero, luego por fecha y distancia', () => {
  const pendiente = ot('P', 'pendiente', '2026-10-29', punto(4.650, -74.080));
  const otroDia = ot('A1', 'asignada', '2026-10-28', punto(4.651, -74.080));
  const mismoDiaLejos = ot('A2', 'asignada', '2026-10-29', punto(4.660, -74.080));
  const mismoDiaCerca = ot('A3', 'asignada', '2026-10-29', punto(4.652, -74.080));
  const resultado = asignadasCerca([pendiente, otroDia, mismoDiaLejos, mismoDiaCerca], sinCerradas);
  expect(resultado.P.map((c) => c.actividad.codigo_bia)).toEqual(['A3', 'A2', 'A1']);
  expect(resultado.P.map((c) => c.mismoDia)).toEqual([true, true, false]);
});

test('no cuentan las lejanas, las vencidas, las cerradas ni las ubicadas por municipio', () => {
  const pendiente = ot('P', 'pendiente', null, punto(4.650, -74.080));
  const otras = [
    ot('LEJOS', 'asignada', HOY, punto(4.700, -74.080)),
    ot('AYER', 'asignada', '2026-10-27', punto(4.650, -74.080)),
    ot('CERRADA', 'asignada', HOY, punto(4.650, -74.080), { cerrada: true }),
    ot('MUNICIPIO', 'asignada', HOY, punto(4.650, -74.080), { ubicacion_municipio: true }),
    ot('SIN_FECHA', 'asignada', null, punto(4.650, -74.080)),
  ];
  expect(asignadasCerca([pendiente, ...otras], sinCerradas)).toEqual({});
  // Una pendiente ubicada solo por su municipio tampoco tiene nada cerca
  const municipio = ot('PM', 'pendiente', null, punto(4.650, -74.080), { ubicacion_municipio: true });
  expect(asignadasCerca([municipio, ot('A', 'asignada', HOY, punto(4.650, -74.080))], sinCerradas)).toEqual({});
});

test('una pendiente sin fecha o vencida se compara con las de hoy', () => {
  const vencida = ot('V', 'pendiente', '2026-10-20', punto(4.650, -74.080));
  const deHoy = ot('H', 'asignada', HOY, punto(4.651, -74.080));
  expect(asignadasCerca([vencida, deHoy], sinCerradas).V[0].mismoDia).toBe(true);
});

test('ubicacionPrecisa y responsableMetabase', () => {
  expect(ubicacionPrecisa({ coordinates: punto(4, -74) })).toBe(true);
  expect(ubicacionPrecisa({ coordinates: punto(4, -74), ubicacion_municipio: true })).toBe(false);
  expect(ubicacionPrecisa({})).toBe(false);
  expect(responsableMetabase({ asignado_a: 'Carlos', contratista_asignado: 'Bia Energy' })).toBe('Carlos');
  expect(responsableMetabase({ asignado_a: 'Pedro', contratista_asignado: 'MONTAJES' })).toBe('Pedro · MONTAJES');
  expect(responsableMetabase({})).toBe('Sin responsable en Metabase');
});

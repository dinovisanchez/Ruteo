import { desplazamientoOk, textoDesplazamiento } from './desplazamiento';

const ot = (extra) => ({
  fecha_visita: '2026-11-05', coordinates: { latitude: 4.678, longitude: -74.046 }, ...extra,
});

test('sin datos del desplazamiento no hay nada que mostrar', () => {
  expect(desplazamientoOk(ot({}))).toBeNull();
});

test('el mismo día de la visita solo muestra la hora, y la distancia a la dirección', () => {
  const d = desplazamientoOk(ot({
    desplazamiento_ok: { latitude: 4.679, longitude: -74.047 }, desplazamiento_ok_en: '2026-11-05 08:52',
  }));
  expect(d).toMatchObject({ cuando: '08:52', km: 0.2, lejos: false });
  expect(d.mapa).toBe('https://www.google.com/maps?q=4.679,-74.047');
  expect(textoDesplazamiento(d)).toBe('Desplazamiento OK 08:52 · a 0,2 km de la dirección');
});

test('lejos de la dirección, otro día o con la dirección aproximada se nota', () => {
  const d = desplazamientoOk(ot({
    desplazamiento_ok: { latitude: 4.70, longitude: -74.046 }, desplazamiento_ok_en: '2026-11-04 17:10',
    coordenadas_aproximadas: true,
  }));
  expect(d.lejos).toBe(true);
  expect(d.cuando).toMatch(/^4 \S+ 17:10$/);
  expect(textoDesplazamiento(d)).toContain('(ubicada aprox.)');
  // Solo la hora, sin ubicación: no hay distancia ni mapa
  expect(desplazamientoOk(ot({ desplazamiento_ok_en: '2026-11-05 09:00' }))).toMatchObject({ km: null, mapa: null });
});

import {
  desplazamientoOk, promediosDesplazamiento, textoDesplazamiento, textoPromedios,
} from './desplazamiento';

const ot = (extra) => ({
  fecha_visita: '2026-11-05', coordinates: { latitude: 4.678, longitude: -74.046 }, ...extra,
});

test('sin datos del desplazamiento no hay nada que mostrar', () => {
  expect(desplazamientoOk(ot({}))).toBeNull();
});

test('el mismo día de la visita: la hora, la distancia al sitio y cuánto tardó en llegar', () => {
  const d = desplazamientoOk(ot({
    desplazamiento_ok: { latitude: 4.679, longitude: -74.047 },
    desplazamiento_ok_en: '2026-11-05 08:52',
    llegada_sitio_en: '2026-11-05 09:07',
  }));
  expect(d).toMatchObject({
    cuando: '08:52', km: 0.2, lejos: false, llegada: '09:07', minutos: 15,
  });
  expect(d.mapa).toBe('https://www.google.com/maps?q=4.679,-74.047');
  expect(textoDesplazamiento(d)).toBe('Desplazamiento OK 08:52 · a 0,2 km del sitio · llegó 09:07 (15 min)');
});

test('lejos del sitio, otro día o con la dirección aproximada se nota; sin llegada no hay tiempo', () => {
  const d = desplazamientoOk(ot({
    desplazamiento_ok: { latitude: 4.70, longitude: -74.046 }, desplazamiento_ok_en: '2026-11-04 17:10',
    coordenadas_aproximadas: true,
  }));
  expect(d.lejos).toBe(true);
  expect(d.cuando).toMatch(/^4 \S+ 17:10$/);
  expect(d.minutos).toBeNull();
  expect(textoDesplazamiento(d)).toContain('(ubicado aprox.)');
  expect(textoDesplazamiento(d)).not.toContain('llegó');
  // Una llegada antes del desplazamiento o de más de 8 horas no es un viaje: no cuenta
  expect(desplazamientoOk(ot({
    desplazamiento_ok_en: '2026-11-05 08:00', llegada_sitio_en: '2026-11-05 18:30',
  })).minutos).toBeNull();
});

test('promedios de km y minutos hasta el sitio, en total y por técnico', () => {
  const con = (km0, salio, llego) => ot({
    desplazamiento_ok: { latitude: 4.678 + km0 / 111, longitude: -74.046 },
    desplazamiento_ok_en: `2026-11-05 ${salio}`,
    llegada_sitio_en: llego ? `2026-11-05 ${llego}` : null,
  });
  const p = promediosDesplazamiento([
    { actividad: con(2, '08:00', '08:20'), responsable: 'Carlos Salas' },
    { actividad: con(4, '10:00', '10:40'), responsable: 'Carlos Salas' },
    { actividad: con(3, '09:00', null), responsable: 'Edicson Lopez' },
    { actividad: ot({}), responsable: 'Edicson Lopez' },
  ]);
  expect(p).toMatchObject({ ots: 3, conTiempo: 2 });
  expect(p.km).toBeCloseTo(3, 1);
  expect(p.minutos).toBe(30);
  expect(p.porTecnico.map((t) => [t.nombre, t.ots, t.minutos])).toEqual([['Carlos Salas', 2, 30], ['Edicson Lopez', 1, null]]);
  expect(textoPromedios(p)).toBe('Desplazamiento OK en 3 OTs · en promedio a 3 km del sitio · 30 min hasta llegar (en 2 con llegada)');
});

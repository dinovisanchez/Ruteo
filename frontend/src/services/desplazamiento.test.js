import {
  desplazamientoOk, promediosDesplazamiento, textoDesplazamiento, textoPromedios,
} from './desplazamiento';

const ot = (extra) => ({
  fecha_visita: '2026-11-05', coordinates: { latitude: 4.678, longitude: -74.046 }, ...extra,
});
// A `km` kilómetros al norte del sitio de la OT
const alNorte = (km) => ({ latitude: 4.678 + km / 111.2, longitude: -74.046 });

test('sin datos del desplazamiento no hay nada que mostrar', () => {
  expect(desplazamientoOk(ot({}))).toBeNull();
});

test('los km se miden hasta donde marcó la llegada, que es el sitio real', () => {
  const d = desplazamientoOk(ot({
    desplazamiento_ok: alNorte(3.2),
    desplazamiento_ok_en: '2026-11-05 08:52',
    llegada_sitio_en: '2026-11-05 09:07',
    llegada_sitio: alNorte(0),
    // Aunque la dirección esté lejos o ubicada aproximadamente
    coordinates: { latitude: 4.6, longitude: -74.1 },
    coordenadas_aproximadas: true,
  }));
  expect(d).toMatchObject({
    cuando: '08:52', km: 3.2, hastaLlegada: true, llegada: '09:07', minutos: 15, revisar: false,
  });
  expect(d.mapa).toBe(`https://www.google.com/maps?q=${alNorte(3.2).latitude},-74.046`);
  expect(textoDesplazamiento(d)).toBe('Desplazamiento OK 08:52 · a 3,2 km del sitio · llegó 09:07 (15 min)');
});

test('abierto ya en el sitio: a menos de 300 m de donde marcó la llegada', () => {
  const d = desplazamientoOk(ot({
    desplazamiento_ok: alNorte(0.1), desplazamiento_ok_en: '2026-11-05 09:08',
    llegada_sitio_en: '2026-11-05 09:09', llegada_sitio: alNorte(0),
  }));
  expect(d).toMatchObject({ enSitio: true, revisar: true, minutos: 1 });
  expect(textoDesplazamiento(d)).toBe('Desplazamiento OK 09:08 · abierto ya en el sitio · llegó 09:09 (1 min)');
});

test('sin la llegada, la dirección solo sirve si está ubicada exacta', () => {
  // El caso de la CO7600006927: dirección por el centro del municipio, 9,4 km «en 1 min»
  const aprox = desplazamientoOk(ot({
    desplazamiento_ok: alNorte(9.4), desplazamiento_ok_en: '2026-11-05 09:08',
    llegada_sitio_en: '2026-11-05 09:09', coordenadas_aproximadas: true,
  }));
  expect(aprox).toMatchObject({ km: null, sinKmPorDireccion: true, revisar: false });
  expect(textoDesplazamiento(aprox)).toBe('Desplazamiento OK 09:08 · sin km: la dirección está ubicada aprox. · llegó 09:09 (1 min)');
  const exacta = desplazamientoOk(ot({ desplazamiento_ok: alNorte(2), desplazamiento_ok_en: '2026-11-04 17:10' }));
  expect(exacta).toMatchObject({ km: 2, hastaLlegada: false, minutos: null });
  expect(exacta.cuando).toMatch(/^4 \S+ 17:10$/);
});

test('no cuadra: más de 90 km/h, o una llegada fuera de tiempo que no cuenta', () => {
  const rapido = desplazamientoOk(ot({
    desplazamiento_ok: alNorte(9.4), desplazamiento_ok_en: '2026-11-05 09:08',
    llegada_sitio_en: '2026-11-05 09:10', llegada_sitio: alNorte(0),
  }));
  expect(rapido).toMatchObject({ noCuadra: true, revisar: true });
  expect(textoDesplazamiento(rapido)).toBe('Desplazamiento OK 09:08 · a 9,4 km del sitio · llegó 09:10 (2 min) · no cuadra');
  // Llegada más de 8 horas después: no es un viaje, no hay minutos
  expect(desplazamientoOk(ot({
    desplazamiento_ok_en: '2026-11-05 08:00', llegada_sitio_en: '2026-11-05 18:30',
  })).minutos).toBeNull();
});

test('promedios de km y minutos hasta el sitio, sin los que no cuadran, en total y por técnico', () => {
  const con = (km0, salio, llego) => ot({
    desplazamiento_ok: alNorte(km0), llegada_sitio: alNorte(0),
    desplazamiento_ok_en: `2026-11-05 ${salio}`, llegada_sitio_en: llego ? `2026-11-05 ${llego}` : null,
  });
  const p = promediosDesplazamiento([
    { actividad: con(2, '08:00', '08:20'), responsable: 'Carlos Salas' },
    { actividad: con(4, '10:00', '10:40'), responsable: 'Carlos Salas' },
    { actividad: con(0.1, '11:00', '11:01'), responsable: 'Carlos Salas' },
    { actividad: con(3, '09:00', null), responsable: 'Edicson Lopez' },
    { actividad: con(9.4, '12:00', '12:01'), responsable: 'Edicson Lopez' },
    { actividad: ot({}), responsable: 'Edicson Lopez' },
  ]);
  expect(p).toMatchObject({ ots: 5, conTiempo: 2, enSitio: 1, noCuadran: 1 });
  expect(p.km).toBeCloseTo(3, 1);
  expect(p.minutos).toBe(30);
  expect(p.porTecnico.map((t) => [t.nombre, t.ots, t.minutos, t.enSitio, t.noCuadran]))
    .toEqual([['Carlos Salas', 3, 30, 1, 0], ['Edicson Lopez', 2, null, 0, 1]]);
  expect(textoPromedios(p)).toBe('Desplazamiento OK en 5 OTs · en promedio a 3 km del sitio · 30 min hasta llegar · '
    + 'no cuentan: 1 abiertos ya en el sitio y 1 que no cuadran');
});

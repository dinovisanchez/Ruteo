import {
  entraEnElDia, esCerrada, firmaOts, grupoPendiente, matchesAssignee, paraOlibia, restaurar,
} from './plan';

const HOY = '2026-10-28';

describe('entraEnElDia', () => {
  test('un día tiene las OTs con esa fecha, asignadas o pendientes', () => {
    expect(entraEnElDia({ fecha_visita: '2026-10-29', situacion: 'pendiente' }, '2026-10-29', HOY)).toBe(true);
    expect(entraEnElDia({ fecha_visita: '2026-10-29', situacion: 'asignada' }, '2026-10-29', HOY)).toBe(true);
    expect(entraEnElDia({ fecha_visita: '2026-10-30', situacion: 'pendiente' }, '2026-10-29', HOY)).toBe(false);
  });

  test('solo hoy suma las vencidas y las sin fecha', () => {
    const vencida = { fecha_visita: '2026-10-20', situacion: 'pendiente' };
    const sinFecha = { situacion: 'pendiente' };
    expect(entraEnElDia(vencida, HOY, HOY)).toBe(true);
    expect(entraEnElDia(sinFecha, HOY, HOY)).toBe(true);
    expect(entraEnElDia(vencida, '2026-10-29', HOY)).toBe(false);
    expect(entraEnElDia(sinFecha, '2026-10-29', HOY)).toBe(false);
    // Una asignada de otro día no entra, ni vencida
    expect(entraEnElDia({ fecha_visita: '2026-10-20', situacion: 'asignada' }, HOY, HOY)).toBe(false);
  });
});

test('grupoPendiente ordena vencidas, hoy, próximas y sin fecha', () => {
  expect(grupoPendiente('2026-10-27', HOY)).toBe('vencida');
  expect(grupoPendiente(HOY, HOY)).toBe('hoy');
  expect(grupoPendiente('2026-11-02', HOY)).toBe('proxima');
  expect(grupoPendiente(null, HOY)).toBe('sin_fecha');
});

test('firmaOts cambia si Metabase cambia el estado, la fecha o el responsable, no el orden', () => {
  const a = { codigo_bia: 'A', situacion: 'pendiente', fecha_visita: HOY };
  const b = { codigo_bia: 'B', situacion: 'asignada', fecha_visita: HOY, asignado_a: 'Carlos' };
  expect(firmaOts([a, b])).toBe(firmaOts([b, a]));
  expect(firmaOts([{ ...a, situacion: 'asignada' }, b])).not.toBe(firmaOts([a, b]));
  expect(firmaOts([a, { ...b, asignado_a: 'Juan' }])).not.toBe(firmaOts([a, b]));
  expect(firmaOts([{ ...a, fecha_visita: '2026-10-29' }, b])).not.toBe(firmaOts([a, b]));
});

test('esCerrada por el campo del backend o por la columna Situación', () => {
  expect(esCerrada({ cerrada: true }, null)).toBe(true);
  expect(esCerrada({ extras: { Situación: 'Cerrada' } }, 'Situación')).toBe(true);
  expect(esCerrada({ extras: { Situación: 'Asignada' } }, 'Situación')).toBe(false);
  expect(esCerrada({}, undefined)).toBe(false);
});

test('restaurar devuelve las ediciones a como estaban', () => {
  const actuales = { A: 'tecnico:1', B: 'empresa:x', C: 'auto' };
  expect(restaurar(actuales, { A: undefined, B: 'tecnico:2' })).toEqual({ B: 'tecnico:2', C: 'auto' });
  expect(actuales).toEqual({ A: 'tecnico:1', B: 'empresa:x', C: 'auto' });
});

describe('matchesAssignee', () => {
  const tecnicos = { enviar_a: 'tecnico', responsable: 'Carlos Salas + Juan Reyes' };
  const contratista = { enviar_a: 'contratista', responsable: 'MONTAJES MTE (Bogotá) · Cuadrilla 1' };
  test('sin filtro pasa todo', () => expect(matchesAssignee(tecnicos, [])).toBe(true));
  test('un técnico de una pareja', () => {
    expect(matchesAssignee(tecnicos, ['t:Juan Reyes'])).toBe(true);
    expect(matchesAssignee(tecnicos, ['t:Juan'])).toBe(false);
  });
  test('un contratista por su nombre', () => {
    expect(matchesAssignee(contratista, ['c:MONTAJES MTE'])).toBe(true);
    expect(matchesAssignee(contratista, ['t:Carlos Salas', 'c:MONTAJES MTE'])).toBe(true);
  });
  test('sin asignar', () => expect(matchesAssignee({ enviar_a: 'sin_asignar' }, ['sin'])).toBe(true));
});

describe('paraOlibia', () => {
  const fila = (codigo, enviarA, situacion, extra = {}) => ({
    decision: { codigo_bia: codigo, enviar_a: enviarA, situacion, responsable: 'Carlos Salas', hora_llegada: '09:30:00' },
    actividad: { codigo_bia: codigo, fecha_visita: '2026-10-29', ciudad: 'Bogotá', direccion: 'Calle 1', ...extra },
  });
  test('lleva las sugeridas, las elegidas a mano y las reasignadas; no lo que ya está así en Metabase', () => {
    const filas = [
      fila('SUGERIDA', 'tecnico', 'pendiente'),
      fila('A_MANO', 'contratista', 'pendiente'),
      fila('REASIGNADA', 'tecnico', 'asignada', { asignado_a: 'Juan Reyes' }),
      fila('IGUAL', 'tecnico', 'asignada'),
      fila('SIN_DESTINO', 'sin_asignar', 'pendiente'),
      fila('EXTERNA', 'externo', 'asignada'),
    ];
    const lista = paraOlibia(filas, { A_MANO: 'empresa:x', REASIGNADA: 'tecnico:t2' });
    expect(lista.map((f) => f.codigo)).toEqual(['SUGERIDA', 'A_MANO', 'REASIGNADA']);
    expect(lista[0]).toMatchObject({ fecha: '2026-10-29', hora: '09:30', destino: 'Técnico Bia', cambio: 'Asignar' });
    expect(lista[2].cambio).toBe('Reasignar (estaba con Juan Reyes)');
    expect(lista.map((f) => f.editada)).toEqual([false, true, true]);
  });
});

// El plan del día cuadra con lo que trae Metabase: días, OR, lo que falta por asignar y las cerradas
const {
  test, expect, diaBogota, quieto, abrirConPlan, fila, codigosDeLaLista, otsDeLaApi, nombresOr, cambiarDia,
} = require('./ayuda');

test('al abrir carga las OTs de Metabase y arma el plan de hoy', async ({ page, request }) => {
  await abrirConPlan(page);
  const ots = await otsDeLaApi(request);
  await expect(page.locator('.app-subtitle')).toContainText(`${ots.length} OTs cargadas`);
  const pendientes = ots.filter((a) => a.situacion === 'pendiente').length;
  await expect(page.locator('.kpi:has-text("Falta por asignar") .kpi-value')).toHaveText(String(pendientes));
});

test('cada día muestra exactamente sus OTs, también filtradas por OR', async ({ page, request }) => {
  await abrirConPlan(page);
  const ots = await otsDeLaApi(request);
  const resueltos = await nombresOr(request, ots);
  const dia = diaBogota(2);
  await cambiarDia(page, 2);
  const deEseDia = ots.filter((a) => a.fecha_visita === dia);
  expect(deEseDia.length).toBeGreaterThan(0);
  expect(await codigosDeLaLista(page)).toEqual(deEseDia.map((a) => a.codigo_bia).sort());

  // "Enel" junta las dos formas en que Metabase escribe el OR
  await page.click('.filter-or');
  await page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option:has-text("Enel ·")')
    .first().click();
  await page.keyboard.press('Escape');
  const enel = deEseDia.filter((a) => (resueltos[a.or_operador] || a.or_operador) === 'Enel');
  expect(enel.some((a) => a.or_operador !== 'Enel')).toBe(true);
  expect(await codigosDeLaLista(page)).toEqual(enel.map((a) => a.codigo_bia).sort());
});

test('falta por asignar muestra todas las pendientes y las asignadas cerca', async ({ page, request }) => {
  await abrirConPlan(page);
  const ots = await otsDeLaApi(request);
  await page.click('.kpi:has-text("Falta por asignar")');
  expect(await codigosDeLaLista(page)).toEqual(ots.filter((a) => a.situacion === 'pendiente').map((a) => a.codigo_bia).sort());
  // La visita vigente de una OT con varias filas (pasado mañana), con una asignada de ese mismo día a 0,6 km
  const cerca = fila(page, 'CO0800000000').locator('td').nth(3);
  await expect(cerca).toContainText('Luis Bermudez');
  await expect(cerca).toContainText('mismo día');
  await expect(page.locator('.summary-note')).toContainText('tienen OTs asignadas a 2 km o menos');
});

test('una visita cerrada no se edita ni entra en un lote', async ({ page }) => {
  await abrirConPlan(page);
  // El historial no trae domingos: el último día con visitas cerradas
  const atras = new Date(`${diaBogota(-1)}T12:00:00`).getDay() === 0 ? 2 : 1;
  await cambiarDia(page, -atras);
  await page.fill('.filter-search input', `CO09${String(atras).padStart(2, '0')}`);
  const primera = page.locator('.plain-table tr.ant-table-row').first();
  await expect(primera).toContainText('Cerrada en Metabase');
  await expect(primera.locator('.edit-button')).toHaveCount(0);
  await expect(primera.locator('.ant-checkbox-wrapper-disabled')).toHaveCount(1);
  await quieto(page);
});

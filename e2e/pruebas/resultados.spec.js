// Lo que falta llevar a Olibia y los resultados de las sugerencias
const { test, expect, abrirConPlan } = require('./ayuda');

test('para Olibia junta las sugeridas del día y se pueden copiar', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await abrirConPlan(page);
  const boton = page.locator('button:has-text("Para Olibia")');
  const cuantas = Number((await boton.innerText()).match(/\((\d+)\)/)[1]);
  expect(cuantas).toBeGreaterThan(0);
  await boton.click();
  const modal = page.locator('.ant-modal:has-text("Para cargar en Olibia")');
  await expect(modal.locator('.ot-code').first()).toBeVisible();
  await modal.locator('button:has-text("Copiar")').click();
  const copiado = await page.evaluate(() => navigator.clipboard.readText());
  expect(copiado.split('\n')[0]).toBe('OT\tFecha\tLlega\tCiudad\tDirección\tQué hacer\tDestino\tAsignar a');
  expect(copiado.split('\n')).toHaveLength(cuantas + 1);
  // Copia todas, no solo la página que se ve
  expect(copiado).toContain('CO0700000000\t');
});

test('resultados cuenta lo que sugirió el plan', async ({ page }) => {
  await abrirConPlan(page);
  await page.click('.title-row .ant-segmented-item:has-text("Resultados")');
  const sugeridas = page.locator('.kpi:has-text("Sugeridas") .kpi-value');
  await expect(sugeridas).toBeVisible();
  expect(Number(await sugeridas.innerText())).toBeGreaterThan(0);
  // Nadie ha asignado nada en el Metabase simulado: lo que sigue en la pregunta sigue por asignar
  // (otras pruebas guardan sugerencias de OTs que ya no vienen: esas cuentan como sin dato)
  const pendientes = Number(await page.locator('.kpi:has-text("Siguen por asignar") .kpi-value').innerText());
  expect(pendientes).toBeGreaterThan(0);
  expect(pendientes).toBeLessThanOrEqual(Number(await sugeridas.innerText()));
  await expect(page.locator('.kpi:has-text("Cambiadas") .kpi-value')).toHaveText('0');
  await expect(page.locator('.results-head')).toContainText('Últimos 7 días');
});

// Ediciones, cambios de día y de ajustes mientras se calcula o se lee Metabase: siempre vale lo último
const {
  test, expect, quieto, abrirConPlan, fila, editar, diaBogota,
} = require('./ayuda');

// Las OTs de Chicó están en el plan de hoy (pendientes sin fecha)
const OT = 'CO0700000000';

const pedidosAsignar = (page) => {
  const pedidos = [];
  page.on('request', (r) => { if (r.url().endsWith('/api/asignar')) pedidos.push(JSON.parse(r.postData())); });
  return pedidos;
};
const leerMetabaseDespacio = (page) => page.route('**/api/metabase/ots**', async (ruta) => {
  await new Promise((listo) => { setTimeout(listo, 4000); });
  await ruta.continue();
});

test('una edición se aplica y, si el plan no se puede recalcular, se deshace', async ({ page }) => {
  await abrirConPlan(page);
  await editar(page, OT, 'Juan Jaramillo');
  await quieto(page);
  await expect(fila(page, OT).locator('.assignee')).toContainText('Juan Jaramillo');
  await expect(fila(page, OT).locator('.assignee-sub')).toContainText('Elegido a mano');

  await page.route('**/api/asignar', (r) => r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"falla"}' }));
  await editar(page, 'CO0700000001', 'Juan Jaramillo');
  await expect(page.locator('.ant-message')).toContainText('El cambio no se aplicó');
  await expect(fila(page, 'CO0700000001').locator('.assignee-sub')).not.toContainText('Elegido a mano');
});

test('una edición hecha mientras se lee Metabase no se pierde', async ({ page }) => {
  await abrirConPlan(page);
  const pedidos = pedidosAsignar(page);
  await leerMetabaseDespacio(page);
  const lectura = page.waitForResponse((r) => r.url().includes('/api/metabase/ots'));
  await page.click('button:has-text("Extraer y recomendar")');
  await editar(page, OT, 'Juan Jaramillo');
  await lectura;
  await page.waitForTimeout(500);
  await quieto(page);
  expect(pedidos.length).toBeGreaterThanOrEqual(2);
  expect(pedidos.every((p) => p.fijas[OT])).toBe(true);
  await expect(fila(page, OT).locator('.assignee')).toContainText('Juan Jaramillo');
});

test('cambiar de día mientras se lee Metabase termina en el día elegido', async ({ page }) => {
  await abrirConPlan(page);
  await page.click('.kpi:has-text("Falta por asignar")');
  const pedidos = pedidosAsignar(page);
  await leerMetabaseDespacio(page);
  const lectura = page.waitForResponse((r) => r.url().includes('/api/metabase/ots'));
  await page.click('button:has-text("Extraer y recomendar")');
  await page.locator('button:has-text("Planear el")').first().click();
  await lectura;
  await page.waitForTimeout(500);
  await quieto(page);
  const dias = [...new Set(pedidos.map((p) => p.dia))];
  expect(dias).toHaveLength(1);
  expect(dias[0] > diaBogota(0)).toBe(true);
  const [anio, mes, dia] = dias[0].split('-');
  await expect(page.locator('.filter-bar .ant-picker input')).toHaveValue(`${dia}/${mes}/${anio}`);
  await expect(page.locator('.kpi-row')).toBeVisible();
});

test('un técnico apagado no recibe OTs en el siguiente cálculo', async ({ page }) => {
  await abrirConPlan(page);
  const pedidos = pedidosAsignar(page);
  await page.click('.tool-rail button[aria-label="Técnicos"]');
  await page.locator('.ios-row:has-text("Edicson Lopez") .ant-switch').click();
  const aviso = page.locator('.ant-alert:has-text("Cambiaste técnicos o ajustes")');
  await expect(aviso).toBeVisible();
  await aviso.locator('button:has-text("Recalcular")').click();
  await quieto(page);
  await expect(aviso).toHaveCount(0);
  expect(pedidos.at(-1).tecnicos_ids).not.toContain('hoja-edicson-lopez');
  await page.click('.title-row .ant-segmented-item:has-text("Rutas")');
  await expect(page.locator('.route-title').first()).toBeVisible();
  expect((await page.locator('.route-title').allInnerTexts()).join(' ')).not.toContain('Edicson');
});

test('un campo vacío en Ajustes se avisa en vez de no hacer nada', async ({ page }) => {
  await abrirConPlan(page);
  const pedidos = pedidosAsignar(page);
  await page.click('.tool-rail button[aria-label="Ajustes"]');
  await page.locator('.ant-form-item:has(label:has-text("Horas de trabajo")) input').fill('');
  await page.click('button:has(.anticon-reload)');
  await expect(page.locator('.ant-message')).toContainText('Revisa la jornada en Ajustes');
  expect(pedidos).toHaveLength(0);
});

test('si la actualización automática falla, la app lo dice', async ({ page }) => {
  await page.clock.install({ time: new Date() });
  await abrirConPlan(page);
  await page.route('**/api/metabase/ots**', (r) => r.abort('connectionrefused'));
  await page.clock.fastForward('10:30');
  const aviso = page.locator('.ant-alert:has-text("No se pudo actualizar desde Metabase")');
  await expect(aviso).toBeVisible();
  await expect(aviso).toContainText('Lo que ves es de la lectura de las');
  await expect(aviso.locator('button:has-text("Reintentar")')).toBeVisible();
});

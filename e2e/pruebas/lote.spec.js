// Asignar varias OTs juntas por cercanía y cargar OTs desde un archivo
const { test, expect, quieto, abrirConPlan, fila } = require('./ayuda');

const CHICO = ['CO0700000000', 'CO0700000001', 'CO0700000002'];

test('las OTs cercanas van juntas en la propuesta y se aplican como ediciones', async ({ page }) => {
  await abrirConPlan(page);
  for (const codigo of CHICO) await fila(page, codigo).locator('.ant-checkbox-input').check();
  await expect(page.locator('.lote-bar')).toContainText('3 OTs seleccionadas');
  await page.click('.lote-bar button:has-text("Ver propuesta")');
  const grupo = page.locator('.ant-modal .lote-grupo').first();
  await expect(grupo).toContainText('3 OTs a');
  expect((await grupo.locator('.ot-code').allInnerTexts()).sort()).toEqual(CHICO);
  await page.click('.ant-modal-footer .ant-btn-primary');
  await quieto(page);
  await expect(page.locator('.title-row .ant-segmented-item-selected')).toHaveText('Mapa');
  await expect(page.locator('.filter-bar button:has-text("Quitar")')).toContainText('3 ediciones');
});

test('un CSV de Excel en español se lee como la pregunta de Metabase', async ({ page }) => {
  await abrirConPlan(page);
  const csv = 'Bia Code;OR;Dirección;Ciudad;Situación;Latitud;Longitud\n'
    + 'ARCH1;Enel;Calle 1;Bogotá;Pendiente por asignar;4,65;-74,08\n'
    + 'ARCH2;Enel;Calle 2;Bogotá;Pendiente por asignar;4.66;-74.07\n'
    + 'ARCH3;Enel;Calle 3;Bogotá;Pendiente por asignar;4.67;-74.06\n';
  await page.locator('input[type=file]').setInputFiles({ name: 'ots.csv', mimeType: 'text/csv', buffer: Buffer.from(csv, 'latin1') });
  await expect(page.locator('.app-subtitle')).toContainText('3 OTs cargadas');
  await expect(page.locator('.app-subtitle')).toContainText('Archivo ots.csv');
  await quieto(page);
  for (const codigo of ['ARCH1', 'ARCH2', 'ARCH3']) await expect(fila(page, codigo)).toBeVisible();
});

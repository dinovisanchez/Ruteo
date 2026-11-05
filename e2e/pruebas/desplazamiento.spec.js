// Dónde y cuándo dio cada técnico «Desplazamiento OK» (pregunta 45, unida por «Id visita»)
const {
  test, expect, abrirConPlan, fila,
} = require('./ayuda');

test('cada CO muestra dónde dio el técnico desplazamiento OK y si fue lejos de la dirección', async ({ page }) => {
  await abrirConPlan(page);
  // La búsqueda deja cada OT en la primera página de la lista
  const buscar = page.locator('input[placeholder^="Buscar"]');
  await buscar.fill('CO1000000001');
  const cerca = fila(page, 'CO1000000001').locator('.ot-desplazamiento');
  await expect(cerca).toHaveText(/Desplazamiento OK 13:52 · a 0,1 km de la dirección · ver/);
  await expect(cerca).not.toHaveClass(/lejos/);
  await expect(cerca.locator('a')).toHaveAttribute('href', 'https://www.google.com/maps?q=4.6789,-74.0466');

  await buscar.fill('CO0200000021');
  const lejos = fila(page, 'CO0200000021').locator('.ot-desplazamiento');
  await expect(lejos).toHaveText(/Desplazamiento OK 12:40 · a 2,8 km de la dirección/);
  await expect(lejos).toHaveClass(/lejos/);
  // Las OTs sin desplazamiento no muestran nada
  await buscar.fill('CO0200000001');
  await expect(fila(page, 'CO0200000001')).toBeVisible();
  await expect(fila(page, 'CO0200000001').locator('.ot-desplazamiento')).toHaveCount(0);
});

test('en el mapa se ve dónde dio desplazamiento OK, unido a su parada', async ({ page }) => {
  await abrirConPlan(page);
  await page.click('.title-row .ant-segmented-item:has-text("Mapa")');
  await expect(page.locator('.desplazamiento-dot:not(.leyenda)')).toHaveCount(2);
  await expect(page.locator('.desplazamiento-dot.lejos')).toHaveCount(1);
  await expect(page.locator('.map-legend')).toContainText('Donde dio «Desplazamiento OK»');
  // Con el zoom lejano lo tapa el número de una parada: se abre su globo directamente
  await page.locator('.desplazamiento-dot.lejos').dispatchEvent('click');
  await expect(page.locator('.leaflet-popup-content')).toContainText('a 2,8 km de la dirección');
});

// Dónde y cuándo dio cada técnico «Desplazamiento OK» y el trayecto hasta donde marcó la llegada
// (pregunta 45, unida por «Id visita»)
const {
  test, expect, abrirConPlan, fila,
} = require('./ayuda');

test('cada CO muestra el desplazamiento OK hasta el sitio, y los que no cuadran no cuentan', async ({ page }) => {
  await abrirConPlan(page);
  // Arriba de la lista, el promedio de lo que se ve: sin el que se abrió ya en el sitio
  const promedio = page.locator('.desplazamiento-promedio');
  await expect(promedio).toContainText('Desplazamiento OK en 3 OTs · en promedio a ');
  await expect(promedio).toContainText('km del sitio · 15 min hasta llegar · no cuentan: 1 abiertos ya en el sitio');

  // La búsqueda deja cada OT en la primera página de la lista
  const buscar = page.locator('input[placeholder^="Buscar"]');
  await buscar.fill('CO1000000001');
  const normal = fila(page, 'CO1000000001').locator('.ot-desplazamiento');
  await expect(normal).toHaveText(/Desplazamiento OK 13:52 · a 1,9 km del sitio · llegó 14:07 \(15 min\) · ver/);
  await expect(normal).not.toHaveClass(/revisar/);
  await expect(normal.locator('a')).toHaveAttribute('href', 'https://www.google.com/maps?q=4.695,-74.0466');
  // Con la búsqueda, el promedio es solo de lo que se ve
  await expect(promedio).toContainText('Desplazamiento OK en 1 OT · en promedio a 1,9 km del sitio · 15 min hasta llegar');

  // Sin la llegada marcada: km hasta la dirección (exacta), sin tiempo
  await buscar.fill('CO0200000021');
  const sinLlegada = fila(page, 'CO0200000021').locator('.ot-desplazamiento');
  await expect(sinLlegada).toHaveText(/Desplazamiento OK 12:40 · a 2,8 km del sitio · ver/);
  await expect(sinLlegada).not.toContainText('llegó');

  // Abierto ya en el sitio: en naranja y fuera del promedio
  await buscar.fill('CO0500000001');
  const enSitio = fila(page, 'CO0500000001').locator('.ot-desplazamiento');
  await expect(enSitio).toHaveText(/Desplazamiento OK 14:58 · abierto ya en el sitio · llegó 14:59 \(1 min\)/);
  await expect(enSitio).toHaveClass(/revisar/);

  // Las OTs sin desplazamiento no muestran nada
  await buscar.fill('CO0200000001');
  await expect(fila(page, 'CO0200000001')).toBeVisible();
  await expect(fila(page, 'CO0200000001').locator('.ot-desplazamiento')).toHaveCount(0);
});

test('en el mapa se ve dónde dio desplazamiento OK, unido a su parada', async ({ page }) => {
  await abrirConPlan(page);
  await page.click('.title-row .ant-segmented-item:has-text("Mapa")');
  // La OT de Luis no tiene ubicación: no entra en el mapa
  const rombos = page.locator('.desplazamiento-dot:not(.leyenda)');
  await expect(rombos).toHaveCount(2);
  await expect(page.locator('.map-legend')).toContainText('Donde dio «Desplazamiento OK»');
  // Con el zoom lejano lo puede tapar el número de una parada: se abre su globo directamente
  await rombos.first().dispatchEvent('click');
  await expect(page.locator('.leaflet-popup-content')).toContainText('km del sitio');
});

// Lo que comparten las pruebas: abrir la app con el plan cargado, leer la lista y la API
const fs = require('fs');
const path = require('path');
const base = require('@playwright/test');

const { expect } = base;
const API = 'http://localhost:8000/api';
const CSS_LEAFLET = path.resolve(__dirname, '../../frontend/node_modules/leaflet/dist/leaflet.css');

// Cada prueba falla si la página tuvo un error de JavaScript
const test = base.test.extend({
  errores: [async ({ page }, usar) => {
    const errores = [];
    page.on('pageerror', (e) => errores.push(e.message));
    // Sin internet: la hoja de estilos del mapa sale de node_modules y los mosaicos y el OSRM público no se piden
    await page.route('https://unpkg.com/leaflet@*/dist/leaflet.css', (r) => (fs.existsSync(CSS_LEAFLET)
      ? r.fulfill({ path: CSS_LEAFLET, contentType: 'text/css' }) : r.abort()));
    await page.route(/tile\.openstreetmap\.org|router\.project-osrm\.org|routing\.openstreetmap\.de/, (r) => r.abort());
    await usar(errores);
    expect(errores, 'errores de JavaScript en la página').toEqual([]);
  }, { auto: true }],
});

// YYYY-MM-DD de hoy más `desfase` días en Bogotá (la misma zona que el servidor de prueba)
const diaBogota = (desfase = 0) => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' })
  .format(new Date(Date.now() + desfase * 86400000));

const quieto = (page) => page.waitForFunction(() => !document.querySelector('.ant-spin-spinning'), null, { timeout: 180000 });

async function abrirConPlan(page) {
  await page.goto('/');
  await expect(page.locator('.kpi-row')).toBeVisible({ timeout: 180000 });
  await quieto(page);
}

const fila = (page, codigo) => page.locator(`.plain-table tr.ant-table-row:has(.ot-code:text-is("${codigo}"))`);

// Códigos de la lista, en todas sus páginas
async function codigosDeLaLista(page) {
  const codigos = [];
  const primera = page.locator('.ant-pagination-item-1');
  if (await primera.count()) await primera.first().click();
  for (let pagina = 0; pagina < 40; pagina += 1) {
    codigos.push(...(await page.locator('.plain-table tbody .ot-code').allInnerTexts()).map((t) => t.trim()));
    const siguiente = page.locator('.ant-pagination-next:not(.ant-pagination-disabled)');
    if (!(await siguiente.count())) break;
    await siguiente.first().click();
  }
  return codigos.sort();
}

async function otsDeLaApi(request) {
  return (await (await request.get(`${API}/metabase/ots?card_id=44`)).json()).actividades;
}

// Nombre del catálogo de cada OR tal como lo escribe Metabase ("ENEL COLOMBIA S.A. E.S.P." → "Enel")
async function nombresOr(request, ots) {
  const qs = [...new Set(ots.map((a) => a.or_operador))].map((n) => `nombres=${encodeURIComponent(n)}`).join('&');
  return (await (await request.get(`${API}/operadores?${qs}`)).json()).resueltos;
}

async function cambiarDia(page, pasos) {
  const boton = page.locator(`.filter-bar button:has(.anticon-${pasos > 0 ? 'right' : 'left'})`).first();
  for (let i = 0; i < Math.abs(pasos); i += 1) {
    await boton.click();
    await quieto(page);
  }
}

async function editar(page, codigo, tecnico) {
  await fila(page, codigo).locator('.edit-button').click();
  await page.locator(`.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option:has-text("${tecnico}")`)
    .first().click();
}

module.exports = {
  test, expect, API, diaBogota, quieto, abrirConPlan, fila, codigosDeLaLista, otsDeLaApi, nombresOr, cambiarDia, editar,
};

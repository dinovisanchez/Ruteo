import React, { useEffect, useRef, useState } from 'react';
import { Empty } from 'antd';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { getRouteGeometry } from '../services/api';
import { errorOsrm, rutaPorVias } from '../services/osrm';

export const ROUTE_COLORS = [
  '#007AFF', '#FF9500', '#34C759', '#AF52DE', '#FF2D55',
  '#5AC8FA', '#FFCC00', '#5856D6', '#A2845E', '#30B0C7',
];

const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

// Road geometry per sequence of points, kept across redraws (filters, recalculations, views)
const geometryCache = new Map();
const pointsKey = (points) => points.map(([lat, lon]) => `${lat.toFixed(5)},${lon.toFixed(5)}`).join(';');

const routePoints = (asignada, incluirRetorno) => {
  const base = [asignada.sede.coordinates.latitude, asignada.sede.coordinates.longitude];
  const stops = asignada.ruta.paradas
    .filter((p) => p.actividad.coordinates)
    .map((p) => [p.actividad.coordinates.latitude, p.actividad.coordinates.longitude]);
  return incluirRetorno && stops.length ? [base, ...stops, base] : [base, ...stops];
};

/**
 * Road geometry for one route: first through the backend (it caches and pre-traces right
 * after assigning), then straight from the browser if the backend cannot reach OSRM.
 */
const traceRoute = async (id, points, backend) => {
  if (backend.ok) {
    try {
      const data = await getRouteGeometry([{ id, puntos: points }]);
      if (data.rutas[id]) return { trazo: data.rutas[id] };
      backend.error = data.aviso || 'el servidor no devolvió la ruta';
    } catch (error) {
      backend.error = error.message;
    }
    backend.ok = false;
  }
  const trazo = await rutaPorVias(points);
  return trazo ? { trazo } : { error: errorOsrm() || backend.error };
};

// Each route starts at its own base. Lines start faint and turn into the road geometry as it arrives.
const AssignmentMapView = ({ result, incluirRetorno, visibles, situaciones }) => {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const layerRef = useRef(null);
  const legendRef = useRef(null);
  const [progreso, setProgreso] = useState(null);

  useEffect(() => {
    if (!result || !mapRef.current) return undefined;

    if (!mapInstanceRef.current) {
      mapInstanceRef.current = L.map(mapRef.current, { zoomControl: false }).setView([4.6097, -74.0817], 6);
      L.control.zoom({ position: 'topright' }).addTo(mapInstanceRef.current);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(mapInstanceRef.current);
    }
    const map = mapInstanceRef.current;
    if (layerRef.current) layerRef.current.remove();
    if (legendRef.current) legendRef.current.remove();
    layerRef.current = L.layerGroup().addTo(map);
    const bounds = L.latLngBounds([]);
    const drawnBases = new Set();
    const pendingLines = [];

    result.rutas.forEach((asignada, idx) => {
      const color = ROUTE_COLORS[idx % ROUTE_COLORS.length];
      const base = asignada.sede.coordinates;
      const baseLatLng = [base.latitude, base.longitude];
      const rutaVisible = asignada.ruta.paradas.some((p) => !visibles || visibles.has(p.actividad.codigo_bia));

      if (!drawnBases.has(asignada.sede.id)) {
        drawnBases.add(asignada.sede.id);
        L.marker(baseLatLng, {
          icon: L.divIcon({
            className: 'base-marker',
            html: '<div class="base-dot"></div>',
            iconSize: [18, 18],
            iconAnchor: [9, 9],
          }),
        })
          .bindTooltip(`${escapeHtml(asignada.sede.empresa)} · ${escapeHtml(asignada.sede.ciudad)}`)
          .addTo(layerRef.current);
        if (rutaVisible) bounds.extend(baseLatLng);
      }

      asignada.ruta.paradas.forEach((stop) => {
        const c = stop.actividad.coordinates;
        if (!c) return;
        const latLng = [c.latitude, c.longitude];
        const visible = !visibles || visibles.has(stop.actividad.codigo_bia);
        if (visible) bounds.extend(latLng);
        const yaAsignada = situaciones?.[stop.actividad.codigo_bia] === 'asignada';
        // Already assigned in Metabase: rounded square; suggested by the app: circle
        L.marker(latLng, {
          opacity: visible ? 1 : 0.2,
          icon: L.divIcon({
            className: 'stop-marker',
            html: `<div class="stop-dot${yaAsignada ? ' asignada' : ''}" style="background:${color}">${stop.secuencia}</div>`,
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          }),
        })
          .bindPopup(`
            <div class="map-popup">
              <div class="map-popup-title">OT ${escapeHtml(stop.actividad.codigo_bia)}</div>
              <div>${escapeHtml(asignada.responsable)} · parada ${stop.secuencia}</div>
              <div class="map-popup-sub">${yaAsignada ? 'Ya asignada' : 'Sugerida'} · ${escapeHtml(stop.actividad.servicio)}</div>
              <div class="map-popup-sub">${escapeHtml(stop.actividad.nombre)}</div>
              <div class="map-popup-sub">${escapeHtml(stop.actividad.direccion)}, ${escapeHtml(stop.actividad.ciudad)}</div>
              <div class="map-popup-sub">Llega ${stop.hora_llegada_estimada.slice(0, 5)} · sale ${stop.hora_salida_estimada.slice(0, 5)}</div>
            </div>`)
          .addTo(layerRef.current);
      });

      const points = routePoints(asignada, incluirRetorno);
      if (points.length > 1) {
        const key = pointsKey(points);
        const cached = geometryCache.get(key);
        const line = L.polyline(cached ? cached.geometria : points, cached
          ? { color, weight: 4, opacity: rutaVisible ? 0.85 : 0.12 }
          : { color, weight: 2, opacity: rutaVisible ? 0.35 : 0.08, dashArray: '4 8' })
          .addTo(layerRef.current);
        if (cached) {
          line.bindTooltip(`${escapeHtml(asignada.responsable)} · ${cached.km.toLocaleString('es-CO')} km por carretera`, { sticky: true });
        } else {
          pendingLines.push({ id: asignada.responsable_id, key, points, line, rutaVisible, responsable: asignada.responsable });
        }
      }
    });

    // OTs that could not be assigned but have a location, in gray
    result.sin_asignar.forEach(({ actividad, motivo }) => {
      const c = actividad.coordinates;
      if (!c) return;
      const latLng = [c.latitude, c.longitude];
      const visible = !visibles || visibles.has(actividad.codigo_bia);
      if (visible) bounds.extend(latLng);
      L.circleMarker(latLng, {
        radius: 6, color: '#8E8E93', fillColor: '#C7C7CC', fillOpacity: visible ? 0.9 : 0.2, opacity: visible ? 1 : 0.2, weight: 2,
      })
        .bindPopup(`<div class="map-popup"><div class="map-popup-title">OT ${escapeHtml(actividad.codigo_bia)}</div><div class="map-popup-sub">Sin asignar · ${escapeHtml(motivo)}</div></div>`)
        .addTo(layerRef.current);
    });

    if (bounds.isValid()) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 14 });

    const legend = L.control({ position: 'bottomleft' });
    legend.onAdd = () => {
      const div = L.DomUtil.create('div', 'map-legend');
      div.innerHTML = result.rutas
        .map((r, idx) => ({ r, idx }))
        .filter(({ r }) => !visibles || r.ruta.paradas.some((p) => visibles.has(p.actividad.codigo_bia)))
        .map(({ r, idx }) => `
          <div class="map-legend-row">
            <span style="background:${ROUTE_COLORS[idx % ROUTE_COLORS.length]}"></span>${escapeHtml(r.responsable)}
          </div>`).join('');
      return div;
    };
    legend.addTo(map);
    legendRef.current = legend;

    // One route at a time so the lines turn into roads one by one
    let cancelled = false;
    setProgreso(pendingLines.length ? { hechas: 0, total: pendingLines.length, fallidas: 0, error: null } : null);
    (async () => {
      const backend = { ok: true, error: null };
      let hechas = 0;
      let fallidas = 0;
      let ultimoError = null;
      for (const pending of pendingLines) {
        if (cancelled) return;
        const { trazo, error } = await traceRoute(pending.id, pending.points, backend);
        if (trazo) {
          geometryCache.set(pending.key, trazo);
          if (cancelled) return;
          pending.line.setLatLngs(trazo.geometria);
          pending.line.setStyle({ dashArray: null, weight: 4, opacity: pending.rutaVisible ? 0.85 : 0.12 });
          pending.line.bindTooltip(`${escapeHtml(pending.responsable)} · ${trazo.km.toLocaleString('es-CO')} km por carretera`, { sticky: true });
        } else {
          fallidas += 1;
          ultimoError = error;
        }
        hechas += 1;
        if (!cancelled) setProgreso({ hechas, total: pendingLines.length, fallidas, error: ultimoError });
      }
    })();
    return () => { cancelled = true; };
  }, [result, incluirRetorno, visibles, situaciones]);

  useEffect(() => () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }
  }, []);

  const enCurso = progreso && progreso.hechas < progreso.total;
  return (
    <div className="map-shell">
      <div ref={mapRef} className="map-canvas" />
      {enCurso && (
        <div className="map-status">Trazando por carretera · {progreso.hechas}/{progreso.total}</div>
      )}
      {progreso && !enCurso && progreso.fallidas > 0 && (
        <div className="map-status warn" title={progreso.error || ''}>
          {progreso.fallidas} {progreso.fallidas > 1 ? 'rutas quedaron' : 'ruta quedó'} en línea recta: no se pudo consultar el servidor de rutas
          {progreso.error ? ` (${progreso.error})` : ''}
        </div>
      )}
      {!result && (
        <div className="map-empty"><Empty description="Pulsa «Extraer y recomendar» para ver las rutas" /></div>
      )}
    </div>
  );
};

export default AssignmentMapView;

import React, { useEffect, useRef, useState } from 'react';
import { Card, Empty, Typography } from 'antd';
import { EnvironmentOutlined } from '@ant-design/icons';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { getRouteGeometry } from '../services/api';

const { Text } = Typography;

export const ROUTE_COLORS = [
  '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b',
];

const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

// Road geometry per sequence of points, kept across redraws (filters, recalculations)
const geometryCache = new Map();
const pointsKey = (points) => points.map(([lat, lon]) => `${lat.toFixed(5)},${lon.toFixed(5)}`).join(';');

const routePoints = (asignada, incluirRetorno) => {
  const base = [asignada.sede.coordinates.latitude, asignada.sede.coordinates.longitude];
  const stops = asignada.ruta.paradas
    .filter((p) => p.actividad.coordinates)
    .map((p) => [p.actividad.coordinates.latitude, p.actividad.coordinates.longitude]);
  return incluirRetorno && stops.length ? [base, ...stops, base] : [base, ...stops];
};

// Each route starts at its own base (technician or contractor site). Lines start straight and
// dashed, and are replaced by the road geometry as OSRM returns it.
const AssignmentMapView = ({ result, incluirRetorno, visibles, situaciones }) => {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const layerRef = useRef(null);
  const legendRef = useRef(null);
  const [aviso, setAviso] = useState(null);

  useEffect(() => {
    if (!result) {
      if (layerRef.current) layerRef.current.remove();
      if (legendRef.current) legendRef.current.remove();
      layerRef.current = null;
      legendRef.current = null;
      return undefined;
    }
    if (!mapRef.current) return undefined;

    if (!mapInstanceRef.current) {
      mapInstanceRef.current = L.map(mapRef.current).setView([4.6097, -74.0817], 6);
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
            className: 'depot-marker',
            html: '<div style="background:#000;color:#fff;border-radius:50%;width:34px;height:34px;display:flex;align-items:center;justify-content:center;border:3px solid #fff;box-shadow:0 3px 8px rgba(0,0,0,.4);font-size:16px;">🏠</div>',
            iconSize: [34, 34],
            iconAnchor: [17, 17],
          }),
        })
          .bindPopup(`<strong>${escapeHtml(asignada.sede.empresa)}</strong><br/>${escapeHtml(asignada.sede.ciudad)}<br/><small>${escapeHtml(asignada.sede.direccion)}</small>`)
          .addTo(layerRef.current);
        bounds.extend(baseLatLng);
      }

      asignada.ruta.paradas.forEach((stop) => {
        const c = stop.actividad.coordinates;
        if (!c) return;
        const latLng = [c.latitude, c.longitude];
        const visible = !visibles || visibles.has(stop.actividad.codigo_bia);
        if (visible) bounds.extend(latLng);
        const aprox = stop.actividad.coordenadas_aproximadas;
        const yaAsignada = situaciones?.[stop.actividad.codigo_bia] === 'asignada';
        // Already assigned in Metabase: rounded square; suggested by the app: circle
        L.marker(latLng, {
          opacity: visible ? 1 : 0.3,
          icon: L.divIcon({
            className: 'custom-marker',
            html: `<div style="background:${color};color:#fff;border-radius:${yaAsignada ? '7px' : '50%'};width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px ${aprox ? 'dashed' : 'solid'} #fff;box-shadow:0 2px 5px rgba(0,0,0,.3);">${stop.secuencia}</div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13],
          }),
        })
          .bindPopup(`
            <div style="min-width:200px">
              <h4 style="margin:0 0 6px;color:${color}">${escapeHtml(asignada.responsable)} · parada ${stop.secuencia}</h4>
              <strong>OT ${escapeHtml(stop.actividad.codigo_bia)}</strong> · ${escapeHtml(stop.actividad.or_operador)}<br/>
              <small>${yaAsignada ? 'Ya asignada en Metabase' : 'Sugerida por la app'}</small><br/>
              ${escapeHtml(stop.actividad.nombre)}<br/>
              <small>${escapeHtml(stop.actividad.direccion)}, ${escapeHtml(stop.actividad.ciudad)}</small><br/>
              ${aprox ? '<small style="color:#d48806">Ubicación aproximada (geocodificada)</small><br/>' : ''}
              <small>Llegada ${stop.hora_llegada_estimada} · Salida ${stop.hora_salida_estimada}</small>
            </div>`)
          .addTo(layerRef.current);
      });

      const points = routePoints(asignada, incluirRetorno);
      if (points.length > 1) {
        const key = pointsKey(points);
        const cached = geometryCache.get(key);
        const line = L.polyline(cached ? cached.geometria : points, {
          color,
          weight: 4,
          opacity: rutaVisible ? 0.8 : 0.2,
          dashArray: cached ? null : '6 8',
        }).addTo(layerRef.current);
        if (cached) {
          line.bindTooltip(`${escapeHtml(asignada.responsable)} · ${cached.km.toLocaleString('es-CO')} km por vía`, { sticky: true });
        } else {
          pendingLines.push({ id: asignada.responsable_id, key, points, line, responsable: asignada.responsable });
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
        radius: 7, color: '#595959', fillColor: '#bfbfbf', fillOpacity: visible ? 0.9 : 0.25, opacity: visible ? 1 : 0.3, weight: 2,
      })
        .bindPopup(`<strong>OT ${escapeHtml(actividad.codigo_bia)}</strong> · sin asignar<br/><small>${escapeHtml(motivo)}</small>`)
        .addTo(layerRef.current);
    });

    if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] });

    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = () => {
      const div = L.DomUtil.create('div');
      div.style.cssText = 'background:#fff;padding:8px 10px;border-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,.15);max-height:220px;overflow:auto;font-size:12px';
      div.innerHTML = result.rutas.map((r, idx) => `
        <div style="display:flex;align-items:center;margin:3px 0">
          <div style="width:18px;height:3px;background:${ROUTE_COLORS[idx % ROUTE_COLORS.length]};margin-right:6px"></div>
          ${escapeHtml(r.responsable)} (${r.ruta.paradas.length})
        </div>`).join('')
        + '<div style="margin-top:6px;color:#8c8c8c">■ ya asignada · ● sugerida</div>';
      return div;
    };
    legend.addTo(map);
    legendRef.current = legend;

    // One route per request so the lines turn into roads one by one
    let cancelled = false;
    (async () => {
      for (const pending of pendingLines) {
        if (cancelled) return;
        try {
          const data = await getRouteGeometry([{ id: pending.id, puntos: pending.points }]);
          if (data.aviso) {
            if (!cancelled) setAviso(data.aviso);
            return;
          }
          const trazo = data.rutas[pending.id];
          if (!trazo) continue;
          geometryCache.set(pending.key, trazo);
          if (cancelled) return;
          pending.line.setLatLngs(trazo.geometria);
          pending.line.setStyle({ dashArray: null });
          pending.line.bindTooltip(`${escapeHtml(pending.responsable)} · ${trazo.km.toLocaleString('es-CO')} km por vía`, { sticky: true });
          setAviso(null);
        } catch (error) {
          if (!cancelled) setAviso('No se pudo trazar las rutas por vías: se muestran en línea recta.');
          return;
        }
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

  return (
    <Card
      title={<span><EnvironmentOutlined /> Mapa de asignación</span>}
      extra={aviso ? <Text type="warning" style={{ fontSize: 12 }}>{aviso}</Text> : null}
      style={{ height: '100%' }}
      styles={{ body: { height: 'calc(100% - 57px)', padding: 0 } }}
    >
      <div style={{ position: 'relative', height: '100%' }}>
        <div ref={mapRef} style={{ height: '100%', width: '100%' }} />
        {!result && (
          <div style={{ position: 'absolute', inset: 0, zIndex: 1000, background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Empty description="Pulsa «Extraer y recomendar» para ver las rutas" />
          </div>
        )}
      </div>
    </Card>
  );
};

export default AssignmentMapView;

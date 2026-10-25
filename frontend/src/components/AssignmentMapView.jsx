import React, { useEffect, useRef } from 'react';
import { Card, Empty } from 'antd';
import { EnvironmentOutlined } from '@ant-design/icons';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export const ROUTE_COLORS = [
  '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b',
];

const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

// Each route starts at its own base (technician or contractor site), unlike MapView's single depot
const AssignmentMapView = ({ result, incluirRetorno }) => {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const layerRef = useRef(null);
  const legendRef = useRef(null);

  useEffect(() => {
    if (!result) {
      if (layerRef.current) layerRef.current.remove();
      if (legendRef.current) legendRef.current.remove();
      layerRef.current = null;
      legendRef.current = null;
      return;
    }
    if (!mapRef.current) return;

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

    result.rutas.forEach((asignada, idx) => {
      const color = ROUTE_COLORS[idx % ROUTE_COLORS.length];
      const base = asignada.sede.coordinates;
      const baseLatLng = [base.latitude, base.longitude];

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

      const line = [baseLatLng];
      asignada.ruta.paradas.forEach((stop) => {
        const c = stop.actividad.coordinates;
        if (!c) return;
        const latLng = [c.latitude, c.longitude];
        line.push(latLng);
        bounds.extend(latLng);
        const aprox = stop.actividad.coordenadas_aproximadas;
        L.marker(latLng, {
          icon: L.divIcon({
            className: 'custom-marker',
            html: `<div style="background:${color};color:#fff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px ${aprox ? 'dashed' : 'solid'} #fff;box-shadow:0 2px 5px rgba(0,0,0,.3);">${stop.secuencia}</div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13],
          }),
        })
          .bindPopup(`
            <div style="min-width:200px">
              <h4 style="margin:0 0 6px;color:${color}">${escapeHtml(asignada.responsable)} · parada ${stop.secuencia}</h4>
              <strong>OT ${escapeHtml(stop.actividad.codigo_bia)}</strong> · ${escapeHtml(stop.actividad.or_operador)}<br/>
              ${escapeHtml(stop.actividad.nombre)}<br/>
              <small>${escapeHtml(stop.actividad.direccion)}, ${escapeHtml(stop.actividad.ciudad)}</small><br/>
              ${aprox ? '<small style="color:#d48806">Ubicación aproximada (geocodificada)</small><br/>' : ''}
              <small>Llegada ${stop.hora_llegada_estimada} · Salida ${stop.hora_salida_estimada}</small>
            </div>`)
          .addTo(layerRef.current);
      });
      if (incluirRetorno && line.length > 1) line.push(baseLatLng);
      if (line.length > 1) L.polyline(line, { color, weight: 3, opacity: 0.75 }).addTo(layerRef.current);
    });

    // OTs that could not be assigned but have a location, in gray
    result.sin_asignar.forEach(({ actividad, motivo }) => {
      const c = actividad.coordinates;
      if (!c) return;
      const latLng = [c.latitude, c.longitude];
      bounds.extend(latLng);
      L.circleMarker(latLng, { radius: 7, color: '#595959', fillColor: '#bfbfbf', fillOpacity: 0.9, weight: 2 })
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
        </div>`).join('');
      return div;
    };
    legend.addTo(map);
    legendRef.current = legend;
  }, [result, incluirRetorno]);

  useEffect(() => () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }
  }, []);

  return (
    <Card
      title={<span><EnvironmentOutlined /> Mapa de asignación</span>}
      style={{ height: '100%' }}
      styles={{ body: { height: 'calc(100% - 57px)', padding: 0 } }}
    >
      <div style={{ position: 'relative', height: '100%' }}>
        <div ref={mapRef} style={{ height: '100%', width: '100%' }} />
        {!result && (
          <div style={{ position: 'absolute', inset: 0, zIndex: 1000, background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Empty description="Trae OTs, elige OR y quién atiende, y pulsa Asignar" />
          </div>
        )}
      </div>
    </Card>
  );
};

export default AssignmentMapView;

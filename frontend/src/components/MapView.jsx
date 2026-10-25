import React, { useEffect, useRef } from 'react';
import { Card, Empty } from 'antd';
import { EnvironmentOutlined } from '@ant-design/icons';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

const MapView = ({ optimizationResult, configuration }) => {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const polylinesRef = useRef([]);

  // Colors for different crews
  const crewColors = [
    '#e74c3c', // Red
    '#3498db', // Blue
    '#2ecc71', // Green
    '#f39c12', // Orange
    '#9b59b6', // Purple
    '#1abc9c', // Turquoise
    '#e67e22', // Carrot
    '#34495e', // Dark gray
    '#16a085', // Green Sea
    '#c0392b', // Dark red
  ];

  useEffect(() => {
    if (!mapRef.current) return;

    // Initialize map if not already initialized
    if (!mapInstanceRef.current) {
      mapInstanceRef.current = L.map(mapRef.current).setView([4.6097, -74.0817], 11);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(mapInstanceRef.current);
    }

    // Clear existing markers and polylines
    markersRef.current.forEach(marker => marker.remove());
    polylinesRef.current.forEach(polyline => polyline.remove());
    markersRef.current = [];
    polylinesRef.current = [];

    if (!optimizationResult || !optimizationResult.rutas) {
      return;
    }

    const map = mapInstanceRef.current;
    const bounds = L.latLngBounds([]);

    // Add starting point (depot) marker
    if (configuration && configuration.punto_partida) {
      const depotLatLng = [configuration.punto_partida.latitude, configuration.punto_partida.longitude];

      // Create special icon for depot
      const depotIcon = L.divIcon({
        className: 'depot-marker',
        html: `<div style="background: #000; color: white; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 3px solid #fff; box-shadow: 0 3px 8px rgba(0,0,0,0.4);">
          <span style="font-size: 20px;">🏠</span>
        </div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20],
      });

      const depotMarker = L.marker(depotLatLng, { icon: depotIcon }).addTo(map);
      depotMarker.bindPopup(`
        <div style="min-width: 150px;">
          <h4 style="margin: 0 0 8px 0; color: #000;">Punto de Partida</h4>
          <p style="margin: 2px 0; font-size: 12px;">Lat: ${configuration.punto_partida.latitude}</p>
          <p style="margin: 2px 0; font-size: 12px;">Lon: ${configuration.punto_partida.longitude}</p>
        </div>
      `);
      markersRef.current.push(depotMarker);
      bounds.extend(depotLatLng);
    }

    // Draw routes for each crew
    optimizationResult.rutas.forEach((route, crewIdx) => {
      const color = crewColors[crewIdx % crewColors.length];

      // Extract coordinates for this route - include depot at start
      const routeCoordinates = [];

      // Add depot as first point if configuration exists
      if (configuration && configuration.punto_partida) {
        routeCoordinates.push([configuration.punto_partida.latitude, configuration.punto_partida.longitude]);
      }

      // Add all stops
      route.paradas.forEach((stop, stopIdx) => {
        const coords = stop.actividad.coordinates;
        if (coords && coords.latitude && coords.longitude) {
          routeCoordinates.push([coords.latitude, coords.longitude]);
        } else {
          console.warn(`Parada ${stop.secuencia} (cuadrilla ${route.cuadrilla_id}) tiene coordenadas inválidas:`, coords);
        }
      });

      // Add return to depot if configured
      if (configuration && configuration.incluir_retorno && configuration.punto_partida) {
        routeCoordinates.push([configuration.punto_partida.latitude, configuration.punto_partida.longitude]);
      }

      // Debug: log route info
      console.log(`Cuadrilla ${route.cuadrilla_id}: ${route.paradas.length} paradas`);
      console.log('Coordenadas de ruta:', routeCoordinates);
      routeCoordinates.forEach((coord, idx) => {
        console.log(`  Coord ${idx}: [${coord[0]}, ${coord[1]}]`);
      });

      // Add markers for each stop
      route.paradas.forEach((stop, stopIdx) => {
        const coords = stop.actividad.coordinates;
        if (!coords || !coords.latitude || !coords.longitude) {
          console.error(`Parada ${stop.secuencia} no tiene coordenadas válidas`);
          return;
        }
        const latLng = [coords.latitude, coords.longitude];
        console.log(`  Parada ${stop.secuencia}: [${latLng}]`);

        // Create custom icon with sequence number
        const icon = L.divIcon({
          className: 'custom-marker',
          html: `<div style="background: ${color}; color: white; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">${stop.secuencia}</div>`,
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        });

        const marker = L.marker(latLng, { icon }).addTo(map);

        // Popup with activity details
        const popupContent = `
          <div style="min-width: 200px;">
            <h4 style="margin: 0 0 8px 0; color: ${color};">Cuadrilla ${route.cuadrilla_id} - Parada ${stop.secuencia}</h4>
            <p style="margin: 4px 0;"><strong>${stop.actividad.nombre}</strong></p>
            <p style="margin: 2px 0; font-size: 12px;">${stop.actividad.direccion}</p>
            <p style="margin: 2px 0; font-size: 12px;">${stop.actividad.ciudad}</p>
            <hr style="margin: 8px 0;" />
            <p style="margin: 2px 0; font-size: 12px;"><strong>Servicio:</strong> ${stop.actividad.servicio}</p>
            <p style="margin: 2px 0; font-size: 12px;"><strong>Llegada:</strong> ${stop.hora_llegada_estimada}</p>
            <p style="margin: 2px 0; font-size: 12px;"><strong>Salida:</strong> ${stop.hora_salida_estimada}</p>
            <p style="margin: 2px 0; font-size: 12px;"><strong>Distancia desde anterior:</strong> ${stop.distancia_desde_anterior_km.toFixed(2)} km</p>
          </div>
        `;

        marker.bindPopup(popupContent);
        markersRef.current.push(marker);

        bounds.extend(latLng);
      });

      // Draw polyline for route
      if (routeCoordinates.length > 1) {
        const polyline = L.polyline(routeCoordinates, {
          color: color,
          weight: 3,
          opacity: 0.7,
        }).addTo(map);

        polylinesRef.current.push(polyline);
      }
    });

    // Fit map to show all markers
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }

    // Add legend
    const legend = L.control({ position: 'bottomright' });

    legend.onAdd = function () {
      const div = L.DomUtil.create('div', 'map-legend');
      div.style.background = 'white';
      div.style.padding = '10px';
      div.style.borderRadius = '4px';
      div.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';

      let html = '<h4 style="margin: 0 0 8px 0; font-size: 14px;">Cuadrillas</h4>';

      optimizationResult.rutas.forEach((route, idx) => {
        const color = crewColors[idx % crewColors.length];
        html += `
          <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 20px; height: 3px; background: ${color}; margin-right: 8px;"></div>
            <span style="font-size: 12px;">Cuadrilla ${route.cuadrilla_id} (${route.paradas.length} paradas)</span>
          </div>
        `;
      });

      div.innerHTML = html;
      return div;
    };

    legend.addTo(map);

  }, [optimizationResult, configuration]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  return (
    <Card
      title={
        <span>
          <EnvironmentOutlined /> Mapa de Rutas
        </span>
      }
      style={{ height: '100%' }}
      bodyStyle={{ height: 'calc(100% - 57px)', padding: 0 }}
    >
      {optimizationResult ? (
        <div
          ref={mapRef}
          style={{
            height: '100%',
            width: '100%',
          }}
        />
      ) : (
        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description="Carga y optimiza actividades para ver el mapa de rutas" />
        </div>
      )}
    </Card>
  );
};

export default MapView;

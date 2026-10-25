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

const ClusterMapView = ({ clusterResult, selectedClusters = [] }) => {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const polylinesRef = useRef([]);

  // Colors for different clusters/lotes
  const clusterColors = [
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
    '#8e44ad', // Purple
    '#27ae60', // Green
    '#2980b9', // Blue
    '#d35400', // Orange
    '#7f8c8d', // Gray
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

    if (!clusterResult || !clusterResult.rutas_por_cluster || selectedClusters.length === 0) {
      return;
    }

    const map = mapInstanceRef.current;
    const bounds = L.latLngBounds([]);

    // Filter clusters to show only selected ones
    const clustersToShow = clusterResult.rutas_por_cluster.filter(
      (routeCluster) => selectedClusters.includes(routeCluster.cluster_id)
    );

    // Draw routes for each selected cluster
    clustersToShow.forEach((routeCluster, idx) => {
      const clusterId = routeCluster.cluster_id;
      const route = routeCluster.ruta;
      const color = clusterColors[clusterId % clusterColors.length];

      // Extract coordinates for this route
      const routeCoordinates = [];

      // Add optimal starting point if available
      if (routeCluster.punto_partida_optimo) {
        const startLatLng = [
          routeCluster.punto_partida_optimo.latitude,
          routeCluster.punto_partida_optimo.longitude
        ];
        routeCoordinates.push(startLatLng);
        bounds.extend(startLatLng);

        // Add depot marker
        const depotIcon = L.divIcon({
          className: 'depot-marker',
          html: `<div style="background: ${color}; color: white; border-radius: 50%; width: 35px; height: 35px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 3px solid #fff; box-shadow: 0 3px 8px rgba(0,0,0,0.4);">
            <span style="font-size: 16px;">🏠</span>
          </div>`,
          iconSize: [35, 35],
          iconAnchor: [17, 17],
        });

        const depotMarker = L.marker(startLatLng, { icon: depotIcon }).addTo(map);
        depotMarker.bindPopup(`
          <div style="min-width: 150px;">
            <h4 style="margin: 0 0 8px 0; color: ${color};">Lote ${clusterId} - Punto de Partida</h4>
            <p style="margin: 2px 0; font-size: 12px;">Lat: ${routeCluster.punto_partida_optimo.latitude.toFixed(4)}</p>
            <p style="margin: 2px 0; font-size: 12px;">Lon: ${routeCluster.punto_partida_optimo.longitude.toFixed(4)}</p>
          </div>
        `);
        markersRef.current.push(depotMarker);
      }

      // Add all stops in order
      route.paradas.forEach((stop, stopIdx) => {
        const coords = stop.actividad.coordinates;
        if (coords && coords.latitude && coords.longitude) {
          const latLng = [coords.latitude, coords.longitude];
          routeCoordinates.push(latLng);

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
              <h4 style="margin: 0 0 8px 0; color: ${color};">Lote ${clusterId} - Parada ${stop.secuencia}</h4>
              <p style="margin: 4px 0;"><strong>${stop.actividad.nombre}</strong></p>
              <p style="margin: 2px 0; font-size: 12px;">${stop.actividad.direccion}</p>
              <p style="margin: 2px 0; font-size: 12px;">${stop.actividad.ciudad}</p>
              <hr style="margin: 8px 0;" />
              <p style="margin: 2px 0; font-size: 12px;"><strong>Servicio:</strong> ${stop.actividad.servicio}</p>
              <p style="margin: 2px 0; font-size: 12px;"><strong>Llegada:</strong> ${stop.hora_llegada_estimada}</p>
              <p style="margin: 2px 0; font-size: 12px;"><strong>Salida:</strong> ${stop.hora_salida_estimada}</p>
              <p style="margin: 2px 0; font-size: 12px;"><strong>Distancia:</strong> ${stop.distancia_desde_anterior_km.toFixed(2)} km</p>
            </div>
          `;

          marker.bindPopup(popupContent);
          markersRef.current.push(marker);
          bounds.extend(latLng);
        }
      });

      // Add return to start point if route has return
      if (routeCluster.punto_partida_optimo && routeCoordinates.length > 0) {
        const startLatLng = [
          routeCluster.punto_partida_optimo.latitude,
          routeCluster.punto_partida_optimo.longitude
        ];
        routeCoordinates.push(startLatLng);
      }

      // Draw polyline for route
      if (routeCoordinates.length > 1) {
        const polyline = L.polyline(routeCoordinates, {
          color: color,
          weight: 4,
          opacity: 0.8,
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
      div.style.maxHeight = '300px';
      div.style.overflowY = 'auto';

      let html = '<h4 style="margin: 0 0 8px 0; font-size: 14px;">Lotes en Mapa</h4>';

      clustersToShow.forEach((routeCluster) => {
        const clusterId = routeCluster.cluster_id;
        const route = routeCluster.ruta;
        const color = clusterColors[clusterId % clusterColors.length];
        const viableIcon = route.viable ? '✅' : '⚠️';
        
        html += `
          <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 20px; height: 4px; background: ${color}; margin-right: 8px;"></div>
            <span style="font-size: 12px;">
              Lote ${clusterId} ${viableIcon} (${route.paradas.length} paradas, ${route.distancia_total_km.toFixed(1)} km)
            </span>
          </div>
        `;
      });

      div.innerHTML = html;
      return div;
    };

    // Remove existing legend if any
    mapInstanceRef.current.eachLayer((layer) => {
      if (layer instanceof L.Control) {
        mapInstanceRef.current.removeControl(layer);
      }
    });

    legend.addTo(map);

  }, [clusterResult, selectedClusters]);

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
          <EnvironmentOutlined /> Mapa de Rutas por Lote
        </span>
      }
      style={{ height: '100%' }}
      bodyStyle={{ height: 'calc(100% - 57px)', padding: 0 }}
    >
      {clusterResult && selectedClusters.length > 0 ? (
        <div
          ref={mapRef}
          style={{
            height: '100%',
            width: '100%',
          }}
        />
      ) : (
        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description="Selecciona lotes para ver las rutas en el mapa" />
        </div>
      )}
    </Card>
  );
};

export default ClusterMapView;


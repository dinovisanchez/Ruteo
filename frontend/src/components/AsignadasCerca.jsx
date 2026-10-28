import React from 'react';
import { Tooltip } from 'antd';
import dayjs from 'dayjs';
import { responsableMetabase, ubicacionPrecisa } from '../services/cercania';

const km = (valor) => valor.toLocaleString('es-CO', { maximumFractionDigits: 1 });
const cuando = (a) => `${dayjs(a.fecha_visita).format('ddd D MMM')}${a.hora_visita ? `, ${a.hora_visita}` : ''}`;
const MOSTRADAS = 2;

const Cercana = ({ cercana: c }) => (
  <div className="cerca-item">
    <div className="cerca-quien">{responsableMetabase(c.actividad)} · {km(c.km)} km</div>
    <div className="ot-cell-sub">
      {c.actividad.codigo_bia} · {cuando(c.actividad)}
      {c.mismoDia && <span className="cerca-dia"> · mismo día</span>}
    </div>
  </div>
);

/** The OTs already assigned near a pending OT: who has them, how far and when */
export const AsignadasCerca = ({ actividad, cercanas, radio }) => {
  const lista = cercanas?.[actividad.codigo_bia] || [];
  if (!lista.length) {
    if (!actividad.coordinates) return <span className="muted-text">Sin ubicación</span>;
    if (!ubicacionPrecisa(actividad)) {
      return (
        <Tooltip title="No se encontró su dirección: su punto es el centro del municipio, así que no se sabe qué tiene cerca">
          <span className="muted-text">Ubicada solo por su municipio</span>
        </Tooltip>
      );
    }
    return <span className="muted-text">Ninguna a {km(radio)} km o menos</span>;
  }
  const resto = lista.slice(MOSTRADAS);
  return (
    <div>
      {lista.slice(0, MOSTRADAS).map((c) => <Cercana key={c.actividad.codigo_bia} cercana={c} />)}
      {resto.length > 0 && (
        <Tooltip title={resto.map((c) => <Cercana key={c.actividad.codigo_bia} cercana={c} />)}>
          <span className="cerca-mas">y {resto.length} más</span>
        </Tooltip>
      )}
    </div>
  );
};

// For sorting: first the ones with an assigned OT near on the same day, then by the nearest one
const orden = (lista) => {
  if (!lista?.length) return Infinity;
  const mismoDia = lista.filter((c) => c.mismoDia);
  return mismoDia.length ? Math.min(...mismoDia.map((c) => c.km)) : 1000 + Math.min(...lista.map((c) => c.km));
};

/** Column «Asignadas cerca» for a table of pending OTs; `actividadDe` gets the OT of a row */
export const columnaCerca = (cercanas, radio, actividadDe, ancho = 280) => ({
  title: (
    <Tooltip
      title={`OTs ya asignadas en Metabase, de hoy en adelante, a ${km(radio)} km o menos en línea recta. `
        + 'Primero las del día en que se planearía la OT (su fecha; las vencidas y las sin fecha, hoy)'}
    >
      Asignadas cerca
    </Tooltip>
  ),
  key: 'cerca',
  width: ancho,
  filters: [
    { text: 'Con asignadas cerca', value: 'si' },
    { text: 'Con asignadas cerca ese mismo día', value: 'dia' },
    { text: 'Sin asignadas cerca', value: 'no' },
  ],
  onFilter: (valor, fila) => {
    const lista = cercanas[actividadDe(fila).codigo_bia] || [];
    if (valor === 'dia') return lista.some((c) => c.mismoDia);
    return (valor === 'si') === (lista.length > 0);
  },
  sorter: (x, y) => orden(cercanas[actividadDe(x).codigo_bia]) - orden(cercanas[actividadDe(y).codigo_bia]),
  render: (_, fila) => <AsignadasCerca actividad={actividadDe(fila)} cercanas={cercanas} radio={radio} />,
});

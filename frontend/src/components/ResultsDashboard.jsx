import React, { useEffect, useState } from 'react';
import {
  Segmented, Table, Tooltip, Spin, message,
} from 'antd';
import dayjs from 'dayjs';
import { getResults } from '../services/api';

const ISO_DAY = 'YYYY-MM-DD';
const porcentaje = (valor) => (valor === null || valor === undefined ? '—' : `${Math.round(valor * 100)} %`);
const PERIODOS = {
  semana: { label: 'Últimos 7 días', dias: 6 },
  mes: { label: 'Últimos 30 días', dias: 29 },
  trimestre: { label: 'Últimos 90 días', dias: 89 },
};

/**
 * How Ruteo is doing, for the project KRs: of the OTs it suggested (pending ones sent to a Bia
 * technician or a contractor in a plan of today or a later day), how many ended up assigned that way
 * in Metabase, how many were assigned to someone else and how many are still pending.
 */
const ResultsDashboard = ({ ots, hoy }) => {
  const [periodo, setPeriodo] = useState('semana');
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (!ots?.length) return undefined;
    let cancelado = false;
    setCargando(true);
    getResults({
      // Without the Metabase columns: the backend only needs the OT fields
      actividades: ots.map((a) => ({ ...a, extras: {} })),
      desde: dayjs(hoy).subtract(PERIODOS[periodo].dias, 'day').format(ISO_DAY),
      hasta: dayjs(hoy).add(7, 'day').format(ISO_DAY),
    })
      .then((d) => { if (!cancelado) setDatos(d); })
      .catch((e) => { if (!cancelado) message.error(`No se pudieron calcular los resultados: ${e.message}`); })
      .finally(() => { if (!cancelado) setCargando(false); });
    return () => { cancelado = true; };
  }, [ots, hoy, periodo]);

  if (!ots?.length) {
    return <div className="empty-state"><div className="empty-title">Sin datos</div><div className="empty-text">Extrae las OTs para ver los resultados.</div></div>;
  }
  const total = datos?.total;
  const tiles = total ? [
    { title: 'Sugeridas', value: total.sugeridas, hint: 'OTs pendientes que Ruteo mandó a un técnico o a un contratista' },
    {
      title: 'Quedaron así',
      value: porcentaje(total.aceptacion),
      color: '#248A3D',
      sub: `${total.aceptadas} de ${total.aceptadas + total.cambiadas} ya asignadas`,
      hint: 'De las que ya se asignaron en Metabase, cuántas quedaron con quien sugirió Ruteo',
    },
    { title: 'Cambiadas', value: total.cambiadas, color: '#C93400', hint: 'Se asignaron a otra persona o empresa' },
    { title: 'Siguen por asignar', value: total.pendientes, hint: 'Metabase todavía las trae por asignar' },
    { title: 'Editadas a mano', value: total.editadas, hint: 'Sugerencias que alguien cambió en Ruteo antes de asignarlas' },
    total.sin_dato ? {
      title: 'Sin dato', value: total.sin_dato, hint: 'Ya no vienen en la pregunta (canceladas, vencidas o fuera de sus fechas)',
    } : null,
  ].filter(Boolean) : [];

  const columnasDia = [
    { title: 'Día', dataIndex: 'dia', render: (d) => dayjs(d).format('ddd D MMM') },
    { title: 'Sugeridas', dataIndex: 'sugeridas', align: 'right', width: 100 },
    { title: 'Quedaron así', dataIndex: 'aceptadas', align: 'right', width: 120 },
    { title: 'Cambiadas', dataIndex: 'cambiadas', align: 'right', width: 110 },
    { title: 'Siguen por asignar', dataIndex: 'pendientes', align: 'right', width: 150 },
    { title: '%', dataIndex: 'aceptacion', align: 'right', width: 80, render: porcentaje },
  ];
  const columnasCambios = [
    { title: 'Día', dataIndex: 'dia', width: 120, render: (d) => dayjs(d).format('ddd D MMM') },
    { title: 'OT', dataIndex: 'codigo', width: 180, render: (c) => <span className="ot-code">{c}</span> },
    {
      title: 'Ruteo sugirió',
      dataIndex: 'sugerido',
      render: (s, f) => (f.editada ? <Tooltip title="Se editó a mano en Ruteo">{s} ✎</Tooltip> : s),
    },
    { title: 'Quedó en Metabase', dataIndex: 'quedo' },
  ];
  const destinos = datos?.por_destino;

  return (
    <Spin spinning={cargando}>
      <div className="results-head">
        <Segmented
          value={periodo}
          onChange={setPeriodo}
          options={Object.entries(PERIODOS).map(([value, p]) => ({ value, label: p.label }))}
        />
        <span className="muted-text">
          Cuenta las sugerencias de los planes de hoy en adelante calculados en esta app, con lo que trae ahora Metabase
        </span>
      </div>
      {total && !total.sugeridas ? (
        <div className="empty-state">
          <div className="empty-title">Todavía no hay sugerencias guardadas</div>
          <div className="empty-text">Se guardan cada vez que la app calcula el plan de hoy o de un día próximo.</div>
        </div>
      ) : null}
      {total && total.sugeridas > 0 && (
        <>
          <div className="kpi-row">
            {tiles.map((t) => (
              <div key={t.title} className="kpi static" title={t.hint}>
                <span className="kpi-title">{t.title}</span>
                <span className="kpi-value" style={t.color ? { color: t.color } : undefined}>{t.value}</span>
                {t.sub && <span className="kpi-sub">{t.sub}</span>}
              </div>
            ))}
          </div>
          {destinos && (
            <div className="summary-note">
              <span>
                Técnicos Bia: {porcentaje(destinos.tecnico.aceptacion)} quedaron así ({destinos.tecnico.sugeridas} sugeridas)
              </span>
              <span>
                Contratistas: {porcentaje(destinos.contratista.aceptacion)} quedaron así ({destinos.contratista.sugeridas} sugeridas)
              </span>
            </div>
          )}
          <h3 className="section-title">Por día</h3>
          <Table
            className="plain-table"
            size="small"
            rowKey="dia"
            columns={columnasDia}
            dataSource={datos.por_dia}
            pagination={false}
          />
          <h3 className="section-title">Cambiadas: quedaron con otra persona o empresa</h3>
          <Table
            className="plain-table"
            size="small"
            rowKey={(f) => `${f.dia}|${f.codigo}`}
            columns={columnasCambios}
            dataSource={datos.cambiadas}
            locale={{
              emptyText: total.aceptadas
                ? 'Ninguna: todas las asignadas quedaron como sugirió Ruteo'
                : 'Todavía no se ha asignado en Metabase ninguna de las sugeridas',
            }}
            pagination={{ pageSize: 20, hideOnSinglePage: true, showSizeChanger: false }}
          />
        </>
      )}
    </Spin>
  );
};

export default ResultsDashboard;

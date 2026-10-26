import React, { useMemo, useState } from 'react';
import {
  Table, Collapse, Button, Tooltip, Descriptions, Select,
} from 'antd';
import { DownloadOutlined, EnvironmentOutlined, LockOutlined, EditOutlined } from '@ant-design/icons';
import AssignmentMapView, { ROUTE_COLORS } from './AssignmentMapView';
import { formatExtra } from './OtsTable';
import { formatCop } from '../services/format';

const km = (value) => (value ?? 0).toLocaleString('es-CO', { maximumFractionDigits: 1 });
const hhmm = (value) => (value ? value.slice(0, 5) : '');

const DESTINO = {
  tecnico: 'Técnico Bia',
  contratista: 'Contratista',
  externo: 'Externo',
  sin_asignar: 'Sin asignar',
};

const Dot = ({ color }) => <span className="dot" style={{ background: color }} />;

const situacion = (valor) => (valor === 'asignada'
  ? <span className="state"><Dot color="#34C759" />Asignada</span>
  : <span className="state"><Dot color="#FF9500" />Por asignar</span>);

const otCell = (actividad, codigo, nuevas) => (
  <div className="ot-cell">
    <span className="ot-code">{codigo}</span>
    {nuevas?.has(codigo) && <span className="new-badge">nueva</span>}
    {actividad?.coordenadas_aproximadas && (
      <Tooltip title="Ubicación aproximada: geocodificada a partir de la dirección o el municipio">
        <EnvironmentOutlined className="approx-icon" />
      </Tooltip>
    )}
    <div className="ot-cell-sub">{[actividad?.servicio, actividad?.nombre, actividad?.ciudad].filter(Boolean).join(' · ')}</div>
  </div>
);

const DetailRow = ({ row, alternativas }) => {
  const { decision: d, actividad } = row;
  const extras = Object.entries(actividad?.extras || {});
  return (
    <Descriptions size="small" column={{ xs: 1, md: 2, xl: 3 }}>
      <Descriptions.Item label="Por qué">{d.motivo}</Descriptions.Item>
      <Descriptions.Item label="OR">{actividad?.or_operador}</Descriptions.Item>
      <Descriptions.Item label="Personas">{actividad?.personas_requeridas || 1}</Descriptions.Item>
      <Descriptions.Item label="Sale de">{d.sede}</Descriptions.Item>
      <Descriptions.Item label="Km a la base">
        {d.distancia_base_km === null || d.distancia_base_km === undefined ? '' : km(d.distancia_base_km)}
      </Descriptions.Item>
      <Descriptions.Item label="Dirección">{actividad?.direccion}</Descriptions.Item>
      <Descriptions.Item label="Otras opciones">
        {alternativas.map((a) => `${a.empresa} (${a.ciudad}) · ${km(a.distancia_km)} km`).join(' / ') || '—'}
      </Descriptions.Item>
      {extras.map(([key, value]) => <Descriptions.Item key={key} label={key}>{formatExtra(value)}</Descriptions.Item>)}
    </Descriptions>
  );
};

const csvValue = (value) => {
  const text = String(value ?? '');
  return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

const exportCsv = (rows, dia) => {
  const extraKeys = [];
  rows.forEach(({ actividad }) => Object.keys(actividad?.extras || {}).forEach((k) => {
    if (!extraKeys.includes(k)) extraKeys.push(k);
  }));

  // ";" and decimal comma so it opens directly in Excel configured in Spanish
  const header = ['Día', 'OT', 'Situación', 'OR', 'Ciudad', 'Dirección', 'Tipo de OT', 'Personas', 'Enviar a', 'Responsable',
    'Fijada', 'Sale de', 'Km a la base', 'Secuencia', 'Llegada', 'Salida', 'Ubicación aproximada', 'Motivo', ...extraKeys];
  const lines = rows.map(({ decision: d, actividad: a, parada }) => [
    dia, d.codigo_bia, d.situacion === 'asignada' ? 'Asignada' : 'Por asignar', a?.or_operador, a?.ciudad, a?.direccion,
    a?.servicio, a?.personas_requeridas, DESTINO[d.enviar_a], d.responsable, d.fijada ? 'Sí' : 'No', d.sede,
    d.distancia_base_km === null || d.distancia_base_km === undefined ? '' : String(d.distancia_base_km).replace('.', ','),
    parada?.secuencia, hhmm(parada?.hora_llegada_estimada), hhmm(parada?.hora_salida_estimada),
    a?.coordenadas_aproximadas ? 'Sí' : 'No', d.motivo, ...extraKeys.map((k) => formatExtra(a?.extras?.[k])),
  ]);
  const csv = [header, ...lines].map((row) => row.map(csvValue).join(';')).join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `plan-ots-${dia || new Date().toISOString().split('T')[0]}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const stopColumns = (nuevas, situaciones) => [
  { title: '#', dataIndex: 'secuencia', width: 40 },
  { title: 'OT', render: (_, p) => otCell(p.actividad, p.actividad.codigo_bia, nuevas) },
  { title: 'Estado', width: 120, render: (_, p) => situacion(situaciones[p.actividad.codigo_bia]) },
  { title: 'Dirección', render: (_, p) => p.actividad.direccion },
  { title: 'Llega', dataIndex: 'hora_llegada_estimada', width: 70, render: hhmm },
  { title: 'Sale', dataIndex: 'hora_salida_estimada', width: 70, render: hhmm },
  { title: 'Viaje', dataIndex: 'tiempo_desplazamiento_minutos', width: 80, render: (v) => `${v} min` },
];

/**
 * Options to change who attends an OT: let the app decide, an available technician,
 * the nearest contractor of its OR, or a specific contractor.
 */
const editOptions = (tecnicos, empresas, alternativas, yaAsignada) => [
  {
    label: 'Automático',
    options: [{ value: 'auto', label: yaAsignada ? 'Que la app la reasigne' : 'Que decida la app' }],
  },
  {
    label: 'Técnicos',
    options: tecnicos.map((t) => ({
      value: `tecnico:${t.id}`,
      label: t.disponible ? t.nombre : `${t.nombre} (no disponible)`,
      disabled: !t.disponible,
    })),
  },
  {
    label: 'Contratistas',
    options: [
      { value: 'contratista', label: 'El más cercano de su OR' },
      // The nearest options for this OT first, then the rest
      ...[...alternativas, ...empresas.filter((e) => !alternativas.some((a) => a.id === e.id))]
        .map((e) => ({ value: `empresa:${e.id}`, label: e.km !== undefined ? `${e.nombre} · ${km(e.km)} km` : e.nombre })),
    ],
  },
];

// Who attends the OT; the pencil opens the list to send it to someone else
const EnviarA = ({ decision: d, editada, options, onEdit, editing }) => {
  const [abierto, setAbierto] = useState(false);
  return (
    <div className="assignee">
      <div className="assignee-name">
        {d.responsable || DESTINO[d.enviar_a]}
        {d.fijada && !editada && (
          <Tooltip title="Se respeta la asignación de Metabase"><LockOutlined className="muted-icon" /></Tooltip>
        )}
        {onEdit && (
          <Tooltip title="Enviar a otro técnico o contratista">
            <Button
              type="text"
              size="small"
              className="edit-button"
              icon={<EditOutlined />}
              disabled={editing}
              onClick={() => setAbierto(true)}
            />
          </Tooltip>
        )}
      </div>
      <div className="assignee-sub">{DESTINO[d.enviar_a]}{editada ? ' · editada a mano' : ''}</div>
      {abierto && (
        <Select
          size="small"
          autoFocus
          defaultOpen
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="Enviar a…"
          value={editada}
          onChange={(value) => { setAbierto(false); onEdit(d.codigo_bia, value, d.situacion); }}
          onDropdownVisibleChange={(visible) => { if (!visible) setAbierto(false); }}
          options={options}
          popupMatchSelectWidth={false}
          style={{ width: 220, marginTop: 4 }}
        />
      )}
    </div>
  );
};

const AssignmentResults = ({
  result, ots, nuevas, incluirRetorno, view = 'lista', visibles = null, fijas = {}, onEdit, tecnicos = [],
  empresas = [], editing,
}) => {
  const situaciones = useMemo(
    () => Object.fromEntries((result?.decisiones || []).map((d) => [d.codigo_bia, d.situacion])),
    [result],
  );

  if (!result) return null;
  const { metricas } = result;

  // Activity and stop of each OT, to show its data next to the decision
  const actividades = {};
  const paradas = {};
  (ots || []).forEach((a) => { actividades[a.codigo_bia] = a; });
  result.rutas.forEach((r) => r.ruta.paradas.forEach((p) => {
    actividades[p.actividad.codigo_bia] = p.actividad;
    paradas[p.actividad.codigo_bia] = p;
  }));
  result.sin_asignar.forEach(({ actividad }) => { actividades[actividad.codigo_bia] = actividad; });
  const recomendaciones = Object.fromEntries(result.recomendaciones.map((r) => [r.codigo_bia, r]));
  const allRows = result.decisiones.map((d) => ({
    key: d.codigo_bia,
    decision: d,
    actividad: actividades[d.codigo_bia],
    parada: paradas[d.codigo_bia],
  }));
  const rows = visibles ? allRows.filter((r) => visibles.has(r.decision.codigo_bia)) : allRows;

  const resumen = [
    `${result.total_actividades} OTs`,
    `${metricas.ots_ya_asignadas ?? 0} asignadas`,
    `${metricas.ots_pendientes ?? 0} por asignar`,
  ];
  const reparto = [
    `${metricas.ots_con_tecnicos} a técnicos Bia`,
    `${metricas.ots_con_contratistas} a contratistas`,
    metricas.ots_externas ? `${metricas.ots_externas} externas` : null,
    metricas.ots_sin_asignar ? `${metricas.ots_sin_asignar} sin asignar` : null,
    `${km(result.distancia_total_km)} km`,
    metricas.costo_total !== null && metricas.costo_total !== undefined ? formatCop(metricas.costo_total) : null,
  ].filter(Boolean);
  const transito = (metricas.transito || []).filter((z) => z.recargo_pct || z.minutos_extra)
    .map((z) => `${z.nombre} +${z.recargo_pct} %${z.minutos_extra ? ` +${z.minutos_extra} min` : ''}`).join(', ');
  const avisos = [
    metricas.rutas_no_viables > 0 ? `${metricas.rutas_no_viables} rutas pasan de la jornada` : null,
    metricas.tiempos_por_vias ? null : (metricas.aviso_vias || 'Tiempos estimados en línea recta'),
    metricas.asignadas_sin_fecha > 0 ? `${metricas.asignadas_sin_fecha} asignadas sin fecha en Metabase` : null,
    metricas.ots_sin_lista_or > 0 ? `${metricas.ots_sin_lista_or} OTs de OR sin contratistas en su zona` : null,
  ].filter(Boolean);

  const columns = [
    {
      title: 'OT',
      fixed: 'left',
      width: 260,
      render: (_, r) => otCell(r.actividad, r.decision.codigo_bia, nuevas),
    },
    {
      title: 'Estado',
      width: 120,
      render: (_, r) => situacion(r.decision.situacion),
    },
    {
      title: 'Enviar a',
      width: 280,
      sorter: (a, b) => (a.decision.responsable || '~').localeCompare(b.decision.responsable || '~'),
      render: (_, r) => {
        const d = r.decision;
        const alternativas = [recomendaciones[d.codigo_bia]?.elegido, ...(recomendaciones[d.codigo_bia]?.alternativas || [])]
          .filter((a) => a?.empresa_id)
          .map((a) => ({ id: a.empresa_id, nombre: `${a.empresa} (${a.ciudad})`, km: a.distancia_km }));
        return (
          <EnviarA
            decision={d}
            editada={fijas[d.codigo_bia]}
            options={editOptions(tecnicos, empresas, alternativas, d.situacion === 'asignada')}
            onEdit={onEdit}
            editing={editing}
          />
        );
      },
    },
    {
      title: 'Llega',
      width: 70,
      sorter: (a, b) => (a.decision.hora_llegada || '~').localeCompare(b.decision.hora_llegada || '~'),
      render: (_, r) => hhmm(r.decision.hora_llegada),
    },
    {
      title: 'Por qué',
      render: (_, r) => (
        <Tooltip title={r.decision.motivo} placement="topLeft">
          <span className="motivo">{r.decision.motivo}</span>
        </Tooltip>
      ),
    },
  ];

  const rutasVisibles = result.rutas
    .map((r, idx) => ({ r, idx }))
    .filter(({ r }) => !visibles || r.ruta.paradas.some((p) => visibles.has(p.actividad.codigo_bia)));

  return (
    <>
      <div className="summary">
        <div>
          <span className="summary-main">{resumen.join(' · ')}</span>
          <span className="summary-sub">{reparto.join(' · ')}</span>
          {visibles && <span className="summary-sub">Mostrando {rows.length} de {allRows.length}</span>}
        </div>
        <Tooltip title="Descargar el plan en CSV">
          <Button type="text" icon={<DownloadOutlined />} onClick={() => exportCsv(allRows, metricas.dia)} />
        </Tooltip>
      </div>
      <div className="summary-note">
        {metricas.tiempos_por_vias ? <span>Tiempos por carretera{transito ? ` · tránsito ${transito}` : ''}</span> : null}
        {avisos.map((a) => <span key={a} className="warn-text">{a}</span>)}
      </div>

      {view === 'lista' && (
        <Table
          className="plain-table"
          size="middle"
          columns={columns}
          dataSource={rows}
          // Minimum width: "Por qué" takes the rest of the row
          scroll={{ x: 980 }}
          pagination={{ pageSize: 30, hideOnSinglePage: true, showSizeChanger: false }}
          expandable={{
            expandedRowRender: (r) => (
              <DetailRow row={r} alternativas={recomendaciones[r.decision.codigo_bia]?.alternativas || []} />
            ),
          }}
        />
      )}

      {view === 'mapa' && (
        <div className="map-panel">
          <AssignmentMapView result={result} incluirRetorno={incluirRetorno} visibles={visibles} situaciones={situaciones} />
        </div>
      )}

      {view === 'rutas' && (
        <Collapse
          className="routes-list"
          ghost
          items={rutasVisibles.map(({ r, idx }) => {
            const yaAsignadas = r.ruta.paradas.filter((p) => situaciones[p.actividad.codigo_bia] === 'asignada').length;
            const paradasVisibles = visibles ? r.ruta.paradas.filter((p) => visibles.has(p.actividad.codigo_bia)) : r.ruta.paradas;
            return {
              key: r.responsable_id,
              label: (
                <div className="route-head">
                  <Dot color={ROUTE_COLORS[idx % ROUTE_COLORS.length]} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="route-title">{r.responsable}</div>
                    <div className="route-sub">
                      {r.ruta.paradas.length} OTs{yaAsignadas ? ` (${yaAsignadas} asignadas)` : ''}
                      {' · '}{hhmm(r.ruta.hora_inicio)}–{hhmm(r.ruta.hora_fin)} · {km(r.ruta.distancia_total_km)} km
                      {r.personas > 1 ? ` · ${r.personas} personas` : ''}
                      {r.costo !== null && r.costo !== undefined ? ` · ${formatCop(r.costo)}` : ''}
                      {' · sale de '}{r.sede.ciudad}
                    </div>
                  </div>
                  {!r.ruta.viable && <span className="warn-text">Pasa de la jornada</span>}
                </div>
              ),
              children: (
                <Table
                  className="plain-table"
                  rowKey="secuencia"
                  size="small"
                  pagination={false}
                  columns={stopColumns(nuevas, situaciones)}
                  dataSource={paradasVisibles}
                  scroll={{ x: 'max-content' }}
                />
              ),
            };
          })}
        />
      )}
    </>
  );
};

export default AssignmentResults;

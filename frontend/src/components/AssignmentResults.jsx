import React, { useMemo } from 'react';
import {
  Tag, Table, Collapse, Button, Space, Typography, Tooltip, Descriptions, Select,
} from 'antd';
import {
  CheckCircleFilled, CloseCircleFilled, DownloadOutlined, EnvironmentOutlined, WarningFilled, LockOutlined,
} from '@ant-design/icons';
import AssignmentMapView, { ROUTE_COLORS } from './AssignmentMapView';
import { formatExtra } from './OtsTable';
import { formatCop } from '../services/format';

const { Text } = Typography;

const km = (value) => (value ?? 0).toLocaleString('es-CO', { maximumFractionDigits: 1 });
const hhmm = (value) => (value ? value.slice(0, 5) : '');

const DESTINO = {
  tecnico: { label: 'Técnico Bia', color: 'blue' },
  contratista: { label: 'Contratista', color: 'purple' },
  externo: { label: 'Externo', color: 'default' },
  sin_asignar: { label: 'Sin asignar', color: 'red' },
};

const matchesFilter = (decision, filtro) => (
  filtro === 'todas'
  || (filtro === 'asignadas' && decision.situacion === 'asignada')
  || (filtro === 'pendientes' && decision.situacion === 'pendiente')
);

const otCell = (actividad, codigo, nuevas) => (
  <div className="ot-cell">
    <Space size={4}>
      <Text strong>{codigo}</Text>
      {nuevas?.has(codigo) && <Tag color="green" bordered={false}>Nueva</Tag>}
      {actividad?.coordenadas_aproximadas && (
        <Tooltip title="Ubicación aproximada: geocodificada a partir de la dirección o el municipio">
          <EnvironmentOutlined style={{ color: '#FF9500' }} />
        </Tooltip>
      )}
    </Space>
    <div className="ot-cell-sub">{[actividad?.servicio, actividad?.ciudad].filter(Boolean).join(' · ')}</div>
  </div>
);

const situacionTag = (situacion, actividad) => (situacion === 'asignada'
  ? (
    <Tooltip title={[actividad?.asignado_a, actividad?.contratista_asignado].filter(Boolean).join(' · ') || null}>
      <Tag color="green" bordered={false}>Ya asignada</Tag>
    </Tooltip>
  )
  : <Tag color="orange" bordered={false}>Por asignar</Tag>);

const DetailRow = ({ row, alternativas }) => {
  const { decision: d, actividad } = row;
  const extras = Object.entries(actividad?.extras || {});
  return (
    <Descriptions size="small" column={{ xs: 1, md: 2, xl: 3 }} bordered>
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
    dia, d.codigo_bia, d.situacion === 'asignada' ? 'Ya asignada' : 'Por asignar', a?.or_operador, a?.ciudad, a?.direccion,
    a?.servicio, a?.personas_requeridas, DESTINO[d.enviar_a].label, d.responsable, d.fijada ? 'Sí' : 'No', d.sede,
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
  { title: 'Situación', render: (_, p) => situacionTag(situaciones[p.actividad.codigo_bia], p.actividad) },
  { title: 'Personas', width: 80, render: (_, p) => p.actividad.personas_requeridas },
  { title: 'Dirección', render: (_, p) => p.actividad.direccion },
  { title: 'Llegada', dataIndex: 'hora_llegada_estimada', width: 80, render: hhmm },
  { title: 'Salida', dataIndex: 'hora_salida_estimada', width: 80, render: hhmm },
  { title: 'Viaje', dataIndex: 'tiempo_desplazamiento_minutos', width: 80, render: (v) => `${v} min` },
  { title: 'Km', dataIndex: 'distancia_desde_anterior_km', width: 70, render: km },
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

const Kpi = ({ title, value, color }) => (
  <div className="kpi-tile">
    <div className="kpi-title">{title}</div>
    <div className="kpi-value" style={color ? { color } : undefined}>{value}</div>
  </div>
);

const AssignmentResults = ({
  result, ots, nuevas, incluirRetorno, view = 'lista', filtro = 'todas', fijas = {}, onEdit, tecnicos = [],
  empresas = [], editing,
}) => {
  const situaciones = useMemo(
    () => Object.fromEntries((result?.decisiones || []).map((d) => [d.codigo_bia, d.situacion])),
    [result],
  );
  const visibles = useMemo(() => (filtro === 'todas' ? null : new Set(
    (result?.decisiones || []).filter((d) => matchesFilter(d, filtro)).map((d) => d.codigo_bia),
  )), [result, filtro]);

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
  const rows = allRows.filter((r) => matchesFilter(r.decision, filtro));

  const kpis = [
    { title: 'OTs del día', value: result.total_actividades },
    { title: 'Ya asignadas', value: metricas.ots_ya_asignadas ?? 0, color: '#248A3D' },
    { title: 'Por asignar', value: metricas.ots_pendientes ?? 0, color: '#C93400' },
    { title: 'Técnicos Bia', value: metricas.ots_con_tecnicos, color: '#007AFF' },
    { title: 'Contratistas', value: metricas.ots_con_contratistas, color: '#AF52DE' },
  ];
  if (metricas.ots_externas) kpis.push({ title: 'Externas', value: metricas.ots_externas });
  if (metricas.ots_sin_asignar) kpis.push({ title: 'Sin asignar', value: metricas.ots_sin_asignar, color: '#FF3B30' });
  kpis.push({ title: 'Km', value: km(result.distancia_total_km) });
  if (metricas.costo_total !== null && metricas.costo_total !== undefined) {
    kpis.push({ title: 'Costo técnicos', value: formatCop(metricas.costo_total) });
  }
  const transito = (metricas.transito || []).filter((z) => z.recargo_pct || z.minutos_extra)
    .map((z) => `${z.nombre} +${z.recargo_pct}%${z.minutos_extra ? ` +${z.minutos_extra} min` : ''}`).join(', ');

  const columns = [
    {
      title: 'OT',
      fixed: 'left',
      width: 200,
      render: (_, r) => otCell(r.actividad, r.decision.codigo_bia, nuevas),
    },
    {
      title: 'Situación',
      width: 110,
      render: (_, r) => situacionTag(r.decision.situacion, r.actividad),
    },
    {
      title: 'Enviar a',
      width: 250,
      filters: Object.entries(DESTINO).map(([value, { label }]) => ({ text: label, value })),
      onFilter: (value, r) => r.decision.enviar_a === value,
      sorter: (a, b) => (a.decision.responsable || '~').localeCompare(b.decision.responsable || '~'),
      render: (_, r) => {
        const d = r.decision;
        const editada = fijas[d.codigo_bia];
        const alternativas = [recomendaciones[d.codigo_bia]?.elegido, ...(recomendaciones[d.codigo_bia]?.alternativas || [])]
          .filter((a) => a?.empresa_id)
          .map((a) => ({ id: a.empresa_id, nombre: `${a.empresa} (${a.ciudad})`, km: a.distancia_km }));
        return (
          <div>
            <Space size={4} wrap>
              <Tag color={DESTINO[d.enviar_a].color} bordered={false}>{DESTINO[d.enviar_a].label}</Tag>
              {d.fijada && !editada && (
                <Tooltip title="Se respeta la asignación de Metabase">
                  <LockOutlined style={{ color: '#8E8E93' }} />
                </Tooltip>
              )}
              {editada && <Tag color="gold" bordered={false}>Editada</Tag>}
            </Space>
            {d.responsable && <div className="responsable">{d.responsable}</div>}
            {onEdit && (
              <Select
                size="small"
                variant="filled"
                allowClear
                showSearch
                optionFilterProp="label"
                placeholder="Cambiar…"
                disabled={editing}
                value={editada}
                onChange={(value) => onEdit(d.codigo_bia, value, d.situacion)}
                options={editOptions(tecnicos, empresas, alternativas, d.situacion === 'asignada')}
                popupMatchSelectWidth={false}
                style={{ width: 220, marginTop: 4 }}
              />
            )}
          </div>
        );
      },
    },
    {
      title: 'Llegada',
      width: 80,
      sorter: (a, b) => (a.decision.hora_llegada || '~').localeCompare(b.decision.hora_llegada || '~'),
      render: (_, r) => <Text strong>{hhmm(r.decision.hora_llegada)}</Text>,
    },
    {
      title: 'Por qué',
      render: (_, r) => <Text type="secondary" className="motivo">{r.decision.motivo}</Text>,
    },
  ];

  const rutasVisibles = result.rutas
    .map((r, idx) => ({ r, idx }))
    .filter(({ r }) => !visibles || r.ruta.paradas.some((p) => visibles.has(p.actividad.codigo_bia)));

  return (
    <>
      <div className="kpi-grid">
        {kpis.map((k) => <Kpi key={k.title} {...k} />)}
      </div>

      <div className="status-row">
        {result.viable_en_un_dia
          ? <span className="status-chip ok"><CheckCircleFilled /> Todo cabe en la jornada</span>
          : metricas.rutas_no_viables > 0 && (
            <span className="status-chip bad"><CloseCircleFilled /> {metricas.rutas_no_viables} rutas superan la jornada</span>
          )}
        <span className={`status-chip${metricas.tiempos_por_vias ? '' : ' warn'}`}>
          {metricas.tiempos_por_vias ? 'Tiempos por las vías (OSRM)' : (metricas.aviso_vias || 'Tiempos estimados en línea recta')}
          {transito ? ` · tránsito ${transito}` : ''}
        </span>
        {metricas.parejas > 0 && <span className="status-chip">{metricas.parejas} pareja(s) para OTs de 2 personas</span>}
        {metricas.ots_otros_dias > 0 && <span className="status-chip">{metricas.ots_otros_dias} asignadas para otros días</span>}
        {metricas.asignadas_sin_fecha > 0 && (
          <span className="status-chip warn">{metricas.asignadas_sin_fecha} asignadas sin fecha en Metabase</span>
        )}
        {metricas.ots_sin_lista_or > 0 && (
          <span className="status-chip warn">
            <WarningFilled /> {metricas.ots_sin_lista_or} OTs de OR sin contratistas en su zona
          </span>
        )}
        <Button size="small" shape="round" icon={<DownloadOutlined />} onClick={() => exportCsv(allRows, metricas.dia)}>
          CSV
        </Button>
      </div>

      {view === 'lista' && (
        <div className="glass-panel">
          <Table
            size="middle"
            columns={columns}
            dataSource={rows}
            // Minimum width: "Por qué" takes the rest of the row and wraps instead of overflowing
            scroll={{ x: 980 }}
            pagination={{ pageSize: 25, hideOnSinglePage: true, showSizeChanger: false }}
            expandable={{
              expandedRowRender: (r) => (
                <DetailRow row={r} alternativas={recomendaciones[r.decision.codigo_bia]?.alternativas || []} />
              ),
            }}
          />
        </div>
      )}

      {view === 'mapa' && (
        <div className="map-panel">
          <AssignmentMapView result={result} incluirRetorno={incluirRetorno} visibles={visibles} situaciones={situaciones} />
        </div>
      )}

      {view === 'rutas' && (
        <Collapse
          className="routes-list"
          bordered={false}
          items={rutasVisibles.map(({ r, idx }) => {
            const yaAsignadas = r.ruta.paradas.filter((p) => situaciones[p.actividad.codigo_bia] === 'asignada').length;
            return {
              key: r.responsable_id,
              label: (
                <div className="route-head">
                  <span className="route-dot" style={{ background: ROUTE_COLORS[idx % ROUTE_COLORS.length] }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="route-title">{r.responsable}</div>
                    <div className="route-sub">
                      {r.tipo === 'tecnico' ? 'Técnico Bia' : 'Contratista'} · sale de {r.sede.empresa} ({r.sede.ciudad})
                      {' · '}{hhmm(r.ruta.hora_inicio)}–{hhmm(r.ruta.hora_fin)} · {km(r.ruta.distancia_total_km)} km
                      {r.costo !== null && r.costo !== undefined ? ` · ${formatCop(r.costo)}/día` : ''}
                    </div>
                  </div>
                  <Space size={4} wrap>
                    <Tag bordered={false}>{r.ruta.paradas.length} OTs</Tag>
                    {yaAsignadas > 0 && <Tag color="green" bordered={false}>{yaAsignadas} ya asignadas</Tag>}
                    {r.personas > 1 && <Tag color="blue" bordered={false}>{r.personas} personas</Tag>}
                    {r.ruta.viable
                      ? <Tag color="success" bordered={false}>Cabe en la jornada</Tag>
                      : <Tag color="error" bordered={false}>Supera la jornada</Tag>}
                  </Space>
                </div>
              ),
              children: (
                <Table
                  rowKey="secuencia"
                  size="small"
                  pagination={false}
                  columns={stopColumns(nuevas, situaciones)}
                  dataSource={r.ruta.paradas}
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

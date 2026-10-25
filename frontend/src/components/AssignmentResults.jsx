import React, { useMemo } from 'react';
import {
  Card, Row, Col, Statistic, Tag, Table, Collapse, Alert, Button, Space, Typography, Tooltip, Descriptions, Select,
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, DownloadOutlined, EnvironmentOutlined, WarningOutlined, LockOutlined,
} from '@ant-design/icons';
import AssignmentMapView, { ROUTE_COLORS } from './AssignmentMapView';
import { formatExtra } from './OtsTable';
import { formatCop } from '../services/format';

const { Text } = Typography;

const km = (value) => (value ?? 0).toLocaleString('es-CO', { maximumFractionDigits: 1 });
const hhmm = (value) => (value ? value.slice(0, 5) : '');

const DESTINO = {
  tecnico: { label: 'Técnico in-house', color: 'blue' },
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
  <Space size={4}>
    <Text strong>{codigo}</Text>
    {nuevas?.has(codigo) && <Tag color="green">Nueva</Tag>}
    {actividad?.coordenadas_aproximadas && (
      <Tooltip title="Ubicación aproximada: geocodificada a partir de la dirección o el municipio">
        <EnvironmentOutlined style={{ color: '#FF9500' }} />
      </Tooltip>
    )}
  </Space>
);

const situacionTag = (situacion, actividad) => (situacion === 'asignada'
  ? (
    <Tooltip title={[actividad?.asignado_a, actividad?.contratista_asignado].filter(Boolean).join(' · ') || null}>
      <Tag color="green">Ya asignada</Tag>
    </Tooltip>
  )
  : <Tag color="orange">Por asignar</Tag>);

const ExtrasDetail = ({ actividad }) => {
  const rows = Object.entries(actividad?.extras || {});
  if (!rows.length) return <Text type="secondary">Sin columnas adicionales</Text>;
  return (
    <Descriptions size="small" column={3} bordered>
      {rows.map(([key, value]) => <Descriptions.Item key={key} label={key}>{formatExtra(value)}</Descriptions.Item>)}
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
  { title: 'OR', render: (_, p) => p.actividad.or_operador },
  { title: 'Tipo de OT', render: (_, p) => <Tag color="blue">{p.actividad.servicio}</Tag> },
  { title: 'Personas', width: 80, render: (_, p) => p.actividad.personas_requeridas },
  { title: 'Dirección', render: (_, p) => `${p.actividad.direccion}${p.actividad.ciudad ? `, ${p.actividad.ciudad}` : ''}` },
  { title: 'Llegada', dataIndex: 'hora_llegada_estimada', width: 80, render: hhmm },
  { title: 'Salida', dataIndex: 'hora_salida_estimada', width: 80, render: hhmm },
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

const AssignmentResults = ({
  result, ots, nuevas, incluirRetorno, filtro = 'todas', fijas = {}, onEdit, tecnicos = [], empresas = [], editing,
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

  const stats = [
    { title: 'OTs del día', value: result.total_actividades },
    { title: 'Ya asignadas', value: metricas.ots_ya_asignadas ?? 0, color: '#34C759' },
    { title: 'Por asignar', value: metricas.ots_pendientes ?? 0, color: '#FF9500' },
    { title: 'A técnicos', value: metricas.ots_con_tecnicos, color: '#007AFF' },
    { title: 'A contratistas', value: metricas.ots_con_contratistas, color: '#AF52DE' },
  ];
  if (metricas.ots_externas) stats.push({ title: 'Externas', value: metricas.ots_externas });
  stats.push(
    { title: 'Sin asignar', value: metricas.ots_sin_asignar, color: metricas.ots_sin_asignar ? '#FF3B30' : undefined },
    { title: 'Km totales', value: km(result.distancia_total_km) },
  );
  if (metricas.costo_total !== null && metricas.costo_total !== undefined) {
    stats.push({ title: 'Costo técnicos (día)', value: formatCop(metricas.costo_total) });
  }

  // The decision and its reason go first so they are visible without scrolling
  const columns = [
    {
      title: 'OT',
      fixed: 'left',
      render: (_, r) => otCell(r.actividad, r.decision.codigo_bia, nuevas),
    },
    {
      title: 'Situación',
      render: (_, r) => situacionTag(r.decision.situacion, r.actividad),
    },
    {
      title: 'Enviar a',
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
          <Space direction="vertical" size={2} style={{ minWidth: 210 }}>
            <Space size={4} wrap>
              <Tag color={DESTINO[d.enviar_a].color}>{DESTINO[d.enviar_a].label}</Tag>
              {d.fijada && !editada && (
                <Tooltip title="Se respeta la asignación de Metabase">
                  <LockOutlined style={{ color: '#8E8E93' }} />
                </Tooltip>
              )}
              {editada && <Tag color="gold">Editada</Tag>}
            </Space>
            {d.responsable && <Text strong>{d.responsable}</Text>}
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
                style={{ width: 210 }}
              />
            )}
          </Space>
        );
      },
    },
    {
      title: 'Por qué',
      width: 340,
      render: (_, r) => <Text style={{ fontSize: 12 }}>{r.decision.motivo}</Text>,
    },
    { title: 'Tipo de OT', render: (_, r) => r.actividad?.servicio },
    {
      title: 'Personas',
      align: 'center',
      render: (_, r) => {
        const personas = r.actividad?.personas_requeridas || 1;
        return <Tag color={personas > 1 ? 'blue' : undefined}>{personas}</Tag>;
      },
    },
    { title: 'Llegada', render: (_, r) => hhmm(r.decision.hora_llegada) },
    { title: 'OR', render: (_, r) => r.actividad?.or_operador },
    { title: 'Ciudad', render: (_, r) => r.actividad?.ciudad },
    { title: 'Sale de', render: (_, r) => r.decision.sede },
    {
      title: 'Km a la base',
      align: 'right',
      render: (_, r) => (r.decision.distancia_base_km === null || r.decision.distancia_base_km === undefined
        ? '' : km(r.decision.distancia_base_km)),
    },
    {
      title: 'Otras opciones',
      render: (_, r) => (recomendaciones[r.decision.codigo_bia]?.alternativas || []).map((a) => (
        <div key={a.sede_id} style={{ fontSize: 12 }}>{a.empresa} ({a.ciudad}) · {km(a.distancia_km)} km</div>
      )),
    },
  ];

  const rutasVisibles = result.rutas
    .map((r, idx) => ({ r, idx }))
    .filter(({ r }) => !visibles || r.ruta.paradas.some((p) => visibles.has(p.actividad.codigo_bia)));

  return (
    <>
      <Card
        title="Recomendación"
        style={{ marginBottom: 16 }}
        extra={(
          <Space wrap>
            {result.viable_en_un_dia && <Tag icon={<CheckCircleOutlined />} color="success">Todo cabe en la jornada</Tag>}
            {metricas.rutas_no_viables > 0 && (
              <Tag icon={<CloseCircleOutlined />} color="error">{metricas.rutas_no_viables} rutas superan la jornada</Tag>
            )}
            <Button icon={<DownloadOutlined />} onClick={() => exportCsv(allRows, metricas.dia)}>Descargar CSV</Button>
          </Space>
        )}
      >
        <Row gutter={[16, 16]}>
          {stats.map((s) => (
            <Col key={s.title} flex="1 1 110px">
              <Statistic title={s.title} value={s.value} valueStyle={s.color ? { color: s.color } : undefined} />
            </Col>
          ))}
        </Row>
        {metricas.parejas > 0 && (
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            {metricas.parejas} pareja(s) de técnicos para OTs de 2 personas
            {metricas.cuadrillas_manuales ? ' (incluye las armadas a mano o que ya salen juntas en Metabase)' : ''}.
          </Text>
        )}
        {(metricas.ots_otros_dias > 0 || metricas.asignadas_sin_fecha > 0) && (
          <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
            {metricas.ots_otros_dias > 0 && `${metricas.ots_otros_dias} OTs asignadas para otros días no entran en este plan. `}
            {metricas.asignadas_sin_fecha > 0 && `${metricas.asignadas_sin_fecha} OTs asignadas no tienen fecha de visita en Metabase.`}
          </Text>
        )}
        {metricas.ots_sin_lista_or > 0 && (
          <Alert
            style={{ marginTop: 12 }}
            type="warning"
            showIcon
            icon={<WarningOutlined />}
            message={`${metricas.ots_sin_lista_or} OTs son de OR sin contratistas con sede en su zona: se eligió el más cercano de todos. Revisa «Contratistas por OR».`}
          />
        )}
        <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
          Tiempos estimados con línea recta × factor vial {metricas.factor_vial}; el mapa traza cada ruta por las vías
          {metricas.radio_inhouse_km ? ` · técnicos atienden hasta ${metricas.radio_inhouse_km} km de su base` : ''}.
        </Text>
      </Card>

      <Card title={`¿A quién enviar cada OT? (${rows.length})`} style={{ marginBottom: 16 }}>
        <Table
          size="small"
          columns={columns}
          dataSource={rows}
          scroll={{ x: 'max-content' }}
          pagination={{ pageSize: 25, hideOnSinglePage: true, showSizeChanger: false }}
          expandable={{ expandedRowRender: (r) => <ExtrasDetail actividad={r.actividad} /> }}
        />
      </Card>

      <div style={{ marginBottom: 16, height: 520 }}>
        <AssignmentMapView result={result} incluirRetorno={incluirRetorno} visibles={visibles} situaciones={situaciones} />
      </div>

      <Card title={`Rutas (${rutasVisibles.length})`} style={{ marginBottom: 16 }}>
        <Collapse
          items={rutasVisibles.map(({ r, idx }) => {
            const yaAsignadas = r.ruta.paradas.filter((p) => situaciones[p.actividad.codigo_bia] === 'asignada').length;
            return {
              key: r.responsable_id,
              label: (
                <Space wrap>
                  <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 6, background: ROUTE_COLORS[idx % ROUTE_COLORS.length] }} />
                  <Text strong>{r.responsable}</Text>
                  <Text type="secondary">desde {r.sede.empresa} ({r.sede.ciudad})</Text>
                  <Tag color={r.tipo === 'tecnico' ? 'blue' : 'purple'}>{r.tipo === 'tecnico' ? 'In-house' : 'Contratista'}</Tag>
                  <Tag>{r.ruta.paradas.length} OTs</Tag>
                  {yaAsignadas > 0 && <Tag color="green">{yaAsignadas} ya asignadas</Tag>}
                  <Tag color={r.personas > 1 ? 'blue' : undefined}>{r.personas} {r.personas > 1 ? 'personas' : 'persona'}</Tag>
                  {r.costo !== null && r.costo !== undefined && <Tag color="gold">{formatCop(r.costo)}/día</Tag>}
                  <Tag>{km(r.ruta.distancia_total_km)} km</Tag>
                  <Tag>{hhmm(r.ruta.hora_inicio)}–{hhmm(r.ruta.hora_fin)}</Tag>
                  {r.ruta.viable ? <Tag color="success">Cabe en la jornada</Tag> : <Tag color="error">Supera la jornada</Tag>}
                </Space>
              ),
              children: (
                <Table
                  rowKey="secuencia"
                  size="small"
                  pagination={false}
                  columns={stopColumns(nuevas, situaciones)}
                  dataSource={r.ruta.paradas}
                  expandable={{ expandedRowRender: (p) => <ExtrasDetail actividad={p.actividad} /> }}
                />
              ),
            };
          })}
        />
      </Card>
    </>
  );
};

export default AssignmentResults;

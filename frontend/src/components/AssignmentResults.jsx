import React from 'react';
import { Card, Row, Col, Statistic, Tag, Table, Collapse, Alert, Button, Space, Typography, Tooltip, Descriptions } from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, DownloadOutlined, EnvironmentOutlined, WarningOutlined,
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
  sin_asignar: { label: 'Sin asignar', color: 'red' },
};

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

const exportCsv = (rows) => {
  const extraKeys = [];
  rows.forEach(({ actividad }) => Object.keys(actividad?.extras || {}).forEach((k) => {
    if (!extraKeys.includes(k)) extraKeys.push(k);
  }));

  // ";" and decimal comma so it opens directly in Excel configured in Spanish
  const header = ['OT', 'OR', 'Ciudad', 'Dirección', 'Tipo de OT', 'Personas', 'Enviar a', 'Responsable', 'Sale de',
    'Km a la base', 'Secuencia', 'Llegada', 'Salida', 'Ubicación aproximada', 'Motivo', ...extraKeys];
  const lines = rows.map(({ decision: d, actividad: a, parada }) => [
    d.codigo_bia, a?.or_operador, a?.ciudad, a?.direccion, a?.servicio, a?.personas_requeridas,
    DESTINO[d.enviar_a].label, d.responsable, d.sede,
    d.distancia_base_km === null || d.distancia_base_km === undefined ? '' : String(d.distancia_base_km).replace('.', ','),
    parada?.secuencia, hhmm(parada?.hora_llegada_estimada), hhmm(parada?.hora_salida_estimada),
    a?.coordenadas_aproximadas ? 'Sí' : 'No', d.motivo, ...extraKeys.map((k) => formatExtra(a?.extras?.[k])),
  ]);
  const csv = [header, ...lines].map((row) => row.map(csvValue).join(';')).join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `recomendacion-ots-${new Date().toISOString().split('T')[0]}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const stopColumns = (nuevas) => [
  { title: '#', dataIndex: 'secuencia', width: 40 },
  { title: 'OT', render: (_, p) => otCell(p.actividad, p.actividad.codigo_bia, nuevas) },
  { title: 'OR', render: (_, p) => p.actividad.or_operador },
  { title: 'Tipo de OT', render: (_, p) => <Tag color="blue">{p.actividad.servicio}</Tag> },
  { title: 'Personas', width: 80, render: (_, p) => p.actividad.personas_requeridas },
  { title: 'Dirección', render: (_, p) => `${p.actividad.direccion}${p.actividad.ciudad ? `, ${p.actividad.ciudad}` : ''}` },
  { title: 'Llegada', dataIndex: 'hora_llegada_estimada', width: 80, render: hhmm },
  { title: 'Salida', dataIndex: 'hora_salida_estimada', width: 80, render: hhmm },
  { title: 'Km', dataIndex: 'distancia_desde_anterior_km', width: 70, render: km },
];

const AssignmentResults = ({ result, ots, nuevas, incluirRetorno }) => {
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
  const rows = result.decisiones.map((d) => ({
    key: d.codigo_bia,
    decision: d,
    actividad: actividades[d.codigo_bia],
    parada: paradas[d.codigo_bia],
  }));

  const stats = [
    { title: 'OTs', value: result.total_actividades },
    { title: 'A técnicos', value: metricas.ots_con_tecnicos, color: '#007AFF' },
    { title: 'A contratistas', value: metricas.ots_con_contratistas, color: '#AF52DE' },
    { title: 'Sin asignar', value: metricas.ots_sin_asignar, color: metricas.ots_sin_asignar ? '#FF3B30' : undefined },
    { title: 'Km totales', value: km(result.distancia_total_km) },
  ];
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
      title: 'Enviar a',
      filters: Object.entries(DESTINO).map(([value, { label }]) => ({ text: label, value })),
      onFilter: (value, r) => r.decision.enviar_a === value,
      sorter: (a, b) => (a.decision.responsable || '~').localeCompare(b.decision.responsable || '~'),
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Tag color={DESTINO[r.decision.enviar_a].color}>{DESTINO[r.decision.enviar_a].label}</Tag>
          {r.decision.responsable && <Text strong>{r.decision.responsable}</Text>}
        </Space>
      ),
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
            <Button icon={<DownloadOutlined />} onClick={() => exportCsv(rows)}>Descargar CSV</Button>
          </Space>
        )}
      >
        <Row gutter={[16, 16]}>
          {stats.map((s) => (
            <Col key={s.title} flex="1 1 120px">
              <Statistic title={s.title} value={s.value} valueStyle={s.color ? { color: s.color } : undefined} />
            </Col>
          ))}
        </Row>
        {metricas.parejas > 0 && (
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            {metricas.parejas} pareja(s) de técnicos {metricas.cuadrillas_manuales ? 'armadas a mano' : 'para OTs de 2 personas'}.
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
          Distancias aproximadas: línea recta × factor vial {metricas.factor_vial}
          {metricas.radio_inhouse_km ? ` · técnicos atienden hasta ${metricas.radio_inhouse_km} km de su base` : ''}.
        </Text>
      </Card>

      <Card title="¿A quién enviar cada OT?" style={{ marginBottom: 16 }}>
        <Table
          size="small"
          columns={columns}
          dataSource={rows}
          scroll={{ x: 'max-content' }}
          pagination={{ pageSize: 25, hideOnSinglePage: true, showSizeChanger: false }}
          expandable={{ expandedRowRender: (r) => <ExtrasDetail actividad={r.actividad} /> }}
        />
      </Card>

      <div style={{ marginBottom: 16, height: 500 }}>
        <AssignmentMapView result={result} incluirRetorno={incluirRetorno} />
      </div>

      <Card title={`Rutas (${result.rutas.length})`} style={{ marginBottom: 16 }}>
        <Collapse
          items={result.rutas.map((r, idx) => ({
            key: r.responsable_id,
            label: (
              <Space wrap>
                <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 6, background: ROUTE_COLORS[idx % ROUTE_COLORS.length] }} />
                <Text strong>{r.responsable}</Text>
                <Text type="secondary">desde {r.sede.empresa} ({r.sede.ciudad})</Text>
                <Tag color={r.tipo === 'tecnico' ? 'blue' : 'purple'}>{r.tipo === 'tecnico' ? 'In-house' : 'Contratista'}</Tag>
                <Tag>{r.ruta.paradas.length} OTs</Tag>
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
                columns={stopColumns(nuevas)}
                dataSource={r.ruta.paradas}
                expandable={{ expandedRowRender: (p) => <ExtrasDetail actividad={p.actividad} /> }}
              />
            ),
          }))}
        />
      </Card>
    </>
  );
};

export default AssignmentResults;

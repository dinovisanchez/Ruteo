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

const otCell = (actividad, nuevas) => (
  <Space size={4}>
    <Text strong>{actividad.codigo_bia}</Text>
    {nuevas?.has(actividad.codigo_bia) && <Tag color="green">Nueva</Tag>}
    {actividad.coordenadas_aproximadas && (
      <Tooltip title="Ubicación aproximada: geocodificada a partir de la dirección o el municipio">
        <EnvironmentOutlined style={{ color: '#d48806' }} />
      </Tooltip>
    )}
  </Space>
);

const csvValue = (value) => {
  const text = String(value ?? '');
  return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

const extrasRows = (actividad) => Object.entries(actividad.extras || {})
  .map(([key, value]) => ({ key, value: formatExtra(value) }));

const ExtrasDetail = ({ actividad }) => {
  const rows = extrasRows(actividad);
  if (!rows.length) return <Text type="secondary">Sin columnas adicionales</Text>;
  return (
    <Descriptions size="small" column={3} bordered>
      {rows.map(({ key, value }) => <Descriptions.Item key={key} label={key}>{value}</Descriptions.Item>)}
    </Descriptions>
  );
};

const exportCsv = (result) => {
  const extraKeys = [];
  const addKeys = (a) => Object.keys(a.extras || {}).forEach((k) => { if (!extraKeys.includes(k)) extraKeys.push(k); });
  result.rutas.forEach((r) => r.ruta.paradas.forEach((p) => addKeys(p.actividad)));
  result.sin_asignar.forEach(({ actividad }) => addKeys(actividad));
  const extras = (a) => extraKeys.map((k) => formatExtra(a.extras?.[k]));

  // ";" and decimal comma so it opens directly in Excel configured in Spanish
  const header = ['OT', 'OR', 'Ciudad', 'Dirección', 'Tipo de OT', 'Personas requeridas', 'Responsable', 'Tipo',
    'Integrantes', 'Personas cuadrilla', 'Costo cuadrilla (día)', 'Sede', 'Secuencia', 'Llegada', 'Salida',
    'Km desde anterior', 'Ubicación aproximada', 'Ruta viable', 'Motivo sin asignar', ...extraKeys];
  const rows = [];
  result.rutas.forEach((r) => {
    r.ruta.paradas.forEach((p) => {
      const a = p.actividad;
      rows.push([a.codigo_bia, a.or_operador, a.ciudad, a.direccion, a.servicio, a.personas_requeridas, r.responsable,
        r.tipo === 'tecnico' ? 'Técnico in-house' : 'Contratista', (r.integrantes || []).join(' + '), r.personas,
        r.costo ?? '', `${r.sede.empresa} (${r.sede.ciudad})`, p.secuencia,
        p.hora_llegada_estimada, p.hora_salida_estimada, String(p.distancia_desde_anterior_km).replace('.', ','),
        a.coordenadas_aproximadas ? 'Sí' : 'No', r.ruta.viable ? 'Sí' : 'No', '', ...extras(a)]);
    });
  });
  result.sin_asignar.forEach(({ actividad: a, motivo }) => {
    rows.push([a.codigo_bia, a.or_operador, a.ciudad, a.direccion, a.servicio, a.personas_requeridas, 'Sin asignar',
      '', '', '', '', '', '', '', '', '', a.coordenadas_aproximadas ? 'Sí' : 'No', '', motivo, ...extras(a)]);
  });
  const csv = [header, ...rows].map((row) => row.map(csvValue).join(';')).join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `asignacion-${result.modo}-${new Date().toISOString().split('T')[0]}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const stopColumns = (nuevas) => [
  { title: '#', dataIndex: 'secuencia', width: 40 },
  { title: 'OT', render: (_, p) => otCell(p.actividad, nuevas) },
  { title: 'OR', render: (_, p) => p.actividad.or_operador },
  { title: 'Tipo de OT', render: (_, p) => <Tag color="blue">{p.actividad.servicio}</Tag> },
  { title: 'Personas', width: 80, render: (_, p) => p.actividad.personas_requeridas },
  { title: 'Dirección', render: (_, p) => `${p.actividad.direccion}${p.actividad.ciudad ? `, ${p.actividad.ciudad}` : ''}` },
  { title: 'Llegada', dataIndex: 'hora_llegada_estimada', width: 80, render: (v) => v.slice(0, 5) },
  { title: 'Salida', dataIndex: 'hora_salida_estimada', width: 80, render: (v) => v.slice(0, 5) },
  { title: 'Km', dataIndex: 'distancia_desde_anterior_km', width: 70, render: km },
];

const AssignmentResults = ({ result, nuevas, incluirRetorno }) => {
  if (!result) return null;
  const { metricas } = result;
  const esContratistas = result.modo === 'contratistas';
  const actividadPorCodigo = {};
  result.rutas.forEach((r) => r.ruta.paradas.forEach((p) => { actividadPorCodigo[p.actividad.codigo_bia] = p.actividad; }));

  const stats = [
    { title: 'OTs', value: result.total_actividades },
    { title: 'Asignadas', value: metricas.ots_asignadas, color: '#34C759' },
    { title: 'Sin asignar', value: metricas.ots_sin_asignar, color: metricas.ots_sin_asignar ? '#FF3B30' : undefined },
    { title: esContratistas ? 'Cuadrillas' : 'Cuadrillas con ruta', value: metricas.rutas },
    { title: 'Km totales', value: km(result.distancia_total_km) },
    { title: 'Rutas no viables', value: metricas.rutas_no_viables, color: metricas.rutas_no_viables ? '#FF3B30' : undefined },
  ];
  if (metricas.costo_total !== null && metricas.costo_total !== undefined) {
    stats.push({ title: 'Costo técnicos (día)', value: formatCop(metricas.costo_total) });
  }

  const recommendationColumns = [
    { title: 'OT', render: (_, r) => <Text strong>{r.codigo_bia}</Text> },
    { title: 'OR', dataIndex: 'or_operador' },
    { title: 'Tipo de OT', render: (_, r) => actividadPorCodigo[r.codigo_bia]?.servicio },
    { title: 'Personas', render: (_, r) => actividadPorCodigo[r.codigo_bia]?.personas_requeridas },
    {
      title: 'Contratista recomendado',
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Text>{r.elegido?.empresa}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>Sede {r.elegido?.ciudad}</Text>
        </Space>
      ),
    },
    { title: 'Distancia', render: (_, r) => `${km(r.elegido?.distancia_km)} km` },
    {
      title: 'Criterio',
      render: (_, r) => (r.criterio === 'lista_or'
        ? <Tag color="green">Contratista del OR</Tag>
        : <Tooltip title="Este OR no tiene contratistas definidos"><Tag color="orange">Más cercano de todos</Tag></Tooltip>),
    },
    {
      title: 'Alternativas',
      render: (_, r) => r.alternativas.map((a) => (
        <div key={a.sede_id} style={{ fontSize: 12 }}>{a.empresa} ({a.ciudad}) · {km(a.distancia_km)} km</div>
      )),
    },
  ];

  return (
    <>
      <Card
        title="Resultado de la asignación"
        style={{ marginBottom: 16 }}
        extra={(
          <Space>
            {result.viable_en_un_dia && <Tag icon={<CheckCircleOutlined />} color="success">Todo cabe en la jornada</Tag>}
            {metricas.ots_sin_asignar > 0 && (
              <Tag icon={<CloseCircleOutlined />} color="error">{metricas.ots_sin_asignar} OTs sin asignar</Tag>
            )}
            {metricas.rutas_no_viables > 0 && (
              <Tag icon={<CloseCircleOutlined />} color="error">{metricas.rutas_no_viables} rutas superan la jornada</Tag>
            )}
            <Button icon={<DownloadOutlined />} onClick={() => exportCsv(result)}>Descargar CSV</Button>
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
        {!esContratistas && metricas.parejas > 0 && (
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            {metricas.parejas} pareja(s) {metricas.cuadrillas_manuales ? 'armadas a mano' : 'sugeridas por las OTs de 2 personas'}.
          </Text>
        )}
        {esContratistas && metricas.ots_por_contratista && (
          <div style={{ marginTop: 12 }}>
            {Object.entries(metricas.ots_por_contratista).map(([empresa, n]) => <Tag key={empresa}>{empresa}: {n}</Tag>)}
          </div>
        )}
        {esContratistas && metricas.ots_sin_lista_or > 0 && (
          <Alert
            style={{ marginTop: 12 }}
            type="warning"
            showIcon
            icon={<WarningOutlined />}
            message={`${metricas.ots_sin_lista_or} OTs son de OR sin contratistas definidos: se eligió el contratista más cercano de todos. Defínelos en "Contratistas por OR".`}
          />
        )}
        <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
          Distancias aproximadas: línea recta × factor vial {metricas.factor_vial}.
        </Text>
      </Card>

      <div style={{ marginBottom: 16, height: 500 }}>
        <AssignmentMapView result={result} incluirRetorno={incluirRetorno} />
      </div>

      {esContratistas && (
        <Card title="Contratista recomendado por OT" style={{ marginBottom: 16 }}>
          <Table
            rowKey="codigo_bia"
            size="small"
            columns={recommendationColumns}
            dataSource={result.recomendaciones}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
          />
        </Card>
      )}

      <Card title="Rutas" style={{ marginBottom: 16 }}>
        <Collapse
          items={result.rutas.map((r, idx) => ({
            key: r.responsable_id,
            label: (
              <Space wrap>
                <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 6, background: ROUTE_COLORS[idx % ROUTE_COLORS.length] }} />
                <Text strong>{r.responsable}</Text>
                <Text type="secondary">desde {r.sede.empresa} ({r.sede.ciudad})</Text>
                <Tag>{r.ruta.paradas.length} OTs</Tag>
                <Tag color={r.personas > 1 ? 'blue' : undefined}>{r.personas} {r.personas > 1 ? 'personas' : 'persona'}</Tag>
                {r.costo !== null && r.costo !== undefined && <Tag color="gold">{formatCop(r.costo)}/día</Tag>}
                <Tag>{km(r.ruta.distancia_total_km)} km</Tag>
                <Tag>{r.ruta.hora_inicio.slice(0, 5)}–{r.ruta.hora_fin.slice(0, 5)}</Tag>
                {r.ruta.viable ? <Tag color="success">Viable</Tag> : <Tag color="error">Supera la jornada</Tag>}
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

      {result.sin_asignar.length > 0 && (
        <Card title={`Sin asignar (${result.sin_asignar.length})`} style={{ marginBottom: 16 }}>
          <Table
            rowKey={(r) => r.actividad.codigo_bia}
            size="small"
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            dataSource={result.sin_asignar}
            expandable={{ expandedRowRender: (r) => <ExtrasDetail actividad={r.actividad} /> }}
            columns={[
              { title: 'OT', render: (_, r) => otCell(r.actividad, nuevas) },
              { title: 'OR', render: (_, r) => r.actividad.or_operador },
              { title: 'Ciudad', render: (_, r) => r.actividad.ciudad },
              { title: 'Dirección', render: (_, r) => r.actividad.direccion },
              { title: 'Motivo', dataIndex: 'motivo' },
            ]}
          />
        </Card>
      )}
    </>
  );
};

export default AssignmentResults;

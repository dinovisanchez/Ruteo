import React from 'react';
import { Card, Row, Col, Statistic, Tag, Table, Collapse, Alert, Button, Space, Typography, Tooltip } from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, DownloadOutlined, EnvironmentOutlined, WarningOutlined,
} from '@ant-design/icons';
import AssignmentMapView, { ROUTE_COLORS } from './AssignmentMapView';

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

const exportCsv = (result) => {
  // ";" and decimal comma so it opens directly in Excel configured in Spanish
  const header = ['OT', 'OR', 'Ciudad', 'Dirección', 'Servicio', 'Responsable', 'Tipo', 'Sede', 'Secuencia',
    'Llegada', 'Salida', 'Km desde anterior', 'Ubicación aproximada', 'Ruta viable', 'Motivo sin asignar'];
  const rows = [];
  result.rutas.forEach((r) => {
    r.ruta.paradas.forEach((p) => {
      const a = p.actividad;
      rows.push([a.codigo_bia, a.or_operador, a.ciudad, a.direccion, a.servicio, r.responsable,
        r.tipo === 'tecnico' ? 'Técnico in-house' : 'Contratista', `${r.sede.empresa} (${r.sede.ciudad})`, p.secuencia,
        p.hora_llegada_estimada, p.hora_salida_estimada, String(p.distancia_desde_anterior_km).replace('.', ','),
        a.coordenadas_aproximadas ? 'Sí' : 'No', r.ruta.viable ? 'Sí' : 'No', '']);
    });
  });
  result.sin_asignar.forEach(({ actividad: a, motivo }) => {
    rows.push([a.codigo_bia, a.or_operador, a.ciudad, a.direccion, a.servicio, 'Sin asignar', '', '', '', '', '', '',
      a.coordenadas_aproximadas ? 'Sí' : 'No', '', motivo]);
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
  { title: 'Servicio', render: (_, p) => <Tag color="blue">{p.actividad.servicio}</Tag> },
  { title: 'Dirección', render: (_, p) => `${p.actividad.direccion}${p.actividad.ciudad ? `, ${p.actividad.ciudad}` : ''}` },
  { title: 'Llegada', dataIndex: 'hora_llegada_estimada', width: 80, render: (v) => v.slice(0, 5) },
  { title: 'Salida', dataIndex: 'hora_salida_estimada', width: 80, render: (v) => v.slice(0, 5) },
  { title: 'Km', dataIndex: 'distancia_desde_anterior_km', width: 70, render: km },
];

const AssignmentResults = ({ result, nuevas, incluirRetorno }) => {
  if (!result) return null;
  const { metricas } = result;
  const esContratistas = result.modo === 'contratistas';

  const recommendationColumns = [
    { title: 'OT', render: (_, r) => <Text strong>{r.codigo_bia}</Text> },
    { title: 'OR', dataIndex: 'or_operador' },
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
        <Row gutter={16}>
          <Col span={4}><Statistic title="OTs" value={result.total_actividades} /></Col>
          <Col span={4}><Statistic title="Asignadas" value={metricas.ots_asignadas} valueStyle={{ color: '#3f8600' }} /></Col>
          <Col span={4}><Statistic title="Sin asignar" value={metricas.ots_sin_asignar} valueStyle={{ color: metricas.ots_sin_asignar ? '#cf1322' : undefined }} /></Col>
          <Col span={4}><Statistic title={esContratistas ? 'Cuadrillas' : 'Técnicos con ruta'} value={metricas.rutas} /></Col>
          <Col span={4}><Statistic title="Km totales" value={km(result.distancia_total_km)} /></Col>
          <Col span={4}><Statistic title="Rutas no viables" value={metricas.rutas_no_viables} valueStyle={{ color: metricas.rutas_no_viables ? '#cf1322' : undefined }} /></Col>
        </Row>
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
                <Tag>{km(r.ruta.distancia_total_km)} km</Tag>
                <Tag>{r.ruta.hora_inicio.slice(0, 5)}–{r.ruta.hora_fin.slice(0, 5)}</Tag>
                {r.ruta.viable ? <Tag color="success">Viable</Tag> : <Tag color="error">Supera la jornada</Tag>}
              </Space>
            ),
            children: (
              <Table rowKey="secuencia" size="small" pagination={false} columns={stopColumns(nuevas)} dataSource={r.ruta.paradas} />
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

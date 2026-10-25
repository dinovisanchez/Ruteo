import React from 'react';
import { Card, Collapse, Table, Tag, Descriptions, Progress, Empty } from 'antd';
import {
  UnorderedListOutlined,
  TeamOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CarOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';

const { Panel } = Collapse;

const RouteDetails = ({ optimizationResult }) => {
  if (!optimizationResult || !optimizationResult.rutas) {
    return (
      <Card
        title={
          <span>
            <UnorderedListOutlined /> Detalles de Rutas
          </span>
        }
        style={{ marginBottom: 16 }}
      >
        <Empty description="Optimiza las rutas para ver los detalles" />
      </Card>
    );
  }

  const crewColors = [
    '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
    '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b',
  ];

  const columns = [
    {
      title: '#',
      dataIndex: 'secuencia',
      key: 'secuencia',
      width: 50,
      render: (secuencia, record, index) => (
        <Tag color="blue" style={{ fontWeight: 'bold' }}>
          {secuencia}
        </Tag>
      ),
    },
    {
      title: 'Código',
      dataIndex: ['actividad', 'codigo_bia'],
      key: 'codigo',
      width: 120,
    },
    {
      title: 'Actividad',
      dataIndex: ['actividad', 'nombre'],
      key: 'nombre',
    },
    {
      title: 'Dirección',
      dataIndex: ['actividad', 'direccion'],
      key: 'direccion',
    },
    {
      title: 'Servicio',
      dataIndex: ['actividad', 'servicio'],
      key: 'servicio',
      width: 120,
      render: (servicio) => <Tag color="geekblue">{servicio}</Tag>,
    },
    {
      title: 'Llegada',
      dataIndex: 'hora_llegada_estimada',
      key: 'llegada',
      width: 100,
    },
    {
      title: 'Salida',
      dataIndex: 'hora_salida_estimada',
      key: 'salida',
      width: 100,
    },
    {
      title: 'Distancia',
      dataIndex: 'distancia_desde_anterior_km',
      key: 'distancia',
      width: 100,
      render: (dist) => `${dist.toFixed(2)} km`,
    },
    {
      title: 'Tiempo Viaje',
      dataIndex: 'tiempo_desplazamiento_minutos',
      key: 'tiempo',
      width: 100,
      render: (mins) => `${mins} min`,
    },
  ];

  const formatTime = (minutes) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
  };

  return (
    <Card
      title={
        <span>
          <UnorderedListOutlined /> Detalles de Rutas por Cuadrilla
        </span>
      }
      style={{ marginBottom: 16 }}
    >
      <Collapse accordion>
        {optimizationResult.rutas.map((route, index) => {
          const color = crewColors[index % crewColors.length];

          return (
            <Panel
              header={
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>
                    <TeamOutlined style={{ marginRight: 8, color }} />
                    <strong>Cuadrilla {route.cuadrilla_id}</strong>
                    <Tag style={{ marginLeft: 8 }}>{route.paradas.length} paradas</Tag>
                  </span>
                  <span>
                    {route.viable ? (
                      <Tag icon={<CheckCircleOutlined />} color="success">
                        Viable
                      </Tag>
                    ) : (
                      <Tag icon={<CloseCircleOutlined />} color="error">
                        No viable
                      </Tag>
                    )}
                  </span>
                </div>
              }
              key={route.cuadrilla_id}
            >
              <Descriptions bordered size="small" column={{ xs: 1, sm: 2, md: 3 }} style={{ marginBottom: 16 }}>
                <Descriptions.Item label="Hora Inicio">
                  <ClockCircleOutlined /> {route.hora_inicio}
                </Descriptions.Item>
                <Descriptions.Item label="Hora Fin">
                  <ClockCircleOutlined /> {route.hora_fin}
                </Descriptions.Item>
                <Descriptions.Item label="Distancia Total">
                  <CarOutlined /> {route.distancia_total_km.toFixed(2)} km
                </Descriptions.Item>
                <Descriptions.Item label="Tiempo Total">
                  {formatTime(route.tiempo_total_minutos)}
                </Descriptions.Item>
                <Descriptions.Item label="Tiempo Trabajo">
                  {formatTime(route.tiempo_trabajo_minutos)}
                </Descriptions.Item>
                <Descriptions.Item label="Tiempo Viaje">
                  {formatTime(route.tiempo_desplazamiento_minutos)}
                </Descriptions.Item>
                <Descriptions.Item label="Utilización" span={3}>
                  <Progress
                    percent={route.utilization_percent}
                    status={route.utilization_percent >= 80 ? 'success' : 'normal'}
                    format={(percent) => `${percent.toFixed(1)}%`}
                    style={{ width: '100%' }}
                  />
                </Descriptions.Item>
              </Descriptions>

              <Table
                columns={columns}
                dataSource={route.paradas}
                pagination={false}
                size="small"
                scroll={{ x: true }}
                rowKey={(record) => `${route.cuadrilla_id}-${record.secuencia}`}
                bordered
                summary={(pageData) => {
                  const totalDistance = pageData.reduce(
                    (sum, record) => sum + record.distancia_desde_anterior_km,
                    0
                  );
                  const totalTime = pageData.reduce(
                    (sum, record) => sum + record.tiempo_desplazamiento_minutos,
                    0
                  );

                  return (
                    <Table.Summary fixed>
                      <Table.Summary.Row style={{ background: '#fafafa' }}>
                        <Table.Summary.Cell index={0} colSpan={7} align="right">
                          <strong>Total:</strong>
                        </Table.Summary.Cell>
                        <Table.Summary.Cell index={1}>
                          <strong>{totalDistance.toFixed(2)} km</strong>
                        </Table.Summary.Cell>
                        <Table.Summary.Cell index={2}>
                          <strong>{totalTime} min</strong>
                        </Table.Summary.Cell>
                      </Table.Summary.Row>
                    </Table.Summary>
                  );
                }}
              />
            </Panel>
          );
        })}
      </Collapse>
    </Card>
  );
};

export default RouteDetails;

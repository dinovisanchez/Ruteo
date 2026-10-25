import React, { useState } from 'react';
import {
  Card,
  Descriptions,
  Table,
  Tag,
  Space,
  Collapse,
  Statistic,
  Row,
  Col,
  Typography,
  Divider,
  Badge,
  Tooltip,
} from 'antd';
import {
  ClusterOutlined,
  EnvironmentOutlined,
  RiseOutlined,
  CheckCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';

const { Panel } = Collapse;
const { Text } = Typography;

function ClusterResults({ clusterResult, type = 'analyze' }) {
  const [expandedClusters, setExpandedClusters] = useState(['0']);

  if (!clusterResult) {
    return null;
  }

  const isOptimized = type === 'optimize' && clusterResult.rutas_por_cluster;

  // Cluster table columns
  const clusterColumns = [
    {
      title: 'Lote ID',
      dataIndex: 'cluster_id',
      key: 'cluster_id',
      render: (id) => <Tag color="blue">Lote {id}</Tag>,
      width: 100,
    },
    {
      title: 'Actividades',
      dataIndex: 'num_actividades',
      key: 'num_actividades',
      sorter: (a, b) => b.num_actividades - a.num_actividades,
      render: (num) => <strong>{num}</strong>,
      width: 100,
    },
    {
      title: 'Centroid',
      key: 'centroid',
      render: (_, record) => (
        <Space size="small">
          <Text style={{ fontSize: 12 }}>
            {record.centroid.latitude.toFixed(4)}, {record.centroid.longitude.toFixed(4)}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Distancia Promedio',
      dataIndex: 'distancia_promedio_al_centroid_km',
      key: 'avg_dist',
      sorter: (a, b) => a.distancia_promedio_al_centroid_km - b.distancia_promedio_al_centroid_km,
      render: (dist) => `${dist.toFixed(2)} km`,
      width: 140,
    },
    {
      title: 'Dispersión',
      dataIndex: 'distancia_maxima_al_centroid_km',
      key: 'max_dist',
      sorter: (a, b) => a.distancia_maxima_al_centroid_km - b.distancia_maxima_al_centroid_km,
      render: (dist) => (
        <Tooltip title="Distancia máxima al centroid">
          <Tag color={dist < 10 ? 'green' : dist < 20 ? 'orange' : 'red'}>
            {dist.toFixed(2)} km
          </Tag>
        </Tooltip>
      ),
      width: 120,
    },
    {
      title: 'Densidad',
      dataIndex: 'densidad_km2',
      key: 'density',
      sorter: (a, b) => (b.densidad_km2 || 0) - (a.densidad_km2 || 0),
      render: (density) => (
        <Tooltip title="Actividades por km²">
          {density ? `${density.toFixed(2)}/km²` : 'N/A'}
        </Tooltip>
      ),
      width: 110,
    },
  ];

  // Add route info if optimized
  if (isOptimized) {
    clusterColumns.push(
      {
        title: 'Distancia Ruta',
        key: 'route_distance',
        render: (_, record) => {
          const route = clusterResult.rutas_por_cluster.find(
            (r) => r.cluster_id === record.cluster_id
          );
          return route ? `${route.ruta.distancia_total_km.toFixed(2)} km` : 'N/A';
        },
        width: 120,
      },
      {
        title: 'Tiempo',
        key: 'route_time',
        render: (_, record) => {
          const route = clusterResult.rutas_por_cluster.find(
            (r) => r.cluster_id === record.cluster_id
          );
          if (!route) return 'N/A';
          const hours = Math.floor(route.ruta.tiempo_total_minutos / 60);
          const mins = route.ruta.tiempo_total_minutos % 60;
          return `${hours}h ${mins}m`;
        },
        width: 100,
      },
      {
        title: 'Viable',
        key: 'viable',
        render: (_, record) => {
          const route = clusterResult.rutas_por_cluster.find(
            (r) => r.cluster_id === record.cluster_id
          );
          if (!route) return null;
          return route.ruta.viable ? (
            <Tag icon={<CheckCircleOutlined />} color="success">
              Sí
            </Tag>
          ) : (
            <Tag icon={<WarningOutlined />} color="warning">
              No
            </Tag>
          );
        },
        width: 80,
      }
    );
  }

  const clusters = isOptimized
    ? clusterResult.clustering_info.clusters
    : clusterResult.clusters;

  const metrics = isOptimized
    ? clusterResult.clustering_info.metricas_globales
    : clusterResult.metricas_globales;


  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Global Metrics */}
      <Card
        title={
          <Space>
            <ClusterOutlined />
            <span>Resumen de Lotes Generados</span>
          </Space>
        }
      >
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="Total Actividades"
              value={clusterResult.total_actividades}
              prefix={<EnvironmentOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Lotes Generados"
              value={isOptimized ? clusterResult.clustering_info.num_clusters : clusterResult.num_clusters}
              prefix={<ClusterOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Lote Más Grande"
              value={metrics.cluster_mas_grande}
              suffix="actividades"
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Lote Más Pequeño"
              value={metrics.cluster_mas_pequeno}
              suffix="actividades"
            />
          </Col>
        </Row>

        {isOptimized && (
          <>
            <Divider />
            <Row gutter={16}>
              <Col span={8}>
                <Statistic
                  title="Distancia Total"
                  value={clusterResult.distancia_total_km.toFixed(2)}
                  suffix="km"
                  prefix={<RiseOutlined />}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="Tiempo Total"
                  value={(clusterResult.tiempo_total_minutos / 60).toFixed(1)}
                  suffix="horas"
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="Lotes Viables"
                  value={clusterResult.metricas.viable_clusters}
                  suffix={`/ ${clusterResult.metricas.num_clusters}`}
                  valueStyle={{
                    color:
                      clusterResult.metricas.all_clusters_viable ? '#3f8600' : '#faad14',
                  }}
                />
              </Col>
            </Row>
          </>
        )}

        <Divider />

        <Descriptions size="small" column={2}>
          <Descriptions.Item label="Método">
            <Tag color="cyan">
              {isOptimized ? clusterResult.clustering_info.metodo : clusterResult.metodo}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Distancia Máxima">
            {isOptimized ? clusterResult.clustering_info.distancia_maxima_usado_km : clusterResult.distancia_maxima_usado_km} km
          </Descriptions.Item>
          <Descriptions.Item label="Promedio por Lote">
            {metrics.promedio_actividades_por_cluster.toFixed(1)} actividades
          </Descriptions.Item>
          {isOptimized && (
            <Descriptions.Item label="Lote Más Compacto">
              <Tag color="green">Lote {clusterResult.metricas.most_compact_cluster}</Tag>
            </Descriptions.Item>
          )}
          {isOptimized && (
            <Descriptions.Item label="Lote Más Disperso">
              <Tag color="orange">Lote {clusterResult.metricas.most_dispersed_cluster}</Tag>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>


      {/* Cluster Details Table */}
      <Card title="Detalle de Lotes">
        <Table
          columns={clusterColumns}
          dataSource={clusters.map((c) => ({ ...c, key: c.cluster_id }))}
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
        />
      </Card>

      {/* Cluster Activities Expansion */}
      <Card title="Actividades por Lote">
        <Collapse
          activeKey={expandedClusters}
          onChange={setExpandedClusters}
        >
          {clusters.map((cluster) => {
            const route = isOptimized
              ? clusterResult.rutas_por_cluster.find((r) => r.cluster_id === cluster.cluster_id)
              : null;

            return (
              <Panel
                header={
                  <Space>
                    <Badge
                      count={cluster.num_actividades}
                      style={{ backgroundColor: '#1890ff' }}
                    />
                    <span>
                      <strong>Lote {cluster.cluster_id}</strong> -{' '}
                      {cluster.num_actividades} actividades
                    </span>
                    {route && (
                      <Tag color={route.ruta.viable ? 'success' : 'warning'}>
                        {route.ruta.viable ? 'Viable' : 'Excede horario'}
                      </Tag>
                    )}
                  </Space>
                }
                key={cluster.cluster_id.toString()}
              >
                <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="Centroid">
                    {cluster.centroid.latitude.toFixed(6)},{' '}
                    {cluster.centroid.longitude.toFixed(6)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Dispersión Promedio">
                    {cluster.distancia_promedio_al_centroid_km.toFixed(2)} km
                  </Descriptions.Item>
                  <Descriptions.Item label="Dispersión Máxima">
                    {cluster.distancia_maxima_al_centroid_km.toFixed(2)} km
                  </Descriptions.Item>
                  {cluster.densidad_km2 && (
                    <Descriptions.Item label="Densidad">
                      {cluster.densidad_km2.toFixed(2)} act/km²
                    </Descriptions.Item>
                  )}
                </Descriptions>

                {route && (
                  <>
                    <Divider orientation="left" plain>
                      Ruta Optimizada
                    </Divider>
                    <Row gutter={16} style={{ marginBottom: 16 }}>
                      <Col span={6}>
                        <Statistic
                          title="Distancia Total"
                          value={route.ruta.distancia_total_km}
                          suffix="km"
                          precision={2}
                        />
                      </Col>
                      <Col span={6}>
                        <Statistic
                          title="Tiempo Trabajo"
                          value={(route.ruta.tiempo_trabajo_minutos / 60).toFixed(1)}
                          suffix="h"
                        />
                      </Col>
                      <Col span={6}>
                        <Statistic
                          title="Tiempo Viaje"
                          value={(route.ruta.tiempo_desplazamiento_minutos / 60).toFixed(1)}
                          suffix="h"
                        />
                      </Col>
                      <Col span={6}>
                        <Statistic
                          title="Utilización"
                          value={route.ruta.utilization_percent}
                          suffix="%"
                          precision={1}
                          valueStyle={{
                            color: route.ruta.utilization_percent > 80 ? '#3f8600' : '#faad14',
                          }}
                        />
                      </Col>
                    </Row>
                  </>
                )}

                <Table
                  columns={[
                    {
                      title: 'Código',
                      dataIndex: 'codigo_bia',
                      key: 'codigo',
                      width: 120,
                    },
                    {
                      title: 'Nombre',
                      dataIndex: 'nombre',
                      key: 'nombre',
                    },
                    {
                      title: 'Ciudad',
                      dataIndex: 'ciudad',
                      key: 'ciudad',
                      width: 150,
                    },
                    {
                      title: 'Servicio',
                      dataIndex: 'servicio',
                      key: 'servicio',
                      width: 120,
                      render: (service) => <Tag>{service}</Tag>,
                    },
                    {
                      title: 'GPS',
                      dataIndex: 'gps',
                      key: 'gps',
                      width: 180,
                      render: (gps) => <Text code style={{ fontSize: 11 }}>{gps}</Text>,
                    },
                  ]}
                  dataSource={cluster.actividades.map((act, idx) => ({
                    ...act,
                    key: `${cluster.cluster_id}-${idx}`,
                  }))}
                  size="small"
                  pagination={{ pageSize: 10 }}
                />
              </Panel>
            );
          })}
        </Collapse>
      </Card>
    </Space>
  );
}

export default ClusterResults;

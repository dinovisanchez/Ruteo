import React from 'react';
import {
  Card,
  Checkbox,
  Row,
  Col,
  Space,
  Tag,
  Divider,
  Typography,
} from 'antd';
import {
  EnvironmentOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

function ClusterSelectionPanel({ 
  clusterResult, 
  selectedClusters, 
  onSelectionChange 
}) {
  if (!clusterResult || !clusterResult.rutas_por_cluster) {
    return null;
  }

  const allClusterIds = clusterResult.rutas_por_cluster.map(r => r.cluster_id);
  const clusters = clusterResult.clustering_info?.clusters || clusterResult.clusters || [];

  // Handle cluster selection change
  const handleClusterSelection = (checkedValues) => {
    if (onSelectionChange) {
      onSelectionChange(checkedValues);
    }
  };

  return (
    <Card
      title={
        <Space>
          <EnvironmentOutlined />
          <span>Seleccionar Lotes para Mapa</span>
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <Checkbox.Group
        value={selectedClusters}
        onChange={handleClusterSelection}
        style={{ width: '100%' }}
      >
        <Row gutter={[16, 8]}>
          {allClusterIds.map((clusterId) => {
            const routeCluster = clusterResult.rutas_por_cluster.find(
              (r) => r.cluster_id === clusterId
            );
            const cluster = clusters.find((c) => c.cluster_id === clusterId);
            const route = routeCluster?.ruta;
            
            return (
              <Col span={6} key={clusterId}>
                <Checkbox value={clusterId}>
                  <Space>
                    <Tag color={route?.viable ? 'success' : 'warning'}>
                      Lote {clusterId}
                    </Tag>
                    <span style={{ fontSize: 12 }}>
                      {cluster?.num_actividades || 0} act.
                      {route && ` | ${route.distancia_total_km.toFixed(1)} km`}
                    </span>
                  </Space>
                </Checkbox>
              </Col>
            );
          })}
        </Row>
      </Checkbox.Group>
      <Divider style={{ margin: '12px 0' }} />
      <Space>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Seleccionados: {selectedClusters.length} de {allClusterIds.length} lotes
        </Text>
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            handleClusterSelection(allClusterIds);
          }}
          style={{ fontSize: 12 }}
        >
          Seleccionar todos
        </a>
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            handleClusterSelection([]);
          }}
          style={{ fontSize: 12 }}
        >
          Deseleccionar todos
        </a>
      </Space>
    </Card>
  );
}

export default ClusterSelectionPanel;


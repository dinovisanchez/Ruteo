import React, { useCallback, useState } from 'react';
import { Layout, Typography, Space, Spin, message, Button, Tabs, Alert, Card, Empty } from 'antd';
import {
  AppstoreOutlined,
  DownloadOutlined,
  ClusterOutlined,
  RocketOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';

import FileUploader from './components/FileUploader';
import ConfigPanel from './components/ConfigPanel';
import ProximityPanel from './components/ProximityPanel';
import MapView from './components/MapView';
import MetricsPanel from './components/MetricsPanel';
import RouteDetails from './components/RouteDetails';
import ClusterResults from './components/ClusterResults';
import ClusterMapView from './components/ClusterMapView';
import ClusterSelectionPanel from './components/ClusterSelectionPanel';
import AssignmentPanel from './components/AssignmentPanel';
import AssignmentResults from './components/AssignmentResults';
import { optimizeRoutes, analyzeProximity, optimizeByClusters, assignActivities } from './services/api';

import './App.css';

const { Header, Content, Sider, Footer } = Layout;
const { Title, Text } = Typography;

function App() {
  const [activities, setActivities] = useState(null);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const [clusterResult, setClusterResult] = useState(null);
  const [clusterAnalysisType, setClusterAnalysisType] = useState('analyze'); // 'analyze' or 'optimize'
  const [configuration, setConfiguration] = useState(null);
  const [loading, setLoading] = useState(false);
  const [siderCollapsed, setSiderCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState('standard');
  const [selectedClusters, setSelectedClusters] = useState([]);
  const [assignmentOts, setAssignmentOts] = useState(null);
  const [assignmentNuevas, setAssignmentNuevas] = useState(new Set());
  const [assignmentSource, setAssignmentSource] = useState('');
  const [assignmentResult, setAssignmentResult] = useState(null);
  const [assignmentRetorno, setAssignmentRetorno] = useState(true);
  const [assignedCodes, setAssignedCodes] = useState('');

  const handleUploadSuccess = (result) => {
    setActivities(result.activities);
    setOptimizationResult(null); // Clear previous results
    setClusterResult(null); // Clear cluster results
    setSelectedClusters([]); // Clear selected clusters
    message.success(`${result.total_activities} actividades cargadas exitosamente`);
  };

  const handleOptimize = async (activityLot) => {
    setLoading(true);
    try {
      message.loading({ content: 'Optimizando rutas...', key: 'optimize', duration: 0 });

      const result = await optimizeRoutes(activityLot);

      setOptimizationResult(result);
      setConfiguration(activityLot.configuracion);

      message.success({
        content: `Optimización completada: ${result.cuadrillas_necesarias} cuadrillas, ${result.distancia_total_km.toFixed(2)} km total`,
        key: 'optimize',
        duration: 5,
      });
    } catch (error) {
      console.error('Optimization error:', error);
      message.error({
        content: `Error en optimización: ${error.message}`,
        key: 'optimize',
        duration: 10,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleProximityAnalyze = async (maxDistanceKm, method) => {
    if (!activities) {
      message.error('Primero carga un archivo con actividades');
      return;
    }

    setLoading(true);
    setClusterAnalysisType('optimize');

    try {
      message.loading({ content: 'Generando lotes por proximidad y optimizando rutas...', key: 'proximity-opt', duration: 0 });

      // Crear configuración mínima por defecto con tiempos para todos los servicios posibles
      const defaultConfig = {
        horario_inicio: '08:00:00',
        horario_fin: '17:00:00',
        horas_laborales: 8.0,
        velocidad_promedio_kmh: 30.0,
        punto_partida: activities[0].coordinates || { latitude: 4.6, longitude: -74.08 },
        incluir_retorno: true,
        tiempos_servicio: [
          { servicio: 'normalizacion telemedida', duracion_minutos: 60 },
          { servicio: 'instalacion', duracion_minutos: 180 },
          { servicio: 'visita previa', duracion_minutos: 90 },
          { servicio: 'normalizacion medida', duracion_minutos: 120 },
          { servicio: 'legalizacion', duracion_minutos: 120 },
          { servicio: 'pqr', duracion_minutos: 60 },
          { servicio: 'verificacion consumo', duracion_minutos: 30 },
          { servicio: 'desconexion', duracion_minutos: 30 },
          { servicio: 'emergencia', duracion_minutos: 120 },
          { servicio: 'visita conjunta', duracion_minutos: 60 },
          { servicio: 'tlis', duracion_minutos: 30 },
          { servicio: 'reconexion', duracion_minutos: 30 },
          { servicio: 'visita pre-venta', duracion_minutos: 90 },
          { servicio: 'inspeccion de frontera', duracion_minutos: 120 },
          // Default para cualquier otro servicio
          { servicio: 'default', duracion_minutos: 60 }
        ]
      };

      const activityLot = {
        nombre_lote: `Lote de ${activities.length} Actividades`,
        actividades: activities,
        configuracion: defaultConfig,
      };

      const result = await optimizeByClusters(activityLot, maxDistanceKm, method);

      setClusterResult(result);

      // Initialize selected clusters (select all by default)
      if (result.rutas_por_cluster) {
        const allClusterIds = result.rutas_por_cluster.map(r => r.cluster_id);
        setSelectedClusters(allClusterIds);
      }

      message.success({
        content: `${result.rutas_por_cluster.length} lotes generados, ${result.distancia_total_km.toFixed(2)} km total`,
        key: 'proximity-opt',
        duration: 5,
      });
    } catch (error) {
      console.error('Cluster optimization error:', error);
      message.error({
        content: `Error generando lotes: ${error.message}`,
        key: 'proximity-opt',
        duration: 10,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleOtsLoaded = useCallback((ots, nuevas, source) => {
    setAssignmentOts(ots);
    setAssignmentNuevas(nuevas);
    setAssignmentSource(source);
  }, []);

  const handleAssign = async (request) => {
    setLoading(true);
    try {
      message.loading({ content: 'Asignando OTs...', key: 'assign', duration: 0 });
      const result = await assignActivities(request);
      setAssignmentResult(result);
      setAssignmentRetorno(request.jornada.incluir_retorno);
      setAssignedCodes(request.actividades.map((a) => a.codigo_bia).sort().join('|'));
      message.success({
        content: `${result.metricas.ots_asignadas} OTs asignadas en ${result.rutas.length} rutas`,
        key: 'assign',
        duration: 5,
      });
    } catch (error) {
      console.error('Assignment error:', error);
      message.error({ content: `Error asignando: ${error.message}`, key: 'assign', duration: 10 });
    } finally {
      setLoading(false);
    }
  };

  const assignmentStale = Boolean(assignmentResult && assignmentOts)
    && assignmentOts.map((a) => a.codigo_bia).sort().join('|') !== assignedCodes;

  const resultForTab = { standard: optimizationResult, proximity: clusterResult, asignacion: assignmentResult };
  const exportNames = { standard: 'rutas-optimizadas', proximity: 'lotes-proximidad', asignacion: 'asignacion-or' };

  const handleExportResults = () => {
    const dataToExport = resultForTab[activeTab];

    if (!dataToExport) {
      message.warning('No hay resultados para exportar');
      return;
    }

    // Create JSON export
    const dataStr = JSON.stringify(dataToExport, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${exportNames[activeTab]}-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    message.success('Resultados exportados exitosamente');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '100%' }}>
          <Space>
            <AppstoreOutlined style={{ fontSize: 24, color: '#fff' }} />
            <Title level={3} style={{ color: '#fff', margin: 0 }}>
              Route Optimizer
            </Title>
          </Space>
          <Space>
            {resultForTab[activeTab] && (
              <Button
                icon={<DownloadOutlined />}
                onClick={handleExportResults}
                style={{ marginRight: 8 }}
              >
                Exportar Resultados
              </Button>
            )}
            <Text style={{ color: '#fff', fontSize: 12 }}>
              Sistema de Optimización de Rutas v1.1
            </Text>
          </Space>
        </div>
      </Header>

      <Layout>
        <Sider
          width={400}
          style={{
            background: '#fff',
            overflow: 'auto',
            height: 'calc(100vh - 64px)',
            position: 'sticky',
            top: 64,
            left: 0,
          }}
          collapsible
          collapsed={siderCollapsed}
          onCollapse={setSiderCollapsed}
          breakpoint="lg"
        >
          {/* Bottom padding so the sider collapse trigger does not cover the last button */}
          <div style={{ padding: 16, paddingBottom: 72 }}>
            <FileUploader onUploadSuccess={handleUploadSuccess} />

            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              style={{ marginTop: 16 }}
              items={[
                {
                  key: 'standard',
                  label: (
                    <span>
                      <RocketOutlined />
                      Estándar
                    </span>
                  ),
                  children: (
                    <ConfigPanel
                      activities={activities}
                      onOptimize={handleOptimize}
                      loading={loading}
                    />
                  ),
                },
                {
                  key: 'proximity',
                  label: (
                    <span>
                      <ClusterOutlined />
                      Proximidad
                    </span>
                  ),
                  children: (
                    <ProximityPanel
                      activities={activities}
                      onAnalyze={handleProximityAnalyze}
                      loading={loading}
                    />
                  ),
                },
                {
                  key: 'asignacion',
                  label: (
                    <span>
                      <ApartmentOutlined />
                      Asignación OR
                    </span>
                  ),
                  children: (
                    <AssignmentPanel
                      uploadedActivities={activities}
                      ots={assignmentOts}
                      onOtsLoaded={handleOtsLoaded}
                      onAssign={handleAssign}
                      loading={loading}
                    />
                  ),
                },
              ]}
            />
          </div>
        </Sider>

        <Layout style={{ padding: '0 24px 24px' }}>
          <Content style={{ margin: '24px 0', minHeight: 280 }}>
            <Spin spinning={loading} size="large" tip={{ standard: 'Optimizando rutas...', proximity: 'Generando lotes por proximidad...', asignacion: 'Asignando OTs (puede tardar hasta un minuto)...' }[activeTab]}>
              {activeTab === 'asignacion' ? (
                <>
                  {assignmentSource && assignmentOts && (
                    <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                      Fuente: {assignmentSource} · {assignmentOts.length} OTs
                    </Text>
                  )}
                  {assignmentStale && (
                    <Alert
                      type="info"
                      showIcon
                      style={{ marginBottom: 16 }}
                      message="Las OTs cambiaron desde la última asignación. Vuelve a pulsar Asignar para actualizar las rutas."
                    />
                  )}
                  {assignmentResult ? (
                    <AssignmentResults result={assignmentResult} nuevas={assignmentNuevas} incluirRetorno={assignmentRetorno} />
                  ) : (
                    <Card style={{ height: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Empty description="Trae OTs de Metabase, filtra por OR, elige técnicos o contratistas y pulsa Asignar" />
                    </Card>
                  )}
                </>
              ) : activeTab === 'standard' ? (
                // Standard Optimization View
                <>
                  <div style={{ marginBottom: 16 }}>
                    <MetricsPanel optimizationResult={optimizationResult} />
                  </div>

                  <div style={{ marginBottom: 16, height: 500 }}>
                    <MapView optimizationResult={optimizationResult} configuration={configuration} />
                  </div>

                  <div>
                    <RouteDetails optimizationResult={optimizationResult} />
                  </div>
                </>
              ) : (
                // Proximity Lotes View
                <>
                  <div style={{ marginBottom: 16 }}>
                    <ClusterResults 
                      clusterResult={clusterResult} 
                      type="optimize"
                    />
                  </div>
                  
                  {clusterResult && clusterResult.rutas_por_cluster && (
                    <>
                      {/* Cluster Selection Panel - Above Map */}
                      <div style={{ marginBottom: 16 }}>
                        <ClusterSelectionPanel
                          clusterResult={clusterResult}
                          selectedClusters={selectedClusters}
                          onSelectionChange={setSelectedClusters}
                        />
                      </div>
                      
                      {/* Map View */}
                      <div style={{ marginBottom: 16, height: 500 }}>
                        <ClusterMapView 
                          clusterResult={clusterResult}
                          selectedClusters={selectedClusters}
                        />
                      </div>
                    </>
                  )}
                </>
              )}
            </Spin>
          </Content>

          <Footer style={{ textAlign: 'center', background: 'transparent' }}>
            <Space direction="vertical" size={0}>
              <Text type="secondary">
                Route Optimizer - Sistema de optimización de rutas y generación de lotes por proximidad
              </Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Powered by Google OR-Tools + K-Means Clustering | React + FastAPI + Docker
              </Text>
            </Space>
          </Footer>
        </Layout>
      </Layout>
    </Layout>
  );
}

export default App;

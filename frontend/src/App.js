import React, { useCallback, useState } from 'react';
import { Layout, Typography, Space, Spin, message, Alert, Card, Empty } from 'antd';

import AssignmentPanel from './components/AssignmentPanel';
import AssignmentResults from './components/AssignmentResults';
import OtsTable from './components/OtsTable';
import { assignActivities } from './services/api';

import './App.css';

const { Header, Content, Sider, Footer } = Layout;
const { Text } = Typography;

const codesKey = (ots) => ots.map((a) => a.codigo_bia).sort().join('|');

function App() {
  const [loading, setLoading] = useState(false);
  const [siderCollapsed, setSiderCollapsed] = useState(false);
  const [ots, setOts] = useState(null);
  const [nuevas, setNuevas] = useState(new Set());
  const [source, setSource] = useState('');
  const [mapeo, setMapeo] = useState({});
  const [result, setResult] = useState(null);
  const [incluirRetorno, setIncluirRetorno] = useState(true);
  const [assignedCodes, setAssignedCodes] = useState('');
  const [config, setConfig] = useState({ tecnicos: [], or_contratistas: {}, tipos_ot: {}, card_id: null });

  const handleOtsLoaded = useCallback((loaded, nuevasSet, sourceLabel, mapeoUsado) => {
    setOts(loaded);
    setNuevas(nuevasSet);
    setSource(sourceLabel);
    setMapeo(mapeoUsado || {});
  }, []);

  const handleAssign = useCallback(async (request) => {
    setLoading(true);
    try {
      message.loading({ content: 'Calculando la recomendación...', key: 'assign', duration: 0 });
      const assignment = await assignActivities(request);
      setResult(assignment);
      setIncluirRetorno(request.jornada.incluir_retorno);
      setAssignedCodes(codesKey(request.actividades));
      const m = assignment.metricas;
      message.success({
        content: `${m.ots_con_tecnicos} OTs a técnicos, ${m.ots_con_contratistas} a contratistas`,
        key: 'assign',
        duration: 5,
      });
    } catch (error) {
      console.error('Assignment error:', error);
      message.error({ content: `Error calculando la recomendación: ${error.message}`, key: 'assign', duration: 10 });
    } finally {
      setLoading(false);
    }
  }, []);

  const stale = Boolean(result && ots) && codesKey(ots) !== assignedCodes;

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header className="ios-header">
        <div className="ios-header-inner">
          <Space size={12}>
            <img src={`${process.env.PUBLIC_URL}/bolt.png`} alt="" className="app-icon" />
            <div>
              <div className="app-title">Ruteo</div>
              <div className="app-subtitle">A quién enviar cada OT: técnicos in-house o contratistas</div>
            </div>
          </Space>
          {source && ots && (
            <Text type="secondary">{source} · {ots.length} OTs</Text>
          )}
        </div>
      </Header>

      <Layout>
        <Sider
          width={400}
          className="ios-sider"
          style={{
            overflow: 'auto',
            height: 'calc(100vh - 64px)',
            position: 'sticky',
            top: 64,
            left: 0,
          }}
          collapsible
          collapsed={siderCollapsed}
          onCollapse={setSiderCollapsed}
          collapsedWidth={0}
          breakpoint="lg"
        >
          {/* Bottom padding so the sider collapse trigger does not cover the last card */}
          <div style={{ padding: 16, paddingBottom: 72 }}>
            <AssignmentPanel
              ots={ots}
              onOtsLoaded={handleOtsLoaded}
              onAssign={handleAssign}
              loading={loading}
              config={config}
              onConfigChange={setConfig}
            />
          </div>
        </Sider>

        <Layout style={{ padding: '0 24px 24px' }}>
          <Content style={{ margin: '24px 0', minHeight: 280 }}>
            <Spin spinning={loading} size="large" tip="Calculando la recomendación (puede tardar hasta un minuto)...">
              {stale && (
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message="Las OTs cambiaron desde la última recomendación. Pulsa Recalcular para actualizarla."
                />
              )}
              {result && (
                <AssignmentResults result={result} ots={ots} nuevas={nuevas} incluirRetorno={incluirRetorno} />
              )}
              {!result && !ots?.length && (
                <Card style={{ height: 420, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Empty description="Pulsa «Extraer y recomendar» para traer las OTs pendientes de Metabase" />
                </Card>
              )}
              <OtsTable
                ots={ots}
                nuevas={nuevas}
                mapeo={mapeo}
                config={config}
                title={`Todas las OTs (${ots?.length || 0}) con todas sus columnas`}
              />
            </Spin>
          </Content>

          <Footer style={{ textAlign: 'center', background: 'transparent' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Ruteo · Google OR-Tools · React · FastAPI
            </Text>
          </Footer>
        </Layout>
      </Layout>
    </Layout>
  );
}

export default App;

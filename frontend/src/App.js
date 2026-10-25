import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Layout, Typography, Space, Spin, message, Alert, Card, Empty, Button, DatePicker, Segmented, Tag,
} from 'antd';
import { LeftOutlined, RightOutlined, UndoOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

import AssignmentPanel from './components/AssignmentPanel';
import AssignmentResults from './components/AssignmentResults';
import OtsTable from './components/OtsTable';
import { assignActivities, getCatalog } from './services/api';

import './App.css';

const { Header, Content, Sider, Footer } = Layout;
const { Text } = Typography;

const codesKey = (ots) => ots.map((a) => a.codigo_bia).sort().join('|');
const ISO_DAY = 'YYYY-MM-DD';

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
  const [catalog, setCatalog] = useState({ sedes: [], empresas: [], avisos: [] });
  const [dia, setDia] = useState(dayjs().format(ISO_DAY));
  const [filtro, setFiltro] = useState('todas');
  // Manual edits: OT → "tecnico:<id>", "empresa:<id>", "contratista" or "auto"
  const [fijas, setFijas] = useState({});
  // Last request built by the panel, to recalculate when the day or an edit changes
  const baseRef = useRef(null);

  useEffect(() => {
    getCatalog().then(setCatalog).catch((e) => message.error(`No se pudo leer el catálogo: ${e.message}`));
  }, []);

  const handleOtsLoaded = useCallback((loaded, nuevasSet, sourceLabel, mapeoUsado) => {
    setOts(loaded);
    setNuevas(nuevasSet);
    setSource(sourceLabel);
    setMapeo(mapeoUsado || {});
  }, []);

  const handleAssign = useCallback(async (base, overrides = {}) => {
    baseRef.current = base;
    const request = { ...base, dia: overrides.dia ?? dia, fijas: overrides.fijas ?? fijas };
    setLoading(true);
    try {
      message.loading({ content: 'Calculando el plan del día...', key: 'assign', duration: 0 });
      const assignment = await assignActivities(request);
      setResult(assignment);
      setIncluirRetorno(request.jornada.incluir_retorno);
      setAssignedCodes(codesKey(request.actividades));
      const m = assignment.metricas;
      message.success({
        content: `${dayjs(request.dia).format('ddd D MMM')}: ${m.ots_con_tecnicos} OTs a técnicos, ${m.ots_con_contratistas} a contratistas`,
        key: 'assign',
        duration: 5,
      });
    } catch (error) {
      console.error('Assignment error:', error);
      message.error({ content: `Error calculando el plan: ${error.message}`, key: 'assign', duration: 10 });
    } finally {
      setLoading(false);
    }
  }, [dia, fijas]);

  const changeDay = (nuevo) => {
    setDia(nuevo);
    if (baseRef.current) handleAssign(baseRef.current, { dia: nuevo });
  };

  const handleEdit = (codigo, value, situacion) => {
    const next = { ...fijas };
    // "Que decida la app" on a pending OT is the same as no edit
    if (!value || (value === 'auto' && situacion !== 'asignada')) delete next[codigo];
    else next[codigo] = value;
    setFijas(next);
    if (baseRef.current) handleAssign(baseRef.current, { fijas: next });
  };

  const clearEdits = () => {
    setFijas({});
    if (baseRef.current) handleAssign(baseRef.current, { fijas: {} });
  };

  const stale = Boolean(result && ots) && codesKey(ots) !== assignedCodes;
  const disponibles = new Set(baseRef.current?.tecnicos_ids || []);
  const tecnicosEdicion = config.tecnicos
    .filter((t) => t.activo !== false)
    .map((t) => ({ id: t.id, nombre: t.nombre, disponible: disponibles.has(t.id) }));
  const decisiones = result?.decisiones || [];
  const cuenta = (situacion) => decisiones.filter((d) => d.situacion === situacion).length;
  const ediciones = Object.keys(fijas).length;

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
              catalog={catalog}
              dia={dia}
            />
          </div>
        </Sider>

        <Layout style={{ padding: '0 24px 24px' }}>
          <Content style={{ margin: '24px 0', minHeight: 280 }}>
            <Card size="small" className="day-bar" style={{ marginBottom: 16 }}>
              <Space wrap size={12} style={{ width: '100%', justifyContent: 'space-between' }}>
                <Space size={4}>
                  <Button
                    icon={<LeftOutlined />}
                    disabled={loading}
                    onClick={() => changeDay(dayjs(dia).subtract(1, 'day').format(ISO_DAY))}
                  />
                  <DatePicker
                    value={dayjs(dia)}
                    allowClear={false}
                    disabled={loading}
                    format="dddd D [de] MMMM YYYY"
                    onChange={(d) => d && changeDay(d.format(ISO_DAY))}
                    style={{ width: 240 }}
                  />
                  <Button
                    icon={<RightOutlined />}
                    disabled={loading}
                    onClick={() => changeDay(dayjs(dia).add(1, 'day').format(ISO_DAY))}
                  />
                  {dia !== dayjs().format(ISO_DAY) && (
                    <Button type="link" disabled={loading} onClick={() => changeDay(dayjs().format(ISO_DAY))}>Hoy</Button>
                  )}
                </Space>
                <Segmented
                  value={filtro}
                  onChange={setFiltro}
                  options={[
                    { value: 'todas', label: `Todas${result ? ` (${decisiones.length})` : ''}` },
                    { value: 'asignadas', label: `Ya asignadas${result ? ` (${cuenta('asignada')})` : ''}` },
                    { value: 'pendientes', label: `Por asignar${result ? ` (${cuenta('pendiente')})` : ''}` },
                  ]}
                />
                {ediciones > 0 && (
                  <Space size={4}>
                    <Tag color="gold">{ediciones} editada{ediciones > 1 ? 's' : ''} a mano</Tag>
                    <Button size="small" icon={<UndoOutlined />} disabled={loading} onClick={clearEdits}>Quitar ediciones</Button>
                  </Space>
                )}
              </Space>
              <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 6 }}>
                El plan del día toma las OTs ya asignadas en Metabase para esa fecha (se respetan si su técnico está
                disponible) y sugiere a quién enviar las pendientes. Cambia «Enviar a» en la tabla para fijar otra opción.
              </Text>
            </Card>
            <Spin spinning={loading} size="large" tip="Calculando el plan del día (puede tardar hasta un minuto)...">
              {stale && (
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message="Las OTs cambiaron desde la última recomendación. Pulsa Recalcular para actualizarla."
                />
              )}
              {result && (
                <AssignmentResults
                  result={result}
                  ots={ots}
                  nuevas={nuevas}
                  incluirRetorno={incluirRetorno}
                  filtro={filtro}
                  fijas={fijas}
                  onEdit={handleEdit}
                  tecnicos={tecnicosEdicion}
                  empresas={catalog.empresas}
                  editing={loading}
                />
              )}
              {!result && !ots?.length && (
                <Card style={{ height: 420, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Empty description="Pulsa «Extraer y recomendar» para traer las OTs de Metabase y armar el plan del día" />
                </Card>
              )}
              <OtsTable
                ots={ots}
                nuevas={nuevas}
                mapeo={mapeo}
                config={config}
                title={`Todas las OTs de la pregunta (${ots?.length || 0}) con todas sus columnas`}
              />
            </Spin>
          </Content>

          <Footer style={{ textAlign: 'center', background: 'transparent' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Ruteo · Google OR-Tools · OSRM · React · FastAPI
            </Text>
          </Footer>
        </Layout>
      </Layout>
    </Layout>
  );
}

export default App;

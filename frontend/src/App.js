import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Layout, Space, Spin, message, Alert, Button, DatePicker, Segmented, Tag, Tooltip,
} from 'antd';
import {
  LeftOutlined, RightOutlined, UndoOutlined, ThunderboltFilled, ReloadOutlined, UnorderedListOutlined,
  EnvironmentOutlined, NodeIndexOutlined, TableOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import AssignmentPanel from './components/AssignmentPanel';
import AssignmentResults from './components/AssignmentResults';
import OtsTable from './components/OtsTable';
import { assignActivities, getCatalog, getZones } from './services/api';

import './App.css';

const { Header, Content, Sider } = Layout;

const codesKey = (ots) => ots.map((a) => a.codigo_bia).sort().join('|');
const ISO_DAY = 'YYYY-MM-DD';
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);

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
  const [zonas, setZonas] = useState({ equipos: [], transito: [] });
  const [dia, setDia] = useState(dayjs().format(ISO_DAY));
  const [vista, setVista] = useState('lista');
  const [filtro, setFiltro] = useState('todas');
  // Manual edits: OT → "tecnico:<id>", "empresa:<id>", "contratista" or "auto"
  const [fijas, setFijas] = useState({});
  const [panelState, setPanelState] = useState({ canExtract: false, fetching: false });
  const panelRef = useRef(null);
  // Last request built by the panel, to recalculate when the day or an edit changes
  const baseRef = useRef(null);

  useEffect(() => {
    getCatalog().then(setCatalog).catch((e) => message.error(`No se pudo leer el catálogo: ${e.message}`));
    getZones().then(setZonas).catch(() => {});
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
        duration: 4,
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

  const busy = loading || panelState.fetching;
  const stale = Boolean(result && ots) && codesKey(ots) !== assignedCodes;
  const disponibles = new Set(baseRef.current?.tecnicos_ids || []);
  const tecnicosEdicion = config.tecnicos
    .filter((t) => t.activo !== false)
    .map((t) => ({ id: t.id, nombre: t.nombre, disponible: disponibles.has(t.id) }));
  const decisiones = result?.decisiones || [];
  const cuenta = (situacion) => decisiones.filter((d) => d.situacion === situacion).length;
  const ediciones = Object.keys(fijas).length;
  const hoy = dayjs().format(ISO_DAY);

  return (
    <Layout className="app-shell">
      <Header className="ios-header">
        <div className="ios-header-inner">
          <Space size={12}>
            <img src={`${process.env.PUBLIC_URL}/bolt.png`} alt="" className="app-icon" />
            <div>
              <div className="app-title">Ruteo</div>
              <div className="app-subtitle">
                {source && ots ? `${source} · ${ots.length} OTs` : 'Técnicos Bia o contratistas, OT por OT'}
              </div>
            </div>
          </Space>
          <Space size={8}>
            {ots?.length > 0 && (
              <Tooltip title="Recalcular con los ajustes actuales">
                <Button shape="circle" size="large" icon={<ReloadOutlined />} disabled={busy} onClick={() => panelRef.current?.recalc()} />
              </Tooltip>
            )}
            <Button
              type="primary"
              shape="round"
              size="large"
              icon={<ThunderboltFilled />}
              loading={busy}
              disabled={!panelState.canExtract}
              onClick={() => panelRef.current?.extract()}
            >
              Extraer y recomendar
            </Button>
          </Space>
        </div>
      </Header>

      <Layout>
        <Sider
          width={380}
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
          {/* Bottom padding so the sider collapse trigger does not cover the last section */}
          <div style={{ padding: 16, paddingBottom: 72 }}>
            <AssignmentPanel
              ref={panelRef}
              ots={ots}
              onOtsLoaded={handleOtsLoaded}
              onAssign={handleAssign}
              loading={loading}
              config={config}
              onConfigChange={setConfig}
              catalog={catalog}
              dia={dia}
              zonas={zonas}
              onStateChange={setPanelState}
            />
          </div>
        </Sider>

        <Layout className="main-pane">
          <Content>
            <div className="day-header">
              <div>
                <div className="eyebrow">{dia === hoy ? 'Plan de hoy' : 'Plan del día'}</div>
                <div className="large-title">{capitalize(dayjs(dia).format('dddd D [de] MMMM'))}</div>
              </div>
              <Space size={6} className="day-nav">
                <Button
                  shape="circle"
                  icon={<LeftOutlined />}
                  disabled={busy}
                  onClick={() => changeDay(dayjs(dia).subtract(1, 'day').format(ISO_DAY))}
                />
                <DatePicker
                  value={dayjs(dia)}
                  allowClear={false}
                  disabled={busy}
                  variant="filled"
                  format="DD/MM/YYYY"
                  onChange={(d) => d && changeDay(d.format(ISO_DAY))}
                  style={{ width: 132 }}
                />
                <Button
                  shape="circle"
                  icon={<RightOutlined />}
                  disabled={busy}
                  onClick={() => changeDay(dayjs(dia).add(1, 'day').format(ISO_DAY))}
                />
                {dia !== hoy && (
                  <Button shape="round" disabled={busy} onClick={() => changeDay(hoy)}>Hoy</Button>
                )}
              </Space>
            </div>

            <div className="toolbar">
              <Segmented
                value={vista}
                onChange={setVista}
                options={[
                  { value: 'lista', label: 'Lista', icon: <UnorderedListOutlined /> },
                  { value: 'mapa', label: 'Mapa', icon: <EnvironmentOutlined /> },
                  { value: 'rutas', label: 'Rutas', icon: <NodeIndexOutlined /> },
                  { value: 'ots', label: 'Metabase', icon: <TableOutlined /> },
                ]}
              />
              {vista !== 'ots' && (
                <Segmented
                  value={filtro}
                  onChange={setFiltro}
                  options={[
                    { value: 'todas', label: `Todas${result ? ` ${decisiones.length}` : ''}` },
                    { value: 'asignadas', label: `Ya asignadas${result ? ` ${cuenta('asignada')}` : ''}` },
                    { value: 'pendientes', label: `Por asignar${result ? ` ${cuenta('pendiente')}` : ''}` },
                  ]}
                />
              )}
              {ediciones > 0 && (
                <Space size={4}>
                  <Tag color="gold" bordered={false}>{ediciones} editada{ediciones > 1 ? 's' : ''}</Tag>
                  <Button size="small" shape="round" icon={<UndoOutlined />} disabled={busy} onClick={clearEdits}>
                    Quitar ediciones
                  </Button>
                </Space>
              )}
            </div>

            <Spin spinning={loading} size="large" tip="Calculando el plan del día...">
              {stale && (
                <Alert
                  type="info"
                  showIcon
                  className="ios-alert"
                  message="Las OTs cambiaron desde la última recomendación. Pulsa recalcular (↻) para actualizarla."
                />
              )}
              {vista === 'ots' && (
                ots?.length ? (
                  <OtsTable ots={ots} nuevas={nuevas} mapeo={mapeo} config={config} title={`Todas las OTs de la pregunta (${ots.length})`} />
                ) : <EmptyState />
              )}
              {vista !== 'ots' && (result ? (
                <AssignmentResults
                  result={result}
                  ots={ots}
                  nuevas={nuevas}
                  incluirRetorno={incluirRetorno}
                  view={vista}
                  filtro={filtro}
                  fijas={fijas}
                  onEdit={handleEdit}
                  tecnicos={tecnicosEdicion}
                  empresas={catalog.empresas}
                  editing={loading}
                />
              ) : <EmptyState />)}
            </Spin>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
}

const EmptyState = () => (
  <div className="empty-state">
    <img src={`${process.env.PUBLIC_URL}/bolt.png`} alt="" />
    <div className="empty-title">Sin plan todavía</div>
    <div className="empty-text">
      Pulsa «Extraer y recomendar» para traer las OTs de Metabase: las ya asignadas para este día se respetan y
      la app sugiere a quién enviar las pendientes.
    </div>
  </div>
);

export default App;

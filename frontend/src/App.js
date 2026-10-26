import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Layout, Space, Spin, message, Alert, Button, DatePicker, Segmented, Tooltip, Input, Select,
} from 'antd';
import {
  LeftOutlined, RightOutlined, UndoOutlined, ReloadOutlined, SearchOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import AssignmentPanel from './components/AssignmentPanel';
import AssignmentResults from './components/AssignmentResults';
import OtsTable from './components/OtsTable';
import UtilizationDashboard from './components/UtilizationDashboard';
import { assignActivities, getCatalog, getZones } from './services/api';
import { matrizPorVias } from './services/osrm';
import { normalizeText } from './services/otTypes';

import './App.css';

const { Header, Content, Sider } = Layout;

const codesKey = (ots) => ots.map((a) => a.codigo_bia).sort().join('|');
const ISO_DAY = 'YYYY-MM-DD';
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);

// Everything the name search looks at
const searchText = (codigo, actividad, responsable) => normalizeText([
  codigo, actividad?.nombre, actividad?.direccion, actividad?.ciudad, actividad?.servicio, actividad?.or_operador,
  responsable, actividad?.asignado_a, actividad?.contratista_asignado,
].filter(Boolean).join(' '));

// "Asignado a" options: every Bia technician, plus the contractors and externals with OTs in the plan
const assigneeOptions = (result, tecnicosApp) => {
  const tecnicos = new Set(tecnicosApp.filter((t) => t.activo !== false).map((t) => t.nombre));
  const contratistas = new Set();
  (result?.rutas || []).forEach((r) => {
    if (r.tipo === 'tecnico') r.integrantes.forEach((n) => tecnicos.add(n));
    else contratistas.add(r.sede.empresa);
  });
  const externos = new Set((result?.decisiones || []).filter((d) => d.enviar_a === 'externo').map((d) => d.responsable));
  const grupos = [
    { label: 'Técnicos Bia', options: [...tecnicos].sort().map((n) => ({ value: `t:${n}`, label: n })) },
    { label: 'Contratistas', options: [...contratistas].sort().map((n) => ({ value: `c:${n}`, label: n })) },
    { label: 'Externos', options: [...externos].sort().map((n) => ({ value: `e:${n}`, label: n })) },
  ];
  if ((result?.decisiones || []).some((d) => d.enviar_a === 'sin_asignar')) {
    grupos.push({ label: 'Otros', options: [{ value: 'sin', label: 'Sin asignar' }] });
  }
  return grupos.filter((g) => g.options.length);
};

// Several people can be selected: the OT matches if it goes to any of them
const matchesAssignee = (decision, values) => !values.length || values.some((value) => {
  if (value === 'sin') return decision.enviar_a === 'sin_asignar';
  const nombre = value.slice(2);
  if (value.startsWith('t:')) return decision.enviar_a === 'tecnico' && (decision.responsable || '').split(' + ').includes(nombre);
  if (value.startsWith('c:')) return decision.enviar_a === 'contratista' && (decision.responsable || '').startsWith(`${nombre} (`);
  return decision.enviar_a === 'externo' && decision.responsable === nombre;
});

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
  // Filters: name search, status and who it is assigned to (the date is the plan day)
  const [busqueda, setBusqueda] = useState('');
  const [estado, setEstado] = useState('todas');
  const [asignadoA, setAsignadoA] = useState([]);
  // Weekly hours of a technician and working days, for utilization (UTR)
  const [capacidad, setCapacidad] = useState({ horasSemana: 42, diasSemana: 5 });
  // Who the plan sends it to: "tecnico", "contratista", "externo" or "sin_asignar" (the summary tiles)
  const [destino, setDestino] = useState(null);
  // Manual edits: OT → "tecnico:<id>", "empresa:<id>", "contratista" or "auto"
  const [fijas, setFijas] = useState({});
  const [panelState, setPanelState] = useState({ canExtract: false, fetching: false });
  const [actualizado, setActualizado] = useState(null);
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
    setActualizado(dayjs());
  }, []);

  const handleAssign = useCallback(async (base, overrides = {}) => {
    baseRef.current = base;
    const diaPlan = overrides.dia ?? dia;
    // Only the OTs of the plan travel to the server: pending ones and those assigned for that day
    // (the history used for utilization stays in the browser)
    const request = {
      ...base,
      actividades: base.actividades.filter((a) => a.situacion !== 'asignada' || !a.fecha_visita || a.fecha_visita === diaPlan),
      dia: diaPlan,
      fijas: overrides.fijas ?? fijas,
    };
    setLoading(true);
    try {
      message.loading({ content: 'Calculando el plan del día...', key: 'assign', duration: 0 });
      let assignment = await assignActivities(request);
      // The backend could not reach the road server: the browser asks for the road times and the plan is redone
      if (!assignment.metricas.tiempos_por_vias) {
        message.loading({ content: 'Consultando tiempos por carretera desde el navegador...', key: 'assign', duration: 0 });
        const puntos = [
          ...catalog.sedes.map((s) => [s.coordinates.latitude, s.coordinates.longitude]),
          ...request.actividades
            .filter((a) => a.coordinates && (a.situacion !== 'asignada' || a.fecha_visita === request.dia))
            .map((a) => [a.coordinates.latitude, a.coordinates.longitude]),
        ];
        const matriz = await matrizPorVias(puntos);
        if (matriz) assignment = await assignActivities({ ...request, matriz });
      }
      setResult(assignment);
      setIncluirRetorno(request.jornada.incluir_retorno);
      setAssignedCodes(codesKey(base.actividades));
      const m = assignment.metricas;
      message.success({
        content: `${dayjs(request.dia).format('ddd D MMM')}: ${m.ots_con_tecnicos} a técnicos, ${m.ots_con_contratistas} a contratistas`,
        key: 'assign',
        duration: 3,
      });
    } catch (error) {
      console.error('Assignment error:', error);
      message.error({ content: `Error calculando el plan: ${error.message}`, key: 'assign', duration: 10 });
    } finally {
      setLoading(false);
    }
  }, [dia, fijas, catalog]);

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

  // Activity of each OT: from Metabase and, for the plan, as the optimizer returned it
  const actividades = useMemo(() => {
    const porCodigo = {};
    (ots || []).forEach((a) => { porCodigo[a.codigo_bia] = a; });
    (result?.rutas || []).forEach((r) => r.ruta.paradas.forEach((p) => { porCodigo[p.actividad.codigo_bia] = p.actividad; }));
    (result?.sin_asignar || []).forEach(({ actividad }) => { porCodigo[actividad.codigo_bia] = actividad; });
    return porCodigo;
  }, [ots, result]);

  const filtrosActivos = Boolean(busqueda.trim() || estado !== 'todas' || asignadoA.length || destino);
  const visibles = useMemo(() => {
    if (!result || !filtrosActivos) return null;
    const texto = normalizeText(busqueda.trim());
    return new Set(result.decisiones.filter((d) => (
      (estado === 'todas' || (estado === 'pendientes' ? d.situacion === 'pendiente' : d.situacion === 'asignada'))
      && (!destino || d.enviar_a === destino)
      && matchesAssignee(d, asignadoA)
      && (!texto || searchText(d.codigo_bia, actividades[d.codigo_bia], d.responsable).includes(texto))
    )).map((d) => d.codigo_bia));
  }, [result, filtrosActivos, busqueda, estado, destino, asignadoA, actividades]);

  // The full table shows the OTs of the day (pending and assigned for that date) with the same filters
  const otsFiltradas = useMemo(() => {
    const texto = normalizeText(busqueda.trim());
    const decisiones = Object.fromEntries((result?.decisiones || []).map((d) => [d.codigo_bia, d]));
    return (ots || []).filter((a) => (
      (a.situacion !== 'asignada' || a.fecha_visita === dia)
      && (estado === 'todas' || (estado === 'pendientes' ? a.situacion === 'pendiente' : a.situacion === 'asignada'))
      && (!destino || decisiones[a.codigo_bia]?.enviar_a === destino)
      && (!asignadoA.length || (decisiones[a.codigo_bia] && matchesAssignee(decisiones[a.codigo_bia], asignadoA)))
      && (!texto || searchText(a.codigo_bia, a, decisiones[a.codigo_bia]?.responsable).includes(texto))
    ));
  }, [ots, result, dia, busqueda, estado, destino, asignadoA]);

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
          <Space size={10}>
            <img src={`${process.env.PUBLIC_URL}/bolt.png`} alt="" className="app-icon" />
            <span className="app-title">Ruteo</span>
            {ots && (
              <span className="app-subtitle">
                {ots.length} OTs{actualizado ? ` · actualizado ${actualizado.format('HH:mm')}` : ''}
                {source.startsWith('Archivo') ? ` · ${source}` : ''}
              </span>
            )}
          </Space>
          <Space size={6}>
            {ots?.length > 0 && (
              <Tooltip title="Recalcular con los ajustes actuales">
                <Button type="text" icon={<ReloadOutlined />} disabled={busy} onClick={() => panelRef.current?.recalc()} />
              </Tooltip>
            )}
            <Button
              type="primary"
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
          width={340}
          className="ios-sider"
          style={{
            overflow: 'auto',
            height: 'calc(100vh - 56px)',
            position: 'sticky',
            top: 56,
            left: 0,
          }}
          collapsible
          collapsed={siderCollapsed}
          onCollapse={setSiderCollapsed}
          collapsedWidth={0}
          breakpoint="lg"
        >
          {/* Bottom padding so the sider collapse trigger does not cover the last section */}
          <div style={{ padding: '8px 0 72px' }}>
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
            <div className="title-row">
              <div>
                <div className="eyebrow">{dia === hoy ? 'Hoy' : 'Plan del día'}</div>
                <div className="large-title">{capitalize(dayjs(dia).format('dddd D [de] MMMM'))}</div>
              </div>
              <Segmented
                value={vista}
                onChange={setVista}
                options={[
                  { value: 'lista', label: 'Lista' },
                  { value: 'mapa', label: 'Mapa' },
                  { value: 'rutas', label: 'Rutas' },
                  { value: 'utilizacion', label: 'Utilización' },
                  { value: 'tabla', label: 'Tabla completa' },
                ]}
              />
            </div>

            <div className="filter-bar">
              {vista !== 'utilizacion' && (
                <Input
                  allowClear
                  variant="filled"
                  prefix={<SearchOutlined />}
                  placeholder="Buscar por nombre, OT o dirección"
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  className="filter-search"
                />
              )}
              <Space.Compact className="filter-date">
                <Button
                  icon={<LeftOutlined />}
                  disabled={busy}
                  onClick={() => changeDay(dayjs(dia).subtract(1, 'day').format(ISO_DAY))}
                />
                <DatePicker
                  value={dayjs(dia)}
                  allowClear={false}
                  disabled={busy}
                  format="DD/MM/YYYY"
                  onChange={(d) => d && changeDay(d.format(ISO_DAY))}
                  style={{ width: 128 }}
                />
                <Button
                  icon={<RightOutlined />}
                  disabled={busy}
                  onClick={() => changeDay(dayjs(dia).add(1, 'day').format(ISO_DAY))}
                />
              </Space.Compact>
              {dia !== hoy && (
                <Button type="link" disabled={busy} onClick={() => changeDay(hoy)} style={{ paddingInline: 4 }}>Hoy</Button>
              )}
              {vista !== 'utilizacion' && (
              <Segmented
                value={estado}
                onChange={setEstado}
                options={[
                  { value: 'todas', label: `Todas${result ? ` ${decisiones.length}` : ''}` },
                  { value: 'pendientes', label: `Por asignar${result ? ` ${cuenta('pendiente')}` : ''}` },
                  { value: 'asignadas', label: `Asignadas${result ? ` ${cuenta('asignada')}` : ''}` },
                ]}
              />
              )}
              <Select
                mode="multiple"
                allowClear
                showSearch
                maxTagCount="responsive"
                variant="filled"
                placeholder="Asignado a"
                value={asignadoA}
                onChange={setAsignadoA}
                options={assigneeOptions(result, config.tecnicos)}
                optionFilterProp="label"
                popupMatchSelectWidth={false}
                className="filter-assignee"
              />
              {filtrosActivos && (
                <Button type="link" onClick={() => { setBusqueda(''); setEstado('todas'); setAsignadoA([]); setDestino(null); }} style={{ paddingInline: 4 }}>
                  Limpiar
                </Button>
              )}
              {ediciones > 0 && (
                <Button type="text" icon={<UndoOutlined />} disabled={busy} onClick={clearEdits}>
                  Quitar {ediciones} {ediciones > 1 ? 'ediciones' : 'edición'}
                </Button>
              )}
            </div>

            <Spin spinning={loading} tip="Calculando el plan del día...">
              {stale && (
                <Alert
                  type="info"
                  showIcon
                  className="ios-alert"
                  message="Las OTs cambiaron desde el último cálculo. Pulsa recalcular (↻) arriba a la derecha."
                />
              )}
              {vista === 'tabla' && (
                ots?.length ? (
                  <OtsTable ots={otsFiltradas} nuevas={nuevas} mapeo={mapeo} config={config} title={`OTs del día (${otsFiltradas.length})`} />
                ) : <EmptyState />
              )}
              {vista === 'utilizacion' && (
                <UtilizationDashboard
                  ots={ots}
                  config={config}
                  dia={dia}
                  result={result}
                  tecnicosFiltro={asignadoA.filter((v) => v.startsWith('t:')).map((v) => v.slice(2))}
                  horasSemana={capacidad.horasSemana}
                  diasSemana={capacidad.diasSemana}
                  onCapacidad={(cambio) => setCapacidad((prev) => ({ ...prev, ...cambio }))}
                />
              )}
              {vista !== 'tabla' && vista !== 'utilizacion' && (result ? (
                <AssignmentResults
                  result={result}
                  ots={ots}
                  nuevas={nuevas}
                  incluirRetorno={incluirRetorno}
                  view={vista}
                  visibles={visibles}
                  horasDia={capacidad.horasSemana / capacidad.diasSemana}
                  estado={estado}
                  destino={destino}
                  onFiltrar={({ estado: nuevoEstado, destino: nuevoDestino }) => {
                    if (nuevoEstado !== undefined) setEstado(nuevoEstado);
                    if (nuevoDestino !== undefined) setDestino(nuevoDestino);
                  }}
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
    <div className="empty-title">Sin plan todavía</div>
    <div className="empty-text">
      Pulsa «Extraer y recomendar»: las OTs ya asignadas para este día se respetan y la app sugiere a quién enviar las pendientes.
    </div>
  </div>
);

export default App;

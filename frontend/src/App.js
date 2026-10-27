import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Layout, Space, Spin, message, Alert, Button, DatePicker, Segmented, Tooltip, Input, Select,
} from 'antd';
import {
  LeftOutlined, RightOutlined, UndoOutlined, ReloadOutlined, SearchOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
  TeamOutlined, ShopOutlined, AppstoreOutlined, SettingOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import AssignmentPanel from './components/AssignmentPanel';
import AssignmentResults from './components/AssignmentResults';
import LoteBar, { POR_CERCANIA } from './components/LoteBar';
import LoteModal from './components/LoteModal';
import OtsTable from './components/OtsTable';
import UtilizationDashboard from './components/UtilizationDashboard';
import {
  assignActivities, getCatalog, getOperators, getUtilization, getZones, proposeBatch,
} from './services/api';
import { matrizPorVias } from './services/osrm';
import { normalizeText } from './services/otTypes';

import './App.css';

const { Header, Content, Sider } = Layout;

// Whether the panel is shown: remembered in this browser; the first time, open on wide screens
const PANEL_KEY = 'ruteo_panel_abierto';
// The OR filter chosen, remembered in this browser
const OR_KEY = 'ruteo_filtro_or';
const leerPanel = () => {
  try {
    const guardado = localStorage.getItem(PANEL_KEY);
    if (guardado !== null) return guardado === '1';
  } catch (error) {
    // Without storage it uses the screen width
  }
  return window.innerWidth >= 992;
};

// Sections of the panel the toolbar opens directly
const SECCIONES_PANEL = [
  { key: 'tecnicos', label: 'Técnicos', icon: <TeamOutlined /> },
  { key: 'contratistas', label: 'Contratistas por OR', icon: <ShopOutlined /> },
  { key: 'tipos', label: 'Tipos de OT', icon: <AppstoreOutlined /> },
  { key: 'ajustes', label: 'Ajustes', icon: <SettingOutlined /> },
];

// Why a loaded OT is or is not in the plan of `dia`, for the full table
const DESTINO_TEXTO = {
  tecnico: 'técnico Bia', contratista: 'contratista', externo: 'externo', sin_asignar: 'sin asignar',
};
const enElPlan = (a, { decision, dia, hoy, filtroOr, calculadas, cerrada }) => {
  const fecha = a.fecha_visita ? dayjs(a.fecha_visita).format('D MMM') : null;
  if (decision) return { dentro: true, texto: `Sí · a ${DESTINO_TEXTO[decision.enviar_a]}` };
  if (calculadas && !calculadas.has(a.codigo_bia)) return { dentro: false, texto: 'Llegó después del último cálculo: recalcula (↻)' };
  if (filtroOr.length && !filtroOr.includes(normalizeText(a.or_operador))) return { dentro: false, texto: 'Su OR no está en el filtro de Ajustes' };
  if (a.situacion === 'asignada') {
    if (!a.fecha_visita) return { dentro: false, texto: 'Asignada sin fecha de visita en Metabase' };
    if (cerrada) return { dentro: false, texto: `Cerrada el ${fecha}: cuenta para la utilización` };
    return { dentro: false, texto: `Asignada para el ${fecha}` };
  }
  if (!a.fecha_visita) return { dentro: false, texto: 'Pendiente sin fecha: entra en el plan de hoy' };
  if (a.fecha_visita < hoy) return { dentro: false, texto: `Vencida (era el ${fecha}): entra en el plan de hoy` };
  if (a.fecha_visita !== dia) return { dentro: false, texto: `Pendiente para el ${fecha}` };
  return { dentro: false, texto: 'No entró en el plan' };
};

const codesKey = (ots) => ots.map((a) => a.codigo_bia).sort().join('|');

/**
 * Whether an OT belongs to the plan of `dia`: the ones whose visit date is that day, assigned or
 * pending, as in Olibia. Only today's plan also takes the pending ones whose date already passed and
 * the undated pending ones, so they get planned. Assigned without a date also travel, so the server
 * can report them (they enter no plan).
 */
const entraEnElDia = (a, dia, hoy) => {
  if (a.fecha_visita === dia) return true;
  if (!a.fecha_visita) return a.situacion === 'asignada' || dia === hoy;
  return a.situacion === 'pendiente' && a.fecha_visita < hoy && dia === hoy;
};
const ISO_DAY = 'YYYY-MM-DD';
// Pending OTs of any date: overdue first, then today, the next days and those without a date
const GRUPOS_PENDIENTES = { vencida: 0, hoy: 1, proxima: 2, sin_fecha: 3 };
const grupoPendiente = (fecha, hoy) => {
  if (!fecha) return 'sin_fecha';
  if (fecha < hoy) return 'vencida';
  return fecha === hoy ? 'hoy' : 'proxima';
};
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);

// Everything the name search looks at
const searchText = (codigo, actividad, responsable) => normalizeText([
  codigo, actividad?.nombre, actividad?.direccion, actividad?.ciudad, actividad?.servicio, actividad?.or_operador,
  responsable, actividad?.asignado_a, actividad?.contratista_asignado, actividad?.creado_por,
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

/**
 * Today's date. It is checked every minute and when coming back to the tab, so it changes by
 * itself at midnight and when the computer wakes up on another day.
 */
const useHoy = () => {
  const [hoy, setHoy] = useState(() => dayjs().format(ISO_DAY));
  useEffect(() => {
    const revisar = () => setHoy(dayjs().format(ISO_DAY));
    const alVolver = () => { if (document.visibilityState === 'visible') revisar(); };
    const id = setInterval(revisar, 60 * 1000);
    document.addEventListener('visibilitychange', alVolver);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', alVolver);
    };
  }, []);
  return hoy;
};

function App() {
  const [loading, setLoading] = useState(false);
  const [panelAbierto, setPanelAbierto] = useState(leerPanel);
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
  const hoy = useHoy();
  const [dia, setDia] = useState(hoy);
  const [vista, setVista] = useState('lista');
  // The plan on screen is always the one of the chosen day: while another day is being calculated
  // (or if it failed) nothing of the previous day is shown
  const plan = result && result.metricas?.dia === dia ? result : null;
  // Filters: name search, status and who it is assigned to (the date is the plan day). The status
  // "backlog" is everything left to assign, whatever its date
  const [busqueda, setBusqueda] = useState('');
  const [estado, setEstado] = useState('todas');
  const [asignadoA, setAsignadoA] = useState([]);
  // Network operators (OR) to show; empty = all. It only filters what is shown, not the plan
  const [ors, setOrs] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(OR_KEY) || '[]');
    } catch (error) {
      return [];
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(OR_KEY, JSON.stringify(ors));
    } catch (error) {
      // Without storage it is not remembered
    }
  }, [ors]);
  // Full table: the OTs of the day's plan, or every OT loaded from Metabase
  const [alcanceTabla, setAlcanceTabla] = useState('dia');
  // Weekly hours of a technician and working days, for utilization (UTR)
  const [capacidad, setCapacidad] = useState({ horasSemana: 42, diasSemana: 5 });
  // UTR of each technician in the week before the plan day (technician id → 0..1), to show when editing
  const [utrSemana, setUtrSemana] = useState({});
  // Who the plan sends it to: "tecnico", "contratista", "externo" or "sin_asignar" (the summary tiles)
  const [destino, setDestino] = useState(null);
  // Manual edits: OT → "tecnico:<id>", "empresa:<id>", "contratista" or "auto"
  const [fijas, setFijas] = useState({});
  const [panelState, setPanelState] = useState({ canExtract: false, fetching: false, autoRefresh: false });
  // OTs selected in the list to assign together, and the proposal "by proximity" for them
  const [seleccion, setSeleccion] = useState([]);
  const [propuesta, setPropuesta] = useState(null);
  const [loteOcupado, setLoteOcupado] = useState(false);
  const [actualizado, setActualizado] = useState(null);
  // Day for which there are no OTs at all (nothing dated that day): it is not an error
  const [diaVacio, setDiaVacio] = useState(null);
  const panelRef = useRef(null);
  // Last request built by the panel, to recalculate when the day or an edit changes
  const baseRef = useRef(null);
  // Exactly what was sent for the current plan (week load, road times...), for the batch proposal
  const ultimoPedidoRef = useRef(null);

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_KEY, panelAbierto ? '1' : '0');
    } catch (error) {
      // Without storage it is not remembered
    }
  }, [panelAbierto]);

  const abrirSeccion = (key) => {
    setPanelAbierto(true);
    panelRef.current?.abrirSeccion(key);
  };

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
      actividades: base.actividades.filter((a) => entraEnElDia(a, diaPlan, hoy)),
      dia: diaPlan,
      fijas: overrides.fijas ?? fijas,
    };
    setLoading(true);
    try {
      message.loading({ content: 'Calculando el plan del día...', key: 'assign', duration: 0 });
      // What each technician already worked this week (Monday to the day before): the plan gives
      // more to whoever has worked less, so the week comes out even
      const lunes = dayjs(diaPlan).subtract((dayjs(diaPlan).day() + 6) % 7, 'day');
      if (lunes.isBefore(dayjs(diaPlan), 'day')) {
        try {
          const semana = await getUtilization({
            actividades: base.actividades.filter((a) => a.situacion === 'asignada').map((a) => ({ ...a, extras: {} })),
            desde: lunes.format(ISO_DAY),
            hasta: dayjs(diaPlan).subtract(1, 'day').format(ISO_DAY),
            horas_semana: capacidad.horasSemana,
            dias_semana: capacidad.diasSemana,
            tiempos_servicio: base.jornada.tiempos_servicio,
            personas_por_tipo: base.personas_por_tipo,
          });
          request.uso_previo = Object.fromEntries(semana.tecnicos.map((t) => [t.id, t.usado_min]));
          request.disponible_previo = semana.tecnicos[0]?.disponible_min || 0;
          setUtrSemana(Object.fromEntries(semana.tecnicos.map((t) => [t.id, t.utr])));
        } catch (error) {
          console.warn('Sin la carga de la semana: el reparto solo equilibra el día', error);
          setUtrSemana({});
        }
      } else {
        setUtrSemana({});
      }
      let pedido = request;
      let assignment = await assignActivities(pedido);
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
        if (matriz) {
          pedido = { ...request, matriz };
          assignment = await assignActivities(pedido);
        }
      }
      ultimoPedidoRef.current = pedido;
      setResult(assignment);
      setDiaVacio(null);
      setIncluirRetorno(request.jornada.incluir_retorno);
      setAssignedCodes(codesKey(base.actividades));
      const m = assignment.metricas;
      message.success({
        content: `${dayjs(request.dia).format('ddd D MMM')}: ${m.ots_con_tecnicos} a técnicos, ${m.ots_con_contratistas} a contratistas`,
        key: 'assign',
        duration: 3,
      });
    } catch (error) {
      if (error.message.startsWith('No hay OTs')) {
        setDiaVacio(diaPlan);
        message.info({ content: `${dayjs(diaPlan).format('ddd D MMM')}: no hay OTs para este día`, key: 'assign', duration: 3 });
      } else {
        console.error('Assignment error:', error);
        message.error({ content: `Error calculando el plan: ${error.message}`, key: 'assign', duration: 10 });
      }
    } finally {
      setLoading(false);
    }
  }, [dia, hoy, fijas, catalog, capacidad]);

  // A new day started: whoever was looking at today moves to the new today, and the plan is redone
  // (with fresh OTs from Metabase if the automatic update is on): overdue pending OTs move to today
  const hoyAnteriorRef = useRef(hoy);
  const [diasNuevos, setDiasNuevos] = useState(0);
  useEffect(() => {
    const anterior = hoyAnteriorRef.current;
    if (anterior === hoy) return;
    hoyAnteriorRef.current = hoy;
    setDia((actual) => (actual === anterior ? hoy : actual));
    setDiasNuevos((n) => n + 1);
  }, [hoy]);
  const nuevoDiaRef = useRef(null);
  nuevoDiaRef.current = () => {
    if (panelState.canExtract && panelState.autoRefresh) panelRef.current?.refresh();
    else if (baseRef.current) handleAssign(baseRef.current);
  };
  useEffect(() => {
    if (diasNuevos) nuevoDiaRef.current();
  }, [diasNuevos]);

  const changeDay = (nuevo) => {
    setDia(nuevo);
    setSeleccion([]);
    setAlcanceTabla((actual) => (actual === 'todas' || actual === 'sin_fecha' ? 'dia' : actual));
    // Choosing a day goes back to that day's plan
    setEstado((actual) => (actual === 'backlog' ? 'pendientes' : actual));
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

  // After assigning a batch, the map shows the route of whoever received it
  const verRutas = (valores) => {
    if (!valores.length) return;
    // The whole route of those people, not only the OTs the search had found
    setBusqueda('');
    setAsignadoA(valores);
    setEstado('todas');
    setDestino(null);
    setVista('mapa');
  };

  // The selected OTs all to one destination, or a proposal by proximity
  const aplicarLote = async (valor, soloPendientes = false) => {
    if (!baseRef.current || !seleccion.length) return;
    const situacionDe = Object.fromEntries((plan?.decisiones || []).map((d) => [d.codigo_bia, d.situacion]));
    // "Solo por asignar" leaves the assigned ones of the selection as they are
    const codigos = soloPendientes ? seleccion.filter((c) => situacionDe[c] === 'pendiente') : seleccion;
    if (!codigos.length) return;
    if (valor === POR_CERCANIA) {
      setLoteOcupado(true);
      try {
        // What each technician already has in the plan being viewed: "near" and "free" are decided on it
        const planActual = Object.fromEntries((plan?.decisiones || [])
          .filter((d) => d.enviar_a === 'tecnico' && d.responsable_id)
          .map((d) => [d.codigo_bia, d.responsable_id]));
        setPropuesta(await proposeBatch({ ...ultimoPedidoRef.current, codigos, plan_actual: planActual }));
      } catch (error) {
        message.error(`No se pudo armar la propuesta: ${error.message}`);
      } finally {
        setLoteOcupado(false);
      }
      return;
    }
    const next = { ...fijas };
    codigos.forEach((codigo) => {
      // "Que decida la app" on a pending OT is the same as no edit
      if (valor === 'auto' && situacionDe[codigo] !== 'asignada') delete next[codigo];
      else next[codigo] = valor;
    });
    const [tipo, id] = valor.split(':');
    const nombre = tipo === 'tecnico' ? config.tecnicos.find((t) => t.id === id)?.nombre
      : catalog.empresas.find((e) => e.id === id)?.nombre;
    setFijas(next);
    setSeleccion([]);
    await handleAssign(baseRef.current, { fijas: next });
    if (nombre) verRutas([`${tipo === 'tecnico' ? 't' : 'c'}:${nombre}`]);
  };

  const confirmarCercania = async (asignaciones, tecnicosElegidos) => {
    const next = { ...fijas, ...asignaciones };
    setFijas(next);
    setPropuesta(null);
    setSeleccion([]);
    await handleAssign(baseRef.current, { fijas: next });
    verRutas([...new Set(tecnicosElegidos.filter(Boolean))].map((n) => `t:${n}`));
  };

  const clearEdits = () => {
    setFijas({});
    if (baseRef.current) handleAssign(baseRef.current, { fijas: {} });
  };

  // Activity of each OT: from Metabase and, for the plan, as the optimizer returned it
  const actividades = useMemo(() => {
    const porCodigo = {};
    (ots || []).forEach((a) => { porCodigo[a.codigo_bia] = a; });
    (plan?.rutas || []).forEach((r) => r.ruta.paradas.forEach((p) => { porCodigo[p.actividad.codigo_bia] = p.actividad; }));
    (plan?.sin_asignar || []).forEach(({ actividad }) => { porCodigo[actividad.codigo_bia] = actividad; });
    return porCodigo;
  }, [ots, plan]);

  const filtrosActivos = Boolean(busqueda.trim() || estado !== 'todas' || asignadoA.length || destino || ors.length);
  // Metabase writes the same OR in several ways ("AFINIA - CARIBEMAR DE LA COSTA", "Afinia"):
  // the filter uses the name of the OR catalog
  const [nombresOr, setNombresOr] = useState({});
  const nombresOrKey = useMemo(() => [...new Set((ots || []).map((a) => a.or_operador))].sort().join('|'), [ots]);
  useEffect(() => {
    if (!nombresOrKey) return;
    getOperators(nombresOrKey.split('|')).then((r) => setNombresOr(r.resueltos || {})).catch(() => setNombresOr({}));
  }, [nombresOrKey]);
  const orDe = useCallback((a) => nombresOr[a?.or_operador] || a?.or_operador, [nombresOr]);
  const pasaOr = useCallback((a) => !ors.length || ors.includes(orDe(a)), [ors, orDe]);
  // The ORs of the loaded OTs, with how many pending OTs (any date) each one has
  const opcionesOr = useMemo(() => {
    const total = {};
    const pendientes = {};
    (ots || []).forEach((a) => {
      const nombre = orDe(a);
      total[nombre] = (total[nombre] || 0) + 1;
      if (a.situacion === 'pendiente') pendientes[nombre] = (pendientes[nombre] || 0) + 1;
    });
    return Object.keys(total).sort().map((nombre) => ({
      value: nombre,
      label: `${nombre} · ${pendientes[nombre] || 0} por asignar`,
    }));
  }, [ots, orDe]);
  // Whether a decision passes the filters; the counts can leave out the status or destination filter
  const pasaFiltros = useCallback((d, { porEstado = true, porDestino = true } = {}) => {
    const texto = normalizeText(busqueda.trim());
    return (!porEstado || estado === 'todas' || (estado === 'asignadas' ? d.situacion === 'asignada' : d.situacion === 'pendiente'))
      && (!porDestino || !destino || d.enviar_a === destino)
      && matchesAssignee(d, asignadoA)
      && pasaOr(actividades[d.codigo_bia])
      && (!texto || searchText(d.codigo_bia, actividades[d.codigo_bia], d.responsable).includes(texto));
  }, [busqueda, estado, destino, asignadoA, actividades, pasaOr]);

  const visibles = useMemo(() => {
    if (!plan || !filtrosActivos) return null;
    return new Set(plan.decisiones.filter((d) => pasaFiltros(d)).map((d) => d.codigo_bia));
  }, [plan, filtrosActivos, pasaFiltros]);

  // Each tile counts the OTs of the selected people/search; it ignores only its own filter,
  // so "Por asignar" still shows how many are pending while "Asignadas" is selected
  const conteos = useMemo(() => {
    if (!plan) return null;
    const sinEstado = plan.decisiones.filter((d) => pasaFiltros(d, { porEstado: false }));
    const sinDestino = plan.decisiones.filter((d) => pasaFiltros(d, { porDestino: false }));
    const cuantas = (lista, campo, valor) => lista.filter((d) => d[campo] === valor).length;
    return {
      total: plan.decisiones.filter((d) => pasaFiltros(d, { porEstado: false, porDestino: false })).length,
      todas: sinEstado.length,
      asignada: cuantas(sinEstado, 'situacion', 'asignada'),
      pendiente: cuantas(sinEstado, 'situacion', 'pendiente'),
      tecnico: cuantas(sinDestino, 'enviar_a', 'tecnico'),
      contratista: cuantas(sinDestino, 'enviar_a', 'contratista'),
      // Suggestions: Ruteo proposes a destination but the OT is still pending in Metabase
      tecnico_sugeridas: sinDestino.filter((d) => d.enviar_a === 'tecnico' && d.situacion === 'pendiente').length,
      contratista_sugeridas: sinDestino.filter((d) => d.enviar_a === 'contratista' && d.situacion === 'pendiente').length,
      externo: cuantas(sinDestino, 'enviar_a', 'externo'),
      sin_asignar: cuantas(sinDestino, 'enviar_a', 'sin_asignar'),
    };
  }, [plan, pasaFiltros]);

  // Every OT still pending in Metabase, whatever its date, with its decision if it is in the day's plan.
  // The search and "Asignado a" apply too (an OT of another day has nobody yet)
  const pendientesTodas = useMemo(() => {
    const texto = normalizeText(busqueda.trim());
    const decisiones = Object.fromEntries((plan?.decisiones || []).map((d) => [d.codigo_bia, d]));
    return (ots || [])
      .filter((a) => a.situacion === 'pendiente')
      .map((a) => ({ actividad: a, grupo: grupoPendiente(a.fecha_visita, hoy), decision: decisiones[a.codigo_bia] }))
      .filter(({ actividad: a, decision: d }) => (!asignadoA.length || (d && matchesAssignee(d, asignadoA)))
        && pasaOr(a)
        && (!texto || searchText(a.codigo_bia, a, d?.responsable).includes(texto)))
      .sort((x, y) => (GRUPOS_PENDIENTES[x.grupo] - GRUPOS_PENDIENTES[y.grupo])
        || (x.actividad.fecha_visita || '').localeCompare(y.actividad.fecha_visita || ''));
  }, [ots, plan, hoy, busqueda, asignadoA, pasaOr]);

  const porAsignar = useMemo(() => {
    const cuantas = (grupo) => pendientesTodas.filter((p) => p.grupo === grupo).length;
    return {
      total: pendientesTodas.length,
      vencidas: cuantas('vencida'),
      hoy: cuantas('hoy'),
      proximas: cuantas('proxima'),
      sinFecha: cuantas('sin_fecha'),
    };
  }, [pendientesTodas]);

  // The full table, with the same filters as the rest: the OTs of the day's plan (exactly the ones in
  // the list), the ones whose visit is that day (any state, as in Olibia), the undated ones, or all
  const tabla = useMemo(() => {
    const texto = normalizeText(busqueda.trim());
    const decisiones = Object.fromEntries((plan?.decisiones || []).map((d) => [d.codigo_bia, d]));
    const filtradas = (ots || []).filter((a) => (
      pasaOr(a)
      && (estado === 'todas' || estado === 'backlog'
        || (estado === 'pendientes' ? a.situacion === 'pendiente' : a.situacion === 'asignada'))
      && (!destino || decisiones[a.codigo_bia]?.enviar_a === destino)
      && (!asignadoA.length || (decisiones[a.codigo_bia] && matchesAssignee(decisiones[a.codigo_bia], asignadoA)))
      && (!texto || searchText(a.codigo_bia, a, decisiones[a.codigo_bia]?.responsable).includes(texto))
    ));
    return {
      dia: filtradas.filter((a) => (plan ? Boolean(decisiones[a.codigo_bia]) : entraEnElDia(a, dia, hoy))),
      visita: filtradas.filter((a) => a.fecha_visita === dia),
      sin_fecha: filtradas.filter((a) => !a.fecha_visita),
      todas: filtradas,
    };
  }, [ots, plan, dia, hoy, busqueda, estado, destino, asignadoA, pasaOr]);
  const otsFiltradas = estado === 'backlog' ? pendientesTodas.map((p) => p.actividad) : tabla[alcanceTabla];

  // For every loaded OT: whether it is in the plan of the day and, if not, why
  const motivosPlan = useMemo(() => {
    if (alcanceTabla === 'dia' || !ots) return null;
    const decisiones = Object.fromEntries((plan?.decisiones || []).map((d) => [d.codigo_bia, d]));
    const filtroOr = (baseRef.current?.or_filtro || []).map(normalizeText);
    const calculadas = baseRef.current ? new Set(baseRef.current.actividades.map((a) => a.codigo_bia)) : null;
    const columnaSituacion = mapeo.situacion;
    return Object.fromEntries(ots.map((a) => [a.codigo_bia, enElPlan(a, {
      decision: decisiones[a.codigo_bia],
      dia,
      hoy,
      filtroOr,
      calculadas,
      cerrada: Boolean(columnaSituacion && normalizeText(String(a.extras?.[columnaSituacion] || '')).includes('cerrad')),
    })]));
  }, [alcanceTabla, ots, plan, dia, hoy, mapeo]);

  const backlog = estado === 'backlog';
  // Views where the chosen date does not apply: the date box says so instead of showing a day
  const sinDia = backlog ? 'Todas las fechas'
    : vista === 'tabla' && alcanceTabla === 'todas' ? 'Todas las fechas'
      : vista === 'tabla' && alcanceTabla === 'sin_fecha' ? 'Sin fecha' : null;
  // The map and the routes are of one day: "Falta por asignar" is a list
  const cambiarVista = (nueva) => {
    setVista(nueva);
    if (backlog && (nueva === 'mapa' || nueva === 'rutas')) setEstado('pendientes');
  };
  const filtrarEstado = (nuevo) => {
    setEstado(nuevo);
    if (nuevo === 'backlog' && (vista === 'mapa' || vista === 'rutas')) setVista('lista');
  };
  // From the list of everything pending: plan the day of that OT (overdue and undated ones, today)
  const planearDia = (fecha) => {
    const objetivo = fecha && fecha > hoy ? fecha : hoy;
    setEstado('pendientes');
    if (objetivo !== dia) changeDay(objetivo);
  };

  const busy = loading || panelState.fetching;
  const stale = Boolean(result && ots) && codesKey(ots) !== assignedCodes;
  const disponibles = new Set(baseRef.current?.tecnicos_ids || []);
  const tecnicosEdicion = config.tecnicos
    .filter((t) => t.activo !== false)
    .map((t) => ({ id: t.id, nombre: t.nombre, disponible: disponibles.has(t.id), utr: utrSemana[t.id] }));
  const ediciones = Object.keys(fijas).length;

  return (
    <Layout className="app-shell">
      <Header className="ios-header">
        <div className="ios-header-inner">
          <Space size={10}>
            <img src={`${process.env.PUBLIC_URL}/bolt.png`} alt="" className="app-icon" />
            <span className="app-title">Ruteo</span>
            {ots && (
              <span className="app-subtitle">
                <Tooltip title="Ver todas las OTs cargadas y por qué cada una está o no en el plan">
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => { setVista('tabla'); setAlcanceTabla('todas'); setEstado((e) => (e === 'backlog' ? 'todas' : e)); }}
                  >
                    {ots.length} OTs cargadas
                  </button>
                </Tooltip>
                {actualizado ? ` · actualizado ${actualizado.format('HH:mm')}` : ''}
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
        <nav className="tool-rail" aria-label="Barra de herramientas">
          <Tooltip title={panelAbierto ? 'Ocultar panel' : 'Mostrar panel'} placement="right">
            <Button
              type="text"
              className="rail-button"
              aria-label={panelAbierto ? 'Ocultar panel' : 'Mostrar panel'}
              aria-pressed={panelAbierto}
              icon={panelAbierto ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
              onClick={() => setPanelAbierto((abierto) => !abierto)}
            />
          </Tooltip>
          <div className="rail-divider" />
          {SECCIONES_PANEL.map((seccion) => (
            <Tooltip key={seccion.key} title={seccion.label} placement="right">
              <Button
                type="text"
                className="rail-button"
                aria-label={seccion.label}
                icon={seccion.icon}
                onClick={() => abrirSeccion(seccion.key)}
              />
            </Tooltip>
          ))}
        </nav>
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
          collapsed={!panelAbierto}
          collapsedWidth={0}
          trigger={null}
          breakpoint="lg"
          // On a narrow screen it starts hidden; the toolbar shows it
          onBreakpoint={(estrecha) => { if (estrecha) setPanelAbierto(false); }}
        >
          <div style={{ padding: '8px 0 24px' }}>
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
                <div className="eyebrow">
                  {backlog ? 'Falta por asignar' : sinDia ? 'OTs cargadas' : (dia === hoy ? 'Hoy' : 'Plan del día')}
                </div>
                <div className="large-title">
                  {sinDia ? (sinDia === 'Sin fecha' ? 'Sin fecha de visita' : sinDia) : capitalize(dayjs(dia).format('dddd D [de] MMMM'))}
                </div>
              </div>
              <Segmented
                value={vista}
                onChange={cambiarVista}
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
                  placeholder="Buscar por nombre, OT, dirección o quién la creó"
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
                  value={sinDia ? null : dayjs(dia)}
                  placeholder={sinDia || 'Elige el día'}
                  allowClear={false}
                  disabled={busy}
                  format="DD/MM/YYYY"
                  onChange={(d) => d && changeDay(d.format(ISO_DAY))}
                  style={{ width: 140 }}
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
                onChange={filtrarEstado}
                options={[
                  { value: 'todas', label: `Todas${conteos ? ` ${conteos.todas}` : ''}` },
                  { value: 'pendientes', label: `Por asignar${conteos ? ` ${conteos.pendiente}` : ''}` },
                  { value: 'asignadas', label: `Asignadas${conteos ? ` ${conteos.asignada}` : ''}` },
                  ...(ots ? [{
                    value: 'backlog',
                    label: (
                      <Tooltip title="Todas las OTs pendientes de Metabase, sin importar la fecha">
                        {`Falta por asignar ${porAsignar.total}`}
                      </Tooltip>
                    ),
                  }] : []),
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
                options={assigneeOptions(plan, config.tecnicos)}
                optionFilterProp="label"
                popupMatchSelectWidth={false}
                className="filter-assignee"
                // It grows with the people chosen, so their names show instead of "+ 2 ..."
                style={{ width: asignadoA.length ? Math.min(460, 140 + asignadoA.length * 150) : 180 }}
              />
              {vista !== 'utilizacion' && (
                <Select
                  mode="multiple"
                  allowClear
                  showSearch
                  maxTagCount="responsive"
                  variant="filled"
                  placeholder="OR"
                  value={ors}
                  onChange={setOrs}
                  options={opcionesOr}
                  optionFilterProp="label"
                  popupMatchSelectWidth={false}
                  className="filter-or"
                  aria-label="Filtrar por OR"
                  style={{ width: ors.length ? Math.min(360, 110 + ors.length * 110) : 110 }}
                />
              )}
              {filtrosActivos && (
                <Button type="link" onClick={() => { setBusqueda(''); setEstado('todas'); setAsignadoA([]); setDestino(null); setOrs([]); }} style={{ paddingInline: 4 }}>
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
                  <>
                    {!backlog && (
                      <Segmented
                        className="tabla-alcance"
                        value={alcanceTabla}
                        onChange={setAlcanceTabla}
                        options={[
                          { value: 'dia', label: `Plan del ${dayjs(dia).format('D MMM')} (${tabla.dia.length})` },
                          { value: 'visita', label: `Con visita el ${dayjs(dia).format('D MMM')} (${tabla.visita.length})` },
                          { value: 'sin_fecha', label: `Sin fecha (${tabla.sin_fecha.length})` },
                          { value: 'todas', label: `Todas las fechas (${tabla.todas.length})` },
                        ]}
                      />
                    )}
                    <OtsTable
                      ots={otsFiltradas}
                      nuevas={nuevas}
                      mapeo={mapeo}
                      config={config}
                      enPlan={!backlog ? motivosPlan : null}
                      enPlanTitulo={`En el plan del ${dayjs(dia).format('D MMM')}`}
                      title={backlog ? `Falta por asignar, todas las fechas (${otsFiltradas.length})` : {
                        dia: `En el plan del ${dayjs(dia).format('D MMM')} (${otsFiltradas.length})`,
                        visita: `Con visita el ${dayjs(dia).format('D MMM')}, en cualquier estado (${otsFiltradas.length})`,
                        sin_fecha: `Sin fecha de visita (${otsFiltradas.length})`,
                        todas: `Todas las cargadas, todas las fechas (${otsFiltradas.length})`,
                      }[alcanceTabla]}
                    />
                  </>
                ) : <EmptyState />
              )}
              {vista === 'utilizacion' && (
                <UtilizationDashboard
                  ots={ots}
                  config={config}
                  dia={dia}
                  result={plan}
                  tecnicosFiltro={asignadoA.filter((v) => v.startsWith('t:')).map((v) => v.slice(2))}
                  horasSemana={capacidad.horasSemana}
                  diasSemana={capacidad.diasSemana}
                  onCapacidad={(cambio) => setCapacidad((prev) => ({ ...prev, ...cambio }))}
                />
              )}
              {vista !== 'tabla' && vista !== 'utilizacion' && (plan ? (
                <AssignmentResults
                  result={plan}
                  ots={ots}
                  nuevas={nuevas}
                  incluirRetorno={incluirRetorno}
                  view={vista}
                  visibles={visibles}
                  conteos={conteos}
                  porAsignar={porAsignar}
                  pendientesTodas={backlog ? pendientesTodas : null}
                  onPlanearDia={planearDia}
                  hoy={hoy}
                  horasDia={capacidad.horasSemana / capacidad.diasSemana}
                  estado={estado}
                  destino={destino}
                  onFiltrar={({ estado: nuevoEstado, destino: nuevoDestino }) => {
                    if (nuevoEstado !== undefined) filtrarEstado(nuevoEstado);
                    if (nuevoDestino !== undefined) setDestino(nuevoDestino);
                  }}
                  fijas={fijas}
                  seleccion={seleccion}
                  onSeleccion={vista === 'lista' && !backlog ? setSeleccion : undefined}
                  onEdit={handleEdit}
                  tecnicos={tecnicosEdicion}
                  empresas={catalog.empresas}
                  editing={loading}
                />
              ) : (
                <EmptyState
                  vacio={diaVacio === dia}
                  otroDia={Boolean(result)}
                  calculando={loading}
                  dia={dayjs(dia).format('dddd D [de] MMMM')}
                />
              ))}
            </Spin>
            {vista === 'lista' && !backlog && plan && seleccion.length > 0 && (
              <LoteBar
                cantidad={seleccion.length}
                pendientes={seleccion.filter((c) => plan?.decisiones.find((d) => d.codigo_bia === c)?.situacion === 'pendiente').length}
                tecnicos={tecnicosEdicion}
                empresas={catalog.empresas}
                onAplicar={aplicarLote}
                onLimpiar={() => setSeleccion([])}
                ocupado={loteOcupado || loading}
              />
            )}
            <LoteModal
              propuesta={propuesta}
              actividades={actividades}
              onCancelar={() => setPropuesta(null)}
              onAplicar={confirmarCercania}
              ocupado={loading}
            />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
}

const EmptyState = ({
  vacio = false, otroDia = false, calculando = false, dia = '',
}) => {
  if (vacio && !calculando) {
    return (
      <div className="empty-state">
        <div className="empty-title">{`No hay OTs para el ${dia}`}</div>
        <div className="empty-text">
          Ninguna OT tiene visita ese día con los OR de Ajustes. Lo que falta por asignar de otras fechas está en «Falta por asignar».
        </div>
      </div>
    );
  }
  if (otroDia) {
    return (
      <div className="empty-state">
        <div className="empty-title">{calculando ? `Calculando el plan del ${dia}…` : `Sin plan para el ${dia}`}</div>
        {!calculando && (
          <div className="empty-text">Pulsa recalcular (↻) arriba a la derecha para armar el plan de este día.</div>
        )}
      </div>
    );
  }
  return (
    <div className="empty-state">
      <div className="empty-title">Sin plan todavía</div>
      <div className="empty-text">
        Pulsa «Extraer y recomendar»: las OTs ya asignadas para este día se respetan y la app sugiere a quién enviar las pendientes.
      </div>
    </div>
  );
};

export default App;

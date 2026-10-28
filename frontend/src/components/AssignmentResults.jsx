import React, { useMemo, useState } from 'react';
import {
  Table, Collapse, Button, Tooltip, Descriptions, Select,
} from 'antd';
import { DownloadOutlined, EnvironmentOutlined, LockOutlined, EditOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import AssignmentMapView, { ROUTE_COLORS } from './AssignmentMapView';
import { columnaCerca } from './AsignadasCerca';
import { formatExtra } from './OtsTable';
import { formatCop } from '../services/format';

const km = (value) => (value ?? 0).toLocaleString('es-CO', { maximumFractionDigits: 1 });
const hhmm = (value) => (value ? value.slice(0, 5) : '');

const DESTINO = {
  tecnico: 'Técnico Bia',
  contratista: 'Contratista',
  externo: 'Externo',
  sin_asignar: 'Sin asignar',
};

const Dot = ({ color }) => <span className="dot" style={{ background: color }} />;

const situacion = (valor) => (valor === 'asignada'
  ? <span className="state"><Dot color="#34C759" />Asignada</span>
  : <span className="state"><Dot color="#FF9500" />Por asignar</span>);

// The visit date of an OT in the plan of `dia`: that day, overdue or undated (these two, only today)
const fechaEnPlan = (actividad, dia) => {
  const fecha = actividad?.fecha_visita;
  if (!fecha) return 'Sin fecha de visita';
  const hora = actividad.hora_visita ? `, ${actividad.hora_visita}` : '';
  if (fecha < dia) return `Vencida: era el ${dayjs(fecha).format('D MMM')}${hora}`;
  return `Visita el ${dayjs(fecha).format('D MMM')}${hora}`;
};

// Where the destination comes from: still pending (a suggestion), assigned or closed in Metabase, or edited
const origenDecision = (d, editada, cerrada = false) => {
  if (d.enviar_a === 'sin_asignar') return 'Sin asignar';
  if (cerrada) return 'Cerrada en Metabase';
  if (editada) return d.situacion === 'asignada' ? 'Reasignada a mano' : 'Elegido a mano, sigue por asignar';
  return d.situacion === 'asignada' ? 'Asignada en Metabase' : 'Sugerido por Ruteo';
};

const otCell = (actividad, codigo, nuevas) => (
  <div className="ot-cell">
    <span className="ot-code">{codigo}</span>
    {nuevas?.has(codigo) && <span className="new-badge">nueva</span>}
    {actividad?.coordenadas_aproximadas && (
      <Tooltip title="Ubicación aproximada: geocodificada a partir de la dirección o el municipio">
        <EnvironmentOutlined className="approx-icon" />
      </Tooltip>
    )}
    <div className="ot-cell-sub">{[actividad?.servicio, actividad?.nombre, actividad?.ciudad].filter(Boolean).join(' · ')}</div>
    {actividad?.creado_por && (
      <div className="ot-cell-sub ot-creator">
        Creada por {actividad.creado_por}{actividad.fecha_creacion ? ` el ${dayjs(actividad.fecha_creacion).format('D MMM')}` : ''}
      </div>
    )}
  </div>
);

const plural = (n, singular, varias) => `${n}\u00a0${n === 1 ? singular : varias}`;

// When each pending OT is due, with how late or how soon
const fechaPendiente = (actividad, grupo, hoy) => {
  const fecha = actividad.fecha_visita;
  if (!fecha) return <span className="state"><Dot color="#C7C7CC" />Sin fecha</span>;
  const dias = Math.abs(dayjs(fecha).diff(dayjs(hoy), 'day'));
  const estado = {
    vencida: ['#FF3B30', `Vencida hace ${plural(dias, 'día', 'días')}`],
    hoy: ['#FF9500', 'Para hoy'],
    proxima: ['#007AFF', `En ${plural(dias, 'día', 'días')}`],
  }[grupo];
  return (
    <div>
      <span className="state"><Dot color={estado[0]} />{estado[1]}</span>
      <div className="ot-cell-sub">{dayjs(fecha).format('ddd D MMM YYYY')}</div>
    </div>
  );
};

const DetailRow = ({ row, alternativas }) => {
  const { decision: d, actividad } = row;
  const extras = Object.entries(actividad?.extras || {});
  return (
    <Descriptions size="small" column={{ xs: 1, md: 2, xl: 3 }}>
      <Descriptions.Item label="Por qué">{d.motivo}</Descriptions.Item>
      <Descriptions.Item label="OR">{actividad?.or_operador}</Descriptions.Item>
      <Descriptions.Item label="Personas">{actividad?.personas_requeridas || 1}</Descriptions.Item>
      <Descriptions.Item label="Sale de">{d.sede}</Descriptions.Item>
      <Descriptions.Item label="Km a la base">
        {d.distancia_base_km === null || d.distancia_base_km === undefined ? '' : km(d.distancia_base_km)}
      </Descriptions.Item>
      <Descriptions.Item label="Dirección">{actividad?.direccion}</Descriptions.Item>
      <Descriptions.Item label="Otras opciones">
        {alternativas.map((a) => `${a.empresa} (${a.ciudad}) · ${km(a.distancia_km)} km`).join(' / ') || '—'}
      </Descriptions.Item>
      {extras.map(([key, value]) => <Descriptions.Item key={key} label={key}>{formatExtra(value)}</Descriptions.Item>)}
    </Descriptions>
  );
};

const csvValue = (value) => {
  const text = String(value ?? '');
  return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

const exportCsv = (rows, dia) => {
  const extraKeys = [];
  rows.forEach(({ actividad }) => Object.keys(actividad?.extras || {}).forEach((k) => {
    if (!extraKeys.includes(k)) extraKeys.push(k);
  }));

  // ";" and decimal comma so it opens directly in Excel configured in Spanish
  const header = ['Día', 'OT', 'Situación', 'OR', 'Ciudad', 'Dirección', 'Tipo de OT', 'Personas', 'Enviar a', 'Responsable',
    'Fijada', 'Sale de', 'Km a la base', 'Secuencia', 'Llegada', 'Salida', 'Ubicación aproximada', 'Creada por',
    'Fecha de creación', 'Motivo', ...extraKeys];
  const lines = rows.map(({ decision: d, actividad: a, parada }) => [
    dia, d.codigo_bia, d.situacion === 'asignada' ? 'Asignada' : 'Por asignar', a?.or_operador, a?.ciudad, a?.direccion,
    a?.servicio, a?.personas_requeridas, DESTINO[d.enviar_a], d.responsable, d.fijada ? 'Sí' : 'No', d.sede,
    d.distancia_base_km === null || d.distancia_base_km === undefined ? '' : String(d.distancia_base_km).replace('.', ','),
    parada?.secuencia, hhmm(parada?.hora_llegada_estimada), hhmm(parada?.hora_salida_estimada),
    a?.coordenadas_aproximadas ? 'Sí' : 'No', a?.creado_por, a?.fecha_creacion, d.motivo,
    ...extraKeys.map((k) => formatExtra(a?.extras?.[k])),
  ]);
  const csv = [header, ...lines].map((row) => row.map(csvValue).join(';')).join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `plan-ots-${dia || new Date().toISOString().split('T')[0]}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const stopColumns = (nuevas, situaciones) => [
  { title: '#', dataIndex: 'secuencia', width: 40 },
  { title: 'OT', render: (_, p) => otCell(p.actividad, p.actividad.codigo_bia, nuevas) },
  { title: 'Estado', width: 120, render: (_, p) => situacion(situaciones[p.actividad.codigo_bia]) },
  { title: 'Dirección', render: (_, p) => p.actividad.direccion },
  { title: 'Llega', dataIndex: 'hora_llegada_estimada', width: 70, render: hhmm },
  { title: 'Sale', dataIndex: 'hora_salida_estimada', width: 70, render: hhmm },
  { title: 'Viaje', dataIndex: 'tiempo_desplazamiento_minutos', width: 80, render: (v) => `${v} min` },
];

/**
 * Options to change who attends an OT: let the app decide, an available technician,
 * the nearest contractor of its OR, or a specific contractor.
 */
export const editOptions = (tecnicos, empresas, alternativas, yaAsignada) => [
  {
    label: 'Automático',
    options: [{ value: 'auto', label: yaAsignada ? 'Que la app la reasigne' : 'Que decida la app' }],
  },
  {
    label: 'Técnicos',
    // Least loaded first, with their UTR of the week, so the even choice is at hand
    options: [...tecnicos]
      .sort((a, b) => (b.disponible - a.disponible) || ((a.utr ?? 0) - (b.utr ?? 0)))
      .map((t) => ({
        value: `tecnico:${t.id}`,
        label: !t.disponible ? `${t.nombre} (no disponible)`
          : `${t.nombre}${t.utr !== undefined && t.utr !== null ? ` · ${Math.round(t.utr * 100)} % en la semana` : ''}`,
        disabled: !t.disponible,
      })),
  },
  {
    label: 'Contratistas',
    options: [
      { value: 'contratista', label: 'El más cercano de su OR' },
      // The nearest options for this OT first, then the rest
      ...[...alternativas, ...empresas.filter((e) => !alternativas.some((a) => a.id === e.id))]
        .map((e) => ({ value: `empresa:${e.id}`, label: e.km !== undefined ? `${e.nombre} · ${km(e.km)} km` : e.nombre })),
    ],
  },
];

// Who attends the OT; the pencil opens the list to send it to someone else
const EnviarA = ({
  decision: d, editada, cerrada, options, onEdit, editing,
}) => {
  const [abierto, setAbierto] = useState(false);
  return (
    <div className="assignee">
      <div className="assignee-name">
        {d.responsable || DESTINO[d.enviar_a]}
        {d.fijada && !editada && (
          <Tooltip title="Se respeta la asignación de Metabase"><LockOutlined className="muted-icon" /></Tooltip>
        )}
        {onEdit && (
          <Tooltip title="Enviar a otro técnico o contratista">
            <Button
              type="text"
              size="small"
              className="edit-button"
              icon={<EditOutlined />}
              disabled={editing}
              onClick={() => setAbierto(true)}
            />
          </Tooltip>
        )}
      </div>
      <div className="assignee-sub">
        {origenDecision(d, editada, cerrada)}{d.enviar_a !== 'sin_asignar' ? ` · ${DESTINO[d.enviar_a]}` : ''}
      </div>
      {abierto && (
        <Select
          size="small"
          autoFocus
          defaultOpen
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="Enviar a…"
          value={editada}
          onChange={(value) => { setAbierto(false); onEdit(d.codigo_bia, value, d.situacion); }}
          onDropdownVisibleChange={(visible) => { if (!visible) setAbierto(false); }}
          options={options}
          popupMatchSelectWidth={false}
          style={{ width: 220, marginTop: 4 }}
        />
      )}
    </div>
  );
};

const AssignmentResults = ({
  result, ots, nuevas, incluirRetorno, view = 'lista', visibles = null, conteos = null, estado = 'todas', destino = null,
  onFiltrar, horasDia = 8.4, porAsignar = null, pendientesTodas = null, onPlanearDia, hoy, cercanas = {}, radioCerca = 2,
  seleccion = [], onSeleccion,
  fijas = {}, onEdit, tecnicos = [], empresas = [], editing,
}) => {
  const situaciones = useMemo(
    () => Object.fromEntries((result?.decisiones || []).map((d) => [d.codigo_bia, d.situacion])),
    [result],
  );

  if (!result) return null;
  const { metricas } = result;

  // Activity and stop of each OT, to show its data next to the decision
  const actividades = {};
  const paradas = {};
  (ots || []).forEach((a) => { actividades[a.codigo_bia] = a; });
  result.rutas.forEach((r) => r.ruta.paradas.forEach((p) => {
    actividades[p.actividad.codigo_bia] = p.actividad;
    paradas[p.actividad.codigo_bia] = p;
  }));
  result.sin_asignar.forEach(({ actividad }) => { actividades[actividad.codigo_bia] = actividad; });
  const recomendaciones = Object.fromEntries(result.recomendaciones.map((r) => [r.codigo_bia, r]));
  const allRows = result.decisiones.map((d) => ({
    key: d.codigo_bia,
    decision: d,
    actividad: actividades[d.codigo_bia],
    parada: paradas[d.codigo_bia],
  }));
  const rows = visibles ? allRows.filter((r) => visibles.has(r.decision.codigo_bia)) : allRows;
  // The ones that can still be (re)assigned: not the visits already closed
  const abiertas = rows.filter((r) => !r.actividad?.cerrada);

  // Routes with some OT that passes the filters: their km, hours and cost are the ones the tiles add up
  const rutasVisibles = result.rutas
    .map((r, idx) => ({ r, idx }))
    .filter(({ r }) => !visibles || r.ruta.paradas.some((p) => visibles.has(p.actividad.codigo_bia)));
  const kmVisibles = rutasVisibles.reduce((suma, { r }) => suma + r.ruta.distancia_total_km, 0);
  const rutasTecnicos = rutasVisibles.filter(({ r }) => r.tipo === 'tecnico');
  const horasTecnicos = rutasTecnicos.reduce((suma, { r }) => suma + r.ruta.tiempo_total_minutos, 0) / 60;
  const costos = rutasTecnicos.map(({ r }) => r.costo).filter((c) => c !== null && c !== undefined);

  // Summary tiles: they count what the filters select (the selected people, the search...);
  // touching one filters by it and touching it again removes that filter
  const c = conteos || {
    total: result.total_actividades,
    asignada: metricas.ots_ya_asignadas ?? 0,
    pendiente: metricas.ots_pendientes ?? 0,
    tecnico: metricas.ots_con_tecnicos,
    contratista: metricas.ots_con_contratistas,
    externo: metricas.ots_externas,
    sin_asignar: metricas.ots_sin_asignar,
  };
  const porEstado = (valor) => () => onFiltrar({ estado: estado === valor ? 'todas' : valor });
  const porDestino = (valor) => () => onFiltrar({ destino: destino === valor ? null : valor });
  const tiles = [
    {
      title: 'OTs del día',
      value: c.total,
      active: estado === 'todas' && !destino,
      onClick: () => onFiltrar({ estado: 'todas', destino: null }),
    },
    { title: 'Asignadas', value: c.asignada, color: '#248A3D', active: estado === 'asignadas', onClick: porEstado('asignadas') },
    {
      title: 'Por asignar',
      value: c.pendiente,
      color: '#C93400',
      active: estado === 'pendientes',
      onClick: porEstado('pendientes'),
      hint: 'Pendientes que entran en el plan de este día',
    },
    // Everything still pending in Metabase, whatever its date
    porAsignar ? {
      title: 'Falta por asignar',
      value: porAsignar.total,
      color: '#C93400',
      active: estado === 'backlog',
      onClick: porEstado('backlog'),
      sub: `todas\u00a0las\u00a0fechas${porAsignar.vencidas ? ` · ${plural(porAsignar.vencidas, 'vencida', 'vencidas')}` : ''}`,
      hint: [
        'Pendientes de Metabase, sin importar la fecha:',
        `· vencidas: ${porAsignar.vencidas}`,
        `· para hoy: ${porAsignar.hoy}`,
        `· próximos días: ${porAsignar.proximas}`,
        `· sin fecha: ${porAsignar.sinFecha}`,
      ].join('\n'),
    } : null,
    {
      title: 'Técnicos Bia',
      value: c.tecnico,
      color: '#007AFF',
      active: destino === 'tecnico',
      onClick: porDestino('tecnico'),
      sub: c.tecnico_sugeridas ? `${c.tecnico_sugeridas} ${c.tecnico_sugeridas === 1 ? 'sugerida' : 'sugeridas'}` : null,
      hint: 'Asignadas en Metabase a técnicos Bia más las sugeridas por Ruteo (siguen por asignar)',
    },
    {
      title: 'Contratistas',
      value: c.contratista,
      color: '#AF52DE',
      active: destino === 'contratista',
      onClick: porDestino('contratista'),
      sub: c.contratista_sugeridas ? `${c.contratista_sugeridas} ${c.contratista_sugeridas === 1 ? 'sugerida' : 'sugeridas'}` : null,
      hint: 'Asignadas en Metabase a contratistas más las sugeridas por Ruteo (siguen por asignar)',
    },
    metricas.ots_externas
      ? { title: 'Externas', value: c.externo, active: destino === 'externo', onClick: porDestino('externo') }
      : null,
    metricas.ots_sin_asignar
      ? { title: 'Sin asignar', value: c.sin_asignar, color: '#FF3B30', active: destino === 'sin_asignar', onClick: porDestino('sin_asignar') }
      : null,
    { title: 'Km', value: km(kmVisibles), hint: visibles ? 'De las rutas que muestra el filtro' : 'De todas las rutas del día' },
    { title: 'Horas técnicos', value: horasTecnicos.toLocaleString('es-CO', { maximumFractionDigits: 1 }), hint: 'OTs + viaje de las rutas de técnicos mostradas' },
    costos.length ? { title: 'Costo técnicos', value: formatCop(costos.reduce((a, b) => a + b, 0)) } : null,
  ].filter(Boolean);
  const transito = (metricas.transito || []).filter((z) => z.recargo_pct || z.minutos_extra)
    .map((z) => `${z.nombre} +${z.recargo_pct} %${z.minutos_extra ? ` +${z.minutos_extra} min` : ''}`).join(', ');
  const avisos = [
    metricas.rutas_no_viables > 0 ? `${metricas.rutas_no_viables} rutas pasan de la jornada` : null,
    metricas.tiempos_por_vias ? null : (metricas.aviso_vias || 'Tiempos estimados en línea recta'),
    metricas.asignadas_sin_fecha > 0 ? `${metricas.asignadas_sin_fecha} asignadas sin fecha en Metabase` : null,
    metricas.ots_sin_lista_or > 0 ? `${metricas.ots_sin_lista_or} OTs de OR sin contratistas en su zona` : null,
    metricas.pendientes_otros_dias > 0 ? `${metricas.pendientes_otros_dias} pendientes tienen fecha de otro día` : null,
    metricas.ots_sin_ubicacion > 0 ? `${metricas.ots_sin_ubicacion} OTs asignadas sin ubicación (no entran en el mapa)` : null,
    metricas.bia_sin_registrar?.length
      ? `Técnicos de Bia en Metabase que no están en la app: ${metricas.bia_sin_registrar.join(', ')} (agrégalos en Técnicos → Gestionar)`
      : null,
  ].filter(Boolean);

  const backlogColumns = [
    {
      title: 'OT',
      fixed: 'left',
      width: 280,
      render: (_, p) => otCell(p.actividad, p.actividad.codigo_bia, nuevas),
    },
    { title: 'Fecha de visita', width: 190, render: (_, p) => fechaPendiente(p.actividad, p.grupo, hoy) },
    { title: 'OR', width: 120, render: (_, p) => p.actividad.or_operador },
    columnaCerca(cercanas, radioCerca, (p) => p.actividad),
    {
      title: `Plan del ${dayjs(metricas.dia).format('D MMM')}`,
      width: 240,
      render: (_, p) => (p.decision ? (
        <div className="assignee">
          <div className="assignee-name">{p.decision.responsable || DESTINO[p.decision.enviar_a]}</div>
          <div className="assignee-sub">{origenDecision(p.decision)} · {DESTINO[p.decision.enviar_a]}</div>
        </div>
      ) : <span className="muted-text">No entra en este día</span>),
    },
    {
      title: '',
      width: 150,
      render: (_, p) => (
        <Button type="link" size="small" style={{ paddingInline: 0 }} onClick={() => onPlanearDia?.(p.actividad.fecha_visita)}>
          {p.grupo === 'proxima' ? `Planear el ${dayjs(p.actividad.fecha_visita).format('D MMM')}` : 'Planear hoy'}
        </Button>
      ),
    },
  ];

  const columns = [
    {
      title: 'OT',
      fixed: 'left',
      width: 260,
      render: (_, r) => otCell(r.actividad, r.decision.codigo_bia, nuevas),
    },
    {
      title: 'Estado',
      width: 160,
      render: (_, r) => (
        <div>
          {situacion(r.decision.situacion)}
          <div className="ot-cell-sub">{fechaEnPlan(r.actividad, metricas.dia)}</div>
        </div>
      ),
    },
    {
      title: 'Enviar a',
      width: 280,
      sorter: (a, b) => (a.decision.responsable || '~').localeCompare(b.decision.responsable || '~'),
      render: (_, r) => {
        const d = r.decision;
        const alternativas = [recomendaciones[d.codigo_bia]?.elegido, ...(recomendaciones[d.codigo_bia]?.alternativas || [])]
          .filter((a) => a?.empresa_id)
          .map((a) => ({ id: a.empresa_id, nombre: `${a.empresa} (${a.ciudad})`, km: a.distancia_km }));
        return (
          <EnviarA
            decision={d}
            editada={fijas[d.codigo_bia]}
            cerrada={Boolean(r.actividad?.cerrada)}
            options={editOptions(tecnicos, empresas, alternativas, d.situacion === 'asignada')}
            // A closed visit was already done: it is not sent to anyone else
            onEdit={r.actividad?.cerrada ? undefined : onEdit}
            editing={editing}
          />
        );
      },
    },
    {
      title: 'Llega',
      width: 70,
      sorter: (a, b) => (a.decision.hora_llegada || '~').localeCompare(b.decision.hora_llegada || '~'),
      render: (_, r) => hhmm(r.decision.hora_llegada),
    },
    {
      title: 'Por qué',
      render: (_, r) => (
        <Tooltip title={r.decision.motivo} placement="topLeft">
          <span className="motivo">{r.decision.motivo}</span>
        </Tooltip>
      ),
    },
  ];

  return (
    <>
      <div className="kpi-row">
        {tiles.map((t) => (
          <button
            key={t.title}
            type="button"
            title={t.hint}
            className={`kpi${t.active ? ' active' : ''}${t.onClick ? '' : ' static'}`}
            aria-pressed={t.onClick ? t.active : undefined}
            disabled={!t.onClick || !onFiltrar}
            onClick={t.onClick}
          >
            <span className="kpi-title">{t.title}</span>
            <span className="kpi-value" style={t.color ? { color: t.color } : undefined}>{t.value}</span>
            {t.sub && <span className="kpi-sub">{t.sub}</span>}
          </button>
        ))}
      </div>
      <div className="summary-note">
        {pendientesTodas && porAsignar && (
          <span className="summary-count">
            {plural(porAsignar.total, 'OT', 'OTs')} por asignar: {plural(porAsignar.vencidas, 'vencida', 'vencidas')}
            {' · '}{porAsignar.hoy} para hoy · {porAsignar.proximas} de próximos días · {porAsignar.sinFecha} sin fecha
          </span>
        )}
        {pendientesTodas && (() => {
          const conCerca = pendientesTodas.filter((p) => cercanas[p.actividad.codigo_bia]);
          const mismoDia = conCerca.filter((p) => cercanas[p.actividad.codigo_bia].some((c) => c.mismoDia)).length;
          return (
            <span>
              {conCerca.length} tienen OTs asignadas a {km(radioCerca)} km o menos
              {conCerca.length ? ` (${mismoDia} ese mismo día)` : ''}
            </span>
          );
        })()}
        {!pendientesTodas && visibles && <span className="summary-count">Mostrando {rows.length} de {allRows.length}</span>}
        {metricas.tiempos_por_vias ? <span>Tiempos por carretera{transito ? ` · tránsito ${transito}` : ''}</span> : null}
        {metricas.tecnicos_disponibles && metricas.radio_grupo_km !== undefined ? (
          <span>
            Reparto: {metricas.radio_grupo_km > 0 ? `primero quien tiene OTs a ${km(metricas.radio_grupo_km)} km o menos, luego ` : 'primero '}
            quien está libre y luego la menor UTR{metricas.reparto_por_semana ? ' de la semana' : ' del día'}
          </span>
        ) : null}
        {metricas.ots_agrupadas ? (
          <span>{metricas.ots_agrupadas} OTs van juntas por estar a {km(metricas.radio_grupo_km)} km o menos</span>
        ) : null}
        {avisos.map((a) => <span key={a} className="warn-text">{a}</span>)}
        <Tooltip title="Descargar el plan en CSV">
          <Button type="text" size="small" icon={<DownloadOutlined />} className="csv-button" onClick={() => exportCsv(allRows, metricas.dia)} />
        </Tooltip>
      </div>

      {view === 'lista' && pendientesTodas && (
        <Table
          className="plain-table"
          size="middle"
          rowKey={(p) => p.actividad.codigo_bia}
          columns={backlogColumns}
          dataSource={pendientesTodas}
          scroll={{ x: 1260 }}
          pagination={{ pageSize: 30, hideOnSinglePage: true, showSizeChanger: false }}
        />
      )}

      {view === 'lista' && !pendientesTodas && onSeleccion && (
        // Quick selection for a batch, among the OTs the filters show (for example, one OR)
        <div className="list-tools">
          <span className="list-tools-label">Seleccionar{visibles ? ' de lo filtrado' : ''}:</span>
          <Button
            type="link"
            size="small"
            onClick={() => onSeleccion(rows.filter((r) => r.decision.situacion === 'pendiente').map((r) => r.key))}
          >
            Solo por asignar ({rows.filter((r) => r.decision.situacion === 'pendiente').length})
          </Button>
          <Button type="link" size="small" onClick={() => onSeleccion(abiertas.map((r) => r.key))}>
            Por asignar y asignadas ({abiertas.length})
          </Button>
          {seleccion.length > 0 && (
            <Button type="link" size="small" onClick={() => onSeleccion([])}>Ninguna</Button>
          )}
        </div>
      )}

      {view === 'lista' && !pendientesTodas && (
        <Table
          className="plain-table"
          size="middle"
          columns={columns}
          dataSource={rows}
          // Minimum width: "Por qué" takes the rest of the row
          scroll={{ x: 980 }}
          // Several OTs can be selected to assign them together (the bar at the bottom)
          rowSelection={onSeleccion ? {
            selectedRowKeys: seleccion,
            onChange: onSeleccion,
            preserveSelectedRowKeys: true,
            columnWidth: 40,
            fixed: true,
            getCheckboxProps: (r) => ({ disabled: Boolean(r.actividad?.cerrada) }),
          } : undefined}
          pagination={{ pageSize: 30, hideOnSinglePage: true, showSizeChanger: false }}
          expandable={{
            expandedRowRender: (r) => (
              <DetailRow row={r} alternativas={recomendaciones[r.decision.codigo_bia]?.alternativas || []} />
            ),
          }}
        />
      )}

      {view === 'mapa' && (
        <div className="map-panel">
          <AssignmentMapView result={result} incluirRetorno={incluirRetorno} visibles={visibles} situaciones={situaciones} />
        </div>
      )}

      {view === 'rutas' && (
        <Collapse
          className="routes-list"
          ghost
          items={rutasVisibles.map(({ r, idx }) => {
            const yaAsignadas = r.ruta.paradas.filter((p) => situaciones[p.actividad.codigo_bia] === 'asignada').length;
            const paradasVisibles = visibles ? r.ruta.paradas.filter((p) => visibles.has(p.actividad.codigo_bia)) : r.ruta.paradas;
            return {
              key: r.responsable_id,
              label: (
                <div className="route-head">
                  <Dot color={ROUTE_COLORS[idx % ROUTE_COLORS.length]} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="route-title">{r.responsable}</div>
                    <div className="route-sub">
                      {r.ruta.paradas.length} OTs{yaAsignadas ? ` (${yaAsignadas} asignadas)` : ''}
                      {' · '}{hhmm(r.ruta.hora_inicio)}–{hhmm(r.ruta.hora_fin)} · {km(r.ruta.distancia_total_km)} km
                      {r.tipo === 'tecnico' && (
                        ` · ${(r.ruta.tiempo_total_minutos / 60).toLocaleString('es-CO', { maximumFractionDigits: 1 })} h usadas`
                        + ` (${(r.ruta.tiempo_trabajo_minutos / 60).toLocaleString('es-CO', { maximumFractionDigits: 1 })} en OTs,`
                        + ` ${(r.ruta.tiempo_desplazamiento_minutos / 60).toLocaleString('es-CO', { maximumFractionDigits: 1 })} de viaje)`
                        + ` · UTR ${Math.round((r.ruta.tiempo_total_minutos / 60 / horasDia) * 100)} %`
                      )}
                      {r.personas > 1 ? ` · ${r.personas} personas` : ''}
                      {r.costo !== null && r.costo !== undefined ? ` · ${formatCop(r.costo)}` : ''}
                      {' · sale de '}{r.sede.ciudad}
                    </div>
                  </div>
                  {!r.ruta.viable && <span className="warn-text">Pasa de la jornada</span>}
                </div>
              ),
              children: (
                <Table
                  className="plain-table"
                  rowKey="secuencia"
                  size="small"
                  pagination={false}
                  columns={stopColumns(nuevas, situaciones)}
                  dataSource={paradasVisibles}
                  scroll={{ x: 'max-content' }}
                />
              ),
            };
          })}
        />
      )}
    </>
  );
};

export default AssignmentResults;

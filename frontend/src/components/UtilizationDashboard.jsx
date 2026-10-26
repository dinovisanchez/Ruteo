import React, { useEffect, useMemo, useState } from 'react';
import {
  Segmented, InputNumber, Select, Switch, Table, Tooltip, Spin, Empty, message,
} from 'antd';
import dayjs from 'dayjs';
import { getUtilization } from '../services/api';
import { otTypeSettings } from '../services/otTypes';

const ISO_DAY = 'YYYY-MM-DD';
const horas = (minutos) => `${(minutos / 60).toLocaleString('es-CO', { maximumFractionDigits: 1 })} h`;
const porcentaje = (valor) => (valor === null || valor === undefined ? '—' : `${Math.round(valor * 100)} %`);

/**
 * Period around the plan day. The current period counts up to today (what already happened plus
 * today's plan); a past or future period counts whole.
 */
const periodo = (tipo, dia) => {
  const ancla = dayjs(dia);
  if (tipo === 'dia') return { desde: ancla, hasta: ancla };
  const inicio = tipo === 'semana' ? ancla.subtract((ancla.day() + 6) % 7, 'day') : ancla.startOf('month');
  const fin = tipo === 'semana' ? inicio.add(6, 'day') : ancla.endOf('month');
  const hoy = dayjs().startOf('day');
  const hastaHoy = !inicio.isAfter(hoy) && fin.isAfter(hoy);
  return { desde: inicio, hasta: hastaHoy ? hoy : fin, hastaHoy };
};

const rangoTexto = ({ desde, hasta, hastaHoy }, tipo) => {
  if (tipo === 'dia') return desde.format('dddd D [de] MMMM');
  if (desde.isSame(hasta, 'day')) {
    return `${tipo === 'semana' ? 'Semana' : capitalizar(desde.format('MMMM'))} · ${desde.format('dddd D [de] MMMM')}${hastaHoy ? ' (hasta hoy)' : ''}`;
  }
  const texto = desde.month() === hasta.month()
    ? `${desde.format('D')} al ${hasta.format('D [de] MMMM')}`
    : `${desde.format('D [de] MMM')} al ${hasta.format('D [de] MMM')}`;
  return `${tipo === 'semana' ? 'Semana' : capitalizar(desde.format('MMMM'))} · ${texto}${hastaHoy ? ' (hasta hoy)' : ''}`;
};

const capitalizar = (texto) => texto.charAt(0).toUpperCase() + texto.slice(1);

const UtrBar = ({ valor }) => (
  <div className="utr-cell">
    <div className="utr-track">
      <div className={`utr-fill${valor > 1 ? ' over' : ''}`} style={{ width: `${Math.min(100, Math.round((valor || 0) * 100))}%` }} />
    </div>
    <span className="utr-value">{porcentaje(valor)}</span>
  </div>
);

/**
 * Mini dashboard of how much of their weekly hours the Bia technicians use: OT time by type plus
 * travel base → OTs → base, against the weekly hours spread over the working days.
 */
const UtilizationDashboard = ({ ots, config, dia, result, tecnicosFiltro, horasSemana, diasSemana, onCapacidad }) => {
  const [tipo, setTipo] = useState('semana');
  const [equipo, setEquipo] = useState('todos');
  const [incluirPlan, setIncluirPlan] = useState(true);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(false);

  const rango = useMemo(() => periodo(tipo, dia), [tipo, dia]);
  const desde = rango.desde.format(ISO_DAY);
  const hasta = rango.hasta.format(ISO_DAY);
  const diaPlan = result?.metricas?.dia;
  const planEnRango = Boolean(diaPlan && diaPlan >= desde && diaPlan <= hasta);

  useEffect(() => {
    if (!ots?.length) return undefined;
    let cancelado = false;
    const tipos = [...new Set(ots.map((a) => a.servicio))];
    const plan = incluirPlan && planEnRango ? {
      dia: diaPlan,
      rutas: result.rutas.filter((r) => r.tipo === 'tecnico').map((r) => ({
        tecnicos_ids: r.responsable_id.split('+'),
        servicio_min: r.ruta.tiempo_trabajo_minutos,
        viaje_min: r.ruta.tiempo_desplazamiento_minutos,
        km: r.ruta.distancia_total_km,
        codigos: r.ruta.paradas.map((p) => p.actividad.codigo_bia),
      })),
    } : null;
    setCargando(true);
    getUtilization({
      // Without the Metabase columns: the backend only needs the OT fields
      actividades: ots.filter((a) => a.situacion === 'asignada').map((a) => ({ ...a, extras: {} })),
      desde,
      hasta,
      horas_semana: horasSemana,
      dias_semana: diasSemana,
      tiempos_servicio: tipos.map((s) => ({ servicio: s, duracion_minutos: otTypeSettings(s, config.tipos_ot).minutos })),
      plan,
    })
      .then((d) => { if (!cancelado) setDatos(d); })
      .catch((e) => { if (!cancelado) message.error(`No se pudo calcular la utilización: ${e.message}`); })
      .finally(() => { if (!cancelado) setCargando(false); });
    return () => { cancelado = true; };
  }, [ots, config, desde, hasta, horasSemana, diasSemana, incluirPlan, planEnRango, diaPlan, result]);

  const equipos = useMemo(() => [...new Set((datos?.tecnicos || []).map((t) => t.equipo))], [datos]);
  const tecnicos = (datos?.tecnicos || []).filter((t) => (
    (equipo === 'todos' || t.equipo === equipo)
    && (!tecnicosFiltro?.length || tecnicosFiltro.includes(t.nombre))
  ));

  // Totals and days of the technicians shown (the filters change them)
  const usado = tecnicos.reduce((s, t) => s + t.usado_min, 0);
  const disponible = tecnicos.reduce((s, t) => s + t.disponible_min, 0);
  const totalOts = tecnicos.reduce((s, t) => s + t.ots, 0);
  const totalKm = tecnicos.reduce((s, t) => s + (t.km || 0), 0);
  const diasConOts = tecnicos.reduce((s, t) => s + t.dias_con_ots, 0);
  const porDia = (datos?.por_dia || []).map((d) => {
    const usadoDia = tecnicos.reduce((s, t) => s + t.dias.filter((x) => x.fecha === d.fecha)
      .reduce((a, x) => a + x.servicio_min + x.viaje_min, 0), 0);
    const disponibleDia = d.laborable ? datos.horas_dia * 60 * tecnicos.length : 0;
    return { ...d, usado: usadoDia, utr: disponibleDia ? usadoDia / disponibleDia : null };
  });

  if (!ots?.length) {
    return <div className="empty-state"><div className="empty-title">Sin datos</div><div className="empty-text">Extrae las OTs para ver la utilización.</div></div>;
  }

  const columns = [
    {
      title: 'Técnico',
      render: (_, t) => (
        <div>
          <div className="ot-code">{t.nombre}</div>
          <div className="ot-cell-sub">{t.equipo}</div>
        </div>
      ),
    },
    { title: 'OTs', dataIndex: 'ots', width: 70, align: 'right', sorter: (a, b) => a.ots - b.ots },
    { title: 'En OTs', width: 90, align: 'right', render: (_, t) => horas(t.servicio_min) },
    {
      title: 'Viaje',
      width: 90,
      align: 'right',
      render: (_, t) => (t.viaje_estimado
        ? <Tooltip title="Algunas OTs no tienen ubicación: su viaje se estimó con el promedio del día">{horas(t.viaje_min)}*</Tooltip>
        : horas(t.viaje_min)),
    },
    { title: 'Km', width: 80, align: 'right', render: (_, t) => (t.km || 0).toLocaleString('es-CO', { maximumFractionDigits: 0 }) },
    { title: 'Usadas', width: 90, align: 'right', render: (_, t) => <strong>{horas(t.usado_min)}</strong> },
    { title: 'Disponibles', width: 100, align: 'right', render: (_, t) => horas(t.disponible_min) },
    {
      title: 'UTR',
      width: 200,
      defaultSortOrder: 'descend',
      sorter: (a, b) => (a.utr ?? -1) - (b.utr ?? -1),
      render: (_, t) => <UtrBar valor={t.utr} />,
    },
  ];

  const detalleDias = (t) => (
    <div className="day-breakdown">
      {t.dias.length ? t.dias.map((d) => (
        <span key={d.fecha}>
          {capitalizar(dayjs(d.fecha).format('ddd D'))}: {d.ots} OTs · {horas(d.servicio_min + d.viaje_min)} · {Math.round(d.km || 0)} km
          {d.plan ? ' (plan)' : ''}
        </span>
      )) : 'Sin OTs en el periodo'}
    </div>
  );

  const maxUtr = Math.max(1, ...porDia.map((d) => d.utr || 0));

  return (
    <Spin spinning={cargando}>
      <div className="dash-toolbar">
        <Segmented
          value={tipo}
          onChange={setTipo}
          options={[{ value: 'dia', label: 'Día' }, { value: 'semana', label: 'Semana' }, { value: 'mes', label: 'Mes' }]}
        />
        <span className="dash-range">{rangoTexto(rango, tipo)}</span>
        {equipos.length > 1 && (
          <Segmented
            value={equipo}
            onChange={setEquipo}
            options={[{ value: 'todos', label: 'Todos' }, ...equipos.map((e) => ({ value: e, label: e.replace('Equipo ', '') }))]}
          />
        )}
      </div>
      <div className="dash-capacity">
        Jornada de
        <InputNumber size="small" min={1} max={80} value={horasSemana} onChange={(v) => v && onCapacidad({ horasSemana: v })} style={{ width: 64 }} />
        h por semana en
        <Select
          size="small"
          value={diasSemana}
          onChange={(v) => onCapacidad({ diasSemana: v })}
          options={[{ value: 5, label: '5 días (L–V)' }, { value: 6, label: '6 días (L–S)' }]}
          style={{ width: 120 }}
          popupMatchSelectWidth={false}
        />
        = {(horasSemana / diasSemana).toLocaleString('es-CO', { maximumFractionDigits: 1 })} h por día
        {planEnRango && (
          <span className="dash-plan">
            <Switch size="small" checked={incluirPlan} onChange={setIncluirPlan} />
            Incluir el plan del {dayjs(diaPlan).format('D [de] MMM')} con sus sugerencias
          </span>
        )}
      </div>

      <div className="kpi-row">
        <div className="kpi static"><span className="kpi-title">UTR</span><span className="kpi-value" style={{ color: '#007AFF' }}>{porcentaje(disponible ? usado / disponible : null)}</span></div>
        <div className="kpi static"><span className="kpi-title">Horas usadas</span><span className="kpi-value">{horas(usado)}</span></div>
        <div className="kpi static"><span className="kpi-title">Horas disponibles</span><span className="kpi-value">{horas(disponible)}</span></div>
        <div className="kpi static"><span className="kpi-title">OTs</span><span className="kpi-value">{totalOts}</span></div>
        <div className="kpi static">
          <span className="kpi-title">OTs por técnico al día</span>
          <span className="kpi-value">{diasConOts ? (totalOts / diasConOts).toLocaleString('es-CO', { maximumFractionDigits: 1 }) : '—'}</span>
        </div>
        <div className="kpi static">
          <span className="kpi-title">Km recorridos</span>
          <span className="kpi-value">{totalKm.toLocaleString('es-CO', { maximumFractionDigits: 0 })}</span>
        </div>
        <div className="kpi static">
          <span className="kpi-title">Viaje / horas usadas</span>
          <span className="kpi-value">{porcentaje(usado ? tecnicos.reduce((s, t) => s + t.viaje_min, 0) / usado : null)}</span>
        </div>
      </div>

      {tipo !== 'dia' && (
        <div className="dash-chart">
          {porDia.map((d) => (
            <Tooltip key={d.fecha} title={`${capitalizar(dayjs(d.fecha).format('dddd D MMM'))}: ${d.laborable ? `${porcentaje(d.utr)} · ${horas(d.usado)}` : `no laborable · ${horas(d.usado)}`}`}>
              <div className={`dash-bar${d.laborable ? '' : ' off'}`}>
                <div className="dash-bar-track">
                  <div className={`dash-bar-fill${(d.utr || 0) > 1 ? ' over' : ''}`} style={{ height: `${Math.round(((d.utr || 0) / maxUtr) * 100)}%` }} />
                </div>
                <span className="dash-bar-label">{tipo === 'semana' ? dayjs(d.fecha).format('dd') : dayjs(d.fecha).format('D')}</span>
              </div>
            </Tooltip>
          ))}
        </div>
      )}

      {tecnicos.length ? (
        <Table
          className="plain-table"
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={tecnicos}
          pagination={false}
          expandable={{ expandedRowRender: detalleDias }}
          scroll={{ x: 'max-content' }}
        />
      ) : <Empty description="No hay técnicos con esos filtros" />}

      <div className="summary-note" style={{ marginTop: 12 }}>
        <span>
          UTR = horas usadas ÷ horas disponibles. Horas usadas: duración de cada OT según su tipo + desplazamiento
          base → OTs → base de cada día (con tránsito). Fuente: OTs asignadas o cerradas en Metabase con fecha de visita y electricistas.
        </span>
        {datos?.sin_registrar?.length > 0 && (
          <span className="warn-text">
            Aparecen como técnicos de Bia en Metabase pero no están en la app:{' '}
            {datos.sin_registrar.map((s) => `${s.nombre} (${s.ots} OTs)`).join(', ')}. Agrégalos en Técnicos → Gestionar.
          </span>
        )}
      </div>
    </Spin>
  );
};

export default UtilizationDashboard;

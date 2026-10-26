import React, {
  forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState,
} from 'react';
import {
  Button, Input, Space, Switch, InputNumber, Alert, Select, Segmented, Tag, Typography,
  Form, TimePicker, Collapse, Upload, notification, message,
} from 'antd';
import { UploadOutlined, WarningOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

import TechniciansModal from './TechniciansModal';
import OrContractorsModal, { buildOrRows } from './OrContractorsModal';
import OtTypesModal from './OtTypesModal';
import {
  getMetabaseStatus, fetchMetabaseOTs, getAssignmentConfig, saveAssignmentConfig, uploadFile,
  getOperators, getSheetTechnicians,
} from '../services/api';
import { otTypeSettings, normalizeText } from '../services/otTypes';
import { formatCop } from '../services/format';

const { Text } = Typography;

const KNOWN_OTS_KEY = 'ruteo_ots_conocidas';

const readKnownOts = () => {
  try {
    return new Set(JSON.parse(localStorage.getItem(KNOWN_OTS_KEY) || '[]'));
  } catch (error) {
    return null;
  }
};

const writeKnownOts = (codes) => {
  try {
    localStorage.setItem(KNOWN_OTS_KEY, JSON.stringify(codes));
  } catch (error) {
    // Without storage the "new" badge just resets on reload
  }
};

// Automatic update: on by default, remembered in this browser
const AUTO_REFRESH_KEY = 'ruteo_actualizar';

const readAutoRefresh = () => {
  try {
    return { activo: true, minutos: 10, ...JSON.parse(localStorage.getItem(AUTO_REFRESH_KEY) || '{}') };
  } catch (error) {
    return { activo: true, minutos: 10 };
  }
};

const countBy = (items, key) => {
  const counts = {};
  (items || []).forEach((a) => { counts[a[key]] = (counts[a[key]] || 0) + 1; });
  return counts;
};

/**
 * Settings of the plan, in collapsible sections. The header calls `extract` and `recalc`
 * through the ref; `onStateChange` tells it whether they can run.
 */
const AssignmentPanel = forwardRef(({
  ots, onOtsLoaded, onAssign, loading, config, onConfigChange, catalog, dia, zonas, onStateChange,
}, ref) => {
  const [form] = Form.useForm();
  const [status, setStatus] = useState(null);
  // Question used to extract; it is not shown, only replaced from Ajustes
  const [cardId, setCardId] = useState('');
  const [cambiandoPregunta, setCambiandoPregunta] = useState(false);
  const [nuevaPregunta, setNuevaPregunta] = useState('');
  const [fetching, setFetching] = useState(false);
  const [fetchInfo, setFetchInfo] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(() => readAutoRefresh().activo);
  const [refreshMinutes, setRefreshMinutes] = useState(() => readAutoRefresh().minutos);
  const [configCargada, setConfigCargada] = useState(false);
  // Every section starts minimized; Ajustes opens by itself when there is no question saved yet
  const [abiertas, setAbiertas] = useState([]);
  const [orFilter, setOrFilter] = useState([]);
  const [modo, setModo] = useState('automatico');
  // Every active technician is available unless switched off for the day
  const [noDisponibles, setNoDisponibles] = useState([]);
  // Manual pairs: technician id → partner id (both directions); empty = the app suggests pairs
  const [parejas, setParejas] = useState({});
  const [transito, setTransito] = useState([]);
  const [techModalOpen, setTechModalOpen] = useState(false);
  const [orModalOpen, setOrModalOpen] = useState(false);
  const [typesModalOpen, setTypesModalOpen] = useState(false);
  const [orInfo, setOrInfo] = useState({ operadores: [], resueltos: {} });
  const [hojaTecnicos, setHojaTecnicos] = useState([]);
  const knownRef = useRef(null);

  useEffect(() => {
    getMetabaseStatus()
      .then((s) => {
        setStatus(s);
        if (s.card_id) setCardId(s.card_id);
        else {
          setAbiertas(['ajustes']);
          setCambiandoPregunta(true);
        }
      })
      .catch(() => setStatus({ configurado: false, sinBackend: true }));
    getAssignmentConfig()
      .then((saved) => { onConfigChange(saved); setConfigCargada(true); })
      .catch((e) => message.error(`No se pudo leer la configuración: ${e.message}`));
    getSheetTechnicians().then(setHojaTecnicos).catch(() => setHojaTecnicos([]));
  }, [onConfigChange]);

  useEffect(() => { setTransito(zonas.transito); }, [zonas]);

  const orCounts = useMemo(() => countBy(ots, 'or_operador'), [ots]);
  const serviceCounts = useMemo(() => countBy(ots, 'servicio'), [ots]);
  const services = Object.keys(serviceCounts).sort();

  // Match the OR names in the OTs to the catalog of network operators
  const orNamesKey = Object.keys(orCounts).sort().join('|');
  useEffect(() => {
    getOperators(orNamesKey ? orNamesKey.split('|') : []).then(setOrInfo).catch(() => {});
  }, [orNamesKey]);
  const orRows = buildOrRows(orInfo.operadores, orInfo.resueltos, orCounts, config.or_contratistas)
    .filter((r) => r.ots > 0);

  const tecnicosFaltantes = hojaTecnicos.filter(
    (t) => !config.tecnicos.some((x) => normalizeText(x.nombre) === normalizeText(t.nombre)),
  );
  const addSheetTechnicians = async () => {
    try {
      const saved = await saveAssignmentConfig({ ...config, tecnicos: [...config.tecnicos, ...tecnicosFaltantes] });
      onConfigChange(saved);
      message.success(`${tecnicosFaltantes.length} técnicos agregados desde la hoja`);
    } catch (error) {
      message.error(`No se pudieron agregar los técnicos: ${error.message}`);
    }
  };
  const sedesById = useMemo(() => Object.fromEntries(catalog.sedes.map((s) => [s.id, s])), [catalog]);
  const empresasById = useMemo(() => Object.fromEntries(catalog.empresas.map((e) => [e.id, e])), [catalog]);

  const tecnicosActivos = config.tecnicos.filter((t) => t.activo !== false);
  const disponibles = tecnicosActivos.filter((t) => !noDisponibles.includes(t.id)).map((t) => t.id);
  const disponiblesKey = disponibles.join('|');

  // Technicians grouped by the Bia team of their base, with what that team covers
  const equipos = useMemo(() => {
    const porBase = {};
    tecnicosActivos.forEach((t) => { (porBase[t.base_id] = porBase[t.base_id] || []).push(t); });
    return Object.entries(porBase).map(([baseId, tecnicos]) => {
      const equipo = zonas.equipos.find((e) => e.base_id === baseId);
      const cubre = equipo
        ? `${equipo.ors.filter((o) => o !== 'Electricaribe').join(', ')} · ${equipo.zonas.length
          ? equipo.zonas.map((z) => z.nombre).join(', ') : 'toda su área'}`
        : 'Sin zona definida';
      return { baseId, nombre: equipo?.equipo || sedesById[baseId]?.empresa || baseId, cubre, tecnicos };
    });
  }, [tecnicosActivos, zonas, sedesById]);

  // A pair only makes sense while both technicians are available
  useEffect(() => {
    const ids = disponiblesKey.split('|');
    setParejas((prev) => Object.fromEntries(
      Object.entries(prev).filter(([a, b]) => ids.includes(a) && ids.includes(b)),
    ));
  }, [disponiblesKey]);

  const setPareja = (id, partnerId) => {
    setParejas((prev) => {
      const next = { ...prev };
      [id, partnerId, prev[id], prev[partnerId]].forEach((x) => { if (x) delete next[x]; });
      if (partnerId) {
        next[id] = partnerId;
        next[partnerId] = id;
      }
      return next;
    });
  };

  const cuadrillasManuales = Object.entries(parejas).filter(([a, b]) => a < b).map(([a, b]) => [a, b]);

  const runAssign = async (actividades) => {
    if (!actividades?.length) return;
    const values = await form.validateFields();
    const tipos = [...new Set(actividades.map((a) => a.servicio))];
    await onAssign({
      modo,
      actividades,
      or_filtro: orFilter,
      // Also in "solo contratistas": OTs already assigned to an available technician stay with them
      tecnicos_ids: disponibles,
      cuadrillas: cuadrillasManuales,
      personas_por_tipo: Object.fromEntries(tipos.map((s) => [s, otTypeSettings(s, config.tipos_ot).personas])),
      transito,
      jornada: {
        horario_inicio: values.horario_inicio.format('HH:mm:ss'),
        horas_laborales: values.horas_laborales,
        velocidad_promedio_kmh: values.velocidad_promedio_kmh,
        factor_vial: values.factor_vial,
        radio_inhouse_km: values.radio_inhouse_km,
        capacidad_maxima_actividades: values.capacidad_maxima_actividades || null,
        incluir_retorno: values.incluir_retorno,
        tiempos_servicio: tipos.map((s) => ({ servicio: s, duracion_minutos: otTypeSettings(s, config.tipos_ot).minutos })),
      },
    });
  };

  // When the OTs were last read from Metabase, and whether a reading is under way
  const ultimaLecturaRef = useRef(0);
  const leyendoRef = useRef(false);

  const loadOts = async (silent) => {
    if (leyendoRef.current) return null;
    leyendoRef.current = true;
    setFetching(true);
    try {
      const data = await fetchMetabaseOTs(cardId.trim());
      ultimaLecturaRef.current = Date.now();
      const codes = data.actividades.map((a) => a.codigo_bia);
      if (knownRef.current === null) knownRef.current = readKnownOts();
      const known = knownRef.current;
      // Without a previous list there is nothing to compare against: nothing is "new"
      const nuevas = new Set(known && known.size ? codes.filter((c) => !known.has(c)) : []);
      knownRef.current = new Set([...(known || []), ...codes]);
      writeKnownOts([...knownRef.current]);

      setFetchInfo(data);
      onOtsLoaded(data.actividades, nuevas, 'Metabase', data.mapeo);
      if (nuevas.size && silent) {
        notification.info({
          message: `Llegaron ${nuevas.size} OTs nuevas`,
          description: 'La recomendación se actualizó con ellas.',
          placement: 'bottomRight',
        });
      }
      return data.actividades;
    } catch (error) {
      if (!silent) message.error(error.message, 8);
      return null;
    } finally {
      leyendoRef.current = false;
      setFetching(false);
    }
  };

  const extractAndRecommend = async (silent) => {
    const actividades = await loadOts(silent);
    if (actividades?.length) await runAssign(actividades);
    else if (actividades && !silent) message.info('La pregunta no devolvió OTs');
  };

  // The header buttons and the interval call the latest version through a ref
  const actionsRef = useRef({});
  actionsRef.current = {
    extract: () => extractAndRecommend(false),
    refresh: () => extractAndRecommend(true),
    recalc: () => runAssign(ots),
  };
  useImperativeHandle(ref, () => ({
    extract: () => actionsRef.current.extract(),
    refresh: () => actionsRef.current.refresh(),
    recalc: () => actionsRef.current.recalc(),
  }), []);

  const canExtract = Boolean(status?.configurado && cardId.trim());
  useEffect(() => {
    onStateChange({ canExtract, fetching, autoRefresh });
  }, [canExtract, fetching, autoRefresh, onStateChange]);

  useEffect(() => {
    try {
      localStorage.setItem(AUTO_REFRESH_KEY, JSON.stringify({ activo: autoRefresh, minutos: refreshMinutes }));
    } catch (error) {
      // Without storage it goes back to the default on reload
    }
  }, [autoRefresh, refreshMinutes]);

  // With automatic update on, the plan loads by itself when the app opens (once the technicians and
  // OT types are read), every N minutes, and when coming back to the tab after longer than that
  const autoRef = useRef(extractAndRecommend);
  autoRef.current = extractAndRecommend;
  const arrancoRef = useRef(false);
  useEffect(() => {
    if (!autoRefresh || !canExtract || !configCargada || arrancoRef.current) return;
    arrancoRef.current = true;
    if (!ultimaLecturaRef.current) autoRef.current(true);
  }, [autoRefresh, canExtract, configCargada]);
  useEffect(() => {
    if (!autoRefresh || !canExtract) return undefined;
    const periodo = Math.max(1, refreshMinutes) * 60 * 1000;
    const id = setInterval(() => autoRef.current(true), periodo);
    const alVolver = () => {
      if (document.visibilityState === 'visible' && Date.now() - ultimaLecturaRef.current > periodo) autoRef.current(true);
    };
    document.addEventListener('visibilitychange', alVolver);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', alVolver);
    };
  }, [autoRefresh, canExtract, refreshMinutes]);

  const saveDefaultCard = async () => {
    try {
      const saved = await saveAssignmentConfig({ ...config, card_id: nuevaPregunta.trim() || null });
      onConfigChange(saved);
      setCardId(saved.card_id || '');
      setNuevaPregunta('');
      setCambiandoPregunta(false);
      message.success('Pregunta guardada');
    } catch (error) {
      message.error(error.message);
    }
  };

  const handleUpload = async ({ file, onSuccess, onError }) => {
    try {
      const data = await uploadFile(file);
      setFetchInfo(null);
      onOtsLoaded(data.activities, new Set(), `Archivo ${file.name}`, {});
      onSuccess(data);
      await runAssign(data.activities);
    } catch (error) {
      message.error(`No se pudo leer el archivo: ${error.message}`);
      onError(error);
    }
  };

  const updateTransito = (nombre, field, value) => {
    setTransito((prev) => prev.map((z) => (z.nombre === nombre ? { ...z, [field]: value ?? 0 } : z)));
  };

  const busy = fetching || loading;
  const savedCard = config.card_id || status?.card_id;

  const tecnicosSection = (
    <>
      {equipos.length ? equipos.map((equipo) => (
        <div key={equipo.baseId} className="ios-list">
          <div className="ios-list-header">
            <Text strong>{equipo.nombre}</Text>
            <Text type="secondary" className="ios-list-sub">{equipo.cubre}</Text>
          </div>
          {equipo.tecnicos.map((t) => {
            const available = disponibles.includes(t.id);
            const partners = tecnicosActivos.filter((o) => o.id !== t.id && disponibles.includes(o.id)
              && o.base_id === t.base_id && (!parejas[o.id] || parejas[o.id] === t.id));
            return (
              <div key={t.id} className={`ios-row${available ? '' : ' ios-row-off'}`}>
                <div className="ios-row-main">
                  <div className="ios-row-title">{t.nombre}</div>
                  <div className="ios-row-sub">
                    {available ? (parejas[t.id] ? 'En pareja' : 'Disponible') : 'No disponible'}
                    {t.costo_dia ? ` · ${formatCop(t.costo_dia)}/día` : ''}
                  </div>
                </div>
                {available && partners.length > 0 && (
                  <Select
                    size="small"
                    variant="borderless"
                    allowClear
                    placeholder="Pareja"
                    value={parejas[t.id]}
                    onChange={(v) => setPareja(t.id, v)}
                    options={partners.map((o) => ({ value: o.id, label: o.nombre.split(' ')[0] }))}
                    popupMatchSelectWidth={false}
                    style={{ width: 96 }}
                  />
                )}
                <Switch
                  checked={available}
                  onChange={(checked) => setNoDisponibles((prev) => (checked
                    ? prev.filter((x) => x !== t.id) : [...prev, t.id]))}
                />
              </div>
            );
          })}
        </div>
      )) : (
        <Text type="secondary">
          Sin técnicos registrados: todo se recomendará a contratistas. Agrégalos en «Gestionar».
        </Text>
      )}
      <Text type="secondary" className="ios-footnote">
        {cuadrillasManuales.length
          ? `${cuadrillasManuales.length} pareja(s) armadas a mano; con el resto se arman las que pidan las OTs de 2 personas.`
          : 'Las parejas para OTs de 2 personas se arman solas (o como ya salen en Metabase).'}
      </Text>
      <Space wrap size={0} style={{ marginTop: 4, marginLeft: -8 }}>
        <Button size="small" type="link" onClick={() => setTechModalOpen(true)}>Gestionar técnicos</Button>
        {tecnicosFaltantes.length > 0 && (
          <Button size="small" type="link" onClick={addSheetTechnicians}>
            Agregar {tecnicosFaltantes.length} de la hoja
          </Button>
        )}
      </Space>
    </>
  );

  const contratistasSection = (
    <>
      {orRows.length ? orRows.map((r) => (
        <div key={r.key} className="ios-list">
          <div className="ios-list-header">
            <Text strong>{r.nombre} <Text type="secondary">({r.ots})</Text></Text>
            {r.departamentos.length > 0 && <Text type="secondary" className="ios-list-sub">{r.departamentos.join(', ')}</Text>}
          </div>
          <div style={{ padding: '6px 12px 8px' }}>
            {r.manual.length > 0 && r.manual.map((id) => <Tag key={id} color="purple">{empresasById[id]?.nombre || id}</Tag>)}
            {!r.manual.length && r.auto.length > 0 && r.auto.map((id) => (
              <Tag key={id} bordered={false}>{empresasById[id]?.nombre || id}</Tag>
            ))}
            {!r.manual.length && !r.auto.length && (
              <Tag icon={<WarningOutlined />} color="warning">
                {r.desconocido ? 'los de su departamento' : 'sin contratistas en la zona: el más cercano'}
              </Tag>
            )}
          </div>
        </div>
      )) : (
        <Text type="secondary" className="ios-footnote">
          Cada OT va al contratista más cercano con sede en los departamentos que atiende su OR.
        </Text>
      )}
      <Button size="small" type="link" style={{ marginTop: 8 }} onClick={() => setOrModalOpen(true)}>Editar contratistas</Button>
    </>
  );

  const tiposSection = (
    <>
      {services.length ? (
        <div className="ios-list">
          {services.map((s) => {
            const tipo = otTypeSettings(s, config.tipos_ot);
            return (
              <div key={s} className="ios-row">
                <div className="ios-row-main">
                  <div className="ios-row-title">{s}</div>
                  <div className="ios-row-sub">{serviceCounts[s]} OTs</div>
                </div>
                <Tag bordered={false}>{tipo.minutos >= 60 && tipo.minutos % 60 === 0 ? `${tipo.minutos / 60} h` : `${tipo.minutos} min`}</Tag>
                <Tag bordered={false} color={tipo.personas > 1 ? 'blue' : undefined}>{tipo.personas} pers.</Tag>
              </div>
            );
          })}
        </div>
      ) : (
        <Text type="secondary" className="ios-footnote">Aparecen al extraer las OTs.</Text>
      )}
      <Button size="small" type="link" style={{ marginTop: 8 }} onClick={() => setTypesModalOpen(true)} disabled={!services.length}>
        Editar duración y personas
      </Button>
    </>
  );

  const ajustesSection = (
    <>
      <div className="ios-field-label">Fuente de datos</div>
      <div className="ios-list">
        <div className="ios-row">
          <div className="ios-row-main">
            <div className="ios-row-title">Metabase</div>
            <div className="ios-row-sub">
              {!status?.configurado ? 'Sin configurar en backend/.env' : (savedCard ? 'Conectado' : 'Falta la pregunta')}
            </div>
          </div>
          {status?.configurado && (
            <Button size="small" type="link" onClick={() => { setCambiandoPregunta((v) => !v); setNuevaPregunta(''); }}>
              {cambiandoPregunta ? 'Cancelar' : (savedCard ? 'Cambiar pregunta' : 'Elegir pregunta')}
            </Button>
          )}
        </div>
      </div>
      {cambiandoPregunta && (
        <Space.Compact style={{ width: '100%' }}>
          <Input
            autoFocus
            value={nuevaPregunta}
            placeholder="Número de la nueva pregunta"
            onChange={(e) => setNuevaPregunta(e.target.value)}
            onPressEnter={saveDefaultCard}
          />
          <Button type="primary" onClick={saveDefaultCard} disabled={!nuevaPregunta.trim()}>Guardar</Button>
        </Space.Compact>
      )}
      <Space style={{ marginTop: 8 }} size={6} wrap>
        <Switch size="small" checked={autoRefresh} onChange={setAutoRefresh} disabled={!status?.configurado} />
        <Text style={{ fontSize: 13 }}>Actualizar cada</Text>
        <InputNumber
          size="small"
          min={1}
          max={120}
          value={refreshMinutes}
          onChange={(v) => setRefreshMinutes(v || 10)}
          style={{ width: 60 }}
        />
        <Text style={{ fontSize: 13 }}>min</Text>
      </Space>
      <Text type="secondary" className="ios-footnote" style={{ display: 'block', marginTop: 2 }}>
        {autoRefresh
          ? 'Carga el plan al abrir la app, cada pocos minutos y al empezar un nuevo día'
          : 'Al empezar un nuevo día solo se recalcula con las OTs ya cargadas'}
      </Text>
      <Upload accept=".xlsx,.xls,.csv" showUploadList={false} customRequest={handleUpload} disabled={busy}>
        <Button type="link" size="small" icon={<UploadOutlined />} style={{ paddingLeft: 0, marginTop: 4 }}>
          o subir un Excel/CSV
        </Button>
      </Upload>
      {fetchInfo?.avisos.map((aviso) => (
        <Alert key={aviso} type="warning" message={aviso} showIcon style={{ marginTop: 4, fontSize: 12 }} />
      ))}

      <div className="ios-field-label">Asignar a</div>
      <Segmented
        block
        value={modo}
        onChange={setModo}
        options={[
          { value: 'automatico', label: 'Automático' },
          { value: 'inhouse', label: 'Técnicos' },
          { value: 'contratistas', label: 'Contratistas' },
        ]}
      />
      <div className="ios-field-label">Filtrar por OR</div>
      <Select
        mode="multiple"
        allowClear
        value={orFilter}
        onChange={setOrFilter}
        style={{ width: '100%' }}
        placeholder="Todos los OR"
        options={Object.entries(orCounts).map(([name, count]) => ({ value: name, label: `${name} (${count})` }))}
      />

      <div className="ios-field-label">Tránsito: más tiempo de desplazamiento</div>
      <div className="ios-list">
        {transito.map((z) => (
          <div key={z.nombre} className="ios-row">
            <div className="ios-row-main"><div className="ios-row-title">{z.nombre}</div></div>
            <InputNumber
              size="small"
              min={0}
              max={500}
              value={z.recargo_pct}
              onChange={(v) => updateTransito(z.nombre, 'recargo_pct', v)}
              addonAfter="%"
              style={{ width: 80 }}
            />
            <InputNumber
              size="small"
              min={0}
              max={240}
              value={z.minutos_extra}
              onChange={(v) => updateTransito(z.nombre, 'minutos_extra', v)}
              addonAfter="min"
              style={{ width: 88 }}
            />
          </div>
        ))}
      </div>
      <Text type="secondary" className="ios-footnote">
        Se suma a cada desplazamiento que empieza o termina en la zona: un % del tiempo por las vías y, si quieres, minutos fijos.
      </Text>

      <div className="ios-field-label">Jornada</div>
      <Form
        form={form}
        layout="vertical"
        size="small"
        initialValues={{
          horario_inicio: dayjs('08:00', 'HH:mm'),
          horas_laborales: 8,
          velocidad_promedio_kmh: 30,
          factor_vial: 1.3,
          radio_inhouse_km: 40,
          capacidad_maxima_actividades: null,
          incluir_retorno: true,
        }}
      >
        <Space wrap>
          <Form.Item label="Inicio" name="horario_inicio" rules={[{ required: true }]}>
            <TimePicker format="HH:mm" />
          </Form.Item>
          <Form.Item label="Horas de trabajo" name="horas_laborales" rules={[{ required: true }]}>
            <InputNumber min={1} max={24} step={0.5} />
          </Form.Item>
          <Form.Item label="Máx. OTs por ruta" name="capacidad_maxima_actividades">
            <InputNumber min={1} placeholder="Sin límite" />
          </Form.Item>
          <Form.Item label="Volver a la base" name="incluir_retorno" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item
            label="Radio técnicos (km)"
            name="radio_inhouse_km"
            hidden={zonas.equipos.length > 0}
            tooltip="Solo si no hay zonas por equipo: las OTs más lejos que esto de la base van a contratistas"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={500} />
          </Form.Item>
          <Form.Item
            label="Velocidad en ciudad (km/h)"
            name="velocidad_promedio_kmh"
            tooltip="Solo si OSRM no responde: los tiempos se estiman en línea recta"
            rules={[{ required: true }]}
          >
            <InputNumber min={5} max={120} />
          </Form.Item>
          <Form.Item
            label="Factor vial"
            name="factor_vial"
            tooltip="Solo si OSRM no responde: aproxima la línea recta a la distancia por carretera"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={3} step={0.1} />
          </Form.Item>
        </Space>
      </Form>
    </>
  );

  return (
    <>
      {status?.sinBackend && (
        <Alert
          type="error"
          showIcon
          className="ios-alert"
          message="No hay conexión con el backend"
          description="El backend no está corriendo en http://localhost:8000. Ciérralo todo y ejecuta ./iniciar.sh; si falla, revisa logs/backend-8000.log."
        />
      )}
      {status && !status.sinBackend && !status.configurado && (
        <Alert
          type="warning"
          showIcon
          className="ios-alert"
          message="Metabase no está configurado"
          description="Completa METABASE_URL y METABASE_API_KEY en backend/.env y reinicia con ./iniciar.sh."
        />
      )}
      {status?.configurado && !savedCard && (
        <Alert type="info" showIcon className="ios-alert" message="Elige la pregunta de Metabase en Ajustes → Fuente de datos" />
      )}
      {fetchInfo && (fetchInfo.geocodificadas > 0 || fetchInfo.sin_coordenadas > 0) && (
        <Text type="secondary" className="ios-footnote" style={{ margin: '0 4px 10px' }}>
          {fetchInfo.geocodificadas ? `${fetchInfo.geocodificadas} OTs ubicadas por dirección` : ''}
          {fetchInfo.geocodificadas && fetchInfo.sin_coordenadas ? ' · ' : ''}
          {fetchInfo.sin_coordenadas ? `${fetchInfo.sin_coordenadas} sin ubicación` : ''}
        </Text>
      )}

      <Collapse
        className="ios-sections"
        bordered={false}
        expandIconPosition="end"
        activeKey={abiertas}
        onChange={setAbiertas}
        items={[
          {
            key: 'tecnicos',
            label: 'Técnicos',
            extra: <Text type="secondary">{disponibles.length} de {tecnicosActivos.length} · {dayjs(dia).format('ddd D')}</Text>,
            children: tecnicosSection,
          },
          {
            key: 'contratistas',
            label: 'Contratistas por OR',
            extra: orRows.length ? <Text type="secondary">{orRows.length} OR</Text> : null,
            children: contratistasSection,
          },
          {
            key: 'tipos',
            label: 'Tipos de OT',
            extra: services.length ? <Text type="secondary">{services.length}</Text> : null,
            children: tiposSection,
          },
          {
            key: 'ajustes',
            label: 'Ajustes',
            forceRender: true,
            children: ajustesSection,
          },
        ]}
      />

      <TechniciansModal
        open={techModalOpen}
        config={config}
        sedes={catalog.sedes}
        onClose={() => setTechModalOpen(false)}
        onSaved={(saved) => { onConfigChange(saved); setTechModalOpen(false); }}
      />
      <OrContractorsModal
        open={orModalOpen}
        config={config}
        empresas={catalog.empresas}
        operadores={orInfo.operadores}
        resueltos={orInfo.resueltos}
        orCounts={orCounts}
        onClose={() => setOrModalOpen(false)}
        onSaved={(saved) => { onConfigChange(saved); setOrModalOpen(false); }}
      />
      <OtTypesModal
        open={typesModalOpen}
        config={config}
        otCounts={serviceCounts}
        onClose={() => setTypesModalOpen(false)}
        onSaved={(saved) => { onConfigChange(saved); setTypesModalOpen(false); }}
      />
    </>
  );
});

export default AssignmentPanel;

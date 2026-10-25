import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Card, Button, Input, Space, Switch, InputNumber, Alert, Select, Segmented, Checkbox, Tag, Typography,
  Form, TimePicker, Collapse, Upload, notification, message,
} from 'antd';
import {
  ThunderboltFilled, ReloadOutlined, UploadOutlined, SettingOutlined, WarningOutlined, SaveOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import TechniciansModal from './TechniciansModal';
import OrContractorsModal from './OrContractorsModal';
import OtTypesModal from './OtTypesModal';
import {
  getMetabaseStatus, fetchMetabaseOTs, getCatalog, getAssignmentConfig, saveAssignmentConfig, uploadFile,
} from '../services/api';
import { otTypeSettings } from '../services/otTypes';
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

const countBy = (items, key) => {
  const counts = {};
  (items || []).forEach((a) => { counts[a[key]] = (counts[a[key]] || 0) + 1; });
  return counts;
};

const AssignmentPanel = ({ ots, onOtsLoaded, onAssign, loading, config, onConfigChange }) => {
  const [form] = Form.useForm();
  const [status, setStatus] = useState(null);
  const [cardId, setCardId] = useState('');
  const [fetching, setFetching] = useState(false);
  const [fetchInfo, setFetchInfo] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshMinutes, setRefreshMinutes] = useState(10);
  const [catalog, setCatalog] = useState({ sedes: [], empresas: [], avisos: [] });
  const [orFilter, setOrFilter] = useState([]);
  const [modo, setModo] = useState('automatico');
  // Every active technician is available unless unchecked for the day
  const [noDisponibles, setNoDisponibles] = useState([]);
  // Manual pairs: technician id → partner id (both directions); empty = the app suggests pairs
  const [parejas, setParejas] = useState({});
  const [techModalOpen, setTechModalOpen] = useState(false);
  const [orModalOpen, setOrModalOpen] = useState(false);
  const [typesModalOpen, setTypesModalOpen] = useState(false);
  const knownRef = useRef(null);

  useEffect(() => {
    getMetabaseStatus()
      .then((s) => {
        setStatus(s);
        if (s.card_id) setCardId(s.card_id);
      })
      .catch(() => setStatus({ configurado: false }));
    getCatalog().then(setCatalog).catch((e) => message.error(`No se pudo leer el catálogo: ${e.message}`));
    getAssignmentConfig().then(onConfigChange).catch((e) => message.error(`No se pudo leer la configuración: ${e.message}`));
  }, [onConfigChange]);

  const orCounts = useMemo(() => countBy(ots, 'or_operador'), [ots]);
  const serviceCounts = useMemo(() => countBy(ots, 'servicio'), [ots]);
  const services = Object.keys(serviceCounts).sort();
  const sedesById = useMemo(() => Object.fromEntries(catalog.sedes.map((s) => [s.id, s])), [catalog]);
  const empresasById = useMemo(() => Object.fromEntries(catalog.empresas.map((e) => [e.id, e])), [catalog]);

  const tecnicosActivos = config.tecnicos.filter((t) => t.activo !== false);
  const disponibles = tecnicosActivos.filter((t) => !noDisponibles.includes(t.id)).map((t) => t.id);
  const disponiblesKey = disponibles.join('|');

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

  const contractorsFor = (orName) => {
    const key = Object.keys(config.or_contratistas).find((k) => k.toLowerCase() === orName.toLowerCase());
    return key ? config.or_contratistas[key] : [];
  };

  const runAssign = async (actividades) => {
    if (!actividades?.length) return;
    const values = await form.validateFields();
    const tipos = [...new Set(actividades.map((a) => a.servicio))];
    await onAssign({
      modo,
      actividades,
      or_filtro: orFilter,
      tecnicos_ids: modo === 'contratistas' ? [] : disponibles,
      cuadrillas: modo === 'contratistas' ? [] : cuadrillasManuales,
      personas_por_tipo: Object.fromEntries(tipos.map((s) => [s, otTypeSettings(s, config.tipos_ot).personas])),
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

  const loadOts = async (silent) => {
    setFetching(true);
    try {
      const data = await fetchMetabaseOTs(cardId.trim());
      const codes = data.actividades.map((a) => a.codigo_bia);
      if (knownRef.current === null) knownRef.current = readKnownOts();
      const known = knownRef.current;
      // Without a previous list there is nothing to compare against: nothing is "new"
      const nuevas = new Set(known && known.size ? codes.filter((c) => !known.has(c)) : []);
      knownRef.current = new Set([...(known || []), ...codes]);
      writeKnownOts([...knownRef.current]);

      setFetchInfo(data);
      onOtsLoaded(data.actividades, nuevas, `Pregunta #${data.card_id}`, data.mapeo);
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
      setFetching(false);
    }
  };

  const extractAndRecommend = async (silent) => {
    const actividades = await loadOts(silent);
    if (actividades?.length) await runAssign(actividades);
    else if (actividades && !silent) message.info('La pregunta no devolvió OTs pendientes');
  };

  // The interval calls the latest version through a ref so it does not restart on every render
  const autoRef = useRef(extractAndRecommend);
  autoRef.current = extractAndRecommend;
  useEffect(() => {
    if (!autoRefresh) return undefined;
    const id = setInterval(() => autoRef.current(true), Math.max(1, refreshMinutes) * 60 * 1000);
    return () => clearInterval(id);
  }, [autoRefresh, refreshMinutes]);

  const saveDefaultCard = async () => {
    try {
      const saved = await saveAssignmentConfig({ ...config, card_id: cardId.trim() || null });
      onConfigChange(saved);
      message.success(`Pregunta #${saved.card_id} guardada como predeterminada`);
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

  const busy = fetching || loading;
  const savedCard = config.card_id || status?.card_id;

  return (
    <>
      <Button
        type="primary"
        size="large"
        block
        icon={<ThunderboltFilled />}
        loading={busy}
        disabled={!status?.configurado || !cardId.trim()}
        onClick={() => extractAndRecommend(false)}
        style={{ height: 52, fontSize: 17, marginBottom: 8 }}
      >
        Extraer y recomendar
      </Button>
      {ots?.length > 0 && (
        <Button block icon={<ReloadOutlined />} disabled={busy} onClick={() => runAssign(ots)} style={{ marginBottom: 12 }}>
          Recalcular con los ajustes actuales
        </Button>
      )}

      <Card size="small" title="Pregunta de Metabase" style={{ marginBottom: 12 }}>
        {status && !status.configurado && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 8 }}
            message="Metabase no está configurado"
            description="Completa METABASE_URL y METABASE_API_KEY en backend/.env y reinicia con ./iniciar.sh."
          />
        )}
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={cardId}
            placeholder="Número de la pregunta"
            onChange={(e) => setCardId(e.target.value)}
            prefix={<Text type="secondary">#</Text>}
          />
          <Button icon={<SaveOutlined />} onClick={saveDefaultCard} disabled={!cardId.trim() || cardId.trim() === savedCard}>
            Predeterminar
          </Button>
        </Space.Compact>
        <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 4 }}>
          {status?.servidor ? `${status.servidor} · ` : ''}
          {savedCard ? `Predeterminada: #${savedCard}` : 'Guarda el número para no escribirlo cada vez'}
        </Text>
        <Space style={{ marginTop: 8 }} size={4} wrap>
          <Switch size="small" checked={autoRefresh} onChange={setAutoRefresh} disabled={!status?.configurado} />
          <Text style={{ fontSize: 12 }}>Extraer y recomendar cada</Text>
          <InputNumber size="small" min={1} max={120} value={refreshMinutes} onChange={setRefreshMinutes} style={{ width: 64 }} />
          <Text style={{ fontSize: 12 }}>min</Text>
        </Space>
        <Upload accept=".xlsx,.xls,.csv" showUploadList={false} customRequest={handleUpload} disabled={busy}>
          <Button type="link" size="small" icon={<UploadOutlined />} style={{ paddingLeft: 0, marginTop: 4 }}>
            o subir un Excel/CSV
          </Button>
        </Upload>
        {fetchInfo && (
          <div style={{ marginTop: 4 }}>
            <Text style={{ fontSize: 12 }}>
              {fetchInfo.actividades.length} OTs · {fetchInfo.geocodificadas} ubicadas por dirección · {fetchInfo.sin_coordenadas} sin ubicación
            </Text>
            {fetchInfo.avisos.map((aviso) => (
              <Alert key={aviso} type="warning" message={aviso} showIcon style={{ marginTop: 4, fontSize: 12 }} />
            ))}
          </div>
        )}
      </Card>

      <Card
        size="small"
        title={`Técnicos disponibles hoy (${disponibles.length})`}
        style={{ marginBottom: 12 }}
        extra={<Button size="small" type="link" icon={<SettingOutlined />} onClick={() => setTechModalOpen(true)}>Gestionar</Button>}
      >
        {tecnicosActivos.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {tecnicosActivos.map((t) => {
              const available = disponibles.includes(t.id);
              const partners = tecnicosActivos.filter((o) => o.id !== t.id && disponibles.includes(o.id)
                && o.base_id === t.base_id && (!parejas[o.id] || parejas[o.id] === t.id));
              return (
                <div key={t.id} className="tech-row">
                  <Checkbox
                    checked={available}
                    onChange={(e) => setNoDisponibles((prev) => (e.target.checked
                      ? prev.filter((x) => x !== t.id) : [...prev, t.id]))}
                  >
                    <span className="tech-name">{t.nombre}</span>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {' '}· {sedesById[t.base_id]?.empresa || t.base_id}
                      {t.costo_dia ? ` · ${formatCop(t.costo_dia)}/día` : ''}
                    </Text>
                  </Checkbox>
                  {available && partners.length > 0 && (
                    <Select
                      size="small"
                      allowClear
                      placeholder="Pareja: auto"
                      value={parejas[t.id]}
                      onChange={(v) => setPareja(t.id, v)}
                      options={partners.map((o) => ({ value: o.id, label: o.nombre }))}
                      style={{ width: 120 }}
                    />
                  )}
                </div>
              );
            })}
            {disponibles.length > 1 && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {cuadrillasManuales.length
                  ? `${cuadrillasManuales.length} pareja(s) armadas a mano; el resto sale solo.`
                  : 'Las parejas para OTs de 2 personas se arman solas.'}
              </Text>
            )}
          </div>
        ) : (
          <Text type="secondary">
            Sin técnicos registrados: todo se recomendará a contratistas. Agrégalos en «Gestionar».
          </Text>
        )}
      </Card>

      <Card
        size="small"
        title="Contratistas por OR"
        style={{ marginBottom: 12 }}
        extra={<Button size="small" type="link" onClick={() => setOrModalOpen(true)}>Editar</Button>}
      >
        {Object.keys(orCounts).length ? Object.keys(orCounts).sort().map((name) => {
          const lista = contractorsFor(name);
          return (
            <div key={name} style={{ marginBottom: 6 }}>
              <Text strong style={{ fontSize: 12 }}>{name} ({orCounts[name]}): </Text>
              {lista.length ? lista.map((id) => <Tag key={id}>{empresasById[id]?.nombre || id}</Tag>) : (
                <Tag icon={<WarningOutlined />} color="warning">el más cercano de todos</Tag>
              )}
            </div>
          );
        }) : (
          <Text type="secondary" style={{ fontSize: 12 }}>
            Para cada OR, el contratista más cercano entre los que lo atienden.
          </Text>
        )}
      </Card>

      {services.length > 0 && (
        <Card
          size="small"
          title="Tipos de OT"
          style={{ marginBottom: 12 }}
          extra={<Button size="small" type="link" onClick={() => setTypesModalOpen(true)}>Editar</Button>}
        >
          {services.map((s) => {
            const tipo = otTypeSettings(s, config.tipos_ot);
            return (
              <div key={s} className="ot-type-row">
                <Text>{s} <Text type="secondary">({serviceCounts[s]})</Text></Text>
                <span>
                  <Tag>{tipo.minutos} min</Tag>
                  <Tag color={tipo.personas > 1 ? 'blue' : undefined}>{tipo.personas} {tipo.personas > 1 ? 'personas' : 'persona'}</Tag>
                </span>
              </div>
            );
          })}
        </Card>
      )}

      <Collapse
        size="small"
        style={{ marginBottom: 12 }}
        items={[{
          key: 'ajustes',
          label: 'Ajustes',
          forceRender: true,
          children: (
            <>
              <Text strong style={{ fontSize: 12 }}>Asignar a</Text>
              <Segmented
                block
                size="small"
                value={modo}
                onChange={setModo}
                style={{ margin: '4px 0 12px' }}
                options={[
                  { value: 'automatico', label: 'Automático' },
                  { value: 'inhouse', label: 'Solo técnicos' },
                  { value: 'contratistas', label: 'Solo contratistas' },
                ]}
              />
              <Text strong style={{ fontSize: 12 }}>Filtrar por OR</Text>
              <Select
                mode="multiple"
                allowClear
                value={orFilter}
                onChange={setOrFilter}
                style={{ width: '100%', margin: '4px 0 12px' }}
                placeholder="Todos los OR"
                options={Object.entries(orCounts).map(([name, count]) => ({ value: name, label: `${name} (${count})` }))}
              />
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
                  <Form.Item
                    label="Radio técnicos (km)"
                    name="radio_inhouse_km"
                    tooltip="En modo automático, las OTs más lejos que esto de la base de los técnicos van a contratistas"
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={1} max={500} />
                  </Form.Item>
                  <Form.Item label="Velocidad (km/h)" name="velocidad_promedio_kmh" rules={[{ required: true }]}>
                    <InputNumber min={5} max={120} />
                  </Form.Item>
                  <Form.Item
                    label="Factor vial"
                    name="factor_vial"
                    tooltip="Las distancias son en línea recta; este factor las aproxima a distancia por carretera"
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={1} max={3} step={0.1} />
                  </Form.Item>
                  <Form.Item label="Máx. OTs por ruta" name="capacidad_maxima_actividades">
                    <InputNumber min={1} placeholder="Sin límite" />
                  </Form.Item>
                  <Form.Item label="Volver a la base" name="incluir_retorno" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Space>
              </Form>
            </>
          ),
        }]}
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
        orsPresentes={Object.keys(orCounts)}
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
};

export default AssignmentPanel;

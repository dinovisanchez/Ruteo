import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Card, Button, Input, Space, Switch, InputNumber, Alert, Select, Segmented, Checkbox, Tag, Typography,
  Form, TimePicker, Collapse, Divider, Empty, notification, message,
} from 'antd';
import {
  CloudDownloadOutlined, FileExcelOutlined, TeamOutlined, ApartmentOutlined, PlayCircleOutlined,
  WarningOutlined, SettingOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import TechniciansModal from './TechniciansModal';
import OrContractorsModal from './OrContractorsModal';
import {
  getMetabaseStatus, fetchMetabaseOTs, getCatalog, getAssignmentConfig,
} from '../services/api';
import { defaultServiceMinutes } from '../services/serviceTimes';

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

const AssignmentPanel = ({ uploadedActivities, ots, onOtsLoaded, onAssign, loading }) => {
  const [form] = Form.useForm();
  const [status, setStatus] = useState(null);
  const [cardId, setCardId] = useState('');
  const [fetching, setFetching] = useState(false);
  const [fetchInfo, setFetchInfo] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshMinutes, setRefreshMinutes] = useState(5);
  const [catalog, setCatalog] = useState({ sedes: [], empresas: [], avisos: [] });
  const [config, setConfig] = useState({ tecnicos: [], or_contratistas: {} });
  const [orFilter, setOrFilter] = useState([]);
  const [modo, setModo] = useState('inhouse');
  const [selectedTecnicos, setSelectedTecnicos] = useState([]);
  const [serviceTimes, setServiceTimes] = useState({});
  const [techModalOpen, setTechModalOpen] = useState(false);
  const [orModalOpen, setOrModalOpen] = useState(false);
  const knownRef = useRef(null);

  useEffect(() => {
    getMetabaseStatus()
      .then((s) => {
        setStatus(s);
        if (s.card_id) setCardId(s.card_id);
      })
      .catch(() => setStatus({ configurado: false }));
    getCatalog().then(setCatalog).catch((e) => message.error(`No se pudo leer el catálogo: ${e.message}`));
    getAssignmentConfig().then(setConfig).catch((e) => message.error(`No se pudo leer la configuración: ${e.message}`));
  }, []);

  const loadOts = useCallback(async (silent = false) => {
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
      onOtsLoaded(data.actividades, nuevas, `Metabase · pregunta ${data.card_id}`);
      if (nuevas.size && silent) {
        notification.info({
          message: `Llegaron ${nuevas.size} OTs nuevas`,
          description: 'Revisa el filtro de OR y vuelve a asignar.',
          placement: 'bottomRight',
        });
      } else if (!silent) {
        message.success(`${data.actividades.length} OTs traídas de Metabase${nuevas.size ? ` (${nuevas.size} nuevas)` : ''}`);
      }
    } catch (error) {
      if (!silent) message.error(error.message, 8);
    } finally {
      setFetching(false);
    }
  }, [cardId, onOtsLoaded]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const id = setInterval(() => loadOts(true), Math.max(1, refreshMinutes) * 60 * 1000);
    return () => clearInterval(id);
  }, [autoRefresh, refreshMinutes, loadOts]);

  const handleUseUploaded = () => {
    setFetchInfo(null);
    onOtsLoaded(uploadedActivities, new Set(), 'Archivo cargado');
  };

  const orCounts = useMemo(() => {
    const counts = {};
    (ots || []).forEach((a) => { counts[a.or_operador] = (counts[a.or_operador] || 0) + 1; });
    return counts;
  }, [ots]);

  const services = useMemo(() => [...new Set((ots || []).map((a) => a.servicio))].sort(), [ots]);

  useEffect(() => {
    setServiceTimes((prev) => {
      const next = {};
      services.forEach((s) => { next[s] = prev[s] || defaultServiceMinutes(s); });
      return next;
    });
  }, [services]);

  const tecnicosActivos = config.tecnicos.filter((t) => t.activo !== false);
  const sedesById = useMemo(() => Object.fromEntries(catalog.sedes.map((s) => [s.id, s])), [catalog]);
  const empresasById = useMemo(() => Object.fromEntries(catalog.empresas.map((e) => [e.id, e])), [catalog]);

  // Drop selections of technicians that were removed
  useEffect(() => {
    setSelectedTecnicos((prev) => prev.filter((id) => config.tecnicos.some((t) => t.id === id)));
  }, [config]);

  const contractorsFor = (orName) => {
    const key = Object.keys(config.or_contratistas).find((k) => k.toLowerCase() === orName.toLowerCase());
    return key ? config.or_contratistas[key] : [];
  };

  const orsShown = orFilter.length ? orFilter : Object.keys(orCounts);
  const filteredCount = (ots || []).filter((a) => !orFilter.length || orFilter.includes(a.or_operador)).length;
  const canAssign = filteredCount > 0 && !loading && (modo === 'contratistas' || selectedTecnicos.length > 0);

  const handleAssign = async () => {
    const values = await form.validateFields();
    onAssign({
      modo,
      actividades: ots,
      or_filtro: orFilter,
      tecnicos_ids: modo === 'inhouse' ? selectedTecnicos : [],
      jornada: {
        horario_inicio: values.horario_inicio.format('HH:mm:ss'),
        horas_laborales: values.horas_laborales,
        velocidad_promedio_kmh: values.velocidad_promedio_kmh,
        factor_vial: values.factor_vial,
        capacidad_maxima_actividades: values.capacidad_maxima_actividades || null,
        incluir_retorno: values.incluir_retorno,
        tiempos_servicio: Object.entries(serviceTimes).map(([servicio, duracion_minutos]) => ({ servicio, duracion_minutos })),
      },
    });
  };

  return (
    <>
      <Card size="small" title={<span><CloudDownloadOutlined /> OTs</span>} style={{ marginBottom: 12 }}>
        {status && !status.configurado && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 8 }}
            message="Metabase no está configurado"
            description="Completa METABASE_URL y METABASE_API_KEY en backend/.env y reinicia el backend."
          />
        )}
        {status?.configurado && (
          <Text type="secondary" style={{ fontSize: 12 }}>Metabase: {status.servidor}</Text>
        )}
        <Space.Compact style={{ width: '100%', marginTop: 8 }}>
          <Input
            value={cardId}
            placeholder="Id de la pregunta"
            onChange={(e) => setCardId(e.target.value)}
            style={{ width: 130 }}
          />
          <Button
            type="primary"
            icon={<CloudDownloadOutlined />}
            loading={fetching}
            disabled={!status?.configurado}
            onClick={() => loadOts(false)}
          >
            Traer OTs
          </Button>
        </Space.Compact>
        <Space style={{ marginTop: 8 }} size={4} wrap>
          <Switch size="small" checked={autoRefresh} onChange={setAutoRefresh} disabled={!status?.configurado} />
          <Text style={{ fontSize: 12 }}>Actualizar cada</Text>
          <InputNumber size="small" min={1} max={120} value={refreshMinutes} onChange={setRefreshMinutes} style={{ width: 64 }} />
          <Text style={{ fontSize: 12 }}>min</Text>
        </Space>
        {uploadedActivities?.length > 0 && (
          <Button icon={<FileExcelOutlined />} size="small" style={{ marginTop: 8 }} block onClick={handleUseUploaded}>
            Usar archivo cargado ({uploadedActivities.length} OTs)
          </Button>
        )}
        {fetchInfo && (
          <div style={{ marginTop: 8 }}>
            <Text style={{ fontSize: 12 }}>
              {fetchInfo.actividades.length} OTs · {fetchInfo.geocodificadas} ubicadas por dirección · {fetchInfo.sin_coordenadas} sin ubicación
            </Text>
            {fetchInfo.avisos.map((aviso) => (
              <Alert key={aviso} type="warning" message={aviso} showIcon style={{ marginTop: 4, fontSize: 12 }} />
            ))}
          </div>
        )}
      </Card>

      <Card size="small" title="Filtrar por OR" style={{ marginBottom: 12 }}>
        {ots?.length ? (
          <>
            <Select
              mode="multiple"
              allowClear
              value={orFilter}
              onChange={setOrFilter}
              style={{ width: '100%' }}
              placeholder="Todos los OR"
              options={Object.entries(orCounts).map(([name, count]) => ({ value: name, label: `${name} (${count})` }))}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>{filteredCount} OTs a asignar</Text>
          </>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Trae OTs de Metabase o usa un archivo" />
        )}
      </Card>

      <Card size="small" title="¿Quién atiende?" style={{ marginBottom: 12 }}>
        <Segmented
          block
          value={modo}
          onChange={setModo}
          options={[
            { value: 'inhouse', label: 'Técnicos in-house', icon: <TeamOutlined /> },
            { value: 'contratistas', label: 'Contratistas', icon: <ApartmentOutlined /> },
          ]}
        />

        {modo === 'inhouse' ? (
          <div style={{ marginTop: 12 }}>
            {tecnicosActivos.length ? (
              <Checkbox.Group value={selectedTecnicos} onChange={setSelectedTecnicos} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {tecnicosActivos.map((t) => (
                  <Checkbox key={t.id} value={t.id}>
                    {t.nombre} <Text type="secondary" style={{ fontSize: 12 }}>· {sedesById[t.base_id]?.empresa || t.base_id}</Text>
                  </Checkbox>
                ))}
              </Checkbox.Group>
            ) : (
              <Alert type="info" showIcon message="Aún no hay técnicos registrados" />
            )}
            <Button size="small" icon={<SettingOutlined />} style={{ marginTop: 8 }} onClick={() => setTechModalOpen(true)}>
              Gestionar técnicos
            </Button>
          </div>
        ) : (
          <div style={{ marginTop: 12 }}>
            {orsShown.map((name) => {
              const lista = contractorsFor(name);
              return (
                <div key={name} style={{ marginBottom: 6 }}>
                  <Text strong style={{ fontSize: 12 }}>{name}: </Text>
                  {lista.length ? lista.map((id) => <Tag key={id}>{empresasById[id]?.nombre || id}</Tag>) : (
                    <Tag icon={<WarningOutlined />} color="warning">el más cercano de todos</Tag>
                  )}
                </div>
              );
            })}
            <Button size="small" icon={<SettingOutlined />} style={{ marginTop: 4 }} onClick={() => setOrModalOpen(true)}>
              Contratistas por OR
            </Button>
          </div>
        )}
      </Card>

      <Collapse
        size="small"
        style={{ marginBottom: 12 }}
        items={[{
          key: 'jornada',
          label: 'Jornada y tiempos de servicio',
          forceRender: true,
          children: (
            <Form
              form={form}
              layout="vertical"
              size="small"
              initialValues={{
                horario_inicio: dayjs('08:00', 'HH:mm'),
                horas_laborales: 8,
                velocidad_promedio_kmh: 30,
                factor_vial: 1.3,
                capacidad_maxima_actividades: null,
                incluir_retorno: true,
              }}
            >
              <Space wrap>
                <Form.Item label="Inicio" name="horario_inicio" rules={[{ required: true }]}>
                  <TimePicker format="HH:mm" />
                </Form.Item>
                <Form.Item label="Horas laborales" name="horas_laborales" rules={[{ required: true }]}>
                  <InputNumber min={1} max={24} step={0.5} />
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
              {services.length > 0 && <Divider plain style={{ margin: '4px 0 8px' }}>Minutos por tipo de OT</Divider>}
              {services.map((s) => (
                <Space key={s} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Tag color="blue">{s}</Tag>
                  <Space size={4}>
                    <InputNumber
                      size="small"
                      min={5}
                      max={600}
                      value={serviceTimes[s]}
                      onChange={(v) => setServiceTimes((prev) => ({ ...prev, [s]: v || defaultServiceMinutes(s) }))}
                      style={{ width: 70 }}
                    />
                    <Text style={{ fontSize: 12 }}>min</Text>
                  </Space>
                </Space>
              ))}
            </Form>
          ),
        }]}
      />

      <Button type="primary" size="large" block icon={<PlayCircleOutlined />} disabled={!canAssign} loading={loading} onClick={handleAssign}>
        Asignar {filteredCount ? `${filteredCount} OTs` : ''}
      </Button>
      {modo === 'inhouse' && filteredCount > 0 && !selectedTecnicos.length && (
        <Text type="secondary" style={{ fontSize: 12 }}>Selecciona los técnicos que salen hoy</Text>
      )}

      <TechniciansModal
        open={techModalOpen}
        config={config}
        sedes={catalog.sedes}
        onClose={() => setTechModalOpen(false)}
        onSaved={(saved) => { setConfig(saved); setTechModalOpen(false); }}
      />
      <OrContractorsModal
        open={orModalOpen}
        config={config}
        empresas={catalog.empresas}
        orsPresentes={Object.keys(orCounts)}
        onClose={() => setOrModalOpen(false)}
        onSaved={(saved) => { setConfig(saved); setOrModalOpen(false); }}
      />
    </>
  );
};

export default AssignmentPanel;

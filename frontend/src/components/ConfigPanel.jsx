import React, { useState, useEffect } from 'react';
import { Card, Form, Input, InputNumber, TimePicker, Switch, Button, Space, Divider, Alert, Tag } from 'antd';
import { SettingOutlined, PlayCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

const ConfigPanel = ({ activities, onOptimize, loading }) => {
  const [form] = Form.useForm();
  const [serviceTimes, setServiceTimes] = useState([]);
  const [estimatedCrews, setEstimatedCrews] = useState(null);

  // Extract unique service types from activities
  useEffect(() => {
    if (activities && activities.length > 0) {
      const uniqueServices = [...new Set(activities.map(act => act.servicio))];
      const times = uniqueServices.map(servicio => ({
        servicio,
        duracion_minutos: getDefaultServiceTime(servicio),
      }));
      setServiceTimes(times);
    }
  }, [activities]);

  const getDefaultServiceTime = (servicio) => {
    const defaults = {
      'instalacion': 60,
      'mantenimiento': 45,
      'reparacion': 90,
      'inspeccion': 30,
      'retiro': 40,
    };
    return defaults[servicio.toLowerCase()] || 60;
  };

  const handleOptimize = async () => {
    try {
      const values = await form.validateFields();

      // Build configuration object
      const configuration = {
        horario_inicio: values.horario_inicio.format('HH:mm:ss'),
        horario_fin: values.horario_fin.format('HH:mm:ss'),
        horas_laborales: values.horas_laborales,
        velocidad_promedio_kmh: values.velocidad_promedio_kmh,
        capacidad_maxima_actividades: values.capacidad_maxima_actividades || null,
        punto_partida: {
          latitude: parseFloat(values.punto_partida_lat),
          longitude: parseFloat(values.punto_partida_lon),
        },
        incluir_retorno: values.incluir_retorno,
        tiempos_servicio: serviceTimes,
      };

      // Build activity lot
      const activityLot = {
        nombre_lote: values.nombre_lote,
        fecha_creacion: new Date().toISOString(),
        actividades: activities,
        configuracion: configuration,
      };

      // Call optimization
      if (onOptimize) {
        onOptimize(activityLot);
      }
    } catch (error) {
      console.error('Form validation error:', error);
    }
  };

  const updateServiceTime = (servicio, minutes) => {
    setServiceTimes(prev =>
      prev.map(st =>
        st.servicio === servicio
          ? { ...st, duracion_minutos: minutes }
          : st
      )
    );
  };

  const canOptimize = activities && activities.length > 0 && !loading;

  return (
    <Card
      title={
        <span>
          <SettingOutlined /> 2. Configuración y Optimización
        </span>
      }
      style={{ marginBottom: 16 }}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          nombre_lote: `Lote ${new Date().toLocaleDateString()}`,
          horario_inicio: dayjs('08:00', 'HH:mm'),
          horario_fin: dayjs('17:00', 'HH:mm'),
          horas_laborales: 8,
          velocidad_promedio_kmh: 30,
          capacidad_maxima_actividades: 15,
          punto_partida_lat: 4.6097,
          punto_partida_lon: -74.0817,
          incluir_retorno: true,
        }}
      >
        <Form.Item
          label="Nombre del Lote"
          name="nombre_lote"
          rules={[{ required: true, message: 'Ingresa un nombre para el lote' }]}
        >
          <Input placeholder="Ej: Lote Bogotá Norte" />
        </Form.Item>

        <Divider>Horario Laboral</Divider>

        <Space style={{ width: '100%' }} size="large">
          <Form.Item
            label="Hora de Inicio"
            name="horario_inicio"
            rules={[{ required: true }]}
          >
            <TimePicker format="HH:mm" />
          </Form.Item>

          <Form.Item
            label="Hora de Fin"
            name="horario_fin"
            rules={[{ required: true }]}
          >
            <TimePicker format="HH:mm" />
          </Form.Item>

          <Form.Item
            label="Horas Laborales"
            name="horas_laborales"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={24} step={0.5} addonAfter="horas" />
          </Form.Item>
        </Space>

        <Divider>Parámetros de Viaje</Divider>

        <Form.Item
          label="Velocidad Promedio"
          name="velocidad_promedio_kmh"
          rules={[{ required: true }]}
          tooltip="Velocidad promedio de desplazamiento en ciudad"
        >
          <InputNumber min={10} max={100} addonAfter="km/h" style={{ width: 200 }} />
        </Form.Item>

        <Form.Item
          label="Capacidad Máxima de Actividades por Cuadrilla"
          name="capacidad_maxima_actividades"
          tooltip="Número máximo de actividades que puede realizar una cuadrilla en un día (opcional)"
        >
          <InputNumber min={1} max={50} style={{ width: 200 }} />
        </Form.Item>

        <Divider>Punto de Partida</Divider>

        <Alert
          message="Coordenadas GPS del punto de inicio/retorno de las cuadrillas"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Space style={{ width: '100%' }}>
          <Form.Item
            label="Latitud"
            name="punto_partida_lat"
            rules={[
              { required: true },
              { type: 'number', min: -90, max: 90, message: 'Latitud entre -90 y 90' },
            ]}
          >
            <InputNumber step={0.0001} style={{ width: 150 }} />
          </Form.Item>

          <Form.Item
            label="Longitud"
            name="punto_partida_lon"
            rules={[
              { required: true },
              { type: 'number', min: -180, max: 180, message: 'Longitud entre -180 y 180' },
            ]}
          >
            <InputNumber step={0.0001} style={{ width: 150 }} />
          </Form.Item>
        </Space>

        <Form.Item
          label="Incluir Retorno al Punto de Partida"
          name="incluir_retorno"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        {serviceTimes.length > 0 && (
          <>
            <Divider>Tiempos de Servicio</Divider>

            <Alert
              message="Define la duración estimada de cada tipo de servicio"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />

            <Space direction="vertical" style={{ width: '100%' }}>
              {serviceTimes.map(st => (
                <div key={st.servicio} style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <Tag color="blue" style={{ minWidth: 120, textAlign: 'center' }}>
                    {st.servicio}
                  </Tag>
                  <InputNumber
                    min={5}
                    max={300}
                    value={st.duracion_minutos}
                    onChange={(val) => updateServiceTime(st.servicio, val)}
                    addonAfter="min"
                    style={{ width: 150 }}
                  />
                </div>
              ))}
            </Space>
          </>
        )}

        <Divider />

        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          onClick={handleOptimize}
          disabled={!canOptimize}
          loading={loading}
          block
        >
          {loading ? 'Optimizando...' : 'Optimizar Rutas'}
        </Button>

        {!canOptimize && !loading && (
          <Alert
            message="Primero debes cargar un archivo de actividades"
            type="warning"
            showIcon
            style={{ marginTop: 16 }}
          />
        )}
      </Form>
    </Card>
  );
};

export default ConfigPanel;

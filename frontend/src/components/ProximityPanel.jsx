import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  InputNumber,
  Select,
  Button,
  Space,
  Divider,
  Typography,
  Tooltip,
  Alert,
  Statistic,
} from 'antd';
import {
  ClusterOutlined,
  InfoCircleOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;

function ProximityPanel({ activities, onAnalyze, loading }) {
  const [form] = Form.useForm();
  const [canExecute, setCanExecute] = useState(false);

  useEffect(() => {
    setCanExecute(activities && activities.length > 0);
  }, [activities]);

  const handleSubmit = (values) => {
    const { max_distance_km, method } = values;
    onAnalyze(max_distance_km, method);
  };

  return (
    <Card
      title={
        <Space>
          <ClusterOutlined />
          <span>Agrupamiento por Proximidad</span>
        </Space>
      }
    >
      <Alert
        message="Agrupa actividades cercanas y genera rutas optimizadas"
        description="Solo carga tu archivo y selecciona la distancia máxima. El sistema identificará los lotes cercanos y generará las rutas automáticamente."
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      {activities && (
        <div style={{ marginBottom: 16 }}>
          <Statistic
            title="Actividades Cargadas"
            value={activities.length}
            prefix={<EnvironmentOutlined />}
            valueStyle={{ color: '#3f8600' }}
          />
        </div>
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          max_distance_km: 20.0,
          method: 'proximity',
        }}
        disabled={loading}
      >

        <Form.Item
          name="method"
          label={
            <Space>
              <span>Método de Agrupamiento</span>
              <Tooltip title="Proximity: agrupa por distancia máxima. K-Means: distribución balanceada">
                <InfoCircleOutlined style={{ color: '#1890ff' }} />
              </Tooltip>
            </Space>
          }
        >
          <Select>
            <Option value="proximity">
              <div>
                <strong>Proximidad</strong>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Agrupa actividades cercanas (distancia máxima)
                </Text>
              </div>
            </Option>
            <Option value="kmeans">
              <div>
                <strong>K-Means</strong>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Distribución balanceada de actividades
                </Text>
              </div>
            </Option>
          </Select>
        </Form.Item>

        <Form.Item
          name="max_distance_km"
          label={
            <Space>
              <span>Distancia Máxima (km)</span>
              <Tooltip title="Distancia máxima para considerar actividades 'cercanas'">
                <InfoCircleOutlined style={{ color: '#1890ff' }} />
              </Tooltip>
            </Space>
          }
          rules={[
            { required: true, message: 'La distancia es requerida' },
            { type: 'number', min: 1, max: 100, message: 'Entre 1 y 100 km' },
          ]}
        >
          <InputNumber
            style={{ width: '100%' }}
            min={1}
            max={100}
            step={5}
            addonAfter="km"
            placeholder="Ej: 20"
          />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0 }}>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            disabled={!canExecute}
            block
            size="large"
            icon={<ClusterOutlined />}
          >
            Generar Lotes y Rutas
          </Button>
        </Form.Item>

        {!canExecute && (
          <Alert
            message="Primero carga un archivo con actividades"
            type="warning"
            showIcon
            style={{ marginTop: 12 }}
          />
        )}

        <Divider />

        <div style={{ marginTop: 16 }}>
          <Title level={5}>¿Qué hace esto?</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            • Identifica grupos de actividades cercanas entre sí
            <br />
            • Genera un lote por cada grupo identificado
            <br />
            • Crea una ruta optimizada para cada lote
            <br />• No requiere configurar horarios ni tiempos de servicio
          </Text>
        </div>
      </Form>
    </Card>
  );
}

export default ProximityPanel;

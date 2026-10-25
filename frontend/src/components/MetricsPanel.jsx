import React from 'react';
import { Card, Row, Col, Statistic, Tag, Empty, Progress } from 'antd';
import {
  DashboardOutlined,
  TeamOutlined,
  CarOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons';

const MetricsPanel = ({ optimizationResult }) => {
  if (!optimizationResult) {
    return (
      <Card
        title={
          <span>
            <DashboardOutlined /> Métricas de Optimización
          </span>
        }
        style={{ marginBottom: 16 }}
      >
        <Empty description="Optimiza las rutas para ver las métricas" />
      </Card>
    );
  }

  const { metricas, viable_en_un_dia } = optimizationResult;

  return (
    <Card
      title={
        <span>
          <DashboardOutlined /> Métricas de Optimización
        </span>
      }
      style={{ marginBottom: 16 }}
      extra={
        viable_en_un_dia ? (
          <Tag icon={<CheckCircleOutlined />} color="success" style={{ fontSize: 14, padding: '4px 12px' }}>
            Viable en un día
          </Tag>
        ) : (
          <Tag icon={<CloseCircleOutlined />} color="error" style={{ fontSize: 14, padding: '4px 12px' }}>
            No viable en un día
          </Tag>
        )
      }
    >
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title="Total de Actividades"
            value={metricas.total_activities}
            prefix={<EnvironmentOutlined />}
            valueStyle={{ color: '#1890ff' }}
          />
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Statistic
            title="Cuadrillas Necesarias"
            value={metricas.total_crews}
            prefix={<TeamOutlined />}
            valueStyle={{ color: '#52c41a' }}
          />
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Statistic
            title="Distancia Total"
            value={metricas.total_distance_km}
            suffix="km"
            precision={2}
            prefix={<CarOutlined />}
            valueStyle={{ color: '#faad14' }}
          />
        </Col>

        <Col xs={24} sm={12} md={6}>
          <Statistic
            title="Distancia Promedio/Cuadrilla"
            value={metricas.avg_distance_per_crew}
            suffix="km"
            precision={2}
            prefix={<CarOutlined />}
            valueStyle={{ color: '#fa8c16' }}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12}>
          <Card size="small" title="Utilización Promedio">
            <Progress
              percent={metricas.avg_utilization_percent}
              status={metricas.avg_utilization_percent >= 80 ? 'success' : 'normal'}
              format={(percent) => `${percent.toFixed(1)}%`}
            />
            <p style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
              Porcentaje de tiempo efectivamente utilizado (trabajo + viaje)
            </p>
          </Card>
        </Col>

        <Col xs={24} sm={12}>
          <Card size="small" title="Tiempo de Ruta">
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="Máximo"
                  value={metricas.max_route_time_minutes}
                  suffix="min"
                  prefix={<ClockCircleOutlined />}
                  valueStyle={{ fontSize: 20 }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="Mínimo"
                  value={metricas.min_route_time_minutes}
                  suffix="min"
                  prefix={<ClockCircleOutlined />}
                  valueStyle={{ fontSize: 20 }}
                />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12}>
          <Card size="small" title="Actividades por Cuadrilla">
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="Máximo"
                  value={metricas.max_activities_per_crew}
                  valueStyle={{ fontSize: 20 }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="Mínimo"
                  value={metricas.min_activities_per_crew}
                  valueStyle={{ fontSize: 20 }}
                />
              </Col>
            </Row>
          </Card>
        </Col>

        <Col xs={24} sm={12}>
          <Card size="small" title="Estado de Viabilidad">
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              {metricas.all_routes_viable ? (
                <>
                  <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                  <p style={{ marginTop: 16, fontSize: 16, fontWeight: 500 }}>
                    Todas las rutas son viables
                  </p>
                  <p style={{ color: '#999', fontSize: 12 }}>
                    Todas las cuadrillas pueden completar sus rutas dentro del horario laboral
                  </p>
                </>
              ) : (
                <>
                  <CloseCircleOutlined style={{ fontSize: 48, color: '#ff4d4f' }} />
                  <p style={{ marginTop: 16, fontSize: 16, fontWeight: 500 }}>
                    Algunas rutas no son viables
                  </p>
                  <p style={{ color: '#999', fontSize: 12 }}>
                    Algunas cuadrillas exceden el horario laboral configurado
                  </p>
                </>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      <Card size="small" title="Resumen" style={{ marginTop: 16 }}>
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <p style={{ margin: '8px 0' }}>
              <strong>Lote:</strong> {optimizationResult.nombre_lote}
            </p>
            <p style={{ margin: '8px 0' }}>
              <strong>Fecha de optimización:</strong>{' '}
              {new Date(optimizationResult.fecha_optimizacion).toLocaleString('es-ES')}
            </p>
            <p style={{ margin: '8px 0' }}>
              <strong>Eficiencia:</strong>{' '}
              {metricas.total_crews > 0
                ? `${(metricas.total_activities / metricas.total_crews).toFixed(1)} actividades/cuadrilla`
                : 'N/A'}
            </p>
          </Col>
        </Row>
      </Card>
    </Card>
  );
};

export default MetricsPanel;

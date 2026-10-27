import React, { useMemo } from 'react';
import { Card, Table, Tooltip, Typography } from 'antd';
import dayjs from 'dayjs';
import { otTypeSettings } from '../services/otTypes';

const { Text } = Typography;

const ISO_DATE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

// Metabase sends dates as ISO strings; show them as local date and time
export const formatExtra = (value) => {
  if (value === null || value === undefined || value === '') return '';
  if (typeof value === 'string' && ISO_DATE.test(value)) return dayjs(value).format('YYYY-MM-DD HH:mm');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const columnFilters = (ots, getter) => [...new Set(ots.map(getter))]
  .filter(Boolean)
  .sort()
  .map((v) => ({ text: v, value: v }));

const OtsTable = ({
  ots, nuevas, mapeo, config, title, enPlan = null, enPlanTitulo = 'En el plan',
}) => {
  // Extra columns: everything Metabase sent that is not already shown as a main column
  const extraKeys = useMemo(() => {
    const mapped = new Set(Object.values(mapeo || {}));
    const keys = [];
    (ots || []).forEach((a) => Object.keys(a.extras || {}).forEach((k) => {
      if (!mapped.has(k) && !keys.includes(k)) keys.push(k);
    }));
    return keys;
  }, [ots, mapeo]);

  if (!ots?.length) return null;

  const columns = [
    {
      title: 'OT',
      dataIndex: 'codigo_bia',
      fixed: 'left',
      width: 150,
      sorter: (a, b) => a.codigo_bia.localeCompare(b.codigo_bia),
      render: (codigo) => (
        <span>
          <Text strong>{codigo}</Text>
          {nuevas?.has(codigo) && <span className="new-badge">nueva</span>}
        </span>
      ),
    },
    {
      title: 'Situación',
      width: 120,
      filters: [{ text: 'Ya asignada', value: 'asignada' }, { text: 'Por asignar', value: 'pendiente' }],
      onFilter: (value, a) => a.situacion === value,
      render: (_, a) => (
        <span className="state">
          <span className="dot" style={{ background: a.situacion === 'asignada' ? '#34C759' : '#FF9500' }} />
          {a.situacion === 'asignada' ? 'Asignada' : 'Por asignar'}
        </span>
      ),
    },
    // With every loaded OT: whether it is in the plan of the day and, if not, why
    ...(enPlan ? [{
      title: enPlanTitulo,
      width: 300,
      filters: [{ text: 'En el plan', value: 'si' }, { text: 'Fuera del plan', value: 'no' }],
      onFilter: (value, a) => (value === 'si') === Boolean(enPlan[a.codigo_bia]?.dentro),
      sorter: (a, b) => Number(Boolean(enPlan[b.codigo_bia]?.dentro)) - Number(Boolean(enPlan[a.codigo_bia]?.dentro)),
      render: (_, a) => (
        <span className="state">
          <span className="dot" style={{ background: enPlan[a.codigo_bia]?.dentro ? '#007AFF' : '#C7C7CC' }} />
          {enPlan[a.codigo_bia]?.texto}
        </span>
      ),
    }] : []),
    {
      title: 'Fecha visita',
      dataIndex: 'fecha_visita',
      width: 120,
      sorter: (a, b) => (a.fecha_visita || '~').localeCompare(b.fecha_visita || '~'),
      filters: columnFilters(ots, (a) => a.fecha_visita),
      onFilter: (value, a) => a.fecha_visita === value,
      render: (fecha) => (fecha ? dayjs(fecha).format('ddd D MMM') : ''),
    },
    {
      title: 'Asignada a',
      width: 220,
      ellipsis: true,
      render: (_, a) => [a.asignado_a, a.contratista_asignado].filter(Boolean).join(' · '),
    },
    {
      title: 'Creada por',
      width: 190,
      ellipsis: true,
      sorter: (a, b) => (a.creado_por || '~').localeCompare(b.creado_por || '~'),
      filters: columnFilters(ots, (a) => a.creado_por),
      onFilter: (value, a) => a.creado_por === value,
      render: (_, a) => [a.creado_por, a.fecha_creacion && dayjs(a.fecha_creacion).format('D MMM')].filter(Boolean).join(' · '),
    },
    {
      title: 'OR',
      dataIndex: 'or_operador',
      width: 110,
      filters: columnFilters(ots, (a) => a.or_operador),
      onFilter: (value, a) => a.or_operador === value,
    },
    {
      title: 'Tipo de OT',
      dataIndex: 'servicio',
      width: 190,
      filters: columnFilters(ots, (a) => a.servicio),
      onFilter: (value, a) => a.servicio === value,
    },
    {
      title: 'Personas',
      width: 90,
      render: (_, a) => {
        return otTypeSettings(a.servicio, config?.tipos_ot).personas;
      },
    },
    { title: 'Cliente', dataIndex: 'nombre', width: 200, ellipsis: true },
    { title: 'Ciudad', dataIndex: 'ciudad', width: 130 },
    { title: 'Dirección', dataIndex: 'direccion', width: 240, ellipsis: true },
    {
      title: 'Ubicación',
      width: 120,
      render: (_, a) => {
        if (!a.coordinates) return <span className="warn-text">Sin ubicación</span>;
        if (a.coordenadas_aproximadas) {
          return (
            <Tooltip title="Geocodificada a partir de la dirección o el municipio">
              <span>Aproximada</span>
            </Tooltip>
          );
        }
        return 'GPS';
      },
    },
    ...extraKeys.map((key) => ({
      title: key,
      key: `extra:${key}`,
      width: 160,
      ellipsis: true,
      render: (_, a) => formatExtra(a.extras?.[key]),
    })),
  ];

  return (
    <Card title={title || `OTs (${ots.length})`} style={{ marginBottom: 16 }}>
      <Table
        rowKey="codigo_bia"
        size="small"
        columns={columns}
        dataSource={ots}
        scroll={{ x: 'max-content' }}
        pagination={{ pageSize: 20, hideOnSinglePage: true, showSizeChanger: false }}
      />
    </Card>
  );
};

export default OtsTable;

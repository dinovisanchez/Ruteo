import React, { useMemo } from 'react';
import { Card, Table, Tag, Tooltip, Typography } from 'antd';
import { EnvironmentOutlined, WarningOutlined } from '@ant-design/icons';
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

const OtsTable = ({ ots, nuevas, mapeo, config, title }) => {
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
          {nuevas?.has(codigo) && <Tag color="green" style={{ marginLeft: 6 }}>Nueva</Tag>}
        </span>
      ),
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
        const personas = otTypeSettings(a.servicio, config?.tipos_ot).personas;
        return <Tag color={personas > 1 ? 'blue' : undefined}>{personas}</Tag>;
      },
    },
    { title: 'Cliente', dataIndex: 'nombre', width: 200, ellipsis: true },
    { title: 'Ciudad', dataIndex: 'ciudad', width: 130 },
    { title: 'Dirección', dataIndex: 'direccion', width: 240, ellipsis: true },
    {
      title: 'Ubicación',
      width: 120,
      render: (_, a) => {
        if (!a.coordinates) return <Tag icon={<WarningOutlined />} color="error">Sin ubicación</Tag>;
        if (a.coordenadas_aproximadas) {
          return (
            <Tooltip title="Geocodificada a partir de la dirección o el municipio">
              <Tag icon={<EnvironmentOutlined />} color="warning">Aproximada</Tag>
            </Tooltip>
          );
        }
        return <Tag icon={<EnvironmentOutlined />} color="success">GPS</Tag>;
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

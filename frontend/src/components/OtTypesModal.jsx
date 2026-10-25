import React, { useEffect, useState } from 'react';
import { Modal, Table, InputNumber, Typography, Tag, message } from 'antd';
import { saveAssignmentConfig } from '../services/api';
import { otTypeSettings } from '../services/otTypes';

const { Text } = Typography;

const OtTypesModal = ({ open, config, otCounts, onClose, onSaved }) => {
  const [rows, setRows] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const saved = config?.tipos_ot || {};
    const names = [...new Set([...Object.keys(otCounts), ...Object.keys(saved)])].sort((a, b) => a.localeCompare(b));
    setRows(names.map((nombre) => ({ nombre, ...otTypeSettings(nombre, saved) })));
  }, [open, config, otCounts]);

  const update = (nombre, field, value) => {
    setRows((prev) => prev.map((r) => (r.nombre === nombre ? { ...r, [field]: value } : r)));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const tiposOt = Object.fromEntries(rows.map((r) => [r.nombre, { minutos: r.minutos || 60, personas: r.personas || 1 }]));
      const saved = await saveAssignmentConfig({ ...config, tipos_ot: tiposOt });
      message.success('Tipos de OT guardados');
      onSaved(saved);
    } catch (error) {
      message.error(`No se pudieron guardar los tipos de OT: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    {
      title: 'Tipo de OT',
      dataIndex: 'nombre',
      render: (nombre) => (
        <span>
          <Text strong>{nombre}</Text>
          {otCounts[nombre] ? <Tag style={{ marginLeft: 8 }}>{otCounts[nombre]} OTs</Tag> : null}
        </span>
      ),
    },
    {
      title: 'Minutos',
      dataIndex: 'minutos',
      width: 110,
      render: (v, r) => <InputNumber min={5} max={600} value={v} onChange={(x) => update(r.nombre, 'minutos', x)} />,
    },
    {
      title: 'Personas',
      dataIndex: 'personas',
      width: 110,
      render: (v, r) => <InputNumber min={1} max={4} value={v} onChange={(x) => update(r.nombre, 'personas', x)} />,
    },
  ];

  return (
    <Modal
      title="Tipos de OT"
      open={open}
      onCancel={onClose}
      onOk={handleSave}
      okText="Guardar"
      cancelText="Cancelar"
      confirmLoading={saving}
      width={620}
    >
      <Text type="secondary">
        Duración de cada visita y cuántas personas necesita. Las OTs de 2 personas solo se asignan a parejas de técnicos.
      </Text>
      <Table
        rowKey="nombre"
        columns={columns}
        dataSource={rows}
        pagination={false}
        size="small"
        style={{ marginTop: 12 }}
        scroll={{ y: 420 }}
      />
    </Modal>
  );
};

export default OtTypesModal;

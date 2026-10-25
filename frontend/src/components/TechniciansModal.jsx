import React, { useEffect, useState } from 'react';
import { Modal, Table, Input, Select, Button, Popconfirm, message } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { saveAssignmentConfig } from '../services/api';

const newId = () => `tec-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;

const TechniciansModal = ({ open, config, sedes, onClose, onSaved }) => {
  const [rows, setRows] = useState([]);
  const [saving, setSaving] = useState(false);

  // In-house technicians leave from a Bia base
  const bases = sedes.filter((s) => s.tipo === 'base');

  useEffect(() => {
    if (open) setRows((config?.tecnicos || []).map((t) => ({ ...t })));
  }, [open, config]);

  const update = (id, field, value) => {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  };

  const addRow = () => {
    setRows((prev) => [...prev, { id: newId(), nombre: '', base_id: bases[0]?.id, activo: true }]);
  };

  const handleSave = async () => {
    if (rows.some((r) => !r.nombre.trim() || !r.base_id)) {
      message.error('Cada técnico necesita nombre y base');
      return;
    }
    setSaving(true);
    try {
      const saved = await saveAssignmentConfig({
        ...config,
        tecnicos: rows.map((r) => ({ ...r, nombre: r.nombre.trim() })),
      });
      message.success('Técnicos guardados');
      onSaved(saved);
    } catch (error) {
      message.error(`No se pudieron guardar los técnicos: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    {
      title: 'Nombre',
      dataIndex: 'nombre',
      render: (value, row) => (
        <Input value={value} placeholder="Nombre del técnico" onChange={(e) => update(row.id, 'nombre', e.target.value)} />
      ),
    },
    {
      title: 'Base',
      dataIndex: 'base_id',
      width: 220,
      render: (value, row) => (
        <Select
          value={value}
          style={{ width: '100%' }}
          options={bases.map((b) => ({ value: b.id, label: `${b.empresa} (${b.ciudad})` }))}
          onChange={(v) => update(row.id, 'base_id', v)}
        />
      ),
    },
    {
      title: '',
      width: 50,
      render: (_, row) => (
        <Popconfirm title="¿Eliminar técnico?" onConfirm={() => setRows((prev) => prev.filter((r) => r.id !== row.id))}>
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <Modal
      title="Técnicos in-house"
      open={open}
      onCancel={onClose}
      onOk={handleSave}
      okText="Guardar"
      cancelText="Cancelar"
      confirmLoading={saving}
      width={640}
    >
      <Table rowKey="id" columns={columns} dataSource={rows} pagination={false} size="small" />
      <Button icon={<PlusOutlined />} onClick={addRow} style={{ marginTop: 12 }} block type="dashed">
        Agregar técnico
      </Button>
    </Modal>
  );
};

export default TechniciansModal;

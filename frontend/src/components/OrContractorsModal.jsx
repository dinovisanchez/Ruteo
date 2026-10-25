import React, { useEffect, useState } from 'react';
import { Modal, Table, Select, Input, Button, Space, Typography, message } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { saveAssignmentConfig } from '../services/api';

const { Text } = Typography;

const OrContractorsModal = ({ open, config, empresas, orsPresentes, onClose, onSaved }) => {
  const [mapping, setMapping] = useState({});
  const [newOr, setNewOr] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const initial = { ...(config?.or_contratistas || {}) };
    // Every OR in the current OTs shows up, even without contractors yet
    orsPresentes.forEach((nombre) => {
      const exists = Object.keys(initial).some((k) => k.toLowerCase() === nombre.toLowerCase());
      if (!exists) initial[nombre] = [];
    });
    setMapping(initial);
  }, [open, config, orsPresentes]);

  const addOr = () => {
    const nombre = newOr.trim();
    if (!nombre) return;
    setMapping((prev) => ({ ...prev, [nombre]: prev[nombre] || [] }));
    setNewOr('');
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const saved = await saveAssignmentConfig({ ...config, or_contratistas: mapping });
      message.success('Contratistas por OR guardados');
      onSaved(saved);
    } catch (error) {
      message.error(`No se pudo guardar: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const options = empresas.map((e) => ({ value: e.id, label: `${e.nombre} — ${e.sedes.join(', ')}` }));
  const dataSource = Object.keys(mapping)
    .sort((a, b) => a.localeCompare(b))
    .map((nombre) => ({ key: nombre, nombre, empresas: mapping[nombre] }));

  const columns = [
    { title: 'OR', dataIndex: 'nombre', width: 140, render: (v) => <Text strong>{v}</Text> },
    {
      title: 'Contratistas que lo atienden',
      dataIndex: 'empresas',
      render: (value, row) => (
        <Select
          mode="multiple"
          value={value}
          style={{ width: '100%' }}
          placeholder="Sin lista: se usa el más cercano de todos"
          options={options}
          optionFilterProp="label"
          onChange={(v) => setMapping((prev) => ({ ...prev, [row.nombre]: v }))}
        />
      ),
    },
  ];

  return (
    <Modal
      title="Contratistas por OR"
      open={open}
      onCancel={onClose}
      onOk={handleSave}
      okText="Guardar"
      cancelText="Cancelar"
      confirmLoading={saving}
      width={820}
    >
      <Text type="secondary">
        Para cada OT se elige la sede más cercana entre los contratistas de su OR. Si un OR no tiene contratistas,
        se elige el más cercano de todos.
      </Text>
      <Table
        columns={columns}
        dataSource={dataSource}
        pagination={false}
        size="small"
        style={{ marginTop: 12 }}
      />
      <Space.Compact style={{ marginTop: 12, width: '100%' }}>
        <Input
          value={newOr}
          placeholder="Agregar otro OR (ej. Celsia)"
          onChange={(e) => setNewOr(e.target.value)}
          onPressEnter={addOr}
        />
        <Button icon={<PlusOutlined />} onClick={addOr}>Agregar</Button>
      </Space.Compact>
    </Modal>
  );
};

export default OrContractorsModal;

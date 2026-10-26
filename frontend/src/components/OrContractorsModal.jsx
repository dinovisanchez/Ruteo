import React, { useEffect, useMemo, useState } from 'react';
import { Modal, Table, Select, Typography, Tag, Space, message } from 'antd';
import { saveAssignmentConfig } from '../services/api';
import { normalizeText } from '../services/otTypes';

const { Text } = Typography;

/**
 * One row per network operator (OR): the departments it serves and the contractors that
 * attend its OTs. Without a manual list, the contractors are the ones based in those
 * departments (computed by the backend as empresas_auto).
 */
export const buildOrRows = (operadores, resueltos, orCounts, orContratistas) => {
  const manualFor = (names) => {
    const key = Object.keys(orContratistas || {}).find((k) => names.some((n) => normalizeText(n) === normalizeText(k)));
    return key ? orContratistas[key] : [];
  };
  const rows = operadores.map((op) => {
    const enOts = Object.keys(orCounts).filter((name) => resueltos[name] === op.nombre);
    return {
      key: op.nombre,
      nombre: op.nombre,
      enOts,
      ots: enOts.reduce((sum, name) => sum + orCounts[name], 0),
      departamentos: op.departamentos,
      notas: op.notas,
      auto: op.empresas_auto,
      manual: manualFor([op.nombre, ...enOts]),
    };
  });
  // ORs from the OTs that are not in the catalog: the backend falls back to the OT's department
  Object.keys(orCounts).filter((name) => !resueltos[name]).forEach((name) => {
    rows.push({ key: name, nombre: name, enOts: [name], ots: orCounts[name], departamentos: [], notas: '', auto: [], manual: manualFor([name]), desconocido: true });
  });
  return rows.sort((a, b) => b.ots - a.ots || a.nombre.localeCompare(b.nombre));
};

const OrContractorsModal = ({ open, config, empresas, operadores, resueltos, orCounts, onClose, onSaved }) => {
  const [manual, setManual] = useState({});
  const [saving, setSaving] = useState(false);

  const rows = useMemo(
    () => buildOrRows(operadores, resueltos, orCounts, config?.or_contratistas),
    [operadores, resueltos, orCounts, config],
  );
  const nombreEmpresa = useMemo(() => Object.fromEntries(empresas.map((e) => [e.id, e.nombre])), [empresas]);

  useEffect(() => {
    if (open) setManual(Object.fromEntries(rows.map((r) => [r.key, r.manual])));
  }, [open, rows]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const orContratistas = Object.fromEntries(Object.entries(manual).filter(([, lista]) => lista?.length));
      const saved = await saveAssignmentConfig({ ...config, or_contratistas: orContratistas });
      message.success('Contratistas por OR guardados');
      onSaved(saved);
    } catch (error) {
      message.error(`No se pudo guardar: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const options = empresas.map((e) => ({ value: e.id, label: `${e.nombre} — ${e.sedes.join(', ')}` }));

  const columns = [
    {
      title: 'OR',
      width: 190,
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Space size={4}>
            <Text strong>{r.nombre}</Text>
            {r.ots > 0 && <Tag color="blue">{r.ots} OTs</Tag>}
          </Space>
          {r.enOts.filter((n) => n !== r.nombre).map((n) => (
            <Text key={n} type="secondary" style={{ fontSize: 11 }}>en las OTs: {n}</Text>
          ))}
          {r.desconocido && <Text type="warning" style={{ fontSize: 11 }}>No está en el catálogo de OR</Text>}
        </Space>
      ),
    },
    {
      title: 'Departamentos',
      width: 200,
      render: (_, r) => (
        <Text style={{ fontSize: 12 }}>
          {r.departamentos.length ? r.departamentos.join(', ') : 'El de cada OT'}
          {r.notas ? <Text type="secondary" style={{ display: 'block', fontSize: 11 }}>{r.notas}</Text> : null}
        </Text>
      ),
    },
    {
      title: 'Contratistas que la atienden',
      render: (_, r) => {
        const placeholder = r.auto.length
          ? `Automático: ${r.auto.map((id) => nombreEmpresa[id] || id).join(', ')}`
          : (r.desconocido ? 'Automático: los de su departamento' : 'Sin contratistas en la zona: el más cercano');
        return (
          <Select
            mode="multiple"
            allowClear
            value={manual[r.key] || []}
            style={{ width: '100%' }}
            placeholder={placeholder}
            options={options}
            optionFilterProp="label"
            onChange={(v) => setManual((prev) => ({ ...prev, [r.key]: v }))}
          />
        );
      },
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
      width={960}
    >
      <Text type="secondary">
        Por defecto, cada OT va al contratista más cercano entre los que tienen sede en un departamento que
        atiende su OR (texto gris). Elige contratistas solo si quieres fijar otra lista para ese OR.
      </Text>
      <Table
        columns={columns}
        dataSource={rows}
        pagination={false}
        size="small"
        style={{ marginTop: 12 }}
        scroll={{ y: 480 }}
      />
    </Modal>
  );
};

export default OrContractorsModal;

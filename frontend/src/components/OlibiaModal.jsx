import React from 'react';
import {
  Button, Modal, Table, message,
} from 'antd';
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

const COLUMNAS = [
  ['OT', 'codigo'], ['Fecha', 'fecha'], ['Llega', 'hora'], ['Ciudad', 'ciudad'], ['Dirección', 'direccion'],
  ['Qué hacer', 'cambio'], ['Destino', 'destino'], ['Asignar a', 'responsable'],
];

const celda = (valor) => String(valor ?? '').replace(/[\t\n]+/g, ' ');

/**
 * What still has to be done in Olibia from the plan, to copy into a sheet or download (see paraOlibia)
 */
const OlibiaModal = ({ abierto, filas, dia, onCerrar }) => {
  const copiar = async () => {
    const texto = [COLUMNAS.map(([t]) => t), ...filas.map((f) => COLUMNAS.map(([, k]) => f[k]))]
      .map((fila) => fila.map(celda).join('\t')).join('\n');
    try {
      await navigator.clipboard.writeText(texto);
      message.success(`${filas.length} OTs copiadas: pégalas en una hoja de cálculo`);
    } catch (error) {
      message.error('No se pudo copiar; usa «Descargar CSV»');
    }
  };
  const descargar = () => {
    // ";" so it opens directly in Excel configured in Spanish
    const valor = (v) => (/[";\n]/.test(String(v ?? '')) ? `"${String(v).replace(/"/g, '""')}"` : String(v ?? ''));
    const csv = [COLUMNAS.map(([t]) => t), ...filas.map((f) => COLUMNAS.map(([, k]) => f[k]))]
      .map((fila) => fila.map(valor).join(';')).join('\n');
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = `para-olibia-${dia}.csv`;
    document.body.appendChild(enlace);
    enlace.click();
    document.body.removeChild(enlace);
    URL.revokeObjectURL(url);
  };
  return (
    <Modal
      open={abierto}
      title={`Para cargar en Olibia · ${dayjs(dia).format('ddd D MMM')}`}
      onCancel={onCerrar}
      width={980}
      footer={[
        <Button key="copiar" icon={<CopyOutlined />} onClick={copiar} disabled={!filas.length}>Copiar</Button>,
        <Button key="csv" icon={<DownloadOutlined />} onClick={descargar} disabled={!filas.length}>Descargar CSV</Button>,
        <Button key="cerrar" type="primary" onClick={onCerrar}>Listo</Button>,
      ]}
    >
      <p className="muted-text">
        Lo que el plan manda a alguien y todavía no está así en Metabase: las sugeridas, las elegidas a mano y las
        reasignadas. Respeta los filtros de la lista. Ruteo no escribe en Olibia: asígnalas allá y en la próxima
        actualización aparecen como asignadas.
      </p>
      <Table
        className="plain-table"
        size="small"
        rowKey="codigo"
        dataSource={filas}
        pagination={{ pageSize: 15, hideOnSinglePage: true, showSizeChanger: false }}
        locale={{ emptyText: 'Nada pendiente: el plan coincide con Metabase' }}
        columns={COLUMNAS.map(([titulo, clave]) => ({
          title: titulo,
          dataIndex: clave,
          render: clave === 'codigo' ? (c) => <span className="ot-code">{c}</span> : undefined,
        }))}
      />
    </Modal>
  );
};

export default OlibiaModal;

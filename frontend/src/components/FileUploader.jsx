import React, { useState } from 'react';
import { Upload, Button, Card, Alert, Table, Tag } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { uploadFile } from '../services/api';

const { Dragger } = Upload;

const FileUploader = ({ onUploadSuccess }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);
  const [previewData, setPreviewData] = useState([]);

  const handleUpload = async (file) => {
    setUploading(true);
    setError(null);
    setUploadResult(null);

    try {
      const result = await uploadFile(file);
      setUploadResult(result);

      // Prepare preview data (first 5 activities)
      const preview = result.activities.slice(0, 5).map((act, idx) => ({
        key: idx,
        codigo: act.codigo_bia,
        servicio: act.servicio,
        nombre: act.nombre,
        ciudad: act.ciudad,
        gps: act.gps,
      }));
      setPreviewData(preview);

      // Notify parent component
      if (onUploadSuccess) {
        onUploadSuccess(result);
      }
    } catch (err) {
      setError(err.message || 'Error uploading file');
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }

    // Prevent default upload behavior
    return false;
  };

  const uploadProps = {
    name: 'file',
    multiple: false,
    accept: '.xlsx,.xls,.csv',
    beforeUpload: handleUpload,
    showUploadList: false,
  };

  const columns = [
    {
      title: 'Código',
      dataIndex: 'codigo',
      key: 'codigo',
      width: 120,
    },
    {
      title: 'Servicio',
      dataIndex: 'servicio',
      key: 'servicio',
      render: (servicio) => <Tag color="blue">{servicio}</Tag>,
    },
    {
      title: 'Nombre',
      dataIndex: 'nombre',
      key: 'nombre',
    },
    {
      title: 'Ciudad',
      dataIndex: 'ciudad',
      key: 'ciudad',
    },
    {
      title: 'GPS',
      dataIndex: 'gps',
      key: 'gps',
      width: 150,
    },
  ];

  return (
    <Card title="1. Cargar Archivo de Actividades" style={{ marginBottom: 16 }}>
      <Dragger {...uploadProps} disabled={uploading}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">
          Haz clic o arrastra un archivo a esta área
        </p>
        <p className="ant-upload-hint">
          Archivos soportados: Excel (.xlsx, .xls) o CSV (.csv)
        </p>
        <p className="ant-upload-hint" style={{ fontSize: 12, color: '#999' }}>
          El archivo debe contener las columnas: codigo_bia, servicio, gps, nombre, direccion, ciudad, departamento, or_operador
        </p>
      </Dragger>

      {uploading && (
        <Alert
          message="Cargando..."
          description="Procesando archivo, por favor espera..."
          type="info"
          showIcon
          style={{ marginTop: 16 }}
        />
      )}

      {error && (
        <Alert
          message="Error"
          description={error}
          type="error"
          showIcon
          closable
          onClose={() => setError(null)}
          style={{ marginTop: 16 }}
        />
      )}

      {uploadResult && (
        <div style={{ marginTop: 16 }}>
          <Alert
            message="Archivo cargado exitosamente"
            description={`${uploadResult.total_activities} actividades cargadas. ${uploadResult.message}`}
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
          />

          {previewData.length > 0 && (
            <>
              <h4>Vista previa (primeras 5 actividades):</h4>
              <Table
                columns={columns}
                dataSource={previewData}
                pagination={false}
                size="small"
                scroll={{ x: true }}
              />
              {uploadResult.total_activities > 5 && (
                <p style={{ marginTop: 8, color: '#999', fontSize: 12 }}>
                  ... y {uploadResult.total_activities - 5} actividades más
                </p>
              )}
            </>
          )}
        </div>
      )}
    </Card>
  );
};

export default FileUploader;

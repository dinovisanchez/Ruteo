import React, { useState } from 'react';
import { Button, Segmented, Select } from 'antd';
import { editOptions } from './AssignmentResults';

export const POR_CERCANIA = 'cercania';

/**
 * Bar for the OTs selected in the list: send all of them to one technician or contractor, let the
 * app decide, or group them by proximity (each group to whoever has OTs nearby, else to a free
 * technician, else to the lowest UTR). When the selection mixes pending and assigned OTs, it can
 * take all of them or only the pending ones.
 */
const LoteBar = ({
  cantidad, pendientes, tecnicos, empresas, onAplicar, onLimpiar, ocupado,
}) => {
  const [destino, setDestino] = useState(POR_CERCANIA);
  const [soloPendientes, setSoloPendientes] = useState(false);
  const [automatico, ...resto] = editOptions(tecnicos, empresas, [], false);
  const opciones = [
    {
      ...automatico,
      options: [
        { value: POR_CERCANIA, label: 'Por cercanía: a quien esté cerca, libre o con menor UTR' },
        ...automatico.options,
      ],
    },
    ...resto,
  ];
  const mezcla = pendientes > 0 && pendientes < cantidad;
  const usadas = mezcla && soloPendientes ? pendientes : cantidad;
  return (
    <div className="lote-bar" role="region" aria-label="Asignar las OTs seleccionadas">
      <span className="lote-count">
        {cantidad} {cantidad === 1 ? 'OT seleccionada' : 'OTs seleccionadas'}
      </span>
      {mezcla && (
        <Segmented
          size="small"
          value={soloPendientes ? 'pendientes' : 'todas'}
          onChange={(valor) => setSoloPendientes(valor === 'pendientes')}
          options={[
            { value: 'todas', label: `Por asignar y asignadas (${cantidad})` },
            { value: 'pendientes', label: `Solo por asignar (${pendientes})` },
          ]}
        />
      )}
      <Select
        value={destino}
        onChange={setDestino}
        options={opciones}
        showSearch
        optionFilterProp="label"
        popupMatchSelectWidth={false}
        className="lote-select"
        aria-label="Enviar a"
      />
      <Button type="primary" loading={ocupado} onClick={() => onAplicar(destino, mezcla && soloPendientes)}>
        {destino === POR_CERCANIA ? 'Ver propuesta' : `Asignar ${usadas}`}
      </Button>
      <Button type="text" onClick={onLimpiar} disabled={ocupado}>Quitar selección</Button>
    </div>
  );
};

export default LoteBar;

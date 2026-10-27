import React, { useState } from 'react';
import { Button, Select } from 'antd';
import { editOptions } from './AssignmentResults';

export const POR_CERCANIA = 'cercania';

/**
 * Bar for the OTs selected in the list: send all of them to one technician or contractor, let the
 * app decide, or group them by proximity (each group to whoever has OTs nearby, else to a free
 * technician, else to the lowest UTR).
 */
const LoteBar = ({
  cantidad, tecnicos, empresas, onAplicar, onLimpiar, ocupado,
}) => {
  const [destino, setDestino] = useState(POR_CERCANIA);
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
  return (
    <div className="lote-bar" role="region" aria-label="Asignar las OTs seleccionadas">
      <span className="lote-count">
        {cantidad} {cantidad === 1 ? 'OT seleccionada' : 'OTs seleccionadas'}
      </span>
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
      <Button type="primary" loading={ocupado} onClick={() => onAplicar(destino)}>
        {destino === POR_CERCANIA ? 'Ver propuesta' : 'Asignar'}
      </Button>
      <Button type="text" onClick={onLimpiar} disabled={ocupado}>Quitar selección</Button>
    </div>
  );
};

export default LoteBar;

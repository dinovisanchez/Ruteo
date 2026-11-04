import React, { useEffect, useState } from 'react';
import { Modal, Select } from 'antd';

const pct = (utr) => (utr === null || utr === undefined ? '—' : `${Math.round(utr * 100)} %`);
const horas = (minutos) => (minutos / 60).toLocaleString('es-CO', { maximumFractionDigits: 1 });
const km = (valor) => valor.toLocaleString('es-CO', { maximumFractionDigits: 1 });

// Why that technician, by the same rules as the plan: near their OTs, free, or lowest UTR
const REGLAS = { 1: 'cerca', 2: 'libre', 3: 'menor UTR', 4: 'no cabe' };
const porQue = (opcion) => {
  if (opcion.regla === 1) return `Tiene OTs hoy a ${km(opcion.km_cerca)} km`;
  if (opcion.regla === 2) return 'No tiene OTs hoy y nadie más tiene OTs cerca';
  if (opcion.regla === 3) return 'Todos tienen OTs lejos: el de menor UTR';
  return 'No cabe en la jornada de nadie: el de menor UTR';
};
const detalle = (opcion) => {
  if (opcion.km_cerca === null || opcion.km_cerca === undefined) return 'sin OTs hoy';
  return `sus OTs a ${km(opcion.km_cerca)} km`;
};

/**
 * Proposal for a batch: the OTs close to each other go together, each group to the technician of
 * its team with the lowest UTR of the week. Each group's technician can be changed before applying.
 */
const LoteModal = ({
  propuesta, actividades, onCancelar, onAplicar, ocupado,
}) => {
  // Group → chosen technician id (the suggested one unless changed)
  const [eleccion, setEleccion] = useState({});
  useEffect(() => {
    setEleccion(Object.fromEntries((propuesta?.grupos || []).map((g, i) => [i, g.tecnico_id])));
  }, [propuesta]);

  if (!propuesta) return null;
  const { grupos, sin_tecnico: sinTecnico, sin_ubicacion: sinUbicacion, radio_km: radio } = propuesta;
  const total = grupos.reduce((suma, g) => suma + g.codigos.length, 0) + sinTecnico.length;

  const aplicar = () => {
    const asignaciones = {};
    grupos.forEach((g, i) => g.codigos.forEach((codigo) => { asignaciones[codigo] = `tecnico:${eleccion[i]}`; }));
    sinTecnico.forEach(({ codigo }) => { asignaciones[codigo] = 'contratista'; });
    onAplicar(asignaciones, grupos.map((g, i) => g.opciones.find((o) => o.tecnico_id === eleccion[i])?.tecnico));
  };

  const otLinea = (codigo) => {
    const a = actividades[codigo];
    return (
      <li key={codigo}>
        <span className="ot-code">{codigo}</span>
        <span className="lote-ot-sub">{[a?.servicio, a?.or_operador, a?.direccion, a?.ciudad].filter(Boolean).join(' · ')}</span>
        {a?.situacion === 'asignada' && (
          <span className="lote-ot-asignada">
            Ya asignada{a.asignado_a ? ` a ${a.asignado_a}` : ''}: se reasigna
          </span>
        )}
      </li>
    );
  };

  return (
    <Modal
      open
      title="Asignar por cercanía"
      okText={`Asignar ${total} ${total === 1 ? 'OT' : 'OTs'}`}
      cancelText="Cancelar"
      onOk={aplicar}
      onCancel={onCancelar}
      okButtonProps={{ disabled: !total, loading: ocupado }}
      width={680}
    >
      <p className="lote-intro">
        Las OTs a {km(radio)} km o menos entre sí van juntas. Cada grupo va al técnico que ya tiene OTs a {km(radio)} km o menos;
        si nadie, a uno que no tenga OTs hoy; y si todos tienen OTs lejos, al de menor UTR de la semana. Puedes cambiar
        el técnico de cada grupo.
      </p>
      <div className="lote-grupos">
        {grupos.map((g, i) => {
          const opcion = g.opciones.find((o) => o.tecnico_id === eleccion[i]);
          const sugerido = eleccion[i] === g.tecnico_id;
          return (
            <section key={g.codigos.join('|')} className="lote-grupo">
              <div className="lote-grupo-head">
                <strong>
                  {g.codigos.length > 1 ? `${g.codigos.length} OTs a ${km(g.km_max)} km o menos` : '1 OT'}
                </strong>
                <span className="lote-grupo-meta">{horas(g.minutos)} h con el viaje desde la base</span>
              </div>
              <ul className="lote-ots">{g.codigos.map(otLinea)}</ul>
              <div className="lote-grupo-tecnico">
                <Select
                  value={eleccion[i]}
                  onChange={(valor) => setEleccion((prev) => ({ ...prev, [i]: valor }))}
                  options={g.opciones.map((o) => ({
                    value: o.tecnico_id,
                    label: `${o.tecnico} · ${detalle(o)} · ${pct(o.utr)} en la semana${o.cabe ? '' : ' · no cabe hoy'}`,
                    title: REGLAS[o.regla],
                  }))}
                  popupMatchSelectWidth={false}
                  style={{ minWidth: 260 }}
                  aria-label="Técnico del grupo"
                />
                <span className="lote-grupo-meta">
                  {sugerido
                    ? `${porQue(g)} · UTR ${pct(g.utr_antes)} → ${pct(g.utr_despues)}`
                    : `Lleva ${pct(opcion?.utr)} en la semana`}
                </span>
              </div>
              {(sugerido ? !g.cabe : opcion && !opcion.cabe) && (
                <div className="warn-text">No cabe en su jornada de hoy: su ruta quedará pasada de horas</div>
              )}
              {g.personas > 1 && <div className="lote-grupo-meta">Necesita {g.personas} personas: sale en pareja</div>}
            </section>
          );
        })}
        {sinTecnico.length > 0 && (
          <section className="lote-grupo">
            <div className="lote-grupo-head">
              <strong>Al contratista más cercano de su OR</strong>
              <span className="lote-grupo-meta">{sinTecnico[0].motivo}</span>
            </div>
            <ul className="lote-ots">{sinTecnico.map(({ codigo }) => otLinea(codigo))}</ul>
          </section>
        )}
        {sinUbicacion.length > 0 && (
          <section className="lote-grupo">
            <div className="lote-grupo-head">
              <strong>Sin ubicación: se quedan como están</strong>
              <span className="lote-grupo-meta">Sin coordenadas no se puede saber qué tiene cerca</span>
            </div>
            <ul className="lote-ots">{sinUbicacion.map(otLinea)}</ul>
          </section>
        )}
      </div>
    </Modal>
  );
};

export default LoteModal;

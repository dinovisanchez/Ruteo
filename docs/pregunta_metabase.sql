-- Pregunta de Metabase para Ruteo. Copiarla entera: pbcopy < docs/pregunta_metabase.sql
-- Si otra tabla trae las coordenadas (búscalas con: python -m scripts.explorar_metabase --base <número> --buscar),
-- únela y agrega dos columnas; por ejemplo, si están en una tabla de fronteras por código Bia:
--   LEFT JOIN <esquema>.<tabla_con_coordenadas> u ON u.<codigo> = internal_bia_code
--   y en el SELECT:  u.<latitud> AS "Latitud", u.<longitud> AS "Longitud",
SELECT
  COALESCE(NULLIF(TRIM(internal_bia_code), ''), 'OT-' || CAST(card_id AS VARCHAR)) AS "Bia Code",
  card_id AS "Orden de trabajo",
  CASE
    WHEN status_app = 'PENDING_ASSIGNMENT' THEN 'Pendiente por asignar'
    WHEN status = 'PENDING' THEN 'Asignada'
    ELSE 'Cerrada'
  END AS "Situación",
  estado AS "Estado",
  status_app AS "Estado app",
  fecha_visita AS "Fecha de la visita",
  contratista AS "Contratista asignado",
  electricistas AS "Electricistas asignados",
  electrician_id AS "Id electricista",
  COALESCE(NULLIF(service_name, ''), visit_type_id) AS "Tipo de OT",
  service_type_id AS "Código tipo OT",
  measurement_type_id AS "Tipo de medida",
  company_name AS "Cliente",
  operador_de_red AS "OR",
  address AS "Dirección",
  city_name AS "Ciudad",
  department AS "Departamento",
  wo_generate_by AS "Creado por",
  created_at AS "Fecha de creación"
FROM operations.visitas_general
WHERE deleted_at IS NULL
  AND COALESCE(estado, '') NOT ILIKE '%cancel%'
  AND COALESCE(estado, '') NOT ILIKE '%vencid%'
  AND (
    status_app = 'PENDING_ASSIGNMENT'
    OR (status = 'PENDING' AND fecha_visita >= CURRENT_DATE - INTERVAL '7 days')
    OR (estado IN ('Cierre Exitoso', 'Cierre Fallido', 'Completada')
        AND fecha_visita >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
        AND COALESCE(electricistas, '') <> ''
        AND (contratista ILIKE '%bia%' OR COALESCE(contratista, '') = ''))
  )
ORDER BY fecha_visita NULLS LAST, card_id;

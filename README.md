# Ruteo

Ruteo arma el **plan del día** de las OTs de Bia: lee las OTs de una pregunta de Metabase y recomienda
a quién mandar cada una, a un técnico de Bia (con su ruta por las vías) o al contratista más cercano de
su Operador de Red, y por qué. Respeta lo que ya está asignado en Metabase, reparte parejo según la
utilización (UTR) de la semana y deja editar cada decisión antes de llevarla a Olibia.

Ruteo **no escribe** en Metabase ni en Olibia: lo que decidas aquí se asigna en Olibia.

## Arrancar en el Mac

```bash
cd ~/Downloads/Ruteo
git pull
./iniciar.sh
```

`./iniciar.sh` crea el entorno de Python la primera vez e instala lo que falte (también después de un
`git pull` que cambie versiones), reinicia el backend (el *gateway* en el puerto 8000 y el optimizador
en el 8003, con registros en `logs/`) y abre el frontend en http://localhost:3000. Ctrl+C detiene todo.

Necesita Python 3.9 o más nuevo (el que trae el Mac sirve) y Node.js 18 o más nuevo. La primera vez se
crea `backend/.env`: pon ahí `METABASE_URL` y `METABASE_API_KEY` (la llave **solo** va en ese archivo,
nunca en un chat ni en el repositorio) y vuelve a correr `./iniciar.sh`.

**Subir un Excel o CSV.** En el panel, *o subir un Excel/CSV* carga OTs desde un `.xlsx` o un `.csv`
(con coma o punto y coma, como lo guarda Excel en español) en vez de Metabase. El archivo se lee con las
mismas columnas que la pregunta (*Bia Code*, *OR*, *Dirección*, *Ciudad*, *Situación*, *Fecha de la
visita*, *Latitud*/*Longitud* o *GPS*…) y no se guarda. Un `.xls` viejo se guarda primero como `.xlsx`.

## Cómo se usa

La arquitectura (servicios, endpoints, qué pantalla usa cada uno y los flujos) está en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

Ruteo es una sola pantalla: pulsa **Extraer y recomendar** (arriba a la derecha) y la app trae las OTs de la pregunta de Metabase y arma el **plan del día**: a quién enviar cada OT y por qué. Arriba se elige la vista (*Lista*, *Mapa*, *Rutas* o *Tabla completa* con todas las columnas de la pregunta) y se filtra. A la izquierda, en secciones plegables, están los **técnicos** de cada equipo (con un interruptor de disponibilidad), los contratistas por OR, los tipos de OT y los *Ajustes*. La **barra de herramientas** del borde izquierdo esconde y muestra ese panel (la app recuerda cómo lo dejaste) y con sus iconos lo abre directo en *Técnicos*, *Contratistas por OR*, *Tipos de OT* o *Ajustes*; en pantallas pequeñas el panel empieza escondido y se abre sobre el contenido.

### Plan del día

- **Día a día.** En la barra de filtros eliges el día (flechas o calendario). Un día muestra **las OTs con fecha de visita ese día**, asignadas o pendientes, igual que Olibia. Solo el plan de **hoy** suma además las pendientes **vencidas** («Vencida: era el …») y las pendientes **sin fecha**, para que no queden sin planear. Debajo del estado de cada OT se ve su fecha («Visita el 29 oct», «Vencida: era el 25 oct», «Sin fecha de visita»). Al cambiar de día, la lista no muestra nada del día anterior mientras se calcula el nuevo plan; un día sin OTs lo dice. Las vistas que no son de un día (*Falta por asignar*, y en la *Tabla completa* «Sin fecha» y «Todas las fechas») ponen «Todas las fechas» o «Sin fecha» en la caja de la fecha; al elegir un día vuelves a su plan.
- **Ya asignadas.** Si en Metabase la OT está asignada a un técnico de la app (se reconoce por el nombre en *Electricistas asignados*, aunque venga en mayúsculas o con el segundo nombre) y ese técnico está **marcado como disponible**, la OT se queda con él y entra en su ruta (candado en la tabla). Si no está disponible, la app la reasigna. Si está asignada a un contratista del catálogo, se queda con ese contratista; si el responsable no está en la app, aparece como **Externo** y no entra en las rutas. Las OTs de un **contratista** nunca se le cuentan a un técnico de Bia, aunque su electricista se llame parecido. Las visitas **cerradas** ya se hicieron: dicen «Cerrada en Metabase», no se pueden editar ni meter en un lote, y si su técnico hoy no está disponible se quedan con él (como externas) en vez de volver a repartirse.
- **Se actualiza sola.** Con *Actualizar cada N min* encendido (viene encendido y la app lo recuerda), el plan se carga solo al abrir la app, se vuelve a traer de Metabase cada N minutos y al volver a la pestaña si pasó más que eso. Al empezar un nuevo día (a medianoche o cuando el computador despierta otro día), si estabas viendo *Hoy* pasa al nuevo día y rehace el plan: las pendientes que quedaron sin asignar entran como "Pendiente desde…". Con el interruptor apagado solo recalcula con las OTs ya cargadas. Si una actualización falla (Metabase o el backend no responden), arriba de la lista sale «No se pudo actualizar desde Metabase a las …» con la hora de los datos que estás viendo y un botón *Reintentar*; el aviso se quita cuando una lectura funciona.
- **El plan en pantalla siempre es el último que pediste.** Si cambias de día, editas una OT o llega la actualización automática mientras se calcula otro plan, solo cuenta la respuesta más reciente; una edición hecha mientras se leía Metabase se mantiene. Si el plan no se puede recalcular, la edición se deshace y la app lo avisa. Si apagas un técnico o cambias *Ajustes*, las ediciones y los cambios de día ya lo tienen en cuenta, y un aviso con el botón *Recalcular* dice que el plan en pantalla todavía es el de antes. Si un campo de la jornada queda vacío o fuera de rango, la app lo dice y abre *Ajustes* en vez de no hacer nada.
- **Pendientes.** La app sugiere a quién enviarlas con las reglas de abajo, llenando la jornada de los técnicos disponibles junto con lo que ya tienen asignado.
- **Filtros.** Buscar por nombre (cliente, OT, dirección, técnico, contratista o quién la creó), fecha, *Todas · Por asignar · Asignadas*, *Asignado a* (uno o varios técnicos, contratistas o externos) y **OR** (uno o varios; junta las formas en que Metabase escribe el mismo OR, por ejemplo "AFINIA - CARIBEMAR DE LA COSTA" y "Afinia"). El filtro de OR solo cambia lo que se ve, no el plan (para calcular el plan solo con algunos OR está *Ajustes → Filtrar por OR*). Las tarjetas del resumen cuentan lo que seleccionas: si eliges un técnico en *Asignado a*, muestran sus OTs, sus asignadas y por asignar, los km y las horas de su ruta. También son filtros (*Asignadas*, *Por asignar*, *Técnicos Bia*, *Contratistas*, *Externas*, *Sin asignar*): al tocar una se filtra por ella, al tocarla otra vez se quita, y se pueden combinar (por ejemplo *Por asignar* + *Contratistas*); *OTs del día* quita esos filtros. *Por asignar* son las pendientes que entran en el plan del día elegido; **Falta por asignar** (tarjeta y botón en la barra) son **todas** las pendientes de Metabase sin importar la fecha. Al tocarla la lista muestra cada una con su fecha de visita (vencidas primero, luego para hoy, próximos días y sin fecha), a quién la manda el plan si entra en el día que estás viendo y un botón *Planear hoy* / *Planear el …* que abre el plan de ese día. La columna **Asignadas cerca** dice qué OTs ya asignadas en Metabase quedan a la distancia «cerca» de *Ajustes* (2 km por defecto, en línea recta): quién la tiene, a cuántos km, su código y cuándo es. Solo cuentan las de hoy en adelante y no cerradas; primero salen las del **mismo día** en que se planearía la pendiente (su fecha; las vencidas y las sin fecha, hoy), marcadas «mismo día». El resumen dice cuántas pendientes tienen alguna cerca, y el filtro de la columna deja ver solo las que tienen asignadas cerca ese mismo día (o las que no tienen ninguna). La misma columna sale en la *Tabla completa* de *Falta por asignar*. Las OTs ubicadas solo por su municipio (no se encontró la dirección) no cuentan como cerca de nada, ni aquí ni en el plan: su punto es el centro del municipio. La búsqueda y *Asignado a* también la filtran. Todo filtra la lista, el mapa, las rutas y la tabla completa.
- **Editar.** En la columna *Enviar a* cada OT tiene un selector: *Que decida la app*, un técnico disponible, *El más cercano de su OR* o un contratista concreto. Al cambiarlo la app recalcula el plan respetando la edición (etiqueta *Editada*); *Quitar ediciones* vuelve a la sugerencia. Si una OT fijada no cabe en la jornada de su técnico, la ruta se marca como *Supera la jornada* y las demás OTs pasan a otros técnicos o contratistas.
- **Todas las OTs cargadas.** La *Tabla completa* tiene cuatro alcances, todos con los mismos filtros: *Plan del día* (exactamente lo de la lista), *Con visita el día* (todas las OTs con esa fecha, en cualquier estado, también las cerradas), *Sin fecha* y *Todas las fechas*. El número de OTs del encabezado («409 OTs cargadas») abre *Todas las fechas*, y la columna *En el plan del día* dice si cada OT está en el plan y, si no, por qué: asignada para otro día, cerrada (solo cuenta para la utilización), pendiente para otra fecha, su OR fuera del filtro de *Ajustes*, o llegó después del último cálculo.
- **Varias OTs a la vez (lote).** Encima de la lista, *Seleccionar: Solo por asignar · Por asignar y asignadas* marca de una vez las OTs que muestran los filtros (por ejemplo, solo las de un OR); también se pueden marcar una por una. Si la selección mezcla pendientes y asignadas, la barra deja elegir *Por asignar y asignadas* o *Solo por asignar*; las ya asignadas que entran en el lote se reasignan (la propuesta lo avisa). Abajo aparece una barra para mandarlas todas a un técnico, a un contratista, a *Que decida la app* o **por cercanía**. Por cercanía, la app junta las que están a 2 km o menos entre sí y propone cada grupo con las mismas reglas del plan (abajo, *A quién le toca cada OT*), contando lo que cada técnico ya tiene en el plan que estás viendo; la propuesta dice por qué (cerca, libre o menor UTR), la UTR antes y después, si cabe en su jornada y si necesita pareja, y se puede cambiar el técnico de cada grupo. Al asignar, la app recalcula el plan y abre el **mapa con la ruta** de esos técnicos.
- **Mapa por carretera.** Cada ruta se dibuja siguiendo las vías con OSRM: el servidor público `router.project-osrm.org` y, si no responde, el de OpenStreetMap (`OSRM_URL` y `OSRM_URL_RESPALDO` en `backend/.env`). El backend traza las rutas apenas se calcula el plan, así que el mapa suele abrir ya trazado. Si el backend no llega a OSRM (por ejemplo, por un proxy), el navegador consulta directo, tanto el trazado como los tiempos por carretera. Mientras traza se ve "Trazando por carretera · n/m"; si una ruta no se puede trazar, el mapa dice por qué. `GET /api/rutas/estado` dice si el backend llega a OSRM. Los cuadrados son OTs ya asignadas y los círculos, sugeridas.

### Cómo decide (modo automático)

1. **Equipos Bia primero, según su zona.** Cada equipo atiende ciertos OR en ciertas zonas (`backend/data/zonas_bia.json`):
   - **Equipo Bia Costa** (base Barranquilla): Air-e y Afinia en Barranquilla y alrededores, Santa Marta, Ciénaga, y Cartagena y alrededores.
   - **Equipo Bia Bogotá**: todo lo que cubre Enel (Bogotá y Cundinamarca).

   Una OT entra en una zona si su municipio está en la lista de la zona o si cae dentro de su radio. Las OTs de la zona de un equipo con técnicos disponibles se reparten entre ellos, cada uno saliendo de su base y sin pasar de las **horas de trabajo** (8 por defecto, incluyendo desplazamientos y el regreso a la base). La carga se reparte de forma pareja. Si no hay zonas definidas, vale la regla anterior: las OTs a menos de *Radio técnicos* de una base.
   **A quién le toca cada OT.** Entre los técnicos del equipo en cuya jornada cabe, en este orden:
   1. **Cerca:** si la OT está a 2 km o menos de las OTs que un técnico ya tiene ese día, va a ese técnico (el más cercano), aunque otro tenga menos UTR.
   2. **Libre:** si nadie está cerca, va a un técnico disponible que todavía no tiene OTs ese día (el de menor UTR entre ellos).
   3. **Menor UTR:** si todos tienen OTs y están lejos, va al de menor UTR de la semana (lo trabajado de lunes al día anterior más lo que ya tiene ese día).

   Por ejemplo, si Carlos tiene la UTR más baja y una OT en el norte, una OT del sur va al técnico que ya tiene OTs cerca en el sur; si nadie, a un técnico sin OTs; y solo si todos tienen OTs lejos, a Carlos. El motivo de cada OT dice cuál regla se aplicó y, al cambiar *Enviar a*, los técnicos aparecen de menor a mayor UTR. La distancia «cerca» se cambia en *Ajustes → Jornada → Distancia «cerca» (km)*.
2. **OTs cercanas juntas.** Las OTs a **2 km o menos** entre sí por carretera van a la misma cuadrilla en vez de repartirse entre varios técnicos; el grupo entero sigue las reglas de arriba. El motivo dice *Va junto con…*. Un grupo nunca pasa del 60 % de la jornada; si aun así no cabe, se separa.
3. **Personas por OT.** Las OTs de 2 personas (por defecto Instalación, Emergencia y Normalización medida) solo van a parejas de técnicos; la app arma las parejas que hacen falta en cada base (respetando las que ya salen juntas en Metabase), o puedes fijarlas con el selector *Pareja*. Si a un técnico le fijas una OT de 2 personas (a mano o por lote), sale en pareja.
4. **Contratistas para el resto.** Las OTs fuera de la zona de los equipos Bia, las que no caben en la jornada de los técnicos y las que piden más personas de las disponibles van al **contratista más cercano entre los que pueden atender su OR**, en este orden: la lista que fijes a mano en *Contratistas por OR*; si no hay, los contratistas con sede en los **departamentos donde opera el OR** (catálogo `backend/data/operadores_red.csv`, que reconoce variantes como "ENEL COLOMBIA S.A. E.S.P." o "Codensa"); si el OR no está en el catálogo, los del departamento de la OT; y si nadie tiene sede en la zona, el más cercano de todos. Para cada sede elegida se arman las cuadrillas mínimas para que todo quepa en la jornada.

El resultado muestra la lista de OTs con a quién enviarlas, la hora de llegada y el motivo (al desplegar una fila: OR, personas, de dónde sale, otras opciones y todas sus columnas), el mapa, las rutas de cada técnico o cuadrilla con su costo, y todas las columnas de la pregunta. Todo se descarga en CSV. En *Ajustes* se puede cambiar a *Solo técnicos* o *Solo contratistas*, filtrar por OR y ajustar la jornada y el tránsito.

### Utilización de los técnicos (UTR)

La vista **Utilización** muestra, por técnico de Bia y por equipo, las horas usadas frente a las disponibles en el **día**, la **semana** o el **mes** del día elegido (el periodo actual cuenta hasta hoy):

- **Horas disponibles**: jornada semanal (42 h por defecto) repartida en los días laborables (5 días, lunes a viernes = 8,4 h por día; se puede cambiar a 6 días).
- **Horas usadas** de un técnico en un día: la duración de cada una de sus OTs según el tipo, más el desplazamiento base → OTs → base (en el orden de la hora de visita, con el tránsito de cada zona). Si una OT no tiene ubicación, su viaje se estima con el promedio del día.
- **UTR** = horas usadas ÷ horas disponibles. También se ven las OTs, las OTs por técnico al día, el peso del viaje y una barra por día.
- Fuente: las OTs asignadas o cerradas en Metabase, con fecha de visita y electricistas. El día del plan puede contar con las sugerencias del plan (interruptor *Incluir el plan*).
- Se filtra por equipo y con *Asignado a* (uno o varios técnicos). En la vista *Rutas*, cada técnico muestra sus horas usadas y su UTR del día.

**Quién hizo cada OT.** El responsable es el del *Id electricista* de la visita (la app aprende sola qué técnico es cada id, a partir de las OTs con un solo electricista); de los demás de *Electricistas asignados* solo cuentan tantos como personas pide el tipo de OT, así una OT de una persona no se le suma a dos técnicos. Un tramo de más de 200 km se toma como dirección mal ubicada y su viaje se estima. En el detalle de cada técnico, cada día muestra sus OTs (códigos), horas en OTs y de viaje, y km, para revisarlo contra el plan de ese día. El plan y la utilización usan la misma regla.

Los técnicos se reconocen en *Electricistas asignados* aunque el nombre venga con segundo nombre, en mayúsculas o con otra ortografía (Jhonatan / Jonathan, Gelvez / Gelver). El nombre de pila tiene que sonar igual (Daniela no es Daniel, María no es Mario); la letra de diferencia solo se acepta en los apellidos. Solo se buscan técnicos de Bia en las OTs cuyo *Contratista asignado* es Bia o viene vacío. Si un *Id electricista* aprendido antes aparece en OTs de un contratista, la app lo olvida; y si una OT nueva de un solo electricista dice otra cosa, manda la OT. Los técnicos de la pestaña *Tecnicos* de la hoja se agregan solos a la app. Si alguien aparece en Metabase como técnico de Bia pero no está registrado, la app lo avisa en lugar de tratarlo como externo.

### Tiempos de desplazamiento y de cada visita

- **Por las vías.** El tiempo entre dos puntos es el de la ruta por carretera según OSRM (una consulta de tabla por plan, guardada en memoria). Si OSRM no responde, se estima con la línea recta × *factor vial*: los primeros 15 km a la velocidad en ciudad y el resto a 60 km/h.
- **Tránsito.** A cada desplazamiento que empieza o termina en estas zonas se le suma un porcentaje: **Bogotá +20 %**, **Barranquilla +15 %**, **Cartagena +10 %**. Se cambian en *Ajustes → Tránsito*, donde también se pueden sumar minutos fijos por desplazamiento.
- **Duración de cada visita** (promedios; se ajustan en *Tipos de OT*):

  | Tipo de OT | Duración |
  |---|---|
  | Visita previa (VIPE) | 1 h |
  | Instalación directa | 2 h |
  | Instalación semidirecta | 4 h |
  | Instalación indirecta | 6 h |
  | Normalización (cualquiera) | 2 h |
  | Normalización Telemedidas | 1 h |
  | Toma de lectura | 20 min |

  Las instalaciones se separan por el *Tipo de medida* de la pregunta (DIRECT, SEMI_DIRECT, INDIRECT); sin ese dato cuentan como directas.

### Configuración

**1. Metabase** — en `backend/.env` (se crea desde `backend/.env.example` la primera vez que corres `./iniciar.sh`):

```env
METABASE_URL=https://metabase.tu-empresa.com
METABASE_API_KEY=...            # o METABASE_USERNAME / METABASE_PASSWORD
```

La pregunta se elige en *Ajustes → Fuente de datos → Cambiar pregunta* (también se puede poner en `METABASE_CARD_ID`); la app no muestra su número. La pregunta necesita una columna con el OR; el código de la OT (`Bia Code`, `OT`…) es recomendable. La ubicación puede venir como `GPS` ("lat, lon"), como `Latitud`/`Longitud`, o solo como `Dirección` + `Ciudad`; en ese caso la OT se geocodifica (ver **Ubicaciones** más abajo) y se marca como **ubicación aproximada**: primero se ubica por su municipio (son pocos y se buscan enseguida, así ninguna OT queda sin ubicación) y la dirección exacta se busca en segundo plano para la siguiente extracción. Una OT asignada que aun así no tiene ubicación se queda con su técnico o contratista, aunque no entre en la ruta ni en el mapa. Los nombres de columna en español se reconocen solos; si no, defínelos con `METABASE_COLUMN_MAP`. Para el plan del día, la pregunta debe traer también las OTs asignadas con *Situación*, *Fecha de la visita*, *Electricistas asignados* y *Contratista asignado*. Esta consulta SQL sobre `operations.visitas_general` sirve:

```sql
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
  -- Ni canceladas ni de cierre vencido (Olibia las cuenta aparte)
  AND COALESCE(estado, '') NOT ILIKE '%cancel%'
  AND COALESCE(estado, '') NOT ILIKE '%vencid%'
  AND (
    -- Por asignar: todo lo que Olibia tiene esperando contratista, sin depender del texto de "estado"
    status_app = 'PENDING_ASSIGNMENT'
    -- Asignadas y activas (Asignada, Reasignado, Lista para ejecutar...), de la última semana en adelante
    OR (status = 'PENDING' AND fecha_visita >= CURRENT_DATE - INTERVAL '7 days')
    -- Visitas hechas por técnicos de Bia desde el mes pasado: para la utilización (UTR)
    OR (estado IN ('Cierre Exitoso', 'Cierre Fallido', 'Completada')
        AND fecha_visita >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
        AND COALESCE(electricistas, '') <> ''
        AND (contratista ILIKE '%bia%' OR COALESCE(contratista, '') = ''))
  )
ORDER BY fecha_visita NULLS LAST, card_id;
```

La misma consulta está en [docs/pregunta_metabase.sql](docs/pregunta_metabase.sql), para copiarla entera: en el Mac, `pbcopy < docs/pregunta_metabase.sql` la deja en el portapapeles.

**Estados y fechas.** La *Situación* se lee por su valor completo: «Pendiente por asignar», «Asignada», «Reasignada», «Cerrada», «Cierre exitoso»… Si la pregunta no trae *Situación*, vale *Estado app* de Olibia (`PENDING_ASSIGNMENT`, `ASSIGNED`, `REASSIGNED`, `COMPLETED`…). Las canceladas, anuladas o rechazadas no se cargan, y un valor que Ruteo no conoce (por ejemplo «No asignada») se toma como por asignar, para que se vea, y el panel lo avisa con el valor y cuántas filas lo traen. Las fechas con hora que Metabase manda con zona (`…-05:00`) o en UTC (`…Z`) se pasan a la hora de Colombia, así una visita de las 10 p. m. no cae al día siguiente; medianoche cuenta como fecha sin hora. En un Excel o CSV las fechas en texto van con el día primero (`03/11/2026` es el 3 de noviembre). «Hoy» es hoy en Colombia (`ZONA_HORARIA`), aunque el servidor esté en otra zona.

**Ubicaciones.** Con coordenadas en la pregunta, la ruta, los km y la columna *Asignadas cerca* son exactos; con solo la dirección dependen de encontrarla en el mapa. Por eso:

- **Busca si su base tiene coordenadas.** Desde la carpeta `backend`, con el número de la base (el `database` en la URL de una pregunta): `.venv/bin/python -m scripts.explorar_metabase --base <número> --buscar` lista las columnas con *latitud*, *longitud*, *gps* o *coordenadas*. Con acceso de SQL, esta consulta hace lo mismo:

  ```sql
  SELECT table_schema, table_name, column_name
  FROM information_schema.columns
  WHERE column_name ~* '(lat|lon|lng|coord|gps|geo|ubicaci)'
    AND table_schema NOT IN ('pg_catalog', 'information_schema')
  ORDER BY table_schema, table_name, column_name;
  ```

  Si una tabla (por ejemplo la del cliente o la de la frontera) las tiene, únela en la pregunta y agrega `… AS "Latitud"` y `… AS "Longitud"` (el comentario al inicio de `docs/pregunta_metabase.sql` tiene el molde). Ruteo las usa solas y deja de geocodificar esas OTs.
- **Sin coordenadas, Ruteo busca la dirección.** Antes la escribe como la entiende el mapa: «Cl. 58 #10-32 Apto 3» se busca como «Calle 58 10-32» (tipos de vía como CL, KR, AK, DG o TV; sin «#», «No.», apartamento ni barrio). Si el mapa solo encuentra la calle o el municipio, la OT queda como **ubicación aproximada** y no cuenta como cerca de nada (ni en el plan ni en *Asignadas cerca*), porque su punto es un centro. Una dirección que no se encontró se vuelve a buscar a los 7 días.
- **Nominatim o Google.** Por defecto se usa Nominatim (OpenStreetMap): gratis, pero pide máximo una consulta por segundo (Ruteo la respeta entre todas sus búsquedas) y conoce pocas direcciones de Colombia. Con `GOOGLE_GEOCODING_API_KEY` en `backend/.env` (Google Cloud → *Geocoding API*) se usa Google, que ubica muchas más direcciones a nivel de casa. Google cobra por uso después de una cuota gratis mensual; como Ruteo guarda cada dirección encontrada en `backend/data/geocache.json`, solo paga la primera vez que ve una dirección. Revisa el precio vigente antes de activarlo.

**Quién creó la OT.** `Creado por` y `Fecha de creación` salen en la lista (debajo de cada OT), en la tabla completa, en el CSV y en la búsqueda. En `operations.visitas_general` el creador es `wo_generate_by` (no hay `created_by`) y la fecha, `created_at`. La app reconoce también `Creada por`, `Creador` y `Created by`.

**Si Ruteo no cuadra con Olibia.** Ruteo solo ve lo que trae la pregunta. Para comparar un día (por ejemplo el 29 de octubre) corre en Metabase, sin guardarla, esta consulta y compárala con Olibia filtrado en ese día y los mismos OR:

```sql
SELECT internal_bia_code, card_id, status, status_app, estado, contratista, electricistas, fecha_visita, operador_de_red
FROM operations.visitas_general
WHERE deleted_at IS NULL
  AND fecha_visita >= DATE '2026-10-29' AND fecha_visita < DATE '2026-10-30'
ORDER BY operador_de_red, fecha_visita;
```

Las OTs que salen ahí y no en Ruteo tienen un `status`, `status_app` o `estado` que la pregunta deja por fuera; con esos valores se ajusta el `WHERE`. En Ruteo, la *Tabla completa → Con visita el día* muestra todas las OTs de esa fecha que trajo la pregunta, en cualquier estado.

**Una OT con varias visitas.** `visitas_general` trae una fila por visita, y una OT (mismo `internal_bia_code` y `card_id`) puede tener varias: la que se reprogramó, la que falló y la nueva. Ruteo toma como vigente la visita que sigue **por asignar** o, si ninguna, la más reciente, y le deja el código tal cual (`CO0100006578`). Las visitas anteriores ya asignadas o cerradas entran aparte con su fecha (`CO0100006578 · 2026-10-15`), porque ocuparon a su técnico ese día; las anteriores que dicen «por asignar» no cuentan aparte, porque vale la más reciente. Dos filas de la misma OT con la misma fecha y hora son la misma visita y cuentan una vez. Si Metabase trae más filas que OTs cargadas, el panel lo dice («Metabase trajo 285 filas y quedaron … OTs») y explica la diferencia. Para ver todas las visitas de una OT:

```sql
SELECT internal_bia_code, card_id, fecha_visita, status, status_app, estado, contratista, electricistas
FROM operations.visitas_general
WHERE deleted_at IS NULL AND internal_bia_code IN ('CO0100006578', 'CO0100002144')
ORDER BY internal_bia_code, card_id, fecha_visita;
```

Las visitas cerradas solo sirven para la utilización: no entran al plan salvo las del mismo día (que ya ocuparon tiempo de su técnico). La última condición toma las de técnicos de Bia; si en Metabase el contratista de Bia se llama distinto, ajusta `contratista ILIKE '%bia%'`.

**2. Catálogo de bases y contratistas** — `backend/data/contratistas.csv` es la hoja *Data Contratista* (sin datos de contacto). Para leerla directamente de Google Sheets, publícala como CSV y pon la URL en `CONTRATISTAS_CSV_URL`.

**3. Técnicos, contratistas por OR y tipos de OT** — se editan desde la app y se guardan en `backend/data/asignacion.json`: técnicos con base (por defecto Bia Bogotá) y **costo por día**; contratistas que atienden cada OR; minutos y **personas** de cada tipo de OT. Los técnicos de la pestaña *Tecnicos* de la hoja están en `backend/data/tecnicos.csv` (base *Costa* = Bia Barranquilla, *Bogota* = Bia Bogotá): se cargan solos la primera vez y, si faltan, con el botón *Agregar técnicos de la hoja*.

**4. Zonas de los equipos Bia y del tránsito** — `backend/data/zonas_bia.json`: qué OR y zonas (centro, radio y municipios) atiende cada equipo, y el recargo de tránsito de cada zona. Edítalo y reinicia con `./iniciar.sh`.

**5. Operadores de Red** — `backend/data/operadores_red.csv` lista los OR de Colombia, los nombres con que pueden aparecer y los departamentos que atienden. Es una versión inicial: revísala y ajústala si algún OR atiende otros departamentos.

Con *Actualizar cada N min* la app vuelve a traer la pregunta sola, avisa cuántas OTs llegaron y las marca como **Nueva**.

Si OSRM, Nominatim o Metabase responden con una página de error en vez de datos, la app lo trata como si no respondieran: prueba el servidor de respaldo, usa la línea recta o avisa, en lugar de fallar. El backend solo atiende a `localhost` y `127.0.0.1` (`ALLOWED_HOSTS`), así una página web no puede usar tu llave de Metabase a través de él.

> Para decidir y estimar horarios, las distancias son en línea recta multiplicadas por un **factor vial** (1,3 por defecto, ajustable en *Ajustes*); el mapa sí dibuja la ruta por las vías.

Endpoints: `GET /api/health`, `GET /api/metabase/estado`, `GET /api/metabase/ots?card_id=`, `GET /api/catalogo`, `GET /api/operadores`, `GET /api/tecnicos/hoja`, `GET|PUT /api/asignacion/config`, `POST /api/asignar` (con `dia`, `fijas` y `transito`), `POST /api/asignar/lote` (propuesta por cercanía para las OTs elegidas), `POST /api/rutas/trazado`, `GET /api/rutas/estado`, `GET /api/zonas`, `POST /api/utilizacion`, `POST /api/upload` (Excel o CSV).

## Pruebas

```bash
./probar.sh          # backend, frontend y navegador (cierra antes ./iniciar.sh)
./probar.sh rapido   # sin las de navegador
```

- **Backend** (`backend/tests`, pytest): lectura de la pregunta y de archivos, visitas de una misma OT,
  nombres de técnicos y contratistas, qué entra en el plan de un día, reglas de reparto (cerca, libre,
  menor UTR, OTs juntas, lote), respaldos cuando OSRM, Nominatim o Metabase fallan, y la API completa.
  No usan la red ni el `backend/.env` real.
- **Frontend** (`frontend/src/**/*.test.js`, jest): reglas del día, ediciones y cercanía.
- **Navegador** (`e2e/`, Playwright): levantan un Metabase simulado con fechas relativas a hoy, el
  backend y el frontend compilado, y prueban la app como la usa un coordinador: días y filtros por OR,
  *Falta por asignar*, cerradas, ediciones mientras se lee Metabase, técnicos apagados, ajustes
  inválidos, actualización que falla, lotes por cercanía y archivos.

En GitHub las tres corren solas en cada push (`.github/workflows/pruebas.yml`), el backend con Python
3.9 y 3.12. Si una de navegador falla, el resultado trae los registros de los servidores, capturas y
trazas.

## Si algo no funciona

- **«No hay conexión con el backend»**: corre `./iniciar.sh` y revisa `logs/backend-8000.log`.
- **«Metabase no está configurado»**: completa `METABASE_URL` y `METABASE_API_KEY` en `backend/.env`
  (`open -e backend/.env`) y reinicia.
- **«El puerto 8000 está ocupado»**: otro Ruteo sigue abierto; ciérralo con el `kill` que muestra el
  mensaje.
- **Ruteo no cuadra con Olibia**: mira «Si Ruteo no cuadra con Olibia» en la sección de Metabase.
- **Versiones anteriores** dejaban archivos subidos en `backend/uploads/`; ya no se usa y se puede borrar.

## Arquitectura

Cómo está armado (gateway, optimizador, frontend), qué endpoint usa cada pantalla y dónde cambiar cada
regla: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

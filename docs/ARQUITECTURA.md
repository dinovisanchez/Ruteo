# Arquitectura de Ruteo

Cómo se conectan el frontend (la pantalla) y el backend (los servicios), qué hace cada pieza y por dónde pasa una OT desde Metabase hasta el plan del día.

## Vista general

```mermaid
flowchart LR
  subgraph Navegador["Navegador · frontend React (puerto 3000)"]
    App["App.js<br/>día, filtros, lote"]
    Panel["AssignmentPanel<br/>técnicos, contratistas, tipos, ajustes"]
    Vistas["Lista · Mapa · Rutas<br/>Utilización · Tabla completa"]
  end

  subgraph Backend["Backend FastAPI"]
    GW["API Gateway :8000<br/>/api/..."]
    OPT["Optimizer :8003<br/>/assign · /lote"]
    Shared[("shared/<br/>modelos, distancias,<br/>zonas, operadores")]
    Files[("backend/data/<br/>zonas, contratistas,<br/>técnicos, asignacion.json")]
  end

  Metabase[(Metabase)]
  OSRM[(OSRM<br/>rutas por carretera)]
  Nominatim[(Nominatim<br/>geocodificación)]
  Olibia[(Olibia<br/>pendiente de integrar)]

  App --> GW
  Panel --> GW
  Vistas --> GW
  GW --> OPT
  GW --> Metabase
  GW --> Nominatim
  GW --> OSRM
  Vistas -. respaldo si el backend no llega .-> OSRM
  GW --- Shared
  OPT --- Shared
  GW --- Files
  Olibia -. asignación a mano .-> Metabase
```

- El **frontend** solo habla con el **API Gateway** (`http://localhost:8000/api`, o `REACT_APP_API_URL`). La única excepción es OSRM: si el backend no llega, el navegador pide directo los tiempos y el trazado por carretera (`services/osrm.js`).
- El **API Gateway** lee Metabase (o un Excel/CSV con las mismas columnas), ubica las OTs, arma el plan del día y le pide al **Optimizer** que decida. También calcula la utilización (UTR) y traza las rutas.
- El **Optimizer** es el motor: reparte las OTs entre cuadrillas de técnicos (OR-Tools) y contratistas.
- **Olibia** todavía no está conectada: la asignación se hace a mano en Olibia y vuelve a Ruteo a través de Metabase.

## Cómo se arranca

`./iniciar.sh` en la raíz:

1. Crea `backend/.venv` y lo pone al día con `requirements.txt` (versiones fijas que funcionan con Python 3.9 a 3.13).
2. Crea `backend/.env` desde `backend/.env.example` si no existe.
3. Levanta 2 servicios con uvicorn: optimizer `8003` y gateway `8000` (registros en `logs/`). Antes detiene los de una versión anterior, incluidos los servicios de datos y distancias que ya no existen.
4. Espera a que el gateway responda en `/api/health` y avisa si Metabase no está configurado.
5. Instala los paquetes del frontend si cambió `package-lock.json` y arranca `npm start` (puerto 3000).

## Backend

### API Gateway (`backend/api_gateway`, puerto 8000)

| Módulo | Qué hace |
|---|---|
| `main.py` | Crea la app, CORS, el chequeo de host (solo `localhost`/`127.0.0.1`), `/api/health` y monta los routers bajo `/api` |
| `assignment_routes.py` | Endpoints del plan: Metabase, archivo (`/upload`), catálogo, configuración, `/asignar`, `/asignar/lote`, trazado. Aquí está `plan_del_dia` (qué OTs entran el día elegido y a quién quedan fijadas) y el reconocimiento de técnicos por nombre (`responsables`, `tecnicos_mencionados`) |
| `metabase.py` | Llama a la pregunta de Metabase y convierte cada fila en una OT (`filas_a_actividades`). `ALIAS_COLUMNAS` define qué nombres de columna reconoce: situación, fecha, electricistas, creado por, etc. Cada fila es una visita: `_codigos_por_fila` elige la visita vigente de cada OT (la que sigue por asignar o la más reciente) y nombra las anteriores con su fecha. |
| `geocoding.py` | Ubica las OTs sin GPS con Nominatim: municipio enseguida, dirección en segundo plano, con caché en `data/geocache.json`. Las que solo tienen su municipio llevan `ubicacion_municipio` y no cuentan como cerca de nada |
| `trazado.py` | Habla con OSRM: matriz de tiempos por carretera (`matriz_vial`) y trazado de cada ruta (`trazar`), con servidor de respaldo y caché |
| `utilizacion.py` | `/utilizacion`: horas usadas por técnico y día frente a las disponibles (UTR) |
| `archivo.py` | Lee un Excel (`.xlsx`) o CSV (coma o punto y coma, UTF-8 o latin-1) como filas de la pregunta; `/upload` las pasa por `filas_a_actividades` igual que Metabase |

### Optimizer (`backend/services/optimizer_service`, puerto 8003)

| Endpoint | Función | Qué hace |
|---|---|---|
| `POST /assign` | `assignment.asignar` | Decide a quién va cada OT del día y arma las rutas |
| `POST /lote` | `assignment.repartir_lote` | Propuesta para varias OTs elegidas: grupos por cercanía, cada uno con las mismas reglas del plan (cerca, libre, menor UTR) |

Cómo decide `asignar`:

1. Separa las OTs **externas** (su responsable no está en la app) y las **sin ubicación**.
2. Respeta las **fijadas**: asignadas en Metabase a un técnico disponible o a un contratista del catálogo, y las ediciones a mano.
3. Cada OT libre va al **equipo Bia** que cubre su OR y su zona (`data/zonas_bia.json`); si ningún equipo la cubre, a contratistas.
4. Arma **cuadrillas** de 1 o 2 personas según lo que piden las OTs (`armar_cuadrillas`). Un técnico con una OT fijada de 2 personas no sale solo.
5. Junta las OTs libres que están a **2 km o menos** entre sí (`grupos_cercanos`, `radio_grupo_km`): viajan como un solo punto, así las hace una sola cuadrilla. Si un grupo no cabe en ninguna jornada, se separa y se vuelve a resolver.
6. Decide la **cuadrilla de cada grupo libre** con reglas (`repartir_por_reglas`), entre las cuadrillas de su equipo en cuya jornada cabe: primero la que ya tiene OTs a 2 km o menos ese día; si ninguna, una que todavía no tiene OTs; si todas tienen OTs lejos, la de menor carga en la semana (`uso_previo` más lo del día). Cada decisión cuenta para las siguientes.
7. Resuelve un **VRP con OR-Tools** (`_resolver_vrp`) con esas cuadrillas fijas: ordena cada ruta con tiempos por carretera y tránsito y revisa que quepa en la jornada.
8. Lo que no cabe en los técnicos va al **contratista más cercano de su OR** (`_asignar_contratistas`).
9. Devuelve rutas, una **decisión por OT** con su motivo, y métricas.

### Código compartido (`backend/shared`)

| Archivo | Qué contiene |
|---|---|
| `models.py` | Modelos Pydantic: `Activity` (una OT), `Tecnico`, `SedeOperativa`, `JornadaConfig`, `AssignmentRequest`, `AssignmentResult`, `DecisionOT`… Es el contrato entre gateway y optimizer |
| `distancias.py` | Km y minutos entre dos puntos: matriz de OSRM si existe; si no, línea recta × factor vial. Suma el recargo de tránsito de la zona |
| `zonas.py` | Zonas de los equipos Bia y de tránsito; si una OT está en una zona |
| `operadores.py` | Catálogo de OR (Enel, Air-e, Afinia…) y sus nombres alternativos |
| `catalogo.py` | Bases Bia y sedes de contratistas desde `data/contratistas.csv` o la hoja publicada |
| `config.py` | Variables de `backend/.env` |
| `utils.py` | Distancia en línea recta, horas y registros |

### Datos y configuración

| Archivo | Qué guarda | Se edita |
|---|---|---|
| `backend/.env` | Metabase (URL, API key, pregunta), OSRM, geocodificación | A mano; no se sube al repositorio |
| `data/asignacion.json` | Técnicos, contratistas por OR, minutos y personas por tipo de OT | Desde la app (`PUT /api/asignacion/config`) |
| `data/zonas_bia.json` | OR y zonas que cubre cada equipo; recargo de tránsito por ciudad | A mano |
| `data/contratistas.csv` | Bases y sedes de contratistas (sin datos de contacto) | A mano o desde la hoja |
| `data/tecnicos.csv` | Técnicos de la hoja, para cargarlos la primera vez | A mano |
| `data/operadores_red.csv` | OR de Colombia y sus departamentos | A mano |
| `data/geocache.json` | Caché de direcciones ya ubicadas | Solo |

## Frontend (`frontend/src`)

| Archivo | Qué hace |
|---|---|
| `App.js` | Estado de la pantalla: día del plan (y el cambio solo a medianoche), filtros, cuadros, ediciones a mano (`fijas`), selección y asignación por lote. Llama a `/asignar` con la carga de la semana para el reparto parejo. Cada cálculo lleva un número (`turnoRef`) y solo se muestra la respuesta del último; los recálculos piden al panel el pedido con los ajustes de ese momento (`pedido()`) |
| `components/AssignmentPanel.jsx` | Panel izquierdo: técnicos por equipo y disponibilidad, contratistas por OR, tipos de OT y ajustes. Trae las OTs de Metabase, se actualiza solo y arma el pedido del plan |
| `components/AssignmentResults.jsx` | Cuadros que filtran, lista de decisiones con el lápiz para editar y casillas para el lote, «Falta por asignar» y rutas |
| `components/AssignmentMapView.jsx` | Mapa Leaflet: bases, OTs y rutas por carretera |
| `components/UtilizationDashboard.jsx` | Utilización por técnico, por día, semana o mes |
| `components/LoteBar.jsx` | Barra de las OTs seleccionadas: a un técnico, a un contratista o por cercanía |
| `components/LoteModal.jsx` | Propuesta por cercanía: grupos y técnico de cada uno, editable |
| `components/OtsTable.jsx` | Tabla completa con todas las columnas de la pregunta |
| `components/AsignadasCerca.jsx` | Columna «Asignadas cerca» de «Falta por asignar» (lista y tabla completa) |
| `components/TechniciansModal.jsx`, `OrContractorsModal.jsx`, `OtTypesModal.jsx` | Ventanas para editar técnicos, contratistas por OR y tipos de OT |
| `services/api.js` | Todas las llamadas al gateway |
| `services/osrm.js` | OSRM desde el navegador, de respaldo |
| `services/otTypes.js` | Minutos y personas por defecto de cada tipo de OT |
| `services/cercania.js` | Para cada pendiente, las OTs ya asignadas a la distancia «cerca» (en línea recta, en el navegador) |
| `services/plan.js` | Reglas del día que no dependen de la pantalla: qué OTs entran en un día, grupos de pendientes, cuándo el plan quedó viejo, filtros por persona |

## Endpoints y quién los usa

| Endpoint | Qué hace | Lo usa | Llama a |
|---|---|---|---|
| `GET /api/metabase/estado` | Si Metabase está configurado y la pregunta guardada | Panel | — |
| `GET /api/metabase/ots` | Trae las OTs de la pregunta y ubica las que no tienen GPS | Panel (Extraer y recomendar, actualización automática) | Metabase, Nominatim |
| `POST /api/upload` | Lee un Excel/CSV de OTs con las columnas de la pregunta | Panel (Ajustes) | — |
| `GET /api/catalogo` | Bases Bia y sedes de contratistas | App | — |
| `GET /api/operadores` | OR del catálogo para los nombres que traen las OTs | Panel | — |
| `GET /api/zonas` | Equipos con sus zonas y tránsito por ciudad | App (y se los pasa al panel) | — |
| `GET /api/tecnicos/hoja` | Técnicos de la hoja; el panel avisa cuáles faltan en la app | Panel | — |
| `GET/PUT /api/asignacion/config` | Técnicos, contratistas por OR, tipos de OT | Panel y sus ventanas | — |
| `POST /api/asignar` | Plan del día | App (cada cálculo, cambio de día o edición) | OSRM, Optimizer `/assign` |
| `POST /api/asignar/lote` | Propuesta por cercanía para las OTs seleccionadas | App (barra del lote) | OSRM, Optimizer `/lote` |
| `POST /api/utilizacion` | UTR por técnico y día | App (carga de la semana), Utilización | — |
| `POST /api/rutas/trazado` | Geometría de cada ruta por carretera | Mapa | OSRM |
| `GET /api/rutas/estado` | Si el backend llega a OSRM | Diagnóstico | OSRM |

Heredados, sin uso en la pantalla actual: `/api/optimize`, `/api/estimate-crews`, `/api/geographic-summary`, `/api/analyze-proximity`, `/api/optimize-by-clusters`, `/api/info`.

## Flujos

### Extraer y recomendar

```mermaid
sequenceDiagram
  participant P as Panel
  participant A as App
  participant G as Gateway
  participant M as Metabase
  participant N as Nominatim
  participant O as Optimizer
  P->>G: GET /metabase/ots
  G->>M: pregunta (pendientes, asignadas, cerradas del mes)
  G->>N: municipios y direcciones sin GPS
  G-->>P: OTs
  P->>A: pedido del plan (técnicos disponibles, tipos, jornada)
  A->>G: POST /utilizacion (lunes a ayer)
  G-->>A: carga de la semana por técnico
  A->>G: POST /asignar (OTs del día, fijas, uso_previo)
  G->>G: plan_del_dia, coberturas, matriz OSRM
  G->>O: POST /assign
  O-->>G: rutas y decisiones
  G-->>A: plan del día
  A->>G: POST /rutas/trazado (al abrir el mapa)
```

Al abrir la app, cada 10 minutos y al empezar un nuevo día el panel repite este flujo solo (`Actualizar cada N min`).

### Asignar varias OTs por cercanía

```mermaid
sequenceDiagram
  participant U as Usuario
  participant A as App
  participant G as Gateway
  participant O as Optimizer
  U->>A: marca OTs en la lista y elige «Por cercanía»
  A->>G: POST /asignar/lote (el mismo pedido del plan + códigos)
  G->>O: POST /lote
  O-->>A: grupos a 2 km o menos, cada uno al técnico cercano, libre o de menor UTR
  U->>A: revisa y confirma (puede cambiar el técnico de un grupo)
  A->>G: POST /asignar con esas OTs fijadas
  G-->>A: plan nuevo
  A->>A: abre el mapa filtrado en esos técnicos
```

Con un técnico o contratista concreto en la barra no hay propuesta: las OTs quedan fijadas a ese destino y se recalcula el plan.

### De la asignación en Olibia de vuelta a Ruteo

1. En Ruteo se revisa el plan y se asigna en **Olibia** (a mano por ahora).
2. Metabase refleja la asignación (qué tan rápido depende de cómo esté conectado a la base de Olibia): la OT pasa a *Asignada* con su técnico.
3. En la siguiente actualización Ruteo la trae como asignada y la fija a ese técnico.

Para que Ruteo asigne directo en Olibia hace falta la petición que hace Olibia al asignar (Copy as cURL, sin el token) y un usuario de servicio en `backend/.env`.

## Dónde tocar para…

| Cambio | Dónde |
|---|---|
| Una columna nueva de Metabase | La pregunta (SQL en el README) y `ALIAS_COLUMNAS` en `api_gateway/metabase.py`; el campo en `Activity` (`shared/models.py`) |
| Duración o personas de un tipo de OT | En la app: *Tipos de OT*; los valores por defecto en `frontend/src/services/otTypes.js` |
| Qué cubre cada equipo o el tránsito | `backend/data/zonas_bia.json` |
| La distancia «cerca» (juntar OTs y preferir al técnico que ya tiene OTs cerca) | En la app: *Ajustes → Jornada → Distancia «cerca» (km)* (`radio_grupo_km`) |
| El orden de las reglas de reparto | `repartir_por_reglas` en `backend/services/optimizer_service/assignment.py` |
| Cómo decide el motor | `backend/services/optimizer_service/assignment.py` |
| Qué OTs entran en el plan de un día | `plan_del_dia` en `api_gateway/assignment_routes.py` y `entraEnElDia` en `frontend/src/services/plan.js` |

## Pruebas

| Dónde | Qué prueban | Cómo correrlas |
|---|---|---|
| `backend/tests` | pytest: lectura de la pregunta y de archivos, nombres, plan del día, reglas de reparto, respaldos y la API completa con el optimizador en el mismo proceso | `cd backend && .venv/bin/python -m pytest` |
| `frontend/src/**/*.test.js` | jest: `services/plan.js` y `services/cercania.js` | `cd frontend && CI=true npx react-scripts test` |
| `e2e/` | Playwright: la app compilada con un Metabase simulado (`e2e/servidor/metabase_simulado.py`, fechas relativas a hoy) | `cd e2e && npx playwright test` (o `./probar.sh` para todo) |

`.github/workflows/pruebas.yml` corre las tres en cada push.

# Route Optimizer - Sistema de Optimización de Rutas para Cuadrillas

<div align="center">

![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![React](https://img.shields.io/badge/react-18.2-blue.svg)

**Sistema completo de optimización de rutas para cuadrillas de campo con arquitectura de microservicios**

[Características](#-características) • [Instalación](#-instalación-y-ejecución) • [Documentación](#-documentación) • [API](#-api-endpoints) • [Desarrollo](#-desarrollo-local)

</div>

---

## 📋 Descripción

**Route Optimizer** es una aplicación web completa que permite cargar actividades de campo desde archivos Excel/CSV y optimizar las rutas de las cuadrillas minimizando distancias y tiempos de viaje, garantizando que todas las tareas se completen dentro de la jornada laboral.

El sistema utiliza algoritmos avanzados de optimización (VRP/TSP) con Google OR-Tools, clustering geográfico para agrupar actividades cercanas, y caché distribuido con Redis para optimizar el rendimiento.

### Características Principales

- ✅ **Optimización Inteligente**: Utiliza Google OR-Tools para resolver problemas de VRP/TSP
- ✅ **Clustering Geográfico**: Agrupa actividades cercanas usando K-means
- ✅ **Caché Inteligente**: Redis para almacenar matrices de distancia calculadas
- ✅ **Validación de Datos**: Validación automática de GPS y rangos geográficos
- ✅ **Arquitectura de Microservicios**: Servicios independientes y escalables
- ✅ **Interfaz Moderna**: React con Ant Design y mapas interactivos con Leaflet
- ✅ **API RESTful**: Documentación completa con OpenAPI/Swagger
- ✅ **Asignación por OR desde Metabase**: Trae OTs de una pregunta de Metabase y las reparte entre técnicos in-house o el contratista más cercano de cada OR

---

## 🏗️ Arquitectura de Microservicios

El sistema está compuesto por **6 servicios principales** que trabajan de forma coordinada:

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                         │
│                    Puerto: 3000                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 API Gateway (FastAPI)                        │
│                 Puerto: 8000                                 │
│                 • Orquesta las llamadas                      │
│                 • Punto de entrada único                      │
└─────┬───────────────┬───────────────┬───────────────────────┘
      │               │               │
      ▼               ▼               ▼
┌─────────────┐ ┌──────────────┐ ┌──────────────┐
│ Data Service│ │Distance Svc  │ │Optimizer Svc │
│ Puerto:8001 │ │ Puerto:8002  │ │ Puerto:8003  │
│ • Valida    │ │ • Calcula    │ │ • Optimiza   │
│ • Procesa   │ │   distancias │ │   rutas      │
└──────┬──────┘ └──────┬───────┘ └──────┬───────┘
       │               │                │
       └───────────────┴────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │  Redis Cache  │
              │  Puerto:6379  │
              │  • Caché      │
              └───────────────┘
```

### Servicios Detallados

1. **API Gateway** (Puerto 8000)
   - Punto de entrada principal
   - Orquesta las llamadas a los microservicios
   - Maneja autenticación y validación de requests
   - Documentación Swagger/OpenAPI

2. **Data Service** (Puerto 8001)
   - Procesa archivos Excel/CSV
   - Valida estructura de datos
   - Valida coordenadas GPS (rangos de Colombia)
   - Extrae y normaliza actividades

3. **Distance Service** (Puerto 8002)
   - Calcula matrices de distancia usando fórmula Haversine
   - Calcula tiempos de desplazamiento
   - Utiliza Redis para caché de cálculos
   - Optimiza cálculos repetidos

4. **Optimizer Service** (Puerto 8003)
   - Clustering geográfico con K-means
   - Optimización VRP/TSP con Google OR-Tools
   - Estimación de cuadrillas necesarias
   - Validación de viabilidad en jornada laboral

5. **Frontend** (Puerto 3000)
   - Interfaz web React
   - Carga de archivos con drag & drop
   - Visualización de mapas interactivos
   - Panel de métricas y resultados

6. **Redis** (Puerto 6379)
   - Caché distribuido para matrices de distancia
   - Mejora rendimiento en cálculos repetidos
   - Persistencia de datos

---

## 🛠️ Stack Tecnológico

### Backend

| Tecnología | Versión | Uso |
|------------|---------|-----|
| **Python** | 3.10+ | Lenguaje principal |
| **FastAPI** | 0.104.1 | Framework web asíncrono |
| **Uvicorn** | 0.24.0 | Servidor ASGI |
| **Google OR-Tools** | 9.8.3296 | Optimización VRP/TSP |
| **Pandas** | 2.1.3 | Procesamiento de datos |
| **NumPy** | 1.26.2 | Cálculos numéricos |
| **Scikit-learn** | 1.3.2 | Clustering K-means |
| **Geopy** | 2.4.1 | Cálculos geográficos |
| **Redis** | 5.0.1 | Caché distribuido |
| **Pydantic** | 2.5.2 | Validación de datos |
| **OpenPyXL** | 3.1.2 | Procesamiento Excel |
| **HTTPX** | 0.25.2 | Cliente HTTP asíncrono |

### Frontend

| Tecnología | Versión | Uso |
|------------|---------|-----|
| **React** | 18.2.0 | Framework UI |
| **Ant Design** | 5.11.5 | Componentes UI |
| **Leaflet** | 1.9.4 | Mapas interactivos |
| **React-Leaflet** | 4.2.1 | Integración Leaflet-React |
| **Axios** | 1.6.2 | Cliente HTTP |
| **Day.js** | 1.11.10 | Manejo de fechas |

### DevOps

| Tecnología | Uso |
|------------|-----|
| **Docker** | Contenedorización |
| **Docker Compose** | Orquestación de servicios |
| **Nginx** | Servidor estático y reverse proxy |

---

## 📦 Instalación y Ejecución

### Inicio rápido sin Docker (Mac/Linux)

```bash
./iniciar.sh
```

Crea el entorno de Python la primera vez, reinicia los 4 servicios del backend (registros en `logs/`) y abre el frontend en http://localhost:3000. Ctrl+C detiene todo. Úsalo también después de cada `git pull`: así el backend siempre corre la versión nueva.

### Requisitos Previos

- **Docker** 20.10 o superior
- **Docker Compose** 2.0 o superior
- *(Opcional para desarrollo)* Node.js 18+ y Python 3.10+

### Inicio Rápido con Docker

1. **Clonar o navegar al proyecto**
```bash
cd Ruteo
```

2. **Construir e iniciar todos los servicios**
```bash
docker-compose up --build
```

Este comando:
- Construye las imágenes de todos los servicios
- Inicia todos los contenedores
- Configura la red interna
- Muestra los logs en tiempo real

3. **Ejecutar en segundo plano (detached mode)**
```bash
docker-compose up --build -d
```

4. **Acceder a la aplicación**
- **Frontend**: http://localhost:3000
- **API Gateway**: http://localhost:8000/api
- **Documentación Swagger**: http://localhost:8000/docs
- **Documentación ReDoc**: http://localhost:8000/redoc

### Comandos Útiles

**Detener los servicios:**
```bash
docker-compose down
```

**Detener y eliminar volúmenes:**
```bash
docker-compose down -v
```

**Ver logs de todos los servicios:**
```bash
docker-compose logs -f
```

**Ver logs de un servicio específico:**
```bash
docker-compose logs -f api-gateway
docker-compose logs -f optimizer-service
docker-compose logs -f data-service
docker-compose logs -f distance-service
docker-compose logs -f frontend
docker-compose logs -f redis
```

**Reconstruir un servicio específico:**
```bash
docker-compose up --build -d api-gateway
```

**Ver estado de los servicios:**
```bash
docker-compose ps
```

**Verificar salud de los servicios:**
```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/services
```

---

## 📄 Formato de Datos

### Estructura del Archivo

El archivo de actividades debe ser **Excel** (.xlsx, .xls) o **CSV** con las siguientes columnas obligatorias:

| Columna | Tipo | Descripción | Ejemplo | Validación |
|---------|------|-------------|---------|------------|
| `codigo_bia` | string | Código único de actividad | `BIA001` | Requerido, no vacío |
| `servicio` | string | Tipo de servicio | `instalacion` | Requerido, no vacío |
| `gps` | string | Coordenadas GPS | `4.6097,-74.0817` | Formato: `lat,lon` |
| `nombre` | string | Nombre del cliente | `Cliente Ejemplo` | Requerido, no vacío |
| `direccion` | string | Dirección completa | `Calle 123 #45-67` | Requerido, no vacío |
| `ciudad` | string | Ciudad | `Bogotá` | Requerido, no vacío |
| `departamento` | string | Departamento | `Cundinamarca` | Requerido, no vacío |
| `or_operador` | string | Código del operador | `OP001` | Requerido, no vacío |

### Formato de GPS

El campo `gps` debe tener el formato: **`latitud,longitud`** (separados por coma)

**Ejemplos válidos:**
- `4.6097,-74.0817`
- `4.6097, -74.0817` (los espacios se eliminan automáticamente)
- `4,-74`
- `-4.6097,74.0817`

**Validaciones:**
- ✅ Latitud: entre -90 y 90
- ✅ Longitud: entre -180 y 180
- ✅ Debe estar dentro de los límites de Colombia
- ✅ Solo números separados por coma

### Ejemplo de Archivo CSV

```csv
codigo_bia,servicio,gps,nombre,direccion,ciudad,departamento,or_operador
BIA001,instalacion,"4.6097,-74.0817",Cliente 1,Calle 123 #45-67,Bogotá,Cundinamarca,OP001
BIA002,mantenimiento,"4.6500,-74.1000",Cliente 2,Calle 456 #78-90,Bogotá,Cundinamarca,OP002
BIA003,instalacion,"4.6200,-74.0900",Cliente 3,Carrera 789 #12-34,Bogotá,Cundinamarca,OP001
```

### Ejemplo de Archivo Excel

| codigo_bia | servicio | gps | nombre | direccion | ciudad | departamento | or_operador |
|------------|----------|-----|--------|-----------|--------|--------------|-------------|
| BIA001 | instalacion | 4.6097,-74.0817 | Cliente 1 | Calle 123 #45-67 | Bogotá | Cundinamarca | OP001 |
| BIA002 | mantenimiento | 4.6500,-74.1000 | Cliente 2 | Calle 456 #78-90 | Bogotá | Cundinamarca | OP002 |

**Nota:** Las columnas pueden tener mayúsculas/minúsculas diferentes, el sistema las normaliza automáticamente.

---

## 🚀 Uso de la Aplicación

La arquitectura (servicios, endpoints, qué pantalla usa cada uno y los flujos) está en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

Ruteo es una sola pantalla: pulsa **Extraer y recomendar** (arriba a la derecha) y la app trae las OTs de la pregunta de Metabase y arma el **plan del día**: a quién enviar cada OT y por qué. Arriba se elige la vista (*Lista*, *Mapa*, *Rutas* o *Tabla completa* con todas las columnas de la pregunta) y se filtra. A la izquierda, en secciones plegables, están los **técnicos** de cada equipo (con un interruptor de disponibilidad), los contratistas por OR, los tipos de OT y los *Ajustes*. La **barra de herramientas** del borde izquierdo esconde y muestra ese panel (la app recuerda cómo lo dejaste) y con sus iconos lo abre directo en *Técnicos*, *Contratistas por OR*, *Tipos de OT* o *Ajustes*; en pantallas pequeñas el panel empieza escondido y se abre sobre el contenido.

### Plan del día

- **Día a día.** En la barra de filtros eliges el día (flechas o calendario). Un día muestra **las OTs con fecha de visita ese día**, asignadas o pendientes, igual que Olibia. Solo el plan de **hoy** suma además las pendientes **vencidas** («Vencida: era el …») y las pendientes **sin fecha**, para que no queden sin planear. Debajo del estado de cada OT se ve su fecha («Visita el 29 oct», «Vencida: era el 25 oct», «Sin fecha de visita»). Al cambiar de día, la lista no muestra nada del día anterior mientras se calcula el nuevo plan; un día sin OTs lo dice. Las vistas que no son de un día (*Falta por asignar*, y en la *Tabla completa* «Sin fecha» y «Todas las fechas») ponen «Todas las fechas» o «Sin fecha» en la caja de la fecha; al elegir un día vuelves a su plan.
- **Ya asignadas.** Si en Metabase la OT está asignada a un técnico de la app (se reconoce por el nombre en *Electricistas asignados*, aunque venga en mayúsculas o con el segundo nombre) y ese técnico está **marcado como disponible**, la OT se queda con él y entra en su ruta (candado en la tabla). Si no está disponible, la app la reasigna. Si está asignada a un contratista del catálogo, se queda con ese contratista; si el responsable no está en la app, aparece como **Externo** y no entra en las rutas.
- **Se actualiza sola.** Con *Actualizar cada N min* encendido (viene encendido y la app lo recuerda), el plan se carga solo al abrir la app, se vuelve a traer de Metabase cada N minutos y al volver a la pestaña si pasó más que eso. Al empezar un nuevo día (a medianoche o cuando el computador despierta otro día), si estabas viendo *Hoy* pasa al nuevo día y rehace el plan: las pendientes que quedaron sin asignar entran como "Pendiente desde…". Con el interruptor apagado solo recalcula con las OTs ya cargadas.
- **Pendientes.** La app sugiere a quién enviarlas con las reglas de abajo, llenando la jornada de los técnicos disponibles junto con lo que ya tienen asignado.
- **Filtros.** Buscar por nombre (cliente, OT, dirección, técnico, contratista o quién la creó), fecha, *Todas · Por asignar · Asignadas*, *Asignado a* (uno o varios técnicos, contratistas o externos) y **OR** (uno o varios; junta las formas en que Metabase escribe el mismo OR, por ejemplo "AFINIA - CARIBEMAR DE LA COSTA" y "Afinia"). El filtro de OR solo cambia lo que se ve, no el plan (para calcular el plan solo con algunos OR está *Ajustes → Filtrar por OR*). Las tarjetas del resumen cuentan lo que seleccionas: si eliges un técnico en *Asignado a*, muestran sus OTs, sus asignadas y por asignar, los km y las horas de su ruta. También son filtros (*Asignadas*, *Por asignar*, *Técnicos Bia*, *Contratistas*, *Externas*, *Sin asignar*): al tocar una se filtra por ella, al tocarla otra vez se quita, y se pueden combinar (por ejemplo *Por asignar* + *Contratistas*); *OTs del día* quita esos filtros. *Por asignar* son las pendientes que entran en el plan del día elegido; **Falta por asignar** (tarjeta y botón en la barra) son **todas** las pendientes de Metabase sin importar la fecha. Al tocarla la lista muestra cada una con su fecha de visita (vencidas primero, luego para hoy, próximos días y sin fecha), a quién la manda el plan si entra en el día que estás viendo y un botón *Planear hoy* / *Planear el …* que abre el plan de ese día. La búsqueda y *Asignado a* también la filtran. Todo filtra la lista, el mapa, las rutas y la tabla completa.
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

Los técnicos se reconocen en *Electricistas asignados* aunque el nombre venga con segundo nombre, en mayúsculas o con otra ortografía (Jhonatan / Jonathan, Gelvez / Gelver). Los técnicos de la pestaña *Tecnicos* de la hoja se agregan solos a la app. Si alguien aparece en Metabase como técnico de Bia pero no está registrado, la app lo avisa en lugar de tratarlo como externo.

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

La pregunta se elige en *Ajustes → Fuente de datos → Cambiar pregunta* (también se puede poner en `METABASE_CARD_ID`); la app no muestra su número. La pregunta necesita una columna con el OR; el código de la OT (`Bia Code`, `OT`…) es recomendable. La ubicación puede venir como `GPS` ("lat, lon"), como `Latitud`/`Longitud`, o solo como `Dirección` + `Ciudad`; en ese caso la OT se geocodifica con OpenStreetMap y se marca como **ubicación aproximada**: primero se ubica por su municipio (son pocos y se buscan enseguida, así ninguna OT queda sin ubicación) y la dirección exacta se busca en segundo plano para la siguiente extracción. Una OT asignada que aun así no tiene ubicación se queda con su técnico o contratista, aunque no entre en la ruta ni en el mapa. Los nombres de columna en español se reconocen solos; si no, defínelos con `METABASE_COLUMN_MAP`. Para el plan del día, la pregunta debe traer también las OTs asignadas con *Situación*, *Fecha de la visita*, *Electricistas asignados* y *Contratista asignado*. Esta consulta SQL sobre `operations.visitas_general` sirve:

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
  created_by AS "Creado por",
  created_at AS "Fecha de creación"
FROM operations.visitas_general
WHERE deleted_at IS NULL
  AND (
    -- Pendientes por asignar (sin las de cierre vencido)
    (status = 'PENDING' AND status_app = 'PENDING_ASSIGNMENT' AND estado IN ('Por asignar', 'Cambio de Contratista'))
    -- Asignadas y activas, de la última semana en adelante
    OR (status = 'PENDING' AND estado IN ('Asignada', 'Reasignado') AND fecha_visita >= CURRENT_DATE - INTERVAL '7 days')
    -- Visitas hechas por técnicos de Bia desde el mes pasado: para la utilización (UTR)
    OR (estado IN ('Cierre Exitoso', 'Cierre Fallido', 'Completada')
        AND fecha_visita >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
        AND COALESCE(electricistas, '') <> ''
        AND (contratista ILIKE '%bia%' OR COALESCE(contratista, '') = ''))
  )
ORDER BY fecha_visita NULLS LAST, card_id;
```

**Quién creó la OT.** `Creado por` y `Fecha de creación` salen en la lista (debajo de cada OT), en la tabla completa, en el CSV y en la búsqueda. `created_by` y `created_at` son los nombres más comunes: confirma en Metabase cómo se llaman en `operations.visitas_general` (al editar la pregunta, en la lista de columnas de la tabla). Si `created_by` trae un id y no un nombre, cruza con la tabla de usuarios para traer el nombre, por ejemplo `LEFT JOIN <tabla de usuarios> u ON u.id = v.created_by` y `u.name AS "Creado por"`. La app reconoce también `Creada por`, `Creador` y `Created by`.

Las visitas cerradas solo sirven para la utilización: no entran al plan salvo las del mismo día (que ya ocuparon tiempo de su técnico). La última condición toma las de técnicos de Bia; si en Metabase el contratista de Bia se llama distinto, ajusta `contratista ILIKE '%bia%'`.

**2. Catálogo de bases y contratistas** — `backend/data/contratistas.csv` es la hoja *Data Contratista* (sin datos de contacto). Para leerla directamente de Google Sheets, publícala como CSV y pon la URL en `CONTRATISTAS_CSV_URL`.

**3. Técnicos, contratistas por OR y tipos de OT** — se editan desde la app y se guardan en `backend/data/asignacion.json`: técnicos con base (por defecto Bia Bogotá) y **costo por día**; contratistas que atienden cada OR; minutos y **personas** de cada tipo de OT. Los técnicos de la pestaña *Tecnicos* de la hoja están en `backend/data/tecnicos.csv` (base *Costa* = Bia Barranquilla, *Bogota* = Bia Bogotá): se cargan solos la primera vez y, si faltan, con el botón *Agregar técnicos de la hoja*.

**4. Zonas de los equipos Bia y del tránsito** — `backend/data/zonas_bia.json`: qué OR y zonas (centro, radio y municipios) atiende cada equipo, y el recargo de tránsito de cada zona. Edítalo y reinicia con `./iniciar.sh`.

**5. Operadores de Red** — `backend/data/operadores_red.csv` lista los OR de Colombia, los nombres con que pueden aparecer y los departamentos que atienden. Es una versión inicial: revísala y ajústala si algún OR atiende otros departamentos.

Con *Actualizar cada N min* la app vuelve a traer la pregunta sola, avisa cuántas OTs llegaron y las marca como **Nueva**.

> Para decidir y estimar horarios, las distancias son en línea recta multiplicadas por un **factor vial** (1,3 por defecto, ajustable en *Ajustes*); el mapa sí dibuja la ruta por las vías.

Endpoints: `GET /api/metabase/estado`, `GET /api/metabase/ots?card_id=`, `GET /api/catalogo`, `GET /api/operadores`, `GET /api/tecnicos/hoja`, `GET|PUT /api/asignacion/config`, `POST /api/asignar` (con `dia`, `fijas` y `transito`), `POST /api/asignar/lote` (propuesta por cercanía para las OTs elegidas), `POST /api/rutas/trazado`, `GET /api/rutas/estado`, `GET /api/zonas`, `POST /api/utilizacion`.

---

## 🔌 API Endpoints

### Base URL
```
http://localhost:8000/api
```

### Endpoints Disponibles

#### 1. Health Check

**GET** `/health`
- Verifica el estado del API Gateway
- **Respuesta:**
```json
{
  "status": "healthy",
  "service": "api-gateway",
  "timestamp": "2024-01-15T10:30:00",
  "version": "1.0.0"
}
```

#### 2. Health Check de Servicios

**GET** `/health/services`
- Verifica el estado de todos los microservicios
- **Respuesta:**
```json
{
  "api-gateway": {"status": "healthy"},
  "data-service": {"status": "healthy"},
  "distance-service": {"status": "healthy"},
  "optimizer-service": {"status": "healthy"},
  "redis": {"status": "healthy"}
}
```

#### 3. Información de la API

**GET** `/info`
- Obtiene información sobre la API y sus endpoints
- **Respuesta:**
```json
{
  "name": "Route Optimizer",
  "version": "1.1.0",
  "description": "Microservices-based route optimization system",
  "endpoints": {...},
  "services": {...}
}
```

#### 4. Cargar Archivo

**POST** `/upload`
- Sube y procesa un archivo de actividades
- **Content-Type:** `multipart/form-data`
- **Parámetros:**
  - `file`: Archivo Excel o CSV
- **Respuesta:**
```json
{
  "success": true,
  "message": "Successfully loaded 25 activities",
  "total_activities": 25,
  "activities": [...],
  "gateway_file_id": "uuid-here"
}
```

#### 5. Optimizar Rutas

**POST** `/optimize`
- Ejecuta la optimización completa de rutas
- **Content-Type:** `application/json`
- **Body:**
```json
{
  "nombre_lote": "Lote Bogotá Norte",
  "actividades": [
    {
      "codigo_bia": "BIA001",
      "servicio": "instalacion",
      "gps": "4.6097,-74.0817",
      "nombre": "Cliente 1",
      "direccion": "Calle 123",
      "ciudad": "Bogotá",
      "departamento": "Cundinamarca",
      "or_operador": "OP001"
    }
  ],
  "configuracion": {
    "horario_inicio": "08:00:00",
    "horario_fin": "17:00:00",
    "horas_laborales": 8.0,
    "velocidad_promedio_kmh": 30.0,
    "punto_partida": {
      "latitude": 4.6097,
      "longitude": -74.0817
    },
    "tiempos_servicio": [
      {
        "servicio": "instalacion",
        "duracion_minutos": 60
      }
    ],
    "incluir_retorno": true
  }
}
```
- **Respuesta:**
```json
{
  "nombre_lote": "Lote Bogotá Norte",
  "fecha_optimizacion": "2024-01-15T10:30:00",
  "total_actividades": 25,
  "cuadrillas_necesarias": 3,
  "rutas": [...],
  "distancia_total_km": 135.5,
  "viable_en_un_dia": true,
  "metricas": {...}
}
```

#### 6. Estimar Cuadrillas

**POST** `/estimate-crews`
- Estima el número de cuadrillas necesarias sin optimizar
- **Content-Type:** `application/json`
- **Body:** Mismo formato que `/optimize`
- **Respuesta:**
```json
{
  "estimated_crews": 3,
  "estimated_distance_km": 120.5,
  "estimated_time_hours": 24.0
}
```

#### 7. Resumen Geográfico

**POST** `/geographic-summary`
- Obtiene estadísticas geográficas de las actividades
- **Content-Type:** `application/json`
- **Body:** Lista de actividades
- **Respuesta:**
```json
{
  "total_activities": 25,
  "bounding_box": {
    "min_lat": 4.5,
    "max_lat": 4.7,
    "min_lon": -74.1,
    "max_lon": -74.0
  },
  "centroid": {
    "latitude": 4.6,
    "longitude": -74.05
  },
  "cities": {...},
  "departments": {...}
}
```

#### 8. Optimizar por Lotes (Proximidad)

**POST** `/optimize-by-clusters`
- Analiza actividades por proximidad y optimiza rutas por lote
- **Content-Type:** `application/json`
- **Query Parameters:**
  - `max_distance_km`: Distancia máxima para agrupar (default: 20.0)
  - `method`: Método de clustering - "proximity" o "kmeans" (default: "proximity")
- **Body:** ActivityLot (igual formato que `/optimize`)
- **Respuesta:**
```json
{
  "nombre_lote": "Lote de 25 Actividades",
  "total_actividades": 25,
  "clustering_info": {
    "num_clusters": 5,
    "clusters": [...],
    "metricas_globales": {...}
  },
  "rutas_por_cluster": [
    {
      "cluster_id": 0,
      "cluster_info": {...},
      "ruta": {
        "cuadrilla_id": 1,
        "paradas": [...],
        "distancia_total_km": 45.5,
        "tiempo_total_minutos": 480,
        "viable": true
      },
      "punto_partida_optimo": {...},
      "distancia_desde_punto_partida_km": 12.5
    }
  ],
  "distancia_total_km": 135.5,
  "tiempo_total_minutos": 2400,
  "metricas": {...}
}
```

### Documentación Interactiva

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 💻 Desarrollo Local

### Requisitos

- Python 3.10+
- Node.js 18+
- Redis (opcional, puede usar Docker)
- pip y npm

### Backend

1. **Crear entorno virtual**
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

2. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

3. **Iniciar servicios individualmente**

**Terminal 1 - API Gateway:**
```bash
cd backend
uvicorn api_gateway.main:app --reload --port 8000
```

**Terminal 2 - Data Service:**
```bash
cd backend
uvicorn services.data_service.main:app --reload --port 8001
```

**Terminal 3 - Distance Service:**
```bash
cd backend
uvicorn services.distance_service.main:app --reload --port 8002
```

**Terminal 4 - Optimizer Service:**
```bash
cd backend
uvicorn services.optimizer_service.main:app --reload --port 8003
```

**Terminal 5 - Redis (si no usa Docker):**
```bash
redis-server
```

### Frontend

1. **Instalar dependencias**
```bash
cd frontend
npm install
```

2. **Iniciar servidor de desarrollo**
```bash
npm start
```

El frontend se iniciará en http://localhost:3000

### Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```env
# Service URLs
DATA_SERVICE_URL=http://localhost:8001
DISTANCE_SERVICE_URL=http://localhost:8002
OPTIMIZER_SERVICE_URL=http://localhost:8003

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Logging
LOG_LEVEL=INFO

# Upload
UPLOAD_DIR=./backend/uploads
MAX_UPLOAD_SIZE=10485760
```

---

## 📁 Estructura del Proyecto

```
Ruteo/
├── backend/
│   ├── api_gateway/              # API Gateway principal
│   │   ├── __init__.py
│   │   ├── main.py              # Aplicación FastAPI
│   │   ├── routes.py            # Definición de endpoints
│   │   ├── orchestrator.py      # Orquestador de servicios
│   │   └── Dockerfile
│   │
│   ├── services/
│   │   ├── data_service/        # Servicio de procesamiento de datos
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── service.py       # Lógica de procesamiento
│   │   │   ├── validators.py    # Validadores de datos
│   │   │   └── Dockerfile
│   │   │
│   │   ├── distance_service/     # Servicio de cálculo de distancias
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── service.py
│   │   │   ├── calculator.py    # Cálculos Haversine
│   │   │   └── Dockerfile
│   │   │
│   │   └── optimizer_service/    # Servicio de optimización
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── service.py
│   │       ├── optimizer.py           # Optimización OR-Tools
│   │       ├── clustering.py          # Clustering K-means y proximidad
│   │       ├── proximity_analysis.py   # Análisis y optimización por lotes
│   │       └── Dockerfile
│   │
│   ├── shared/                   # Código compartido
│   │   ├── __init__.py
│   │   ├── models.py           # Modelos Pydantic
│   │   ├── config.py           # Configuración
│   │   └── utils.py             # Utilidades
│   │
│   ├── uploads/                  # Archivos subidos (volumen Docker)
│   └── requirements.txt         # Dependencias Python
│
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUploader.jsx          # Componente de carga
│   │   │   ├── ConfigPanel.jsx           # Panel de configuración
│   │   │   ├── ProximityPanel.jsx        # Panel de lotes por proximidad
│   │   │   ├── MapView.jsx               # Visualización de mapas (modo estándar)
│   │   │   ├── ClusterMapView.jsx        # Visualización de mapas (modo lotes)
│   │   │   ├── ClusterSelectionPanel.jsx  # Panel de selección de lotes
│   │   │   ├── ClusterResults.jsx        # Resultados de clustering
│   │   │   ├── MetricsPanel.jsx          # Panel de métricas
│   │   │   └── RouteDetails.jsx          # Detalles de rutas
│   │   ├── services/
│   │   │   └── api.js             # Cliente API
│   │   ├── App.js                 # Componente principal
│   │   ├── App.css
│   │   ├── index.js
│   │   └── index.css
│   ├── Dockerfile
│   ├── nginx.conf               # Configuración Nginx
│   └── package.json
│
├── docker-compose.yml           # Orquestación de servicios
├── .env.example                # Ejemplo de variables de entorno
├── .gitignore
└── README.md                   # Este archivo
```

---

## 🔧 Configuración Avanzada

### Configuración de Optimización

Los parámetros de optimización se pueden ajustar en `backend/shared/config.py`:

```python
# Máximo de actividades por cuadrilla
MAX_ACTIVITIES_PER_CREW: int = 20

# Mínimo de actividades por cuadrilla
MIN_ACTIVITIES_PER_CREW: int = 1

# Timeout de optimización (segundos)
OPTIMIZATION_TIMEOUT_SECONDS: int = 300  # 5 minutos
```

### Configuración de Redis

```python
# Tiempo de vida del caché (segundos)
CACHE_TTL: int = 3600  # 1 hora

# Host y puerto de Redis
REDIS_HOST: str = "redis"
REDIS_PORT: int = 6379
```

### Configuración de CORS

Para permitir acceso desde otros dominios, editar `backend/shared/config.py`:

```python
CORS_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://tu-dominio.com"
]
```

---

## 🐛 Troubleshooting

### Error de conexión a servicios

**Síntoma:** Los servicios no se pueden conectar entre sí

**Solución:**
```bash
docker-compose down
docker network prune
docker-compose up --build
```

### Redis no conecta

**Síntoma:** Errores de conexión a Redis

**Verificación:**
```bash
docker-compose ps redis
docker-compose logs redis
```

**Solución:**
```bash
docker-compose restart redis
```

### Frontend no muestra el mapa

**Síntoma:** El mapa no se carga o aparece en blanco

**Solución:**
```bash
cd frontend
npm install leaflet react-leaflet
npm start
```

### Error al procesar archivo Excel

**Síntoma:** Error al leer archivos Excel

**Solución:**
- Verificar que el archivo no esté abierto en otra aplicación
- Verificar formato de columnas (deben coincidir exactamente)
- Verificar que el archivo no esté corrupto

### Error de validación GPS

**Síntoma:** "Invalid GPS format" o "GPS out of Colombia bounds"

**Solución:**
- Verificar formato: debe ser `lat,lon` (ej: `4.6097,-74.0817`)
- Verificar que las coordenadas estén dentro de Colombia:
  - Latitud: -4.2 a 13.4
  - Longitud: -81.8 a -66.9

### Servicios no inician

**Síntoma:** Los contenedores se detienen inmediatamente

**Solución:**
```bash
# Ver logs detallados
docker-compose logs -f

# Verificar puertos disponibles
netstat -an | grep 8000
netstat -an | grep 3000
netstat -an | grep 6379

# Reconstruir sin caché
docker-compose build --no-cache
docker-compose up
```

### Optimización toma mucho tiempo

**Síntoma:** La optimización no termina

**Solución:**
- Reducir el número de actividades (< 100 recomendado por lote)
- Aumentar el timeout en `config.py`
- Verificar que Redis esté funcionando (caché ayuda)

---

## 📊 Algoritmos y Métodos

### Optimización de Rutas

El sistema utiliza **Google OR-Tools** para resolver el problema de **Vehicle Routing Problem (VRP)**:

- **Algoritmo**: Solución híbrida con metaheurísticas
- **Objetivo**: Minimizar distancia total
- **Restricciones**:
  - Tiempo máximo de jornada laboral
  - Capacidad máxima por cuadrilla
  - Tiempos de servicio
  - Punto de partida y retorno

### Clustering Geográfico

El sistema ofrece dos métodos de clustering:

1. **K-means** para agrupar actividades cercanas:
   - Reduce la complejidad del problema
   - Agrupa actividades por proximidad geográfica
   - Mejora la eficiencia de la optimización

2. **Clustering por Proximidad**:
   - Agrupa actividades dentro de una distancia máxima
   - Método más simple y directo
   - Ideal para zonas geográficas definidas
   - Cada grupo se optimiza independientemente

### Cálculo de Distancias

**Fórmula de Haversine** para calcular distancias geodésicas:

- Precisión: ~99.5% para distancias cortas
- Considera la curvatura de la Tierra
- Caché con Redis para optimizar cálculos repetidos

---

## 🧪 Pruebas

### Pruebas Manuales

1. **Health Checks:**
```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/services
```

2. **Upload de archivo:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@Pruebas/Pruebas_ruteo.xlsx"
```

3. **Optimización:**
```bash
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d @test_data.json
```

### Archivos de Prueba

El proyecto incluye un archivo de ejemplo en `Pruebas/Pruebas_ruteo.xlsx` para pruebas.

---

## 📝 Notas de Desarrollo

### Convenciones de Código

- **Backend**: PEP 8 (Python)
- **Frontend**: ESLint con configuración de React
- **Commits**: Mensajes descriptivos en español o inglés

### Mejores Prácticas

- ✅ Validación de datos en cada capa
- ✅ Manejo de errores robusto
- ✅ Logging estructurado
- ✅ Documentación de código
- ✅ Separación de responsabilidades
- ✅ Principios SOLID

---

## 🔐 Seguridad

### Consideraciones Actuales

- Validación de tipos de archivo
- Validación de tamaños de archivo
- Validación de rangos GPS
- Sanitización de inputs

### Recomendaciones para Producción

- [ ] Autenticación y autorización (JWT, OAuth)
- [ ] Rate limiting
- [ ] HTTPS/TLS
- [ ] Validación de CORS más estricta
- [ ] Logging de seguridad
- [ ] Encriptación de datos sensibles

---

## 📈 Roadmap

### Funcionalidades Futuras

- [ ] Múltiples puntos de partida
- [ ] Restricciones de ventanas de tiempo
- [ ] Priorización de actividades
- [ ] Historial de optimizaciones
- [ ] Exportación a PDF
- [ ] Integración con mapas de Google Maps
- [ ] Dashboard de métricas históricas
- [ ] API de webhooks para notificaciones
- [ ] Modo offline para frontend
- [ ] Comparación de múltiples escenarios de optimización
- [ ] Edición manual de rutas en el mapa
- [ ] Exportación de rutas a formato GPX para navegación
- [ ] Integración con sistemas de gestión de campo

## 🆕 Últimas Actualizaciones

### Versión 1.1 - Funcionalidad de Lotes por Proximidad

**Nuevas Características:**
- ✅ **Generación de lotes por proximidad geográfica**
  - Clustering automático de actividades cercanas
  - Dos métodos: proximidad simple y K-means
  - Configuración de distancia máxima para agrupación
  
- ✅ **Optimización independiente por lote**
  - Cada lote se optimiza como una unidad separada
  - Punto de partida optimizado (centroide del lote)
  - Validación de viabilidad por lote
  
- ✅ **Visualización avanzada de lotes**
  - Mapa interactivo dedicado para rutas de lotes
  - Panel de selección con checkboxes
  - Colores únicos por lote
  - Leyenda interactiva
  
- ✅ **Mejoras en la interfaz**
  - Tabs para cambiar entre modos de optimización
  - Panel de selección de lotes arriba del mapa
  - Información detallada de cada lote
  - Métricas globales y por lote

**Correcciones:**
- ✅ Validación correcta de `cuadrilla_id` (corregido bug de índice 0)
- ✅ Manejo robusto de clusters vacíos
- ✅ Mejoras en la estructura de componentes React

---

## 🤝 Contribución

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

---

## 👥 Autores

**Route Optimizer Team**

- Desarrollo y arquitectura
- Optimización de algoritmos
- Interfaz de usuario

---

## 🙏 Agradecimientos

- **Google OR-Tools** - Herramientas de optimización
- **Ant Design** - Componentes UI
- **Leaflet** - Mapas interactivos
- **FastAPI** - Framework web moderno
- **React** - Biblioteca UI

---

## 📞 Soporte

Para soporte, por favor:
- Abre un issue en el repositorio
- Revisa la documentación en `/docs`
- Consulta la documentación interactiva en http://localhost:8000/docs

---

<div align="center">

**Route Optimizer** - Optimizando rutas, maximizando eficiencia

Made with ❤️ by Route Optimizer Team

</div>

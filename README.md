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

La aplicación ofrece dos modos principales de optimización:

### Modo 1: Optimización Estándar

Este modo optimiza todas las actividades en un solo proceso de optimización.

1. **Cargar Archivo**
   - Accede a http://localhost:3000
   - Arrastra y suelta un archivo Excel o CSV
   - O haz clic para seleccionar el archivo
   - El sistema valida y muestra una vista previa

2. **Configurar Parámetros**
   - **Nombre del lote**: Identificador del lote de actividades
   - **Horario laboral**:
     - Hora de inicio (ej: 08:00)
     - Hora de fin (ej: 17:00)
     - Horas laborales totales (ej: 8.0)
   - **Velocidad promedio**: Velocidad de desplazamiento en km/h (ej: 30)
   - **Punto de partida**: Coordenadas GPS del punto de inicio (lat,lon)
   - **Tiempos de servicio**: Duración en minutos por tipo de servicio
     - Ej: instalacion: 60 minutos
     - Ej: mantenimiento: 45 minutos
   - **Capacidad máxima** (opcional): Límite de actividades por cuadrilla

3. **Optimizar Rutas**
   - Haz clic en "Optimizar Rutas"
   - El sistema procesa:
     - Validación de datos
     - Cálculo de distancias
     - Clustering geográfico
     - Optimización de rutas
   - Los resultados se muestran en segundos o minutos dependiendo del tamaño

4. **Visualizar Resultados**
   - **Métricas generales**:
     - Total de actividades
     - Cuadrillas necesarias
     - Distancia total
     - Utilización promedio
     - Viabilidad en un día
   - **Mapa interactivo**:
     - Marcadores numerados por secuencia
     - Rutas coloreadas por cuadrilla
     - Popups con información detallada
   - **Tabla de rutas**:
     - Detalles de cada cuadrilla
     - Horarios de llegada y salida
     - Distancias y tiempos
     - Exportación a JSON

### Modo 2: Lotes por Proximidad

Este modo agrupa actividades por proximidad geográfica y optimiza cada lote independientemente, ideal para distribuir trabajo en zonas específicas.

1. **Cargar Archivo** (igual que el Modo 1)

2. **Configurar Parámetros de Proximidad**
   - **Distancia máxima**: Distancia en km para agrupar actividades (ej: 20 km)
   - **Método de clustering**: 
     - **Proximidad**: Agrupa actividades cercanas entre sí
     - **K-means**: Agrupa usando clustering geográfico K-means
   - El sistema usa configuración por defecto para tiempos de servicio

3. **Generar Lotes y Optimizar**
   - Haz clic en "Generar Lotes por Proximidad"
   - El sistema:
     - Analiza la proximidad geográfica de las actividades
     - Crea lotes basados en la distancia máxima
     - Optimiza la ruta de cada lote independientemente
     - Calcula métricas por lote y globales

4. **Visualizar Resultados de Lotes**
   - **Resumen de lotes**:
     - Total de lotes generados
     - Actividades por lote
     - Métricas de cada lote (distancia, tiempo, viabilidad)
     - Tabla detallada con información geográfica
   
   - **Panel de selección de lotes**:
     - Checkboxes para seleccionar qué lotes visualizar
     - Información de cada lote (actividades, distancia, viabilidad)
     - Botones para seleccionar/deseleccionar todos
     - Contador de lotes seleccionados
   
   - **Mapa interactivo de lotes**:
     - Visualización de rutas de los lotes seleccionados
     - Cada lote con un color único
     - Marcadores numerados por secuencia en cada ruta
     - Punto de partida optimizado por lote
     - Polylines coloreadas mostrando la ruta completa
     - Leyenda con información de lotes visibles
     - Popups con detalles de cada parada
   
   - **Detalles expandibles**:
     - Información completa de cada lote
     - Lista de actividades por lote
     - Métricas de ruta optimizada
     - Exportación de resultados a JSON

### Modo 3: Asignación por OR (Metabase)

Pestaña **Asignación OR**. Trae las OTs de una pregunta de Metabase, las filtra por OR y decide quién las atiende:

- **Técnicos in-house**: marcas los técnicos que salen ese día y cada uno sale desde su base de Bia. Las OTs se reparten entre ellos de forma equilibrada; las que no caben en la jornada quedan como *sin asignar*.
- **Contratistas**: para cada OT se elige la sede más cercana entre los contratistas que atienden su OR (se definen en **Contratistas por OR**). Si el OR no tiene lista, se elige el más cercano de todos. Luego se arman las cuadrillas mínimas de cada sede para que todo quepa en la jornada; las OTs que ni solas caben en un día quedan en un *viaje de más de una jornada*.

**1. Configurar Metabase** — copia `backend/.env.example` como `backend/.env` y completa:

```env
METABASE_URL=https://metabase.tu-empresa.com
METABASE_API_KEY=...            # o METABASE_USERNAME / METABASE_PASSWORD
METABASE_CARD_ID=123            # el número en la URL /question/123-...
```

La pregunta debe tener, como mínimo, una columna con el código de la OT y otra con el OR. La ubicación puede venir como `GPS` ("lat, lon"), como `Latitud`/`Longitud`, o solo como `Dirección` + `Municipio`; en ese caso la OT se geocodifica con OpenStreetMap y se marca como **ubicación aproximada**. Los nombres de columna en español se reconocen solos (OT, Orden de trabajo, Operador de red, Tipo de servicio, Municipio, Dirección…); si no, defínelos con `METABASE_COLUMN_MAP`.

**2. Catálogo de bases y contratistas** — `backend/data/contratistas.csv` es la hoja *Data Contratista* (sin datos de contacto). Para leerla directamente de Google Sheets, publícala como CSV y pon la URL en `CONTRATISTAS_CSV_URL`.

**3. Técnicos, contratistas por OR y tipos de OT** — se editan desde la app y se guardan en `backend/data/asignacion.json`:
- **Técnicos in-house**: nombre, base (por defecto Bia Bogotá) y **costo por día**. El resultado muestra el costo de cada cuadrilla y el total.
- **Tipos de OT**: minutos y **personas** de cada tipo. Por defecto Instalación, Emergencia y Normalización medida piden 2 personas. Esas OTs solo se asignan a parejas: la app sugiere las parejas que hacen falta en cada base, o puedes armarlas a mano con el selector *Pareja* junto a cada técnico.

La tabla **Todas las OTs** muestra todas las columnas que trae la pregunta de Metabase; en el resultado, cada OT se puede expandir para verlas, y el CSV las incluye.

**4. Usar** — *Traer OTs* (o activa *Actualizar cada N min*: las OTs nuevas se marcan como **Nueva**), filtra por OR, elige *Técnicos in-house* o *Contratistas* y pulsa **Asignar**. El resultado se puede descargar en CSV.

> Las distancias son en línea recta multiplicadas por un **factor vial** (1,3 por defecto, ajustable en *Jornada y tiempos de servicio*), no por la red vial real.

Endpoints nuevos: `GET /api/metabase/estado`, `GET /api/metabase/ots?card_id=`, `GET /api/catalogo`, `GET|PUT /api/asignacion/config`, `POST /api/asignar`.

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

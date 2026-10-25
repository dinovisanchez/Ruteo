# Route Optimizer - Proyecto Completo

Necesito crear un sistema completo de optimización de rutas para cuadrillas de campo con arquitectura de microservicios.

## ESTRUCTURA DEL PROYECTO

Crea esta estructura completa:
```
route-optimizer/
├── backend/
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── config.py
│   │   └── utils.py
│   ├── api_gateway/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routes.py
│   │   ├── orchestrator.py
│   │   └── Dockerfile
│   ├── services/
│   │   ├── data_service/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── service.py
│   │   │   ├── validators.py
│   │   │   └── Dockerfile
│   │   ├── distance_service/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── service.py
│   │   │   ├── calculator.py
│   │   │   └── Dockerfile
│   │   └── optimizer_service/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── service.py
│   │       ├── optimizer.py
│   │       ├── clustering.py
│   │       └── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── index.js
│   │   ├── index.css
│   │   ├── App.js
│   │   ├── components/
│   │   │   ├── FileUploader.jsx
│   │   │   ├── ConfigPanel.jsx
│   │   │   ├── MapView.jsx
│   │   │   ├── MetricsPanel.jsx
│   │   │   └── RouteDetails.jsx
│   │   └── services/
│   │       └── api.js
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .gitignore
├── .env.example
└── README.md
```

## STACK TECNOLÓGICO

**Backend:**
- Python 3.10+ con FastAPI
- Google OR-Tools para optimización
- Pandas para procesamiento de datos
- Redis para caché
- Pydantic para validación

**Frontend:**
- React 18
- Ant Design (componentes UI)
- Leaflet (mapas)
- Axios (API client)

**DevOps:**
- Docker & Docker Compose
- Nginx como reverse proxy

## IMPLEMENTACIÓN DETALLADA

### 1. Backend - Modelos Compartidos (backend/shared/models.py)

Crea modelos Pydantic completos para:
```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import datetime, time

class GPSCoordinates(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

class Activity(BaseModel):
    codigo_bia: str
    servicio: str
    gps: str  # Formato: "lat,lon"
    nombre: str
    direccion: str
    ciudad: str
    departamento: str
    or_operador: str
    coordinates: Optional[GPSCoordinates] = None
    
    def parse_coordinates(self) -> GPSCoordinates:
        lat, lon = self.gps.replace(' ', '').split(',')
        self.coordinates = GPSCoordinates(latitude=float(lat), longitude=float(lon))
        return self.coordinates

class ServiceTime(BaseModel):
    servicio: str
    duracion_minutos: int

class WorkConfiguration(BaseModel):
    horario_inicio: time = Field(default=time(8, 0))
    horario_fin: time = Field(default=time(17, 0))
    horas_laborales: float = Field(default=8.0)
    velocidad_promedio_kmh: float = Field(default=30.0)
    capacidad_maxima_actividades: Optional[int] = None
    punto_partida: GPSCoordinates
    incluir_retorno: bool = True
    tiempos_servicio: List[ServiceTime]

class ActivityLot(BaseModel):
    nombre_lote: str
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    actividades: List[Activity]
    configuracion: WorkConfiguration

class DistanceMatrix(BaseModel):
    activities_ids: List[str]
    distances_km: List[List[float]]
    durations_minutes: List[List[int]]

class RouteStop(BaseModel):
    secuencia: int
    actividad: Activity
    hora_llegada_estimada: time
    hora_salida_estimada: time
    distancia_desde_anterior_km: float = 0.0
    tiempo_desplazamiento_minutos: int = 0

class CrewRoute(BaseModel):
    cuadrilla_id: int
    paradas: List[RouteStop]
    distancia_total_km: float
    tiempo_total_minutos: int
    tiempo_trabajo_minutos: int
    tiempo_desplazamiento_minutos: int
    hora_inicio: time
    hora_fin: time
    utilization_percent: float
    viable: bool

class OptimizationResult(BaseModel):
    nombre_lote: str
    fecha_optimizacion: datetime = Field(default_factory=datetime.now)
    total_actividades: int
    cuadrillas_necesarias: int
    rutas: List[CrewRoute]
    distancia_total_km: float
    viable_en_un_dia: bool
    metricas: Dict[str, float]
```

### 2. Backend - Configuración (backend/shared/config.py)
```python
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Route Optimizer"
    VERSION: str = "1.0.0"
    
    DATA_SERVICE_URL: str = os.getenv("DATA_SERVICE_URL", "http://localhost:8001")
    DISTANCE_SERVICE_URL: str = os.getenv("DISTANCE_SERVICE_URL", "http://localhost:8002")
    OPTIMIZER_SERVICE_URL: str = os.getenv("OPTIMIZER_SERVICE_URL", "http://localhost:8003")
    
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = 6379
    
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_EXTENSIONS: list = [".xlsx", ".xls", ".csv"]
    CORS_ORIGINS: list = ["http://localhost:3000"]
    
    DEFAULT_WORK_HOURS: float = 8.0
    DEFAULT_SPEED_KMH: float = 30.0
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 3. Backend - Data Service (backend/services/data_service/)

**main.py** - FastAPI app con endpoints:
- GET /health
- POST /upload (carga archivos Excel/CSV)
- POST /validate (valida actividades)

**service.py** - Lógica para:
- Procesar archivos Excel/CSV con pandas
- Validar datos GPS
- Limpiar y normalizar información

**validators.py** - Validadores para:
- Formato GPS (lat,lon)
- Rangos de Colombia
- Campos requeridos

### 4. Backend - Distance Service (backend/services/distance_service/)

**calculator.py** - Implementa:
- Fórmula de Haversine para distancias GPS
- Cálculo eficiente entre múltiples puntos

**service.py** - Incluye:
- Cálculo de matriz de distancias completa
- Caché con Redis para optimizar
- Búsqueda de vecinos cercanos

**main.py** - Endpoints:
- POST /calculate-matrix
- POST /distance-between-two
- GET /cache/stats

### 5. Backend - Optimizer Service (backend/services/optimizer_service/)

**optimizer.py** - Motor de optimización:
- Usar Google OR-Tools
- Implementar VRP (Vehicle Routing Problem)
- Implementar TSP (Traveling Salesman Problem)

**clustering.py** - Clustering geográfico:
- K-means geográfico para agrupar actividades
- Algoritmo DBSCAN adaptado

**service.py** - Orquestación:
- Estimar cuadrillas necesarias
- Optimizar rutas completas
- Validar viabilidad en jornada laboral

**main.py** - Endpoints:
- POST /optimize
- POST /estimate-crews
- POST /validate-feasibility

### 6. Backend - API Gateway (backend/api_gateway/)

**main.py** - Aplicación principal FastAPI

**routes.py** - Endpoints públicos:
- POST /api/upload
- POST /api/optimize
- POST /api/estimate-crews

**orchestrator.py** - Coordina llamadas entre servicios:
1. Validar datos (Data Service)
2. Calcular distancias (Distance Service)
3. Optimizar rutas (Optimizer Service)

### 7. Backend - requirements.txt
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
pandas==2.1.3
numpy==1.26.2
openpyxl==3.1.2
ortools==9.8.3296
geopy==2.4.1
httpx==0.25.2
redis==5.0.1
pydantic==2.5.2
pydantic-settings==2.1.0
python-dateutil==2.8.2
python-dotenv==1.0.0
```

### 8. Frontend - package.json
```json
{
  "name": "route-optimizer-frontend",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1",
    "axios": "^1.6.2",
    "leaflet": "^1.9.4",
    "react-leaflet": "^4.2.1",
    "antd": "^5.11.5",
    "@ant-design/icons": "^5.2.6",
    "dayjs": "^1.11.10"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build"
  },
  "proxy": "http://localhost:8000"
}
```

### 9. Frontend - Componentes React

**App.js** - Componente principal con:
- Estado para activities, config, results, loading
- Layout con Header, Sider, Content
- Integración de todos los componentes

**FileUploader.jsx** - Carga de archivos:
- Ant Design Upload con drag & drop
- Validación de formato
- Preview de datos cargados

**ConfigPanel.jsx** - Configuración:
- Formulario Ant Design
- GPS punto de partida
- Horarios, velocidad, tiempos por servicio
- Botón de optimización

**MapView.jsx** - Mapa interactivo:
- React-Leaflet con OpenStreetMap
- Marcadores por actividad con números
- Polylines coloreadas por cuadrilla
- Popups con información detallada
- Leyenda

**MetricsPanel.jsx** - Dashboard de métricas:
- Ant Design Statistics
- Indicador de viabilidad (✓/✗)
- KPIs: cuadrillas, distancia, tiempo, utilización

**RouteDetails.jsx** - Detalles de rutas:
- Ant Design Collapse + Table
- Una sección por cuadrilla
- Tabla con orden de visitas, ETAs, distancias

**services/api.js** - Cliente Axios:
- uploadFile()
- optimizeRoutes()
- Configuración base URL
- Interceptors para logging

### 10. Docker Configuration

**docker-compose.yml** - Orquesta 8 servicios:
- api-gateway (8000)
- data-service (8001)
- distance-service (8002)
- optimizer-service (8003)
- redis (6379)
- frontend (3000)

Cada servicio con:
- Build context
- Variables de entorno
- Volumes compartidos
- Network route-network
- Health checks
- Depends_on para orden

**Dockerfiles** - Multi-stage builds:
- Backend: python:3.10-slim
- Frontend: node:18-alpine + nginx:alpine

### 11. Archivos de Configuración

**.gitignore** para Python, Node, Docker

**.env.example** con todas las variables

**README.md** con:
- Descripción del proyecto
- Stack tecnológico
- Instrucciones de inicio
- Formato de datos
- Acceso a servicios

## FUNCIONALIDAD ESPERADA

El sistema debe:
1. Cargar archivo Excel/CSV con actividades
2. Validar datos y coordenadas GPS
3. Calcular matriz de distancias entre actividades
4. Optimizar rutas usando OR-Tools
5. Determinar automáticamente cuántas cuadrillas se necesitan
6. Generar rutas optimizadas por cuadrilla
7. Visualizar rutas en mapa interactivo
8. Mostrar métricas y viabilidad
9. Permitir exportar resultados

## REQUISITOS DE IMPLEMENTACIÓN

- Todo el código debe estar COMPLETO y FUNCIONAL
- No uses placeholders o "TODO"
- Incluye manejo de errores
- Logging en todos los servicios
- Validación de datos en frontend y backend
- Comentarios en código complejo
- Type hints en Python
- PropTypes en React

## RESULTADO ESPERADO

Al ejecutar `docker-compose up --build` el sistema debe:
- Levantar todos los servicios
- Frontend accesible en http://localhost:3000
- API docs en http://localhost:8000/docs
- Permitir cargar archivo y optimizar rutas
- Visualizar resultados en mapa

Implementa TODO el código necesario para que funcione completamente.

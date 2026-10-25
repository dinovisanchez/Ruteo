Initial commit: Route Optimizer - Sistema de Optimización de Rutas para Cuadrillas

Sistema completo de optimización de rutas para cuadrillas de campo con arquitectura de microservicios.

## Descripción del Proyecto

Route Optimizer es una aplicación web completa que permite cargar actividades de campo desde archivos Excel/CSV y optimizar las rutas de las cuadrillas minimizando distancias y tiempos de viaje, garantizando que todas las tareas se completen dentro de la jornada laboral.

## Stack Tecnológico

### Backend
- Python 3.10+ con FastAPI
- Google OR-Tools para optimización VRP/TSP
- Scikit-learn para clustering geográfico K-means
- Redis para caché de matrices de distancia
- Pandas para procesamiento de datos
- Arquitectura de microservicios (API Gateway, Data Service, Distance Service, Optimizer Service)

### Frontend
- React 18 con Hooks
- Ant Design para componentes UI
- Leaflet/React-Leaflet para mapas interactivos
- Axios para cliente HTTP

### DevOps
- Docker y Docker Compose para orquestación
- Nginx como servidor estático

## Funcionalidades Principales

### Modo 1: Optimización Estándar
- Carga de archivos Excel/CSV con validación automática
- Optimización de rutas para todas las actividades
- Visualización en mapa interactivo con rutas coloreadas
- Métricas detalladas por cuadrilla
- Exportación de resultados a JSON

### Modo 2: Lotes por Proximidad (NUEVA FUNCIONALIDAD)
- Generación automática de lotes por proximidad geográfica
- Dos métodos de clustering: proximidad simple y K-means
- Optimización independiente de cada lote
- Panel de selección de lotes con checkboxes
- Mapa interactivo dedicado para visualizar rutas de lotes seleccionados
- Cada lote con color único y punto de partida optimizado
- Métricas globales y por lote

## Características Técnicas

- Validación automática de GPS (rangos de Colombia)
- Cálculo eficiente de distancias con fórmula Haversine
- Caché con Redis para optimizar cálculos repetidos
- Clustering geográfico para agrupar actividades cercanas
- Optimización VRP/TSP con Google OR-Tools
- Estimación automática de cuadrillas necesarias
- Validación de viabilidad en jornada laboral
- API RESTful documentada con OpenAPI/Swagger

## Correcciones Incluidas

- Validación correcta de cuadrilla_id (corregido bug de índice 0)
- Manejo robusto de clusters vacíos
- Mejoras en la estructura de componentes React

## Estructura del Proyecto

```
backend/
├── api_gateway/          # API Gateway principal
├── services/
│   ├── data_service/     # Procesamiento de datos
│   ├── distance_service/ # Cálculo de distancias
│   └── optimizer_service/# Optimización y clustering
│       ├── optimizer.py
│       ├── clustering.py
│       └── proximity_analysis.py
└── shared/               # Código compartido

frontend/
├── src/
│   ├── components/
│   │   ├── MapView.jsx
│   │   ├── ClusterMapView.jsx
│   │   ├── ClusterSelectionPanel.jsx
│   │   ├── ClusterResults.jsx
│   │   └── ...
│   └── services/
└── Dockerfile
```

## Endpoints API Principales

- POST /api/upload - Cargar archivo de actividades
- POST /api/optimize - Optimizar rutas (modo estándar)
- POST /api/optimize-by-clusters - Optimizar por lotes (modo proximidad)
- GET /api/health - Health check
- GET /api/docs - Documentación Swagger

## Instalación y Uso

```bash
# Iniciar todos los servicios
docker-compose up --build

# Acceder a la aplicación
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

## Documentación

- README.md completo con guía de instalación, uso y API
- Documentación interactiva en Swagger UI
- Ejemplos de formato de datos

---

Versión: 1.1.0
Licencia: MIT


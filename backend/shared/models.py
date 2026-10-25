"""Pydantic models for Route Optimizer system"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, time


class GPSCoordinates(BaseModel):
    """GPS coordinates with validation for valid ranges"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 4.6097,
                "longitude": -74.0817
            }
        }


class Activity(BaseModel):
    """Field activity with location and service information"""
    codigo_bia: str
    servicio: str
    gps: str  # Format: "lat,lon"
    nombre: str
    direccion: str
    ciudad: str
    departamento: str
    or_operador: str
    coordinates: Optional[GPSCoordinates] = None

    def parse_coordinates(self) -> GPSCoordinates:
        """Parse GPS string into GPSCoordinates object"""
        try:
            # Handle various formats: "lat,lon" or "lat, lon"
            coords_str = self.gps.replace(' ', '')
            parts = coords_str.split(',')
            if len(parts) != 2:
                raise ValueError(f"GPS format must be 'lat,lon', got: {self.gps}")

            lat = float(parts[0])
            lon = float(parts[1])
            self.coordinates = GPSCoordinates(latitude=lat, longitude=lon)
            return self.coordinates
        except Exception as e:
            raise ValueError(f"Error parsing GPS coordinates '{self.gps}': {str(e)}")

    class Config:
        json_schema_extra = {
            "example": {
                "codigo_bia": "BIA001",
                "servicio": "instalacion",
                "gps": "4.6097,-74.0817",
                "nombre": "Cliente Ejemplo",
                "direccion": "Calle 123 #45-67",
                "ciudad": "Bogotá",
                "departamento": "Cundinamarca",
                "or_operador": "OP001"
            }
        }


class ServiceTime(BaseModel):
    """Service duration configuration"""
    servicio: str
    duracion_minutos: int = Field(..., gt=0)

    class Config:
        json_schema_extra = {
            "example": {
                "servicio": "instalacion",
                "duracion_minutos": 60
            }
        }


class WorkConfiguration(BaseModel):
    """Work day configuration for route optimization"""
    horario_inicio: time = Field(default=time(8, 0))
    horario_fin: time = Field(default=time(17, 0))
    horas_laborales: float = Field(default=8.0, gt=0, le=24)
    velocidad_promedio_kmh: float = Field(default=30.0, gt=0)
    capacidad_maxima_actividades: Optional[int] = Field(default=None, gt=0)
    punto_partida: GPSCoordinates
    incluir_retorno: bool = True
    tiempos_servicio: List[ServiceTime]

    @field_validator('tiempos_servicio')
    @classmethod
    def validate_service_times(cls, v):
        """Ensure at least one service time is defined"""
        if not v:
            raise ValueError("At least one service time must be defined")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "horario_inicio": "08:00:00",
                "horario_fin": "17:00:00",
                "horas_laborales": 8.0,
                "velocidad_promedio_kmh": 30.0,
                "capacidad_maxima_actividades": 10,
                "punto_partida": {
                    "latitude": 4.6097,
                    "longitude": -74.0817
                },
                "incluir_retorno": True,
                "tiempos_servicio": [
                    {"servicio": "instalacion", "duracion_minutos": 60},
                    {"servicio": "mantenimiento", "duracion_minutos": 45}
                ]
            }
        }


class ActivityLot(BaseModel):
    """Batch of activities to be optimized"""
    nombre_lote: str
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    actividades: List[Activity]
    configuracion: WorkConfiguration

    @field_validator('actividades')
    @classmethod
    def validate_activities(cls, v):
        """Ensure at least one activity is present"""
        if not v:
            raise ValueError("At least one activity must be provided")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "nombre_lote": "Lote Bogotá Norte",
                "actividades": [],
                "configuracion": {}
            }
        }


class DistanceMatrix(BaseModel):
    """Distance and duration matrix between activities"""
    activities_ids: List[str]
    distances_km: List[List[float]]
    durations_minutes: List[List[int]]

    @field_validator('distances_km', 'durations_minutes')
    @classmethod
    def validate_matrix_dimensions(cls, v, info):
        """Validate matrix is square and matches activities count"""
        if not v:
            return v

        n = len(v)
        for row in v:
            if len(row) != n:
                raise ValueError(f"Matrix must be square, got row with {len(row)} columns for {n} rows")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "activities_ids": ["BIA001", "BIA002"],
                "distances_km": [[0.0, 5.2], [5.2, 0.0]],
                "durations_minutes": [[0, 10], [10, 0]]
            }
        }


class RouteStop(BaseModel):
    """Individual stop in a route"""
    secuencia: int = Field(..., ge=0)
    actividad: Activity
    hora_llegada_estimada: time
    hora_salida_estimada: time
    distancia_desde_anterior_km: float = Field(default=0.0, ge=0)
    tiempo_desplazamiento_minutos: int = Field(default=0, ge=0)

    class Config:
        json_schema_extra = {
            "example": {
                "secuencia": 1,
                "actividad": {},
                "hora_llegada_estimada": "09:00:00",
                "hora_salida_estimada": "10:00:00",
                "distancia_desde_anterior_km": 5.2,
                "tiempo_desplazamiento_minutos": 10
            }
        }


class CrewRoute(BaseModel):
    """Complete route for a single crew"""
    cuadrilla_id: int = Field(..., ge=1)
    paradas: List[RouteStop]
    distancia_total_km: float = Field(..., ge=0)
    tiempo_total_minutos: int = Field(..., ge=0)
    tiempo_trabajo_minutos: int = Field(..., ge=0)
    tiempo_desplazamiento_minutos: int = Field(..., ge=0)
    hora_inicio: time
    hora_fin: time
    utilization_percent: float = Field(..., ge=0, le=100)
    viable: bool

    class Config:
        json_schema_extra = {
            "example": {
                "cuadrilla_id": 1,
                "paradas": [],
                "distancia_total_km": 45.5,
                "tiempo_total_minutos": 480,
                "tiempo_trabajo_minutos": 240,
                "tiempo_desplazamiento_minutos": 90,
                "hora_inicio": "08:00:00",
                "hora_fin": "16:00:00",
                "utilization_percent": 85.5,
                "viable": True
            }
        }


class OptimizationResult(BaseModel):
    """Complete optimization result with all routes"""
    nombre_lote: str
    fecha_optimizacion: datetime = Field(default_factory=datetime.now)
    total_actividades: int = Field(..., ge=0)
    cuadrillas_necesarias: int = Field(..., ge=0)
    rutas: List[CrewRoute]
    distancia_total_km: float = Field(..., ge=0)
    viable_en_un_dia: bool
    metricas: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "nombre_lote": "Lote Bogotá Norte",
                "fecha_optimizacion": "2024-01-15T10:30:00",
                "total_actividades": 25,
                "cuadrillas_necesarias": 3,
                "rutas": [],
                "distancia_total_km": 135.5,
                "viable_en_un_dia": True,
                "metricas": {
                    "avg_utilization": 82.5,
                    "max_route_time": 480,
                    "avg_distance_per_crew": 45.2
                }
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Validation Error",
                "detail": "Invalid GPS coordinates format",
                "timestamp": "2024-01-15T10:30:00"
            }
        }


class ClusterInfo(BaseModel):
    """Information about a geographic cluster"""
    cluster_id: int = Field(..., ge=0)
    actividades: List[Activity]
    num_actividades: int = Field(..., ge=0)
    centroid: GPSCoordinates
    distancia_promedio_al_centroid_km: float = Field(..., ge=0)
    distancia_maxima_al_centroid_km: float = Field(..., ge=0)
    densidad_km2: Optional[float] = Field(default=None, ge=0)

    class Config:
        json_schema_extra = {
            "example": {
                "cluster_id": 1,
                "actividades": [],
                "num_actividades": 12,
                "centroid": {
                    "latitude": 4.6097,
                    "longitude": -74.0817
                },
                "distancia_promedio_al_centroid_km": 3.5,
                "distancia_maxima_al_centroid_km": 8.2,
                "densidad_km2": 0.5
            }
        }


class ProximityClusteringResult(BaseModel):
    """Result of proximity-based clustering analysis"""
    nombre_lote: str
    fecha_analisis: datetime = Field(default_factory=datetime.now)
    total_actividades: int = Field(..., ge=0)
    num_clusters: int = Field(..., ge=0)
    clusters: List[ClusterInfo]
    distancia_maxima_usado_km: float = Field(..., ge=0)
    metodo: str = "proximity"  # "proximity" or "kmeans"
    metricas_globales: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "nombre_lote": "Lote Bogotá Norte",
                "fecha_analisis": "2024-01-15T10:30:00",
                "total_actividades": 60,
                "num_clusters": 5,
                "clusters": [],
                "distancia_maxima_usado_km": 20.0,
                "metodo": "proximity",
                "metricas_globales": {
                    "cluster_mas_grande": 15,
                    "cluster_mas_pequeno": 8,
                    "promedio_actividades_por_cluster": 12.0
                }
            }
        }


class OptimizedClusterRoute(BaseModel):
    """Optimized route for a specific cluster"""
    cluster_id: int = Field(..., ge=0)
    cluster_info: ClusterInfo
    ruta: CrewRoute
    punto_partida_optimo: GPSCoordinates
    distancia_desde_punto_partida_km: float = Field(..., ge=0)

    class Config:
        json_schema_extra = {
            "example": {
                "cluster_id": 1,
                "cluster_info": {},
                "ruta": {},
                "punto_partida_optimo": {
                    "latitude": 4.6097,
                    "longitude": -74.0817
                },
                "distancia_desde_punto_partida_km": 5.2
            }
        }


class ClusterOptimizationResult(BaseModel):
    """Complete result with clusters and optimized routes"""
    nombre_lote: str
    fecha_optimizacion: datetime = Field(default_factory=datetime.now)
    total_actividades: int = Field(..., ge=0)
    clustering_info: ProximityClusteringResult
    rutas_por_cluster: List[OptimizedClusterRoute]
    distancia_total_km: float = Field(..., ge=0)
    tiempo_total_minutos: int = Field(..., ge=0)
    metricas: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "nombre_lote": "Lote Bogotá Norte",
                "fecha_optimizacion": "2024-01-15T10:30:00",
                "total_actividades": 60,
                "clustering_info": {},
                "rutas_por_cluster": [],
                "distancia_total_km": 250.5,
                "tiempo_total_minutos": 2400,
                "metricas": {
                    "avg_cluster_distance": 50.1,
                    "most_compact_cluster": 1,
                    "most_dispersed_cluster": 3
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service": "data-service",
                "timestamp": "2024-01-15T10:30:00",
                "version": "1.0.0"
            }
        }

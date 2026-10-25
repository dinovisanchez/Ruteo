# Nueva Funcionalidad: Análisis de Clusters por Proximidad

## Descripción General

Esta nueva funcionalidad te permite analizar un lote de actividades (por ejemplo, 60 actividades) y agruparlas automáticamente por cercanía geográfica. El sistema identifica cuáles actividades están más cerca entre sí y genera rutas optimizadas para cada grupo.

## ¿Para qué sirve?

Cuando tienes un gran número de actividades (por ejemplo, 60) y quieres:
- **Identificar grupos geográficos**: Ver cuáles actividades están más cerca entre sí
- **Optimizar por grupos**: Generar rutas optimizadas para cada cluster de actividades cercanas
- **Análisis de dispersión**: Entender cómo están distribuidas geográficamente tus actividades
- **Planificación flexible**: Atacar los clusters más cercanos sin importar el punto de salida principal

## Endpoints Disponibles

### 1. Análisis de Proximidad (Solo Agrupamiento)

**Endpoint**: `POST /api/analyze-proximity`

**Qué hace**: Analiza y agrupa actividades por cercanía, sin optimizar rutas. Solo te muestra los clusters.

**Parámetros**:
```json
{
  "activity_lot": { ... },  // Tu lote de actividades
  "max_distance_km": 20.0,  // Distancia máxima para considerar actividades "cercanas" (default: 20km)
  "method": "proximity"      // Método: "proximity" o "kmeans" (default: "proximity")
}
```

**Respuesta**:
```json
{
  "nombre_lote": "Lote Bogotá 60 Actividades",
  "total_actividades": 60,
  "num_clusters": 5,
  "clusters": [
    {
      "cluster_id": 0,
      "num_actividades": 15,
      "centroid": {
        "latitude": 4.6097,
        "longitude": -74.0817
      },
      "distancia_promedio_al_centroid_km": 3.5,
      "distancia_maxima_al_centroid_km": 8.2,
      "densidad_km2": 0.5,
      "actividades": [ ... ]  // Lista completa de actividades en este cluster
    },
    {
      "cluster_id": 1,
      "num_actividades": 12,
      ...
    }
  ],
  "distancia_maxima_usado_km": 20.0,
  "metodo": "proximity",
  "metricas_globales": {
    "num_clusters": 5,
    "cluster_mas_grande": 15,
    "cluster_mas_pequeno": 8,
    "promedio_actividades_por_cluster": 12.0,
    "avg_cluster_density": 0.45
  }
}
```

**Información que obtienes**:
- Cuántos clusters se formaron
- Cuántas actividades hay en cada cluster
- El centroid (punto central) de cada cluster
- Qué tan dispersas están las actividades (distancia promedio y máxima al centro)
- Densidad (actividades por km²)
- Todas las actividades de cada cluster

---

### 2. Optimización por Clusters

**Endpoint**: `POST /api/optimize-by-clusters`

**Qué hace**: Agrupa por cercanía Y genera rutas optimizadas para cada cluster. Cada cluster tiene su propia ruta optimizada.

**Parámetros**:
```json
{
  "activity_lot": { ... },  // Tu lote de actividades
  "max_distance_km": 20.0,  // Distancia máxima para clustering (default: 20km)
  "method": "proximity"      // Método: "proximity" o "kmeans" (default: "proximity")
}
```

**Respuesta**:
```json
{
  "nombre_lote": "Lote Bogotá 60 Actividades",
  "total_actividades": 60,
  "clustering_info": {
    // Misma información del análisis de proximidad
    "num_clusters": 5,
    "clusters": [ ... ]
  },
  "rutas_por_cluster": [
    {
      "cluster_id": 0,
      "cluster_info": {
        // Información del cluster
        "num_actividades": 15,
        "centroid": { ... },
        "distancia_promedio_al_centroid_km": 3.5
      },
      "punto_partida_optimo": {
        // El centroid del cluster, usado como punto de inicio óptimo
        "latitude": 4.6097,
        "longitude": -74.0817
      },
      "distancia_desde_punto_partida_km": 5.2,
      "ruta": {
        // Ruta optimizada para este cluster
        "cuadrilla_id": 0,
        "paradas": [
          {
            "secuencia": 1,
            "actividad": { ... },
            "hora_llegada_estimada": "08:15:00",
            "hora_salida_estimada": "09:15:00",
            "distancia_desde_anterior_km": 2.3
          },
          ...
        ],
        "distancia_total_km": 45.5,
        "tiempo_total_minutos": 420,
        "tiempo_trabajo_minutos": 300,
        "tiempo_desplazamiento_minutos": 120,
        "hora_inicio": "08:00:00",
        "hora_fin": "15:00:00",
        "utilization_percent": 87.5,
        "viable": true
      }
    },
    {
      "cluster_id": 1,
      ...
    }
  ],
  "distancia_total_km": 250.5,
  "tiempo_total_minutos": 2100,
  "metricas": {
    "num_clusters": 5,
    "avg_cluster_distance_km": 50.1,
    "min_cluster_distance_km": 35.2,
    "max_cluster_distance_km": 68.5,
    "most_compact_cluster": 2,
    "most_dispersed_cluster": 4,
    "all_clusters_viable": true,
    "viable_clusters": 5
  }
}
```

**Información que obtienes**:
- Todos los clusters identificados
- Para cada cluster:
  - Ruta optimizada completa
  - Secuencia óptima de visitas
  - Tiempos estimados de llegada y salida
  - Distancias entre paradas
  - Punto de partida óptimo (el centroid del cluster)
  - Si es viable completarlo en una jornada
- Métricas globales:
  - Cluster más compacto y más disperso
  - Distancias promedio por cluster
  - Viabilidad de cada cluster

---

## Métodos de Clustering

### 1. Proximity (Por Proximidad)
- **Cómo funciona**: Agrupa actividades que estén dentro de una distancia máxima entre sí
- **Parámetro clave**: `max_distance_km` (default: 20km)
- **Ventaja**: Clusters más compactos geográficamente
- **Usa cuando**: Quieres garantizar que las actividades de un cluster estén a menos de X km entre sí

### 2. K-Means
- **Cómo funciona**: Algoritmo k-means adaptado para coordenadas GPS
- **Parámetro**: El sistema calcula automáticamente el número óptimo de clusters
- **Ventaja**: Clusters más balanceados en tamaño
- **Usa cuando**: Quieres una distribución más uniforme de actividades por cluster

---

## Casos de Uso

### Caso 1: Análisis Inicial
**Objetivo**: Ver cómo se agrupan 60 actividades geográficamente

```bash
POST /api/analyze-proximity
{
  "activity_lot": { ... 60 actividades ... },
  "max_distance_km": 15.0,
  "method": "proximity"
}
```

**Resultado**: Identificas que hay 4 clusters principales, con tamaños de 18, 16, 14 y 12 actividades.

---

### Caso 2: Optimización por Áreas
**Objetivo**: Generar rutas optimizadas para cada área geográfica

```bash
POST /api/optimize-by-clusters
{
  "activity_lot": { ... 60 actividades ... },
  "max_distance_km": 20.0,
  "method": "kmeans"
}
```

**Resultado**: Obtienes 5 rutas optimizadas, una por cada cluster, con:
- Secuencia óptima de visitas
- Tiempos estimados
- Punto de inicio óptimo para cada ruta
- Métricas de viabilidad

---

### Caso 3: Comparar Métodos
Puedes llamar ambos métodos y comparar:

**Proximity**:
```json
{
  "method": "proximity",
  "max_distance_km": 15.0
}
```
Resultado: 6 clusters, más compactos pero de tamaños variables (5, 8, 12, 14, 10, 11)

**K-Means**:
```json
{
  "method": "kmeans"
}
```
Resultado: 5 clusters, más balanceados en tamaño (12, 12, 12, 12, 12)

---

## Ejemplo Completo de Uso

### Request:
```json
POST /api/optimize-by-clusters

{
  "activity_lot": {
    "nombre_lote": "Lote Bogotá - 60 Actividades",
    "actividades": [
      {
        "codigo_bia": "BIA001",
        "servicio": "instalacion",
        "gps": "4.6097,-74.0817",
        "nombre": "Cliente 1",
        "direccion": "Calle 100 #15-20",
        "ciudad": "Bogotá",
        "departamento": "Cundinamarca",
        "or_operador": "OP001"
      },
      ... // 59 actividades más
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
      "incluir_retorno": true,
      "tiempos_servicio": [
        {
          "servicio": "instalacion",
          "duracion_minutos": 60
        },
        {
          "servicio": "mantenimiento",
          "duracion_minutos": 45
        }
      ]
    }
  },
  "max_distance_km": 20.0,
  "method": "proximity"
}
```

### Response (Simplificado):
```json
{
  "nombre_lote": "Lote Bogotá - 60 Actividades",
  "total_actividades": 60,
  "clustering_info": {
    "num_clusters": 5,
    "metricas_globales": {
      "cluster_mas_grande": 15,
      "cluster_mas_pequeno": 10,
      "promedio_actividades_por_cluster": 12.0
    }
  },
  "rutas_por_cluster": [
    {
      "cluster_id": 0,
      "cluster_info": {
        "num_actividades": 15,
        "centroid": {"latitude": 4.65, "longitude": -74.08}
      },
      "ruta": {
        "distancia_total_km": 48.5,
        "tiempo_total_minutos": 405,
        "viable": true
      }
    },
    ... // 4 clusters más
  ],
  "distancia_total_km": 245.5,
  "metricas": {
    "most_compact_cluster": 2,
    "most_dispersed_cluster": 4,
    "all_clusters_viable": true
  }
}
```

---

## Diferencias con la Optimización Normal

### Optimización Normal (`/api/optimize`)
- Usa un **punto de partida fijo**
- Optimiza para **minimizar cuadrillas** necesarias
- Todas las rutas salen del **mismo punto**
- Objetivo: Completar todas las actividades con el mínimo de recursos

### Optimización por Clusters (`/api/optimize-by-clusters`)
- Usa el **centroid de cada cluster** como punto de partida óptimo
- Agrupa por **proximidad geográfica** primero
- Cada cluster tiene su **punto de inicio óptimo**
- Objetivo: Identificar grupos cercanos y optimizar cada uno independientemente

---

## Configuración Recomendada

### Para áreas urbanas densas:
```json
{
  "max_distance_km": 10.0,  // 10km máximo
  "method": "proximity"
}
```

### Para áreas rurales o dispersas:
```json
{
  "max_distance_km": 30.0,  // 30km máximo
  "method": "kmeans"
}
```

### Para distribución balanceada:
```json
{
  "method": "kmeans"
}
```

---

## Métricas Importantes

### Por Cluster:
- **num_actividades**: Cuántas actividades tiene el cluster
- **distancia_promedio_al_centroid_km**: Qué tan compacto es el cluster
- **densidad_km2**: Actividades por kilómetro cuadrado
- **viable**: Si se puede completar en una jornada laboral

### Globales:
- **num_clusters**: Cuántos grupos se formaron
- **cluster_mas_grande / mas_pequeno**: Balance entre clusters
- **most_compact_cluster**: El cluster más compacto (menos disperso)
- **most_dispersed_cluster**: El cluster más disperso
- **all_clusters_viable**: Si todos son viables

---

## Ventajas de Esta Funcionalidad

1. **Flexibilidad**: No estás atado a un punto de salida fijo
2. **Eficiencia**: Identifica automáticamente áreas geográficas de trabajo
3. **Análisis**: Puedes ver cómo se distribuyen tus actividades
4. **Planificación**: Atacar primero los clusters más cercanos o compactos
5. **Escalabilidad**: Funciona con 60+ actividades sin problema

---

## Testing

Para probar la funcionalidad, puedes usar cualquier cliente HTTP (Postman, curl, etc.):

```bash
# Análisis simple
curl -X POST http://localhost:8000/api/analyze-proximity \
  -H "Content-Type: application/json" \
  -d @tu_archivo_actividades.json

# Optimización completa
curl -X POST http://localhost:8000/api/optimize-by-clusters \
  -H "Content-Type: application/json" \
  -d @tu_archivo_actividades.json
```

---

## Resumen

Esta nueva funcionalidad te permite:
- ✅ Identificar actividades cercanas entre sí (clusters por proximidad)
- ✅ Ver métricas de dispersión y densidad
- ✅ Generar rutas optimizadas por cada grupo geográfico
- ✅ Usar el punto óptimo de inicio para cada cluster
- ✅ Analizar 60+ actividades eficientemente
- ✅ Elegir entre método de proximidad o k-means

Es perfecta para cuando tienes muchas actividades y quieres entender cómo están distribuidas geográficamente y cuál sería la mejor forma de atacarlas por grupos cercanos.

"""Geographic clustering algorithms for activity grouping"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import math
from typing import List, Dict, Tuple
import numpy as np

from shared.models import Activity, GPSCoordinates
from shared.utils import setup_logging

logger = setup_logging("optimizer-service")


def kmeans_geographic_clustering(
    activities: List[Activity],
    num_clusters: int,
    max_iterations: int = 100
) -> Dict[int, List[Activity]]:
    """
    K-means clustering adapted for geographic coordinates
    Returns dict mapping cluster_id -> list of activities
    """
    if num_clusters <= 0:
        raise ValueError("Number of clusters must be positive")

    if num_clusters >= len(activities):
        # Each activity in its own cluster
        return {i: [activities[i]] for i in range(len(activities))}

    # Ensure all activities have coordinates
    for activity in activities:
        if not activity.coordinates:
            activity.parse_coordinates()

    # Extract coordinates as numpy array
    coords = np.array([
        [act.coordinates.latitude, act.coordinates.longitude]
        for act in activities
    ])

    # Initialize centroids using k-means++ method
    centroids = _kmeans_plusplus_init(coords, num_clusters)

    # Iterate until convergence or max iterations
    for iteration in range(max_iterations):
        # Assign each point to nearest centroid
        assignments = _assign_to_nearest_centroid(coords, centroids)

        # Calculate new centroids
        new_centroids = np.zeros_like(centroids)
        for i in range(num_clusters):
            cluster_points = coords[assignments == i]
            if len(cluster_points) > 0:
                new_centroids[i] = cluster_points.mean(axis=0)
            else:
                # Empty cluster, keep old centroid
                new_centroids[i] = centroids[i]

        # Check for convergence
        if np.allclose(centroids, new_centroids, atol=1e-6):
            logger.info(f"K-means converged after {iteration + 1} iterations")
            break

        centroids = new_centroids

    # Build clusters
    clusters = {i: [] for i in range(num_clusters)}
    final_assignments = _assign_to_nearest_centroid(coords, centroids)

    for idx, cluster_id in enumerate(final_assignments):
        clusters[cluster_id].append(activities[idx])

    # Remove empty clusters
    clusters = {k: v for k, v in clusters.items() if v}

    logger.info(f"Created {len(clusters)} clusters from {len(activities)} activities")

    return clusters


def _kmeans_plusplus_init(coords: np.ndarray, k: int) -> np.ndarray:
    """Initialize centroids using k-means++ algorithm"""
    n = len(coords)
    centroids = np.zeros((k, 2))

    # Choose first centroid randomly
    centroids[0] = coords[np.random.randint(n)]

    # Choose remaining centroids
    for i in range(1, k):
        # Calculate distances to nearest existing centroid
        distances = np.array([
            min(_haversine_np(point, centroid) for centroid in centroids[:i])
            for point in coords
        ])

        # Choose next centroid with probability proportional to distance squared
        probabilities = distances ** 2
        probabilities /= probabilities.sum()
        centroids[i] = coords[np.random.choice(n, p=probabilities)]

    return centroids


def _assign_to_nearest_centroid(coords: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """Assign each coordinate to nearest centroid"""
    n = len(coords)
    k = len(centroids)

    assignments = np.zeros(n, dtype=int)

    for i in range(n):
        distances = [_haversine_np(coords[i], centroids[j]) for j in range(k)]
        assignments[i] = np.argmin(distances)

    return assignments


def _haversine_np(coord1: np.ndarray, coord2: np.ndarray) -> float:
    """Calculate Haversine distance between two points (lat, lon)"""
    R = 6371.0  # Earth radius in km

    lat1, lon1 = np.radians(coord1)
    lat2, lon2 = np.radians(coord2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))

    return R * c


def balance_clusters(
    clusters: Dict[int, List[Activity]],
    max_size: int
) -> Dict[int, List[Activity]]:
    """
    Balance cluster sizes by splitting large clusters
    """
    balanced = {}
    cluster_id = 0

    for activities in clusters.values():
        if len(activities) <= max_size:
            # Cluster is within size limit
            balanced[cluster_id] = activities
            cluster_id += 1
        else:
            # Split large cluster
            num_splits = math.ceil(len(activities) / max_size)
            sub_clusters = kmeans_geographic_clustering(activities, num_splits)

            for sub_activities in sub_clusters.values():
                balanced[cluster_id] = sub_activities
                cluster_id += 1

    logger.info(f"Balanced {len(clusters)} clusters into {len(balanced)} clusters")

    return balanced


def estimate_optimal_clusters(
    total_activities: int,
    max_activities_per_crew: int,
    min_activities_per_crew: int = 1
) -> int:
    """
    Estimate optimal number of clusters based on constraints
    """
    if max_activities_per_crew is None:
        # Use heuristic: aim for 8-10 activities per crew
        optimal = max(1, math.ceil(total_activities / 9))
    else:
        optimal = max(1, math.ceil(total_activities / max_activities_per_crew))

    return optimal


def calculate_cluster_statistics(clusters: Dict[int, List[Activity]]) -> Dict:
    """Calculate statistics for clusters"""
    sizes = [len(activities) for activities in clusters.values()]

    return {
        "num_clusters": len(clusters),
        "total_activities": sum(sizes),
        "min_size": min(sizes) if sizes else 0,
        "max_size": max(sizes) if sizes else 0,
        "avg_size": sum(sizes) / len(sizes) if sizes else 0,
        "cluster_sizes": sizes
    }


def spatial_proximity_clustering(
    activities: List[Activity],
    max_distance_km: float = 20.0
) -> Dict[int, List[Activity]]:
    """
    Simple clustering based on spatial proximity
    Groups activities that are within max_distance_km of each other
    """
    # Ensure coordinates
    for activity in activities:
        if not activity.coordinates:
            activity.parse_coordinates()

    clusters = {}
    cluster_id = 0
    assigned = set()

    for i, activity in enumerate(activities):
        if i in assigned:
            continue

        # Start new cluster
        cluster = [activity]
        assigned.add(i)

        # Find nearby activities
        for j, other in enumerate(activities):
            if j in assigned:
                continue

            # Check distance to any activity in current cluster
            for cluster_activity in cluster:
                dist = _haversine_np(
                    np.array([activity.coordinates.latitude, activity.coordinates.longitude]),
                    np.array([other.coordinates.latitude, other.coordinates.longitude])
                )
                if dist <= max_distance_km:
                    cluster.append(other)
                    assigned.add(j)
                    break

        clusters[cluster_id] = cluster
        cluster_id += 1

    logger.info(f"Created {len(clusters)} proximity-based clusters")

    return clusters


def calculate_cluster_centroid(activities: List[Activity]) -> GPSCoordinates:
    """Calculate geographic centroid of a cluster"""
    if not activities:
        raise ValueError("Cannot calculate centroid for empty cluster")

    # Ensure coordinates
    for activity in activities:
        if not activity.coordinates:
            activity.parse_coordinates()

    # Calculate average lat/lon
    avg_lat = sum(act.coordinates.latitude for act in activities) / len(activities)
    avg_lon = sum(act.coordinates.longitude for act in activities) / len(activities)

    return GPSCoordinates(latitude=avg_lat, longitude=avg_lon)


def calculate_cluster_metrics(activities: List[Activity]) -> Dict:
    """Calculate detailed metrics for a cluster"""
    if not activities:
        return {
            "num_activities": 0,
            "avg_distance_to_centroid": 0.0,
            "max_distance_to_centroid": 0.0,
            "density": 0.0
        }

    # Calculate centroid
    centroid = calculate_cluster_centroid(activities)
    centroid_array = np.array([centroid.latitude, centroid.longitude])

    # Calculate distances to centroid
    distances = []
    for activity in activities:
        if not activity.coordinates:
            activity.parse_coordinates()

        activity_array = np.array([
            activity.coordinates.latitude,
            activity.coordinates.longitude
        ])
        dist = _haversine_np(activity_array, centroid_array)
        distances.append(dist)

    avg_distance = sum(distances) / len(distances) if distances else 0.0
    max_distance = max(distances) if distances else 0.0

    # Calculate density (activities per square km)
    # Using circular area based on max distance
    if max_distance > 0:
        area = math.pi * (max_distance ** 2)
        density = len(activities) / area
    else:
        density = float('inf')  # All points at same location

    return {
        "num_activities": len(activities),
        "centroid": centroid,
        "avg_distance_to_centroid": avg_distance,
        "max_distance_to_centroid": max_distance,
        "density": density
    }


def analyze_proximity_clustering(
    activities: List[Activity],
    max_distance_km: float = 20.0,
    method: str = "proximity"
) -> Tuple[Dict[int, List[Activity]], Dict]:
    """
    Analyze activities and create proximity-based clusters with detailed metrics

    Args:
        activities: List of activities to cluster
        max_distance_km: Maximum distance for proximity clustering
        method: "proximity" or "kmeans"

    Returns:
        Tuple of (clusters dict, global metrics dict)
    """
    # Ensure coordinates
    for activity in activities:
        if not activity.coordinates:
            activity.parse_coordinates()

    # Create clusters based on method
    if method == "proximity":
        clusters = spatial_proximity_clustering(activities, max_distance_km)
    elif method == "kmeans":
        # Estimate optimal number of clusters
        # Use heuristic: average cluster should have ~10-12 activities
        num_clusters = max(1, math.ceil(len(activities) / 11))
        clusters = kmeans_geographic_clustering(activities, num_clusters)
    else:
        raise ValueError(f"Unknown clustering method: {method}")

    # Calculate metrics for each cluster
    cluster_metrics = {}
    cluster_sizes = []

    for cluster_id, cluster_activities in clusters.items():
        metrics = calculate_cluster_metrics(cluster_activities)
        cluster_metrics[cluster_id] = metrics
        cluster_sizes.append(len(cluster_activities))

    # Calculate global metrics
    global_metrics = {
        "num_clusters": len(clusters),
        "total_activities": len(activities),
        "cluster_mas_grande": max(cluster_sizes) if cluster_sizes else 0,
        "cluster_mas_pequeno": min(cluster_sizes) if cluster_sizes else 0,
        "promedio_actividades_por_cluster": sum(cluster_sizes) / len(cluster_sizes) if cluster_sizes else 0,
        "avg_cluster_density": sum(m["density"] for m in cluster_metrics.values()) / len(cluster_metrics) if cluster_metrics else 0,
        "cluster_sizes": cluster_sizes
    }

    logger.info(f"Proximity analysis completed: {len(clusters)} clusters, "
                f"avg size: {global_metrics['promedio_actividades_por_cluster']:.1f}")

    return clusters, global_metrics


def find_nearest_cluster_neighbors(
    clusters: Dict[int, List[Activity]]
) -> Dict[int, List[Tuple[int, float]]]:
    """
    Find nearest neighboring clusters for each cluster
    Returns dict mapping cluster_id -> [(neighbor_id, distance), ...]
    """
    cluster_centroids = {}

    # Calculate centroid for each cluster
    for cluster_id, activities in clusters.items():
        if activities:
            cluster_centroids[cluster_id] = calculate_cluster_centroid(activities)

    # Calculate distances between cluster centroids
    neighbor_distances = {}

    for cluster_id, centroid in cluster_centroids.items():
        distances = []
        centroid_array = np.array([centroid.latitude, centroid.longitude])

        for other_id, other_centroid in cluster_centroids.items():
            if cluster_id == other_id:
                continue

            other_array = np.array([other_centroid.latitude, other_centroid.longitude])
            dist = _haversine_np(centroid_array, other_array)
            distances.append((other_id, dist))

        # Sort by distance
        distances.sort(key=lambda x: x[1])
        neighbor_distances[cluster_id] = distances

    return neighbor_distances

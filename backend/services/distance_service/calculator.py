"""GPS distance calculations using Haversine formula"""
import math
from typing import Tuple, List
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.models import GPSCoordinates


# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371.0


def haversine_distance(coord1: GPSCoordinates, coord2: GPSCoordinates) -> float:
    """
    Calculate the great circle distance between two points on Earth using Haversine formula
    Returns distance in kilometers
    """
    # Convert to radians
    lat1 = math.radians(coord1.latitude)
    lon1 = math.radians(coord1.longitude)
    lat2 = math.radians(coord2.latitude)
    lon2 = math.radians(coord2.longitude)

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    distance = EARTH_RADIUS_KM * c

    return distance


def calculate_duration_minutes(distance_km: float, speed_kmh: float) -> int:
    """
    Calculate travel duration in minutes based on distance and speed
    """
    if speed_kmh <= 0:
        raise ValueError("Speed must be greater than 0")

    hours = distance_km / speed_kmh
    minutes = int(math.ceil(hours * 60))

    return minutes


def calculate_distance_matrix(
    coordinates: List[GPSCoordinates],
    speed_kmh: float = 30.0
) -> Tuple[List[List[float]], List[List[int]]]:
    """
    Calculate full distance and duration matrix for all coordinate pairs
    Returns (distance_matrix_km, duration_matrix_minutes)
    """
    n = len(coordinates)

    # Initialize matrices
    distances = [[0.0 for _ in range(n)] for _ in range(n)]
    durations = [[0 for _ in range(n)] for _ in range(n)]

    # Calculate distances
    for i in range(n):
        for j in range(n):
            if i == j:
                # Same location
                distances[i][j] = 0.0
                durations[i][j] = 0
            else:
                # Calculate distance
                dist = haversine_distance(coordinates[i], coordinates[j])
                distances[i][j] = round(dist, 2)

                # Calculate duration
                duration = calculate_duration_minutes(dist, speed_kmh)
                durations[i][j] = duration

    return distances, durations


def find_nearest_neighbors(
    origin_index: int,
    coordinates: List[GPSCoordinates],
    k: int = 5
) -> List[Tuple[int, float]]:
    """
    Find k nearest neighbors to origin point
    Returns list of (index, distance_km) tuples sorted by distance
    """
    origin = coordinates[origin_index]
    distances = []

    for i, coord in enumerate(coordinates):
        if i != origin_index:
            dist = haversine_distance(origin, coord)
            distances.append((i, dist))

    # Sort by distance and return top k
    distances.sort(key=lambda x: x[1])
    return distances[:k]


def calculate_route_distance(
    route_indices: List[int],
    coordinates: List[GPSCoordinates],
    include_return_to_start: bool = False
) -> float:
    """
    Calculate total distance for a route visiting points in specified order
    Returns total distance in kilometers
    """
    if len(route_indices) < 2:
        return 0.0

    total_distance = 0.0

    # Sum distances between consecutive points
    for i in range(len(route_indices) - 1):
        idx1 = route_indices[i]
        idx2 = route_indices[i + 1]
        total_distance += haversine_distance(coordinates[idx1], coordinates[idx2])

    # Add return to start if requested
    if include_return_to_start and len(route_indices) >= 2:
        last_idx = route_indices[-1]
        first_idx = route_indices[0]
        total_distance += haversine_distance(coordinates[last_idx], coordinates[first_idx])

    return round(total_distance, 2)


def calculate_bounding_box(coordinates: List[GPSCoordinates]) -> dict:
    """
    Calculate bounding box for a set of coordinates
    Returns dict with min/max latitude/longitude
    """
    if not coordinates:
        return {}

    lats = [c.latitude for c in coordinates]
    lons = [c.longitude for c in coordinates]

    return {
        "min_latitude": min(lats),
        "max_latitude": max(lats),
        "min_longitude": min(lons),
        "max_longitude": max(lons),
        "center_latitude": sum(lats) / len(lats),
        "center_longitude": sum(lons) / len(lons)
    }


def estimate_straight_line_distance(coord1: GPSCoordinates, coord2: GPSCoordinates) -> float:
    """
    Quick estimation of distance using simplified calculation
    Useful for sorting/filtering, not for accurate distances
    """
    # Simple Euclidean approximation (fast but less accurate)
    dlat = coord2.latitude - coord1.latitude
    dlon = coord2.longitude - coord1.longitude

    # Approximate km per degree at equator
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians(coord1.latitude))

    dist_km = math.sqrt((dlat * km_per_deg_lat) ** 2 + (dlon * km_per_deg_lon) ** 2)

    return dist_km

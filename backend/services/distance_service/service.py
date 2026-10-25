"""Distance calculation service with caching"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import redis
import json
from typing import List, Optional, Dict, Any
import logging

from shared.models import Activity, GPSCoordinates, DistanceMatrix
from shared.config import settings
from shared.utils import setup_logging, generate_cache_key, Timer
from .calculator import (
    calculate_distance_matrix,
    haversine_distance,
    find_nearest_neighbors,
    calculate_bounding_box
)

logger = setup_logging("distance-service", settings.LOG_LEVEL)


class DistanceService:
    """Service for calculating and caching distances between activities"""

    def __init__(self):
        """Initialize service with Redis cache"""
        self.redis_client = None
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection with error handling"""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=False,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {str(e)}. Caching will be disabled.")
            self.redis_client = None

    def calculate_matrix_for_activities(
        self,
        activities: List[Activity],
        speed_kmh: float = 30.0,
        use_cache: bool = True
    ) -> DistanceMatrix:
        """
        Calculate distance matrix for a list of activities
        """
        with Timer("Distance matrix calculation", logger):
            # Extract coordinates
            coordinates = []
            activity_ids = []

            for activity in activities:
                if not activity.coordinates:
                    activity.parse_coordinates()

                coordinates.append(activity.coordinates)
                activity_ids.append(activity.codigo_bia)

            # Check cache
            if use_cache and self.redis_client:
                cached_matrix = self._get_cached_matrix(activity_ids, speed_kmh)
                if cached_matrix:
                    logger.info("Using cached distance matrix")
                    return cached_matrix

            # Calculate matrix
            logger.info(f"Calculating distance matrix for {len(activities)} activities")
            distances, durations = calculate_distance_matrix(coordinates, speed_kmh)

            # Create result
            matrix = DistanceMatrix(
                activities_ids=activity_ids,
                distances_km=distances,
                durations_minutes=durations
            )

            # Cache result
            if use_cache and self.redis_client:
                self._cache_matrix(activity_ids, speed_kmh, matrix)

            return matrix

    def calculate_distance_between(
        self,
        coord1: GPSCoordinates,
        coord2: GPSCoordinates,
        speed_kmh: float = 30.0
    ) -> Dict[str, Any]:
        """
        Calculate distance and duration between two coordinates
        """
        from .calculator import calculate_duration_minutes

        distance_km = haversine_distance(coord1, coord2)
        duration_minutes = calculate_duration_minutes(distance_km, speed_kmh)

        return {
            "distance_km": round(distance_km, 2),
            "duration_minutes": duration_minutes,
            "duration_hours": round(duration_minutes / 60, 2)
        }

    def find_nearest_activities(
        self,
        origin: Activity,
        candidates: List[Activity],
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find k nearest activities to origin
        """
        if not origin.coordinates:
            origin.parse_coordinates()

        # Ensure all candidates have coordinates
        for activity in candidates:
            if not activity.coordinates:
                activity.parse_coordinates()

        # Get all coordinates
        all_activities = [origin] + candidates
        coordinates = [act.coordinates for act in all_activities]

        # Find nearest (origin is at index 0)
        nearest = find_nearest_neighbors(0, coordinates, k)

        # Build result with activity details
        results = []
        for idx, distance in nearest:
            # Adjust index (subtract 1 because origin was at index 0)
            activity_idx = idx - 1
            activity = candidates[activity_idx]

            results.append({
                "codigo_bia": activity.codigo_bia,
                "nombre": activity.nombre,
                "direccion": activity.direccion,
                "distance_km": round(distance, 2),
                "coordinates": {
                    "latitude": activity.coordinates.latitude,
                    "longitude": activity.coordinates.longitude
                }
            })

        return results

    def get_geographic_summary(self, activities: List[Activity]) -> Dict[str, Any]:
        """
        Get geographic summary of activities
        """
        # Ensure coordinates are parsed
        for activity in activities:
            if not activity.coordinates:
                activity.parse_coordinates()

        coordinates = [act.coordinates for act in activities]

        # Calculate bounding box
        bbox = calculate_bounding_box(coordinates)

        # Calculate approximate coverage area (very rough estimate)
        if bbox:
            lat_range = bbox["max_latitude"] - bbox["min_latitude"]
            lon_range = bbox["max_longitude"] - bbox["min_longitude"]
            # Rough area calculation (not accounting for curvature)
            area_km2 = lat_range * lon_range * (111.0 ** 2)

            bbox["area_km2_approx"] = round(area_km2, 2)

        # Group by city
        cities = {}
        for activity in activities:
            city = activity.ciudad
            if city not in cities:
                cities[city] = 0
            cities[city] += 1

        return {
            "total_activities": len(activities),
            "bounding_box": bbox,
            "cities": cities,
            "unique_cities": len(cities)
        }

    def _get_cached_matrix(
        self,
        activity_ids: List[str],
        speed_kmh: float
    ) -> Optional[DistanceMatrix]:
        """Retrieve cached distance matrix"""
        if not self.redis_client:
            return None

        try:
            # Generate cache key
            cache_data = {
                "ids": sorted(activity_ids),
                "speed": speed_kmh
            }
            cache_key = generate_cache_key("distance_matrix", cache_data)

            # Try to get from cache
            cached = self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return DistanceMatrix(**data)

            return None

        except Exception as e:
            logger.warning(f"Cache retrieval error: {str(e)}")
            return None

    def _cache_matrix(
        self,
        activity_ids: List[str],
        speed_kmh: float,
        matrix: DistanceMatrix
    ):
        """Cache distance matrix"""
        if not self.redis_client:
            return

        try:
            # Generate cache key
            cache_data = {
                "ids": sorted(activity_ids),
                "speed": speed_kmh
            }
            cache_key = generate_cache_key("distance_matrix", cache_data)

            # Store in cache
            data = matrix.model_dump_json()
            self.redis_client.setex(
                cache_key,
                settings.CACHE_TTL,
                data
            )
            logger.info(f"Cached distance matrix with key: {cache_key}")

        except Exception as e:
            logger.warning(f"Cache storage error: {str(e)}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.redis_client:
            return {
                "enabled": False,
                "message": "Cache is not available"
            }

        try:
            info = self.redis_client.info()
            return {
                "enabled": True,
                "connected": True,
                "keys": self.redis_client.dbsize(),
                "memory_used_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {
                "enabled": False,
                "error": str(e)
            }

    def clear_cache(self, pattern: str = "distance_matrix:*") -> int:
        """Clear cache entries matching pattern"""
        if not self.redis_client:
            return 0

        try:
            keys = list(self.redis_client.scan_iter(match=pattern))
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return 0

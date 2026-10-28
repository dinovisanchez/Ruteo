"""Utility functions shared by the gateway and the optimizer"""
import logging
import math
from datetime import time
from typing import Optional, Tuple, Dict

from .models import GPSCoordinates

# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371.0


def get_service_time(service_name: str, service_times_dict: Dict[str, int], default: int = 60) -> int:
    """
    Get service time with case-insensitive lookup and fallback to default

    Args:
        service_name: Name of the service
        service_times_dict: Dictionary with service times
        default: Default time if not found (default: 60 minutes)

    Returns:
        Service time in minutes
    """
    if not service_name:
        return default

    # Try exact match first
    if service_name in service_times_dict:
        return service_times_dict[service_name]

    # Try case-insensitive match
    service_lower = service_name.lower().strip()
    for key, value in service_times_dict.items():
        if key.lower().strip() == service_lower:
            return value

    # Try "default" key
    if 'default' in service_times_dict:
        return service_times_dict['default']

    # Ultimate fallback
    logger = logging.getLogger("utils")
    logger.warning(f"Service time not found for '{service_name}', using default: {default} minutes")
    return default


def setup_logging(service_name: str, log_level: str = "INFO") -> logging.Logger:
    """Configure logging for a service"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=f'%(asctime)s - {service_name} - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(service_name)
    return logger


def haversine_distance(coord1: GPSCoordinates, coord2: GPSCoordinates) -> float:
    """Great circle distance in kilometers between two points"""
    lat1, lon1 = math.radians(coord1.latitude), math.radians(coord1.longitude)
    lat2, lon2 = math.radians(coord2.latitude), math.radians(coord2.longitude)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def time_to_minutes(t: time) -> int:
    """Convert time object to minutes since midnight"""
    return t.hour * 60 + t.minute


def minutes_to_time(minutes: int) -> time:
    """Convert minutes since midnight to time object"""
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return time(hours, mins)


def add_minutes_to_time(t: time, minutes: int) -> time:
    """Add minutes to a time object"""
    total_minutes = time_to_minutes(t) + minutes
    return minutes_to_time(total_minutes)


def calculate_utilization(
    work_minutes: int,
    travel_minutes: int,
    total_available_minutes: int
) -> float:
    """Calculate crew utilization percentage"""
    if total_available_minutes <= 0:
        return 0.0

    used_minutes = work_minutes + travel_minutes
    utilization = (used_minutes / total_available_minutes) * 100
    return min(utilization, 100.0)


def validate_gps_colombia(latitude: float, longitude: float) -> Tuple[bool, Optional[str]]:
    """
    Validate if GPS coordinates are within Colombia boundaries
    Returns (is_valid, error_message)
    """
    from .config import settings

    if not (settings.MIN_LATITUDE <= latitude <= settings.MAX_LATITUDE):
        return False, f"Latitude {latitude} is outside Colombia range ({settings.MIN_LATITUDE} to {settings.MAX_LATITUDE})"

    if not (settings.MIN_LONGITUDE <= longitude <= settings.MAX_LONGITUDE):
        return False, f"Longitude {longitude} is outside Colombia range ({settings.MIN_LONGITUDE} to {settings.MAX_LONGITUDE})"

    return True, None

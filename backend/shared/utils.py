"""Utility functions for Route Optimizer services"""
import logging
from datetime import time, datetime, timedelta
from typing import Optional, Tuple, Dict
import hashlib
import json


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


def time_difference_minutes(start: time, end: time) -> int:
    """Calculate difference in minutes between two times"""
    start_mins = time_to_minutes(start)
    end_mins = time_to_minutes(end)

    if end_mins < start_mins:
        # Handle next day
        end_mins += 24 * 60

    return end_mins - start_mins


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


def generate_cache_key(prefix: str, data: dict) -> str:
    """Generate a cache key from data"""
    # Sort keys to ensure consistent hashing
    data_str = json.dumps(data, sort_keys=True)
    hash_obj = hashlib.md5(data_str.encode())
    return f"{prefix}:{hash_obj.hexdigest()}"


def format_distance(km: float) -> str:
    """Format distance in km with appropriate precision"""
    return f"{km:.2f} km"


def format_duration(minutes: int) -> str:
    """Format duration in human-readable format"""
    if minutes < 60:
        return f"{minutes} min"

    hours = minutes // 60
    mins = minutes % 60

    if mins == 0:
        return f"{hours} h"

    return f"{hours}h {mins}min"


def format_time_range(start: time, end: time) -> str:
    """Format time range as string"""
    return f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}"


def calculate_work_hours(start: time, end: time) -> float:
    """Calculate work hours between two times"""
    minutes = time_difference_minutes(start, end)
    return minutes / 60.0


def is_valid_service_time(
    start: time,
    duration_minutes: int,
    work_start: time,
    work_end: time
) -> bool:
    """Check if a service can be completed within work hours"""
    service_end = add_minutes_to_time(start, duration_minutes)
    work_end_minutes = time_to_minutes(work_end)
    service_end_minutes = time_to_minutes(service_end)

    return service_end_minutes <= work_end_minutes


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero"""
    if denominator == 0:
        return default
    return numerator / denominator


class Timer:
    """Simple timer context manager for performance monitoring"""

    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.logger = logger
        self.start_time = None
        self.elapsed = None

    def __enter__(self):
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = (datetime.now() - self.start_time).total_seconds()
        if self.logger:
            self.logger.info(f"{self.name} took {self.elapsed:.3f} seconds")


def chunk_list(lst: list, chunk_size: int) -> list:
    """Split a list into chunks of specified size"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_list(nested_list: list) -> list:
    """Flatten a nested list"""
    return [item for sublist in nested_list for item in sublist]

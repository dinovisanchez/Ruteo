"""Data validation functions for activities and GPS coordinates"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.models import Activity, GPSCoordinates
from shared.utils import validate_gps_colombia
from typing import List, Tuple, Optional
import re


def validate_gps_format(gps_string: str) -> Tuple[bool, Optional[str], Optional[GPSCoordinates]]:
    """
    Validate GPS coordinate string format
    Returns (is_valid, error_message, coordinates)
    """
    try:
        # Remove whitespace
        gps_clean = gps_string.strip().replace(' ', '')

        # Check format: should be "number,number"
        pattern = r'^-?\d+\.?\d*,-?\d+\.?\d*$'
        if not re.match(pattern, gps_clean):
            return False, f"Invalid GPS format: '{gps_string}'. Expected format: 'latitude,longitude'", None

        # Split and parse
        parts = gps_clean.split(',')
        if len(parts) != 2:
            return False, f"GPS must have exactly 2 values separated by comma", None

        try:
            lat = float(parts[0])
            lon = float(parts[1])
        except ValueError as e:
            return False, f"GPS values must be valid numbers: {str(e)}", None

        # Validate ranges
        if not (-90 <= lat <= 90):
            return False, f"Latitude {lat} must be between -90 and 90", None

        if not (-180 <= lon <= 180):
            return False, f"Longitude {lon} must be between -180 and 180", None

        # Create coordinates object
        coords = GPSCoordinates(latitude=lat, longitude=lon)

        # Validate Colombia boundaries
        is_valid, error = validate_gps_colombia(lat, lon)
        if not is_valid:
            return False, error, coords

        return True, None, coords

    except Exception as e:
        return False, f"Error validating GPS: {str(e)}", None


def validate_required_fields(data: dict, required_fields: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate that all required fields are present and not empty
    Returns (is_valid, error_message)
    """
    missing_fields = []
    empty_fields = []

    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif not data[field] or (isinstance(data[field], str) and not data[field].strip()):
            empty_fields.append(field)

    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    if empty_fields:
        return False, f"Empty required fields: {', '.join(empty_fields)}"

    return True, None


def validate_activity_row(row_dict: dict, row_number: int) -> Tuple[bool, Optional[str], Optional[Activity]]:
    """
    Validate a single activity row
    Returns (is_valid, error_message, activity_object)
    """
    # Define required fields
    required_fields = [
        'codigo_bia',
        'servicio',
        'gps',
        'nombre',
        'direccion',
        'ciudad',
        'departamento',
        'or_operador'
    ]

    # Check required fields
    is_valid, error = validate_required_fields(row_dict, required_fields)
    if not is_valid:
        return False, f"Row {row_number}: {error}", None

    # Validate GPS format
    gps_valid, gps_error, coords = validate_gps_format(row_dict['gps'])
    if not gps_valid:
        return False, f"Row {row_number}: {gps_error}", None

    try:
        # Create Activity object
        activity = Activity(
            codigo_bia=str(row_dict['codigo_bia']).strip(),
            servicio=str(row_dict['servicio']).strip().lower(),
            gps=str(row_dict['gps']).strip(),
            nombre=str(row_dict['nombre']).strip(),
            direccion=str(row_dict['direccion']).strip(),
            ciudad=str(row_dict['ciudad']).strip(),
            departamento=str(row_dict['departamento']).strip(),
            or_operador=str(row_dict['or_operador']).strip(),
            coordinates=coords
        )

        return True, None, activity

    except Exception as e:
        return False, f"Row {row_number}: Error creating activity: {str(e)}", None


def validate_activities_batch(activities: List[Activity]) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validate a batch of activities for consistency
    Returns (is_valid, error_message, list_of_warnings)
    """
    warnings = []

    # Check for duplicate codes
    codes = [act.codigo_bia for act in activities]
    unique_codes = set(codes)
    if len(codes) != len(unique_codes):
        duplicates = [code for code in unique_codes if codes.count(code) > 1]
        warnings.append(f"Duplicate activity codes found: {', '.join(duplicates)}")

    # Check for activities at same location
    locations = {}
    for act in activities:
        if act.coordinates:
            loc_key = f"{act.coordinates.latitude:.6f},{act.coordinates.longitude:.6f}"
            if loc_key in locations:
                locations[loc_key].append(act.codigo_bia)
            else:
                locations[loc_key] = [act.codigo_bia]

    for loc, codes in locations.items():
        if len(codes) > 1:
            warnings.append(f"Multiple activities at same location {loc}: {', '.join(codes)}")

    # Check service types
    service_types = set(act.servicio for act in activities)
    if len(service_types) > 10:
        warnings.append(f"Large number of service types detected ({len(service_types)}). This may affect time estimation.")

    return True, None, warnings


def normalize_service_name(service: str) -> str:
    """Normalize service name to lowercase and remove extra whitespace"""
    return service.strip().lower()


def validate_service_times(service_times: dict, activities: List[Activity]) -> Tuple[bool, Optional[str]]:
    """
    Validate that service times are defined for all service types in activities
    Returns (is_valid, error_message)
    """
    # Get all unique service types from activities
    activity_services = set(act.servicio for act in activities)

    # Get service types with defined times
    defined_services = set(service_times.keys())

    # Check for missing service time definitions
    missing_services = activity_services - defined_services
    if missing_services:
        return False, f"Missing service time definitions for: {', '.join(missing_services)}"

    return True, None

"""Data processing service for file uploads and validation"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pandas as pd
from typing import List, Tuple, Dict, Any
import logging
from pathlib import Path

from shared.models import Activity, ActivityLot, WorkConfiguration
from shared.utils import setup_logging
from .validators import validate_activity_row, validate_activities_batch, validate_service_times

logger = setup_logging("data-service")


class DataProcessor:
    """Process and validate uploaded data files"""

    def __init__(self):
        self.supported_formats = ['.xlsx', '.xls', '.csv']

    def process_file(self, file_path: str) -> Tuple[bool, str, List[Activity]]:
        """
        Process uploaded file and extract activities
        Returns (success, message, activities_list)
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return False, f"File not found: {file_path}", []

            if path.suffix.lower() not in self.supported_formats:
                return False, f"Unsupported file format: {path.suffix}. Supported: {', '.join(self.supported_formats)}", []

            logger.info(f"Processing file: {file_path}")

            # Read file based on format
            if path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            elif path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            else:
                return False, f"Unsupported format: {path.suffix}", []

            # Validate dataframe
            success, message, activities = self._process_dataframe(df)

            if success:
                logger.info(f"Successfully processed {len(activities)} activities from {file_path}")

            return success, message, activities

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            return False, f"Error processing file: {str(e)}", []

    def _process_dataframe(self, df: pd.DataFrame) -> Tuple[bool, str, List[Activity]]:
        """
        Process pandas DataFrame and validate data
        Returns (success, message, activities_list)
        """
        try:
            # Check if dataframe is empty
            if df.empty:
                return False, "File is empty", []

            # Normalize column names (lowercase, strip whitespace)
            df.columns = df.columns.str.strip().str.lower()

            # Define expected columns
            expected_columns = [
                'codigo_bia',
                'servicio',
                'gps',
                'nombre',
                'direccion',
                'ciudad',
                'departamento',
                'or_operador'
            ]

            # Check for required columns
            missing_columns = [col for col in expected_columns if col not in df.columns]
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}", []

            # Remove rows with all NaN values
            df = df.dropna(how='all')

            if df.empty:
                return False, "No valid data rows found", []

            # Process each row
            activities = []
            errors = []

            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                row_number = idx + 2  # +2 because Excel starts at 1 and we have header

                is_valid, error, activity = validate_activity_row(row_dict, row_number)

                if is_valid and activity:
                    activities.append(activity)
                else:
                    errors.append(error)

            # Check if we got any valid activities
            if not activities:
                error_summary = "\n".join(errors[:10])  # Show first 10 errors
                if len(errors) > 10:
                    error_summary += f"\n... and {len(errors) - 10} more errors"
                return False, f"No valid activities found. Errors:\n{error_summary}", []

            # Validate batch consistency
            batch_valid, batch_error, warnings = validate_activities_batch(activities)

            # Log warnings
            for warning in warnings:
                logger.warning(warning)

            # Build success message
            message = f"Successfully loaded {len(activities)} activities"
            if errors:
                message += f" ({len(errors)} rows had errors and were skipped)"
            if warnings:
                message += f". Warnings: {len(warnings)}"

            return True, message, activities

        except Exception as e:
            logger.error(f"Error processing dataframe: {str(e)}")
            return False, f"Error processing data: {str(e)}", []

    def validate_activity_lot(
        self,
        activities: List[Activity],
        configuration: WorkConfiguration
    ) -> Tuple[bool, str]:
        """
        Validate an activity lot with its configuration
        Returns (is_valid, message)
        """
        try:
            if not activities:
                return False, "No activities provided"

            # Create service times dictionary
            service_times_dict = {
                st.servicio: st.duracion_minutos
                for st in configuration.tiempos_servicio
            }

            # Validate service times are defined for all activity types
            is_valid, error = validate_service_times(service_times_dict, activities)
            if not is_valid:
                return False, error

            # Validate work configuration
            if configuration.horas_laborales <= 0:
                return False, "Work hours must be greater than 0"

            if configuration.velocidad_promedio_kmh <= 0:
                return False, "Average speed must be greater than 0"

            # Validate starting point
            if not configuration.punto_partida:
                return False, "Starting point coordinates required"

            return True, "Activity lot is valid"

        except Exception as e:
            logger.error(f"Error validating activity lot: {str(e)}")
            return False, f"Validation error: {str(e)}"

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get information about uploaded file"""
        try:
            path = Path(file_path)

            if not path.exists():
                return {"error": "File not found"}

            info = {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
                "extension": path.suffix,
                "exists": True
            }

            # Try to get row count if it's a supported format
            if path.suffix.lower() in self.supported_formats:
                try:
                    if path.suffix.lower() in ['.xlsx', '.xls']:
                        df = pd.read_excel(file_path)
                    else:
                        df = pd.read_csv(file_path)

                    info["rows"] = len(df)
                    info["columns"] = len(df.columns)
                    info["column_names"] = df.columns.tolist()
                except:
                    pass

            return info

        except Exception as e:
            logger.error(f"Error getting file info: {str(e)}")
            return {"error": str(e)}

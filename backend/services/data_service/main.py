"""Data Service FastAPI application"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import shutil
from pathlib import Path
import uuid

from shared.models import Activity, ActivityLot, WorkConfiguration, HealthResponse, ErrorResponse
from shared.config import settings
from shared.utils import setup_logging
from .service import DataProcessor

# Setup logging
logger = setup_logging("data-service", settings.LOG_LEVEL)

# Create FastAPI app
app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Data Service",
    description="Service for uploading and validating activity data",
    version=settings.VERSION
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directory
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Initialize data processor
processor = DataProcessor()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="data-service",
        version=settings.VERSION
    )


@app.post("/upload", response_model=dict)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload and process activity data file (Excel or CSV)
    Returns parsed activities
    """
    try:
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}{file_ext}"

        # Save uploaded file
        logger.info(f"Saving uploaded file: {file.filename} -> {file_path}")
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Process file
        success, message, activities = processor.process_file(str(file_path))

        if not success:
            # Clean up file
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=message
            )

        # Get file info
        file_info = processor.get_file_info(str(file_path))

        logger.info(f"File processed successfully: {len(activities)} activities loaded")

        return {
            "success": True,
            "message": message,
            "file_id": file_id,
            "file_info": file_info,
            "total_activities": len(activities),
            "activities": [act.model_dump() for act in activities]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in upload endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
    finally:
        # Clean up uploaded file handle
        await file.close()


@app.post("/validate", response_model=dict)
async def validate_activities(activity_lot: ActivityLot):
    """
    Validate activity lot with configuration
    """
    try:
        logger.info(f"Validating activity lot: {activity_lot.nombre_lote}")

        is_valid, message = processor.validate_activity_lot(
            activity_lot.actividades,
            activity_lot.configuracion
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=message
            )

        return {
            "success": True,
            "message": message,
            "total_activities": len(activity_lot.actividades),
            "valid": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in validate endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error: {str(e)}"
        )


@app.get("/files/{file_id}", response_model=dict)
async def get_file_info(file_id: str):
    """Get information about an uploaded file"""
    try:
        # Find file with this ID
        matching_files = list(UPLOAD_DIR.glob(f"{file_id}.*"))

        if not matching_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_id}"
            )

        file_path = matching_files[0]
        file_info = processor.get_file_info(str(file_path))

        return {
            "file_id": file_id,
            "info": file_info
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@app.delete("/files/{file_id}", response_model=dict)
async def delete_file(file_id: str):
    """Delete an uploaded file"""
    try:
        # Find and delete file
        matching_files = list(UPLOAD_DIR.glob(f"{file_id}.*"))

        if not matching_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_id}"
            )

        file_path = matching_files[0]
        file_path.unlink()

        logger.info(f"Deleted file: {file_id}")

        return {
            "success": True,
            "message": f"File {file_id} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

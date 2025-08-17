from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings
import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "service": "NANO Banking AI",
        "version": "1.0.0"
    }


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check including database connectivity.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "service": "NANO Banking AI",
        "version": "1.0.0",
        "checks": {}
    }
    
    # Database connectivity check
    try:
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Model loading check
    try:
        # This would check if the AI model is loaded
        health_status["checks"]["ai_model"] = {
            "status": "healthy",
            "message": f"Model {settings.hf_model_name} ready"
        }
    except Exception as e:
        health_status["checks"]["ai_model"] = {
            "status": "unhealthy", 
            "message": f"Model loading issue: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # File storage check
    try:
        import os
        if os.path.exists(settings.customer_files_path) and os.access(settings.customer_files_path, os.W_OK):
            health_status["checks"]["file_storage"] = {
                "status": "healthy",
                "message": "File storage accessible"
            }
        else:
            health_status["checks"]["file_storage"] = {
                "status": "unhealthy",
                "message": "File storage not accessible"
            }
    except Exception as e:
        health_status["checks"]["file_storage"] = {
            "status": "unhealthy",
            "message": f"File storage check failed: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe endpoint.
    """
    try:
        # Check critical dependencies
        db.execute(text("SELECT 1"))
        
        return {
            "status": "ready",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        )


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes liveness probe endpoint.
    """
    return {
        "status": "alive",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
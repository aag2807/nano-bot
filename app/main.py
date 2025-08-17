from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import uvicorn
import logging
from datetime import datetime

from app.config import settings
from app.database import create_tables, get_db
from app.api.endpoints import chat, health
from app.api.middleware.auth import rate_limit_middleware, security_headers_middleware, input_validator
from app.api.middleware.logging import request_logger

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    """
    # Startup
    logger.info("Starting NANO Banking AI Service...")
    
    # Create database tables
    try:
        create_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    
    # Log startup info
    logger.info(f"Bank Name: {settings.bank_name}")
    logger.info(f"Model: {settings.hf_model_name}")
    logger.info(f"Debug Mode: {settings.debug}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down NANO Banking AI Service...")


# Create FastAPI app
app = FastAPI(
    title="NANO Banking AI",
    description="Professional customer service AI assistant for Bank Of AI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourbankdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Security middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Apply rate limiting
    response = await rate_limit_middleware(request, call_next)
    return response


# Security headers middleware
@app.middleware("http") 
async def add_security_headers(request: Request, call_next):
    response = await security_headers_middleware(request, call_next)
    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Get database session for logging
    db_generator = get_db()
    db = next(db_generator)
    try:
        response = await request_logger.log_request_response(request, call_next, db)
        return response
    finally:
        db.close()


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Include routers
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["Health"]
)

app.include_router(
    chat.router,
    prefix="/api/v1",
    tags=["Chat"]
)


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint with service information.
    """
    return {
        "service": "NANO Banking AI",
        "version": "1.0.0",
        "bank": settings.bank_name,
        "description": "Professional customer service AI assistant",
        "endpoints": {
            "health": "/api/v1/health",
            "chat": "/api/v1/chat",
            "session": "/api/v1/session"
        },
        "timestamp": datetime.utcnow().isoformat()
    }


# API information endpoint
@app.get("/api/v1/info")
async def api_info():
    """
    API information and capabilities.
    """
    return {
        "name": "NANO Banking AI API",
        "version": "1.0.0",
        "capabilities": [
            "Identity Verification",
            "Account Balance Inquiry", 
            "Transaction History",
            "Contact Information Updates",
            "Document Management",
            "General Banking Support",
            "Human Escalation"
        ],
        "security_features": [
            "Multi-factor Authentication",
            "Session Management",
            "Audit Logging",
            "Rate Limiting",
            "Input Validation"
        ],
        "model": settings.hf_model_name,
        "bank": settings.bank_name
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
"""
Legal Data Pipeline - Main FastAPI Application
Blue-Green Deployment Ready
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database.connection import DatabaseConnectionManager
from config import get_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get environment info
ENVIRONMENT = os.getenv('ENVIRONMENT', 'unknown')
APP_VERSION = os.getenv('APP_VERSION', '1.0.0')

app = FastAPI(
    title="Legal Data Pipeline",
    description=f"Legal data processing pipeline - Environment: {ENVIRONMENT}",
    version=APP_VERSION,
    docs_url="/docs" if ENVIRONMENT in ['development', 'blue', 'green'] else None,
    redoc_url="/redoc" if ENVIRONMENT in ['development', 'blue', 'green'] else None
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database manager
db_manager = DatabaseConnectionManager()

class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    timestamp: str
    database: Dict[str, Any]
    uptime_seconds: float

class StatusResponse(BaseModel):
    status: str
    environment: str
    version: str
    timestamp: str
    services: Dict[str, str]

# Application startup time
startup_time = datetime.utcnow()

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Legal Data Pipeline API",
        "environment": ENVIRONMENT,
        "version": APP_VERSION,
        "status": "running"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check endpoint"""
    current_time = datetime.utcnow()
    uptime = (current_time - startup_time).total_seconds()
    
    # Check database connection
    database_status = {"status": "unknown", "error": None}
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as health_check")
            result = cursor.fetchone()
            
            if result and result[0] == 1:
                database_status = {
                    "status": "healthy",
                    "connection_pool_size": db_manager.pool.pool_size if hasattr(db_manager, 'pool') else 0,
                    "host": os.getenv('DB_HOST', 'unknown'),
                    "port": os.getenv('DB_PORT', 'unknown')
                }
            else:
                database_status = {"status": "unhealthy", "error": "Invalid response"}
            
            cursor.close()
            
    except Exception as e:
        logger.error(f"Health check database error: {e}")
        database_status = {"status": "unhealthy", "error": str(e)}
    
    # Determine overall status
    overall_status = "healthy" if database_status["status"] == "healthy" else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        environment=ENVIRONMENT,
        version=APP_VERSION,
        timestamp=current_time.isoformat(),
        database=database_status,
        uptime_seconds=uptime
    )

@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get application status"""
    services = {
        "database": "unknown",
        "redis": "unknown",
        "kafka": "unknown"
    }
    
    # Check database
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            services["database"] = "healthy"
    except:
        services["database"] = "unhealthy"
    
    # Check Redis (basic)
    try:
        import redis
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD', ''),
            socket_timeout=5
        )
        redis_client.ping()
        services["redis"] = "healthy"
    except:
        services["redis"] = "unhealthy"
    
    # Check Kafka (basic)
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(','),
            request_timeout_ms=5000
        )
        # Just try to get metadata
        producer.bootstrap_connected()
        producer.close()
        services["kafka"] = "healthy"
    except:
        services["kafka"] = "unhealthy"
    
    return StatusResponse(
        status="healthy" if all(s == "healthy" for s in services.values()) else "partial",
        environment=ENVIRONMENT,
        version=APP_VERSION,
        timestamp=datetime.utcnow().isoformat(),
        services=services
    )

@app.get("/info")
async def get_info():
    """Get application information"""
    return {
        "name": "Legal Data Pipeline",
        "environment": ENVIRONMENT,
        "version": APP_VERSION,
        "python_version": os.sys.version,
        "startup_time": startup_time.isoformat(),
        "uptime_seconds": (datetime.utcnow() - startup_time).total_seconds(),
        "database": {
            "host": os.getenv('DB_HOST', 'unknown'),
            "port": os.getenv('DB_PORT', 'unknown'),
            "name": os.getenv('DB_NAME', 'unknown')
        },
        "features": [
            "health_monitoring",
            "blue_green_deployment", 
            "database_connectivity",
            "redis_caching",
            "kafka_messaging"
        ]
    }

@app.get("/api/legal-documents")
async def get_legal_documents(limit: int = 10, offset: int = 0):
    """Get legal documents"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Check if table exists
            cursor.execute("SHOW TABLES LIKE 'legal_documents'")
            if not cursor.fetchone():
                return {"documents": [], "total": 0, "message": "Table not yet created"}
            
            # Get documents
            cursor.execute(
                "SELECT * FROM legal_documents ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset)
            )
            documents = cursor.fetchall()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) as total FROM legal_documents")
            total = cursor.fetchone()['total']
            
            cursor.close()
            
            return {
                "documents": documents,
                "total": total,
                "limit": limit,
                "offset": offset,
                "environment": ENVIRONMENT
            }
            
    except Exception as e:
        logger.error(f"Error fetching legal documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/legal-documents")
async def create_legal_document(document: dict):
    """Create a new legal document"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert document (simplified)
            cursor.execute(
                "INSERT INTO legal_documents (title, content, document_type, created_at) VALUES (%s, %s, %s, %s)",
                (
                    document.get('title', 'Untitled'),
                    document.get('content', ''),
                    document.get('document_type', 'unknown'),
                    datetime.utcnow()
                )
            )
            
            document_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            
            logger.info(f"Created document {document_id} in {ENVIRONMENT} environment")
            
            return {
                "id": document_id,
                "message": "Document created successfully",
                "environment": ENVIRONMENT
            }
            
    except Exception as e:
        logger.error(f"Error creating legal document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/deployment/info")
async def deployment_info():
    """Get deployment-specific information"""
    return {
        "environment": ENVIRONMENT,
        "version": APP_VERSION,
        "deployment_time": startup_time.isoformat(),
        "database_config": {
            "host": os.getenv('DB_HOST'),
            "port": os.getenv('DB_PORT'),
            "name": os.getenv('DB_NAME')
        },
        "redis_config": {
            "host": os.getenv('REDIS_HOST'),
            "port": os.getenv('REDIS_PORT')
        }
    }

# Exception handlers
@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "environment": ENVIRONMENT,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info(f"Legal Data Pipeline starting up - Environment: {ENVIRONMENT}, Version: {APP_VERSION}")
    
    # Test database connection
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Legal Data Pipeline shutting down - Environment: {ENVIRONMENT}")
    try:
        db_manager.close_all_connections()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
Deployment API for Blue-Green Management
Provides REST API endpoints for managing blue-green deployments
"""

import os
import logging
from datetime import datetime
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from blue_green_deploy import BlueGreenDeploymentManager
from nginx_controller import NginxController
from health_monitor import HealthMonitor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Blue-Green Deployment API",
    description="API for managing blue-green deployments of Legal Data Pipeline",
    version="1.0.0"
)

# Initialize managers
deployment_manager = BlueGreenDeploymentManager()
nginx_controller = NginxController()

class DeploymentRequest(BaseModel):
    version: Optional[str] = None
    skip_sync: bool = False

class DeploymentResponse(BaseModel):
    success: bool
    message: str
    deployment_id: Optional[str] = None
    timestamp: str

class StatusResponse(BaseModel):
    status: Dict
    timestamp: str

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Blue-Green Deployment API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        redis_status = "healthy"
        try:
            deployment_manager.redis_client.ping()
        except:
            redis_status = "unhealthy"
        
        return {
            "status": "healthy" if redis_status == "healthy" else "unhealthy",
            "redis": redis_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.post("/deploy", response_model=DeploymentResponse)
async def deploy(request: DeploymentRequest, background_tasks: BackgroundTasks):
    """Trigger blue-green deployment"""
    deployment_id = f"deploy_{int(datetime.utcnow().timestamp())}"
    
    try:
        logger.info(f"Starting deployment {deployment_id}")
        
        # Run deployment in background
        def run_deployment():
            try:
                success = deployment_manager.deploy(
                    target_version=request.version,
                    skip_sync=request.skip_sync
                )
                
                # Store deployment result
                result = {
                    "deployment_id": deployment_id,
                    "success": success,
                    "completed_at": datetime.utcnow().isoformat(),
                    "version": request.version
                }
                
                deployment_manager.redis_client.setex(
                    f'deployment:result:{deployment_id}',
                    3600,  # 1 hour expiration
                    str(result)
                )
                
            except Exception as e:
                logger.error(f"Deployment {deployment_id} failed: {e}")
                
                # Store failure result
                result = {
                    "deployment_id": deployment_id,
                    "success": False,
                    "error": str(e),
                    "completed_at": datetime.utcnow().isoformat()
                }
                
                deployment_manager.redis_client.setex(
                    f'deployment:result:{deployment_id}',
                    3600,
                    str(result)
                )
        
        background_tasks.add_task(run_deployment)
        
        return DeploymentResponse(
            success=True,
            message=f"Deployment {deployment_id} started",
            deployment_id=deployment_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start deployment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rollback", response_model=DeploymentResponse)
async def rollback(background_tasks: BackgroundTasks):
    """Trigger rollback to previous environment"""
    rollback_id = f"rollback_{int(datetime.utcnow().timestamp())}"
    
    try:
        logger.info(f"Starting rollback {rollback_id}")
        
        # Run rollback in background
        def run_rollback():
            try:
                success = deployment_manager.rollback()
                
                # Store rollback result
                result = {
                    "rollback_id": rollback_id,
                    "success": success,
                    "completed_at": datetime.utcnow().isoformat()
                }
                
                deployment_manager.redis_client.setex(
                    f'deployment:rollback_result:{rollback_id}',
                    3600,
                    str(result)
                )
                
            except Exception as e:
                logger.error(f"Rollback {rollback_id} failed: {e}")
                
                result = {
                    "rollback_id": rollback_id,
                    "success": False,
                    "error": str(e),
                    "completed_at": datetime.utcnow().isoformat()
                }
                
                deployment_manager.redis_client.setex(
                    f'deployment:rollback_result:{rollback_id}',
                    3600,
                    str(result)
                )
        
        background_tasks.add_task(run_rollback)
        
        return DeploymentResponse(
            success=True,
            message=f"Rollback {rollback_id} started",
            deployment_id=rollback_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to start rollback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status", response_model=StatusResponse)
async def get_deployment_status():
    """Get current deployment status"""
    try:
        status = deployment_manager.status()
        return StatusResponse(
            status=status,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/deployment/{deployment_id}")
async def get_deployment_result(deployment_id: str):
    """Get result of a specific deployment"""
    try:
        result = deployment_manager.redis_client.get(f'deployment:result:{deployment_id}')
        if not result:
            result = deployment_manager.redis_client.get(f'deployment:rollback_result:{deployment_id}')
        
        if result:
            return {"result": eval(result)}  # Note: In production, use json.loads instead of eval
        else:
            raise HTTPException(status_code=404, detail="Deployment result not found")
            
    except Exception as e:
        logger.error(f"Failed to get deployment result: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/nginx/status")
async def get_nginx_status():
    """Get Nginx configuration status"""
    try:
        status = nginx_controller.get_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get Nginx status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/nginx/switch/{environment}")
async def switch_nginx_upstream(environment: str):
    """Manually switch Nginx upstream"""
    if environment not in ['blue', 'green']:
        raise HTTPException(status_code=400, detail="Environment must be 'blue' or 'green'")
    
    try:
        success = nginx_controller.switch_upstream(environment)
        
        if success:
            return {
                "success": True,
                "message": f"Successfully switched to {environment} environment",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to switch upstream")
            
    except Exception as e:
        logger.error(f"Failed to switch upstream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health-monitor")
async def get_health_monitor_status():
    """Get health monitoring data from Redis"""
    try:
        current_status = deployment_manager.redis_client.get('health:current_status')
        alerts = deployment_manager.redis_client.lrange('health:alerts', 0, 9)  # Last 10 alerts
        
        return {
            "current_status": eval(current_status) if current_status else None,
            "recent_alerts": [eval(alert) for alert in alerts] if alerts else [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get health monitor status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)

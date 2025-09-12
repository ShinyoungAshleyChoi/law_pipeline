#!/usr/bin/env python3
"""
Health Monitor for Blue-Green Deployment

Continuously monitors the health of both blue and green environments
and provides real-time status updates.
"""

import os
import time
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

import redis
import httpx
from httpx import ConnectError, TimeoutException

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class HealthStatus:
    """Health status data structure"""
    environment: str
    url: str
    status: str  # healthy, unhealthy, unknown
    response_time_ms: float
    status_code: Optional[int]
    last_check: str
    error_message: Optional[str] = None

@dataclass
class SystemStatus:
    """Overall system status"""
    active_environment: str
    blue_status: HealthStatus
    green_status: HealthStatus
    nginx_status: HealthStatus
    overall_status: str
    last_updated: str

class HealthMonitor:
    """Monitors health of blue-green deployment environments"""
    
    def __init__(self):
        # Configuration from environment variables
        self.blue_app_url = os.getenv('BLUE_APP_URL', 'http://app-blue:8000')
        self.green_app_url = os.getenv('GREEN_APP_URL', 'http://app-green:8000')
        self.nginx_url = os.getenv('NGINX_URL', 'http://nginx:80')
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '30'))
        
        # Redis configuration
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.redis_password = os.getenv('REDIS_PASSWORD', '')
        
        # Setup Redis client
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            decode_responses=True
        )
        
        # HTTP client with timeout
        self.http_client = httpx.AsyncClient(timeout=10.0)
        
        # Health check history (in-memory for simplicity)
        self.health_history: List[SystemStatus] = []
        self.max_history = 100
        
    async def check_endpoint_health(self, url: str, environment: str) -> HealthStatus:
        """Check health of a specific endpoint"""
        start_time = time.time()
        
        try:
            response = await self.http_client.get(f"{url}/health")
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                status = "healthy"
                error_message = None
            else:
                status = "unhealthy"
                error_message = f"HTTP {response.status_code}"
                
            return HealthStatus(
                environment=environment,
                url=url,
                status=status,
                response_time_ms=round(response_time, 2),
                status_code=response.status_code,
                last_check=datetime.utcnow().isoformat(),
                error_message=error_message
            )
            
        except (ConnectError, TimeoutException) as e:
            response_time = (time.time() - start_time) * 1000
            return HealthStatus(
                environment=environment,
                url=url,
                status="unhealthy",
                response_time_ms=round(response_time, 2),
                status_code=None,
                last_check=datetime.utcnow().isoformat(),
                error_message=str(e)
            )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthStatus(
                environment=environment,
                url=url,
                status="unknown",
                response_time_ms=round(response_time, 2),
                status_code=None,
                last_check=datetime.utcnow().isoformat(),
                error_message=str(e)
            )
    
    def get_active_environment(self) -> str:
        """Get currently active environment from Redis"""
        try:
            active_env = self.redis_client.get('deployment:active_environment')
            return active_env or 'blue'
        except Exception as e:
            logger.warning(f"Could not get active environment: {e}")
            return 'blue'
    
    async def run_health_checks(self) -> SystemStatus:
        """Run health checks on all environments"""
        logger.debug("Running health checks...")
        
        # Check all endpoints concurrently
        tasks = [
            self.check_endpoint_health(self.blue_app_url, 'blue'),
            self.check_endpoint_health(self.green_app_url, 'green'),
            self.check_endpoint_health(self.nginx_url, 'nginx')
        ]
        
        blue_status, green_status, nginx_status = await asyncio.gather(*tasks)
        
        # Get active environment
        active_environment = self.get_active_environment()
        
        # Determine overall status
        active_status = blue_status if active_environment == 'blue' else green_status
        overall_status = "healthy" if (active_status.status == "healthy" and nginx_status.status == "healthy") else "unhealthy"
        
        system_status = SystemStatus(
            active_environment=active_environment,
            blue_status=blue_status,
            green_status=green_status,
            nginx_status=nginx_status,
            overall_status=overall_status,
            last_updated=datetime.utcnow().isoformat()
        )
        
        return system_status
    
    def store_health_status(self, status: SystemStatus) -> None:
        """Store health status in Redis and memory"""
        try:
            # Store in Redis with expiration
            status_data = asdict(status)
            self.redis_client.setex(
                'health:current_status',
                self.check_interval * 2,  # Expire after 2 check intervals
                json.dumps(status_data)
            )
            
            # Store detailed history
            self.redis_client.lpush('health:history', json.dumps(status_data))
            self.redis_client.ltrim('health:history', 0, self.max_history - 1)  # Keep only last N entries
            
            # Store in memory
            self.health_history.append(status)
            if len(self.health_history) > self.max_history:
                self.health_history.pop(0)
            
            logger.debug(f"Health status stored - Overall: {status.overall_status}, Active: {status.active_environment}")
            
        except Exception as e:
            logger.error(f"Failed to store health status: {e}")
    
    def get_health_metrics(self) -> Dict:
        """Get health metrics summary"""
        if not self.health_history:
            return {}
        
        recent_checks = self.health_history[-10:]  # Last 10 checks
        
        # Calculate uptime percentages
        total_checks = len(recent_checks)
        blue_healthy = sum(1 for status in recent_checks if status.blue_status.status == "healthy")
        green_healthy = sum(1 for status in recent_checks if status.green_status.status == "healthy")
        nginx_healthy = sum(1 for status in recent_checks if status.nginx_status.status == "healthy")
        overall_healthy = sum(1 for status in recent_checks if status.overall_status == "healthy")
        
        # Calculate average response times
        blue_response_times = [s.blue_status.response_time_ms for s in recent_checks if s.blue_status.response_time_ms]
        green_response_times = [s.green_status.response_time_ms for s in recent_checks if s.green_status.response_time_ms]
        nginx_response_times = [s.nginx_status.response_time_ms for s in recent_checks if s.nginx_status.response_time_ms]
        
        return {
            'total_checks': total_checks,
            'uptime_percentages': {
                'blue': (blue_healthy / total_checks * 100) if total_checks > 0 else 0,
                'green': (green_healthy / total_checks * 100) if total_checks > 0 else 0,
                'nginx': (nginx_healthy / total_checks * 100) if total_checks > 0 else 0,
                'overall': (overall_healthy / total_checks * 100) if total_checks > 0 else 0
            },
            'average_response_times': {
                'blue': sum(blue_response_times) / len(blue_response_times) if blue_response_times else 0,
                'green': sum(green_response_times) / len(green_response_times) if green_response_times else 0,
                'nginx': sum(nginx_response_times) / len(nginx_response_times) if nginx_response_times else 0
            },
            'last_check': recent_checks[-1].last_updated if recent_checks else None
        }
    
    def detect_issues(self, status: SystemStatus) -> List[str]:
        """Detect potential issues in the system"""
        issues = []
        
        # Check if active environment is unhealthy
        active_status = status.blue_status if status.active_environment == 'blue' else status.green_status
        if active_status.status == "unhealthy":
            issues.append(f"Active environment ({status.active_environment}) is unhealthy: {active_status.error_message}")
        
        # Check if nginx is unhealthy
        if status.nginx_status.status == "unhealthy":
            issues.append(f"Load balancer is unhealthy: {status.nginx_status.error_message}")
        
        # Check for high response times
        if active_status.response_time_ms > 5000:  # 5 seconds
            issues.append(f"High response time in {status.active_environment}: {active_status.response_time_ms}ms")
        
        # Check if inactive environment is also unhealthy (potential systemic issue)
        inactive_status = status.green_status if status.active_environment == 'blue' else status.blue_status
        if inactive_status.status == "unhealthy" and active_status.status == "unhealthy":
            issues.append("Both environments are unhealthy - potential systemic issue")
        
        return issues
    
    async def send_alerts(self, issues: List[str]) -> None:
        """Send alerts for detected issues"""
        if not issues:
            return
        
        # Log issues
        for issue in issues:
            logger.warning(f"ALERT: {issue}")
        
        # Store alerts in Redis
        alert_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'issues': issues,
            'alert_level': 'warning' if len(issues) == 1 else 'critical'
        }
        
        try:
            self.redis_client.lpush('health:alerts', json.dumps(alert_data))
            self.redis_client.ltrim('health:alerts', 0, 49)  # Keep last 50 alerts
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    async def run_monitoring_loop(self) -> None:
        """Main monitoring loop"""
        logger.info(f"Starting health monitoring loop (interval: {self.check_interval}s)")
        
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while True:
            try:
                # Run health checks
                status = await self.run_health_checks()
                
                # Store status
                self.store_health_status(status)
                
                # Detect and handle issues
                issues = self.detect_issues(status)
                if issues:
                    await self.send_alerts(issues)
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                
                # Emergency actions for persistent failures
                if consecutive_failures >= max_consecutive_failures:
                    logger.critical(f"System has been unhealthy for {consecutive_failures} consecutive checks!")
                    # Could trigger automatic rollback or other emergency actions here
                
                # Log current status
                metrics = self.get_health_metrics()
                if metrics:
                    logger.info(f"System uptime: {metrics['uptime_percentages']['overall']:.1f}% | "
                              f"Active env: {status.active_environment} | "
                              f"Response time: {metrics['average_response_times'].get(status.active_environment, 0):.1f}ms")
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                consecutive_failures += 1
            
            # Wait for next check
            await asyncio.sleep(self.check_interval)
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        await self.http_client.aclose()

async def main():
    """Main function"""
    monitor = HealthMonitor()
    
    try:
        await monitor.run_monitoring_loop()
    except KeyboardInterrupt:
        logger.info("Shutting down health monitor...")
    finally:
        await monitor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())

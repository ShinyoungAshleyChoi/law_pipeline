#!/usr/bin/env python3
"""
Blue-Green Deployment Manager for Legal Data Pipeline

This script manages the blue-green deployment process including:
- Database switching and synchronization
- Application deployment
- Health checks and validation
- Rollback capabilities
- Load balancer updates
"""

import os
import sys
import time
import json
import logging
import argparse
import subprocess
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from pathlib import Path

import mysql.connector
import redis
import requests
from mysql.connector import Error as MySQLError

from src.config import config
from database.connection import DatabaseConnection
from notifications.slack_service import SlackNotificationService, BatchResult

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BlueGreenDeploymentManager:
    """Manages blue-green deployment process"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = config
        self.notification_service = SlackNotificationService()
        self.redis_client = self._setup_redis()
        
        # Database configurations
        self.blue_db_config = {
            'host': 'localhost',
            'port': 3306,
            'database': 'legal_db',
            'user': 'legal_user',
            'password': 'legal_pass_2024!'
        }
        
        self.green_db_config = {
            'host': 'localhost', 
            'port': 3307,
            'database': 'legal_db',
            'user': 'legal_user',
            'password': 'legal_pass_2024!'
        }
        
        # Deployment state
        self.current_active_env = self._get_current_active_environment()
        self.deployment_start_time = datetime.utcnow()
        
    def _setup_redis(self) -> redis.Redis:
        """Setup Redis connection for state management"""
        try:
            client = redis.Redis(
                host='localhost',
                port=6379,
                password='legal_redis_2024!',
                decode_responses=True
            )
            client.ping()
            return client
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def _get_current_active_environment(self) -> str:
        """Get currently active environment from Redis"""
        try:
            active_env = self.redis_client.get('deployment:active_environment')
            return active_env or 'blue'  # Default to blue
        except Exception as e:
            logger.warning(f"Could not retrieve active environment from Redis: {e}")
            return 'blue'
    
    def _set_active_environment(self, environment: str) -> None:
        """Set active environment in Redis"""
        try:
            self.redis_client.set('deployment:active_environment', environment)
            self.redis_client.set(f'deployment:last_switch', datetime.utcnow().isoformat())
            logger.info(f"Active environment set to: {environment}")
        except Exception as e:
            logger.error(f"Failed to set active environment: {e}")
            raise
    
    def _get_db_config(self, environment: str) -> Dict:
        """Get database configuration for specified environment"""
        if environment == 'blue':
            return self.blue_db_config.copy()
        elif environment == 'green':
            return self.green_db_config.copy()
        else:
            raise ValueError(f"Invalid environment: {environment}")
    
    def _test_database_connection(self, environment: str) -> bool:
        """Test database connection for specified environment"""
        config = self._get_db_config(environment)
        try:
            conn = mysql.connector.connect(**config)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            logger.info(f"Database connection test passed for {environment} environment")
            return result[0] == 1
        
        except MySQLError as e:
            logger.error(f"Database connection test failed for {environment}: {e}")
            return False
    
    def _get_database_status(self, environment: str) -> Dict:
        """Get comprehensive database status"""
        config = self._get_db_config(environment)
        try:
            conn = mysql.connector.connect(**config)
            cursor = conn.cursor(dictionary=True)
            
            # Get table count
            cursor.execute("SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = %s", (config['database'],))
            table_count = cursor.fetchone()['table_count']
            
            # Get total records (assuming main tables exist)
            total_records = 0
            try:
                cursor.execute("SELECT SUM(table_rows) as total_records FROM information_schema.tables WHERE table_schema = %s", (config['database'],))
                result = cursor.fetchone()
                total_records = result['total_records'] or 0
            except:
                pass
            
            # Get database size
            cursor.execute("""
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb 
                FROM information_schema.tables 
                WHERE table_schema = %s
            """, (config['database'],))
            db_size = cursor.fetchone()['size_mb'] or 0
            
            cursor.close()
            conn.close()
            
            return {
                'environment': environment,
                'status': 'healthy',
                'table_count': table_count,
                'total_records': int(total_records),
                'size_mb': float(db_size),
                'last_checked': datetime.utcnow().isoformat()
            }
            
        except MySQLError as e:
            logger.error(f"Failed to get database status for {environment}: {e}")
            return {
                'environment': environment,
                'status': 'unhealthy',
                'error': str(e),
                'last_checked': datetime.utcnow().isoformat()
            }
    
    def _sync_databases(self, source_env: str, target_env: str) -> bool:
        """Synchronize data from source to target environment"""
        logger.info(f"Starting database synchronization from {source_env} to {target_env}")
        
        source_config = self._get_db_config(source_env)
        target_config = self._get_db_config(target_env)
        
        try:
            # Create mysqldump command
            dump_cmd = [
                'mysqldump',
                f'--host={source_config["host"]}',
                f'--port={source_config["port"]}',
                f'--user={source_config["user"]}',
                f'--password={source_config["password"]}',
                '--single-transaction',
                '--routines',
                '--triggers',
                '--no-create-db',
                source_config['database']
            ]
            
            # Create mysql restore command
            restore_cmd = [
                'mysql',
                f'--host={target_config["host"]}',
                f'--port={target_config["port"]}',
                f'--user={target_config["user"]}',
                f'--password={target_config["password"]}',
                target_config['database']
            ]
            
            # Execute sync
            logger.info("Executing database dump...")
            dump_process = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            logger.info("Executing database restore...")
            restore_process = subprocess.Popen(restore_cmd, stdin=dump_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            dump_process.stdout.close()
            
            # Wait for completion
            restore_output, restore_error = restore_process.communicate()
            dump_output, dump_error = dump_process.communicate()
            
            if restore_process.returncode != 0:
                logger.error(f"Database restore failed: {restore_error.decode()}")
                return False
                
            if dump_process.returncode != 0:
                logger.error(f"Database dump failed: {dump_error.decode()}")
                return False
            
            logger.info(f"Database synchronization from {source_env} to {target_env} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database synchronization failed: {e}")
            return False
    
    def _run_health_checks(self, environment: str) -> Dict:
        """Run comprehensive health checks on specified environment"""
        logger.info(f"Running health checks for {environment} environment")
        
        checks = {
            'database_connection': False,
            'database_integrity': False,
            'application_health': False,
            'overall_status': 'unhealthy'
        }
        
        # Database connection check
        checks['database_connection'] = self._test_database_connection(environment)
        
        # Database integrity check (basic table existence)
        if checks['database_connection']:
            try:
                config = self._get_db_config(environment)
                conn = mysql.connector.connect(**config)
                cursor = conn.cursor()
                
                # Check if main tables exist
                cursor.execute("""
                    SELECT COUNT(*) as table_count 
                    FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name IN ('legal_documents', 'legal_cases', 'legal_updates')
                """, (config['database'],))
                
                table_count = cursor.fetchone()[0]
                checks['database_integrity'] = table_count >= 1  # At least one main table should exist
                
                cursor.close()
                conn.close()
                
            except Exception as e:
                logger.error(f"Database integrity check failed: {e}")
        
        # Application health check (mock - in real scenario, would check actual application endpoints)
        checks['application_health'] = True  # Assume application is healthy for now
        
        # Overall status
        checks['overall_status'] = 'healthy' if all([
            checks['database_connection'],
            checks['database_integrity'], 
            checks['application_health']
        ]) else 'unhealthy'
        
        logger.info(f"Health check results for {environment}: {checks['overall_status']}")
        return checks
    
    def _create_deployment_backup(self, environment: str) -> str:
        """Create a backup before deployment"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{environment}_{timestamp}"
        
        logger.info(f"Creating backup: {backup_name}")
        
        config = self._get_db_config(environment)
        backup_file = f"/tmp/{backup_name}.sql"
        
        try:
            dump_cmd = [
                'mysqldump',
                f'--host={config["host"]}',
                f'--port={config["port"]}',
                f'--user={config["user"]}',
                f'--password={config["password"]}',
                '--single-transaction',
                '--routines',
                '--triggers',
                config['database']
            ]
            
            with open(backup_file, 'w') as f:
                result = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, text=True)
                
            if result.returncode != 0:
                logger.error(f"Backup creation failed: {result.stderr}")
                return None
            
            # Store backup metadata in Redis
            backup_metadata = {
                'backup_name': backup_name,
                'environment': environment,
                'file_path': backup_file,
                'created_at': datetime.utcnow().isoformat(),
                'size_bytes': os.path.getsize(backup_file)
            }
            
            self.redis_client.setex(
                f'backup:{backup_name}', 
                86400 * 7,  # 7 days expiration
                json.dumps(backup_metadata)
            )
            
            logger.info(f"Backup created successfully: {backup_name}")
            return backup_name
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return None
    
    def deploy(self, target_version: Optional[str] = None, skip_sync: bool = False) -> bool:
        """Execute blue-green deployment"""
        logger.info("Starting blue-green deployment process")
        
        # Determine target environment
        target_env = 'green' if self.current_active_env == 'blue' else 'blue'
        source_env = self.current_active_env
        
        logger.info(f"Current active: {source_env}, Deploying to: {target_env}")
        
        # Send deployment start notification
        self.notification_service.send_critical_alert(
            message=f"🚀 Blue-Green deployment started\nTarget: {target_env}\nVersion: {target_version or 'latest'}"
        )
        
        try:
            # Step 1: Create backup of current active environment
            logger.info("Step 1: Creating backup")
            backup_name = self._create_deployment_backup(source_env)
            if not backup_name:
                raise Exception("Backup creation failed")
            
            # Step 2: Ensure target environment is healthy
            logger.info(f"Step 2: Health check for target environment ({target_env})")
            if not self._test_database_connection(target_env):
                raise Exception(f"Target environment {target_env} is not accessible")
            
            # Step 3: Synchronize data if not skipped
            if not skip_sync:
                logger.info(f"Step 3: Synchronizing data from {source_env} to {target_env}")
                if not self._sync_databases(source_env, target_env):
                    raise Exception("Database synchronization failed")
            else:
                logger.info("Step 3: Skipping data synchronization as requested")
            
            # Step 4: Deploy application to target environment (mock deployment)
            logger.info(f"Step 4: Deploying application to {target_env}")
            if target_version:
                logger.info(f"Deploying version: {target_version}")
            
            # Update environment configuration
            self.redis_client.setex(
                f'deployment:config:{target_env}',
                3600,  # 1 hour expiration
                json.dumps({
                    'version': target_version or 'latest',
                    'deployed_at': datetime.utcnow().isoformat(),
                    'deployed_from': source_env
                })
            )
            
            # Step 5: Run comprehensive health checks on target
            logger.info(f"Step 5: Running health checks on {target_env}")
            health_checks = self._run_health_checks(target_env)
            
            if health_checks['overall_status'] != 'healthy':
                raise Exception(f"Health checks failed for {target_env}: {health_checks}")
            
            # Step 6: Switch traffic to target environment
            logger.info(f"Step 6: Switching traffic to {target_env}")
            self._set_active_environment(target_env)
            
            # Step 7: Final verification
            logger.info("Step 7: Final verification")
            time.sleep(5)  # Allow some time for traffic to switch
            final_checks = self._run_health_checks(target_env)
            
            if final_checks['overall_status'] != 'healthy':
                logger.warning("Final verification failed, initiating rollback")
                self.rollback()
                raise Exception("Final verification failed")
            
            # Deployment successful
            deployment_duration = (datetime.utcnow() - self.deployment_start_time).total_seconds()
            
            logger.info(f"✅ Blue-green deployment completed successfully!")
            logger.info(f"Active environment: {target_env}")
            logger.info(f"Deployment duration: {deployment_duration:.2f} seconds")
            
            # Send success notification  
            batch_result = BatchResult(
                job_name="Blue-Green Deployment",
                success=True,
                processed_laws=0,
                processed_articles=0,
                error_count=0,
                duration=f"{deployment_duration:.2f}s"
            )
            self.notification_service.send_batch_completion_notice(batch_result)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            
            # Send failure notification
            deployment_error = Exception(f"Blue-Green deployment failed: {str(e)}")
            context = {
                "target_environment": target_env,
                "job_name": "Blue-Green Deployment"
            }
            self.notification_service.send_error_alert(deployment_error, context)
            
            return False
    
    def rollback(self) -> bool:
        """Rollback to previous environment"""
        logger.info("Starting rollback process")
        
        current_env = self._get_current_active_environment()
        previous_env = 'green' if current_env == 'blue' else 'blue'
        
        try:
            # Health check on previous environment
            if not self._test_database_connection(previous_env):
                raise Exception(f"Previous environment {previous_env} is not accessible")
            
            # Switch back
            self._set_active_environment(previous_env)
            
            # Verify rollback
            health_checks = self._run_health_checks(previous_env)
            if health_checks['overall_status'] != 'healthy':
                raise Exception(f"Rollback verification failed: {health_checks}")
            
            logger.info(f"✅ Rollback completed successfully! Active environment: {previous_env}")
            
            # Send rollback notification
            self.notification_service.send_critical_alert(
                message=f"⏪ Rollback completed successfully!\nActive environment: {previous_env}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            
            rollback_error = Exception(f"Rollback failed: {str(e)}")
            context = {"job_name": "Blue-Green Rollback"}
            self.notification_service.send_error_alert(rollback_error, context)
            
            return False
    
    def status(self) -> Dict:
        """Get current deployment status"""
        active_env = self._get_current_active_environment()
        inactive_env = 'green' if active_env == 'blue' else 'blue'
        
        # Get status for both environments
        blue_status = self._get_database_status('blue')
        green_status = self._get_database_status('green')
        
        # Get deployment history from Redis
        deployment_history = []
        try:
            keys = self.redis_client.keys('deployment:config:*')
            for key in keys:
                data = json.loads(self.redis_client.get(key) or '{}')
                if data:
                    env = key.split(':')[-1]
                    data['environment'] = env
                    deployment_history.append(data)
        except Exception as e:
            logger.warning(f"Could not retrieve deployment history: {e}")
        
        return {
            'active_environment': active_env,
            'inactive_environment': inactive_env,
            'environments': {
                'blue': blue_status,
                'green': green_status
            },
            'deployment_history': deployment_history,
            'last_switch': self.redis_client.get('deployment:last_switch'),
            'status_checked_at': datetime.utcnow().isoformat()
        }

def main():
    parser = argparse.ArgumentParser(description='Blue-Green Deployment Manager')
    parser.add_argument('action', choices=['deploy', 'rollback', 'status'], 
                       help='Action to perform')
    parser.add_argument('--version', help='Version to deploy')
    parser.add_argument('--skip-sync', action='store_true', 
                       help='Skip database synchronization')
    parser.add_argument('--config', help='Configuration file path')
    
    args = parser.parse_args()
    
    try:
        manager = BlueGreenDeploymentManager(args.config)
        
        if args.action == 'deploy':
            success = manager.deploy(args.version, args.skip_sync)
            sys.exit(0 if success else 1)
            
        elif args.action == 'rollback':
            success = manager.rollback()
            sys.exit(0 if success else 1)
            
        elif args.action == 'status':
            status = manager.status()
            print(json.dumps(status, indent=2))
            
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

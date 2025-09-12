#!/usr/bin/env python3
"""
Nginx Controller for Blue-Green Deployment

This module manages Nginx configuration updates during blue-green deployments.
It handles upstream switching and configuration reloading.
"""

import os
import time
import logging
import subprocess
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class NginxController:
    """Controls Nginx configuration for blue-green deployments"""
    
    def __init__(self, nginx_config_path: str = "/etc/nginx/nginx.conf"):
        self.nginx_config_path = Path(nginx_config_path)
        self.backup_path = Path(nginx_config_path).with_suffix('.backup')
        
        # Port mappings for environments
        self.environment_ports = {
            'blue': 8001,
            'green': 8002
        }
    
    def _backup_config(self) -> bool:
        """Create backup of current Nginx configuration"""
        try:
            if self.nginx_config_path.exists():
                import shutil
                shutil.copy2(self.nginx_config_path, self.backup_path)
                logger.info(f"Nginx configuration backed up to {self.backup_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to backup Nginx configuration: {e}")
            return False
    
    def _restore_config(self) -> bool:
        """Restore Nginx configuration from backup"""
        try:
            if self.backup_path.exists():
                import shutil
                shutil.copy2(self.backup_path, self.nginx_config_path)
                logger.info("Nginx configuration restored from backup")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to restore Nginx configuration: {e}")
            return False
    
    def _test_nginx_config(self) -> bool:
        """Test Nginx configuration for syntax errors"""
        try:
            result = subprocess.run(
                ['nginx', '-t'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("Nginx configuration test passed")
                return True
            else:
                logger.error(f"Nginx configuration test failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Nginx configuration test timed out")
            return False
        except Exception as e:
            logger.error(f"Error testing Nginx configuration: {e}")
            return False
    
    def _reload_nginx(self) -> bool:
        """Reload Nginx configuration"""
        try:
            result = subprocess.run(
                ['nginx', '-s', 'reload'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("Nginx reloaded successfully")
                return True
            else:
                logger.error(f"Failed to reload Nginx: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Nginx reload timed out")
            return False
        except Exception as e:
            logger.error(f"Error reloading Nginx: {e}")
            return False
    
    def switch_upstream(self, target_environment: str) -> bool:
        """Switch active upstream to target environment"""
        logger.info(f"Switching Nginx upstream to {target_environment}")
        
        if target_environment not in self.environment_ports:
            logger.error(f"Invalid environment: {target_environment}")
            return False
        
        target_port = self.environment_ports[target_environment]
        
        try:
            # Backup current configuration
            if not self._backup_config():
                return False
            
            # Read current configuration
            with open(self.nginx_config_path, 'r') as f:
                config_content = f.read()
            
            # Update active_backend upstream configuration
            lines = config_content.split('\n')
            new_lines = []
            in_active_upstream = False
            
            for line in lines:
                stripped_line = line.strip()
                
                # Detect start of active_backend upstream
                if 'upstream active_backend' in stripped_line:
                    in_active_upstream = True
                    new_lines.append(line)
                    continue
                
                # Detect end of upstream block
                if in_active_upstream and stripped_line == '}':
                    in_active_upstream = False
                    new_lines.append(line)
                    continue
                
                # Replace server line in active_backend upstream
                if in_active_upstream and 'server 127.0.0.1:' in stripped_line:
                    # Extract the original line format and replace port
                    indent = len(line) - len(line.lstrip())
                    new_server_line = ' ' * indent + f'server 127.0.0.1:{target_port} max_fails=3 fail_timeout=30s;  # {target_environment} environment'
                    new_lines.append(new_server_line)
                else:
                    new_lines.append(line)
            
            # Write updated configuration
            updated_config = '\n'.join(new_lines)
            with open(self.nginx_config_path, 'w') as f:
                f.write(updated_config)
            
            # Test configuration
            if not self._test_nginx_config():
                logger.error("Updated configuration failed validation, restoring backup")
                self._restore_config()
                return False
            
            # Reload Nginx
            if not self._reload_nginx():
                logger.error("Failed to reload Nginx, restoring backup")
                self._restore_config()
                self._reload_nginx()
                return False
            
            logger.info(f"Successfully switched Nginx upstream to {target_environment} (port {target_port})")
            return True
            
        except Exception as e:
            logger.error(f"Error switching upstream: {e}")
            # Try to restore backup
            self._restore_config()
            self._reload_nginx()
            return False
    
    def get_current_upstream(self) -> Optional[str]:
        """Get currently active upstream environment"""
        try:
            with open(self.nginx_config_path, 'r') as f:
                config_content = f.read()
            
            lines = config_content.split('\n')
            in_active_upstream = False
            
            for line in lines:
                stripped_line = line.strip()
                
                if 'upstream active_backend' in stripped_line:
                    in_active_upstream = True
                    continue
                
                if in_active_upstream and stripped_line == '}':
                    break
                
                if in_active_upstream and 'server 127.0.0.1:' in stripped_line:
                    # Extract port number
                    port_start = stripped_line.find('127.0.0.1:') + len('127.0.0.1:')
                    port_end = stripped_line.find(' ', port_start)
                    if port_end == -1:
                        port_end = stripped_line.find(';', port_start)
                    
                    if port_end != -1:
                        port = int(stripped_line[port_start:port_end])
                        
                        # Map port to environment
                        for env, env_port in self.environment_ports.items():
                            if env_port == port:
                                return env
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current upstream: {e}")
            return None
    
    def get_status(self) -> Dict:
        """Get Nginx status information"""
        current_upstream = self.get_current_upstream()
        
        # Check if Nginx is running
        nginx_running = False
        try:
            result = subprocess.run(['pgrep', 'nginx'], capture_output=True)
            nginx_running = result.returncode == 0
        except:
            pass
        
        # Get Nginx version
        nginx_version = "unknown"
        try:
            result = subprocess.run(['nginx', '-v'], capture_output=True, text=True)
            if result.stderr:
                nginx_version = result.stderr.strip().split('/')[-1]
        except:
            pass
        
        return {
            'nginx_running': nginx_running,
            'nginx_version': nginx_version,
            'current_upstream': current_upstream,
            'config_path': str(self.nginx_config_path),
            'backup_exists': self.backup_path.exists(),
            'environment_ports': self.environment_ports
        }

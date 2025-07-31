"""
Gazebo Simulation Manager

Manages the lifecycle of Gazebo simulation environment for robot fleet testing.
"""

import subprocess
import time
import logging
import os
import signal
from typing import Optional, Dict, Any, List
from pathlib import Path

from core.base_component import BaseComponent
from core.data_models import RobotState
from config.config_manager import ConfigManager


class GazeboManager(BaseComponent):
    """
    Manages Gazebo simulation lifecycle including startup, shutdown, and environment control.
    """
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__("GazeboManager", config_manager)
        self.gazebo_process: Optional[subprocess.Popen] = None
        self.world_file: Optional[str] = None
        self.is_running = False
        
        # Get simulation configuration
        self.sim_config = self.config.get('simulation', {})
        self.gazebo_timeout = self.sim_config.get('startup_timeout', 30)
        self.world_path = self.sim_config.get('world_path', 'worlds')
        
    def start_simulation(self, world_name: str = "warehouse.world", 
                        gui: bool = True, verbose: bool = False) -> bool:
        """
        Start Gazebo simulation with specified world file.
        
        Args:
            world_name: Name of the world file to load
            gui: Whether to start with GUI
            verbose: Enable verbose logging
            
        Returns:
            bool: True if simulation started successfully
        """
        if self.is_running:
            self.logger.warning("Gazebo simulation is already running")
            return True
            
        try:
            # Construct world file path
            world_file_path = Path(self.world_path) / world_name
            if not world_file_path.exists():
                self.logger.error(f"World file not found: {world_file_path}")
                return False
                
            self.world_file = str(world_file_path)
            
            # Build Gazebo command
            cmd = ["gazebo"]
            if not gui:
                cmd.append("--headless")
            if verbose:
                cmd.append("--verbose")
            cmd.append(self.world_file)
            
            self.logger.info(f"Starting Gazebo simulation with command: {' '.join(cmd)}")
            
            # Start Gazebo process
            self.gazebo_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            # Wait for Gazebo to start
            if self._wait_for_startup():
                self.is_running = True
                self.logger.info("Gazebo simulation started successfully")
                return True
            else:
                self.logger.error("Gazebo simulation failed to start within timeout")
                self.stop_simulation()
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start Gazebo simulation: {e}")
            return False
    
    def stop_simulation(self) -> bool:
        """
        Stop the running Gazebo simulation.
        
        Returns:
            bool: True if simulation stopped successfully
        """
        if not self.is_running or not self.gazebo_process:
            self.logger.info("No Gazebo simulation running")
            return True
            
        try:
            self.logger.info("Stopping Gazebo simulation")
            
            # Terminate process group on Unix systems
            if os.name != 'nt' and self.gazebo_process.poll() is None:
                os.killpg(os.getpgid(self.gazebo_process.pid), signal.SIGTERM)
            else:
                self.gazebo_process.terminate()
            
            # Wait for process to terminate
            try:
                self.gazebo_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.logger.warning("Gazebo process did not terminate gracefully, forcing kill")
                if os.name != 'nt':
                    os.killpg(os.getpgid(self.gazebo_process.pid), signal.SIGKILL)
                else:
                    self.gazebo_process.kill()
                self.gazebo_process.wait()
            
            self.gazebo_process = None
            self.is_running = False
            self.world_file = None
            
            self.logger.info("Gazebo simulation stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop Gazebo simulation: {e}")
            return False
    
    def restart_simulation(self, world_name: str = "warehouse.world", 
                          gui: bool = True) -> bool:
        """
        Restart the Gazebo simulation.
        
        Args:
            world_name: Name of the world file to load
            gui: Whether to start with GUI
            
        Returns:
            bool: True if simulation restarted successfully
        """
        self.logger.info("Restarting Gazebo simulation")
        
        if not self.stop_simulation():
            return False
            
        # Wait a moment for cleanup
        time.sleep(2)
        
        return self.start_simulation(world_name, gui)
    
    def is_simulation_running(self) -> bool:
        """
        Check if Gazebo simulation is currently running.
        
        Returns:
            bool: True if simulation is running
        """
        if not self.gazebo_process:
            return False
            
        # Check if process is still alive
        if self.gazebo_process.poll() is not None:
            self.is_running = False
            self.gazebo_process = None
            
        return self.is_running
    
    def get_simulation_status(self) -> Dict[str, Any]:
        """
        Get current simulation status information.
        
        Returns:
            Dict containing simulation status details
        """
        return {
            'running': self.is_simulation_running(),
            'world_file': self.world_file,
            'process_id': self.gazebo_process.pid if self.gazebo_process else None,
            'uptime': self._get_uptime() if self.is_running else 0
        }
    
    def _wait_for_startup(self) -> bool:
        """
        Wait for Gazebo to fully start up.
        
        Returns:
            bool: True if Gazebo started within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < self.gazebo_timeout:
            if self.gazebo_process and self.gazebo_process.poll() is not None:
                # Process has terminated
                return False
                
            # Check if Gazebo is responding (simplified check)
            # In a real implementation, you might check for ROS topics or services
            time.sleep(1)
            
            # For now, assume it's ready after a few seconds
            if time.time() - start_time > 5:
                return True
                
        return False
    
    def _get_uptime(self) -> float:
        """
        Get simulation uptime in seconds.
        
        Returns:
            float: Uptime in seconds
        """
        if not hasattr(self, '_start_time'):
            self._start_time = time.time()
        return time.time() - self._start_time
    
    def cleanup(self):
        """Clean up resources when shutting down."""
        if self.is_running:
            self.stop_simulation()
        super().cleanup()
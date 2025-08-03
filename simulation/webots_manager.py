"""
Webots Simulation Manager for ChatGPT Robotics.

This module manages the Webots simulation environment, providing
professional-grade multi-robot simulation capabilities with easy setup.
"""

import os
import subprocess
import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.base_component import BaseComponent
from config.config_manager import ConfigManager

# Simple data classes for Webots integration
@dataclass
class SimpleRobotCommand:
    """Simple robot command for Webots integration."""
    robot_id: str
    action: str
    parameters: Dict[str, Any]
    priority: int = 1
    timeout: float = 30.0

@dataclass  
class SimpleRobotState:
    """Simple robot state for Webots integration."""
    robot_id: str
    position: Dict[str, float]
    status: str
    battery_level: float
    last_command_time: datetime
    is_moving: bool


@dataclass
class WebotsConfig:
    """Configuration for Webots simulation."""
    webots_path: str = "C:\\Program Files\\Webots\\msys64\\mingw64\\bin\\webots.exe"
    project_path: str = "webots_simulation"
    world_file: str = "robot_fleet.wbt"
    robot_count: int = 10
    enable_gui: bool = True
    simulation_mode: str = "realtime"  # realtime, fast, pause


@dataclass
class RobotInfo:
    """Information about a robot in the simulation."""
    robot_id: str
    robot_type: str = "e-puck"
    position: Dict[str, float] = None
    status: str = "idle"
    controller: str = "fleet_controller"
    last_command_time: datetime = None
    
    def __post_init__(self):
        if self.position is None:
            self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        if self.last_command_time is None:
            self.last_command_time = datetime.now()


class WebotsManager(BaseComponent):
    """
    Manages Webots simulation lifecycle and robot fleet control.
    
    Provides integration between ChatGPT command system and Webots simulation,
    enabling natural language control of multi-robot systems.
    """
    
    def __init__(self, config_manager: ConfigManager):
        # Get simulation configuration
        sim_config = config_manager.get('simulation', {})
        super().__init__("WebotsManager", sim_config)
        
        self.config_manager = config_manager
        self.webots_config = WebotsConfig(**sim_config.get('webots', {}))
        
        # Simulation state
        self.webots_process: Optional[subprocess.Popen] = None
        self.simulation_running = False
        self.world_loaded = False
        self._start_time: Optional[float] = None
        
        # Robot management
        self.robots: Dict[str, RobotInfo] = {}
        self.robot_states: Dict[str, SimpleRobotState] = {}
        
        # Communication
        self.command_queue: List[SimpleRobotCommand] = []
        self.status_callbacks: List[Callable] = []
        
        # Paths
        self.project_root = Path(self.webots_config.project_path)
        self.worlds_path = self.project_root / "worlds"
        self.controllers_path = self.project_root / "controllers"
        
        # Ensure project structure exists
        self._ensure_project_structure()
        
        self.logger.info("WebotsManager initialized")
    
    def _ensure_project_structure(self) -> None:
        """Ensure Webots project directory structure exists."""
        try:
            # Create main directories
            self.project_root.mkdir(exist_ok=True)
            self.worlds_path.mkdir(exist_ok=True)
            self.controllers_path.mkdir(exist_ok=True)
            (self.project_root / "protos").mkdir(exist_ok=True)
            
            self.logger.info(f"Project structure ensured at: {self.project_root}")
            
        except Exception as e:
            self.logger.error(f"Failed to create project structure: {e}")
            raise
    
    async def start_simulation(self, world_name: Optional[str] = None, 
                             robot_count: Optional[int] = None) -> bool:
        """
        Start Webots simulation with specified world.
        
        Args:
            world_name: Name of world file (optional)
            robot_count: Number of robots to spawn (optional)
            
        Returns:
            True if simulation started successfully
        """
        if self.simulation_running:
            self.logger.warning("Webots simulation is already running")
            return True
        
        try:
            # Use provided parameters or defaults
            world_file = world_name or self.webots_config.world_file
            robot_count = robot_count or self.webots_config.robot_count
            
            # Ensure world file exists
            world_path = self.worlds_path / world_file
            if not world_path.exists():
                self.logger.info(f"World file not found, creating: {world_file}")
                await self._create_default_world(world_path, robot_count)
            
            # Start Webots process
            success = await self._start_webots_process(world_path)
            
            if success:
                self.simulation_running = True
                self._start_time = time.time()
                
                # Initialize robot tracking
                await self._initialize_robots(robot_count)
                
                self.logger.info(f"Webots simulation started with {robot_count} robots")
                await self._notify_status_callbacks("simulation_started")
                
                return True
            else:
                self.logger.error("Failed to start Webots simulation")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting simulation: {e}")
            return False
    
    async def _start_webots_process(self, world_path: Path) -> bool:
        """Start the Webots process."""
        try:
            # Build Webots command
            cmd = [self.webots_config.webots_path]
            
            # Add world file
            cmd.append(str(world_path))
            
            # Add options
            if not self.webots_config.enable_gui:
                cmd.append("--no-rendering")
            
            if self.webots_config.simulation_mode == "fast":
                cmd.append("--mode=fast")
            elif self.webots_config.simulation_mode == "pause":
                cmd.append("--mode=pause")
            
            self.logger.info(f"Starting Webots: {' '.join(cmd)}")
            
            # Start process
            self.webots_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project_root)
            )
            
            # Wait for startup
            await self._wait_for_webots_startup()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Webots process: {e}")
            return False
    
    async def _wait_for_webots_startup(self, timeout: int = 30) -> bool:
        """Wait for Webots to fully start up."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.webots_process and self.webots_process.poll() is not None:
                # Process has terminated
                self.logger.error("Webots process terminated during startup")
                return False
            
            # Check if Webots is responding (simplified check)
            await asyncio.sleep(1)
            
            # For now, assume it's ready after a few seconds
            if time.time() - start_time > 5:
                self.logger.info("Webots startup completed")
                return True
        
        self.logger.error("Webots startup timeout")
        return False
    
    async def _create_default_world(self, world_path: Path, robot_count: int) -> None:
        """Create a default world file with specified number of robots."""
        try:
            world_content = self._generate_world_content(robot_count)
            
            with open(world_path, 'w') as f:
                f.write(world_content)
            
            self.logger.info(f"Created world file: {world_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to create world file: {e}")
            raise
    
    def _generate_world_content(self, robot_count: int) -> str:
        """Generate Webots world file content."""
        world_template = '''#VRML_SIM R2024a utf8

EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2024a/projects/objects/backgrounds/protos/TexturedBackground.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2024a/projects/objects/floors/protos/RectangleArena.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2024a/projects/robots/gctronic/e-puck/protos/E-puck.proto"

WorldInfo {
  basicTimeStep 32
  contactProperties [
    ContactProperties {
      coulombFriction [8]
      bounce 0.4
    }
  ]
}

Viewpoint {
  orientation -0.5 0.5 0.7 2.1
  position 0 15 10
}

TexturedBackground {
}

RectangleArena {
  translation 0 0 0
  floorSize 10 10
  wallHeight 0.5
}

'''
        
        # Add robots in a grid formation
        robots_per_row = min(5, robot_count)
        rows = (robot_count + robots_per_row - 1) // robots_per_row
        
        for i in range(robot_count):
            row = i // robots_per_row
            col = i % robots_per_row
            
            # Calculate position
            x = (col - (robots_per_row - 1) / 2) * 1.5
            y = (row - (rows - 1) / 2) * 1.5
            
            robot_entry = f'''
E-puck {{
  translation {x} {y} 0
  name "robot_{i}"
  controller "fleet_controller"
}}
'''
            world_template += robot_entry
        
        return world_template
    
    async def _initialize_robots(self, robot_count: int) -> None:
        """Initialize robot tracking."""
        try:
            self.robots.clear()
            self.robot_states.clear()
            
            for i in range(robot_count):
                robot_id = f"robot_{i}"
                
                # Create robot info
                robot_info = RobotInfo(
                    robot_id=robot_id,
                    robot_type="e-puck",
                    controller="fleet_controller"
                )
                
                # Create robot state
                robot_state = SimpleRobotState(
                    robot_id=robot_id,
                    position={"x": 0.0, "y": 0.0, "z": 0.0},
                    status="idle",
                    battery_level=100.0,
                    last_command_time=datetime.now(),
                    is_moving=False
                )
                
                self.robots[robot_id] = robot_info
                self.robot_states[robot_id] = robot_state
            
            self.logger.info(f"Initialized {robot_count} robots")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize robots: {e}")
            raise
    
    async def stop_simulation(self) -> bool:
        """Stop the Webots simulation."""
        if not self.simulation_running:
            self.logger.info("No Webots simulation running")
            return True
        
        try:
            self.logger.info("Stopping Webots simulation")
            
            if self.webots_process:
                # Terminate process
                self.webots_process.terminate()
                
                # Wait for process to terminate
                try:
                    await asyncio.wait_for(
                        asyncio.create_task(self._wait_for_process_termination()),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    self.logger.warning("Webots process did not terminate gracefully, forcing kill")
                    self.webots_process.kill()
                    await asyncio.create_task(self._wait_for_process_termination())
            
            # Reset state
            self.webots_process = None
            self.simulation_running = False
            self.world_loaded = False
            self._start_time = None
            
            await self._notify_status_callbacks("simulation_stopped")
            
            self.logger.info("Webots simulation stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping simulation: {e}")
            return False
    
    async def _wait_for_process_termination(self) -> None:
        """Wait for Webots process to terminate."""
        while self.webots_process and self.webots_process.poll() is None:
            await asyncio.sleep(0.1)
    
    async def send_robot_command(self, robot_id: str, command: SimpleRobotCommand) -> bool:
        """
        Send command to a specific robot.
        
        Args:
            robot_id: ID of target robot
            command: Command to send
            
        Returns:
            True if command sent successfully
        """
        if not self.simulation_running:
            self.logger.error("Cannot send command - simulation not running")
            return False
        
        if robot_id not in self.robots:
            self.logger.error(f"Robot {robot_id} not found")
            return False
        
        try:
            # Add command to queue (in real implementation, this would communicate with Webots)
            self.command_queue.append(command)
            
            # Update robot state
            if robot_id in self.robot_states:
                robot_state = self.robot_states[robot_id]
                robot_state.status = "executing"
                robot_state.last_command_time = datetime.now()
                robot_state.is_moving = command.action in ["navigate", "move"]
            
            self.logger.info(f"Command sent to {robot_id}: {command.action}")
            
            # Simulate command execution
            asyncio.create_task(self._simulate_command_execution(robot_id, command))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send command to {robot_id}: {e}")
            return False
    
    async def _simulate_command_execution(self, robot_id: str, command: SimpleRobotCommand) -> None:
        """Simulate command execution (placeholder for real Webots integration)."""
        try:
            # Simulate execution time
            execution_time = 3 + len(command.parameters) * 0.5
            await asyncio.sleep(execution_time)
            
            # Update robot state
            if robot_id in self.robot_states:
                robot_state = self.robot_states[robot_id]
                robot_state.status = "idle"
                robot_state.is_moving = False
                
                # Update position if it was a navigation command
                if command.action == "navigate" and "target_position" in command.parameters:
                    target_pos = command.parameters["target_position"]
                    robot_state.position.update(target_pos)
            
            self.logger.info(f"Command execution completed for {robot_id}")
            
        except Exception as e:
            self.logger.error(f"Error in command execution simulation: {e}")
    
    def get_robot_state(self, robot_id: str) -> Optional[SimpleRobotState]:
        """Get current state of a robot."""
        return self.robot_states.get(robot_id)
    
    def get_all_robot_states(self) -> Dict[str, SimpleRobotState]:
        """Get states of all robots."""
        return self.robot_states.copy()
    
    def get_simulation_status(self) -> Dict[str, Any]:
        """Get current simulation status."""
        return {
            "running": self.simulation_running,
            "world_loaded": self.world_loaded,
            "robot_count": len(self.robots),
            "uptime": self._get_uptime() if self.simulation_running else 0,
            "webots_path": self.webots_config.webots_path,
            "project_path": str(self.project_root),
            "robots": list(self.robots.keys()),
            "command_queue_size": len(self.command_queue)
        }
    
    def _get_uptime(self) -> float:
        """Get simulation uptime in seconds."""
        if not self._start_time:
            return 0.0
        return time.time() - self._start_time
    
    def add_status_callback(self, callback: Callable) -> None:
        """Add callback for simulation status changes."""
        self.status_callbacks.append(callback)
    
    async def _notify_status_callbacks(self, event: str) -> None:
        """Notify status change callbacks."""
        for callback in self.status_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event, self.get_simulation_status())
                else:
                    callback(event, self.get_simulation_status())
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")
    
    async def emergency_stop_all_robots(self) -> None:
        """Emergency stop all robots."""
        self.logger.warning("Emergency stop initiated for all robots")
        
        for robot_id in self.robots:
            if robot_id in self.robot_states:
                robot_state = self.robot_states[robot_id]
                robot_state.status = "emergency_stop"
                robot_state.is_moving = False
        
        # Clear command queue
        self.command_queue.clear()
        
        self.logger.info("Emergency stop completed for all robots")
    
    async def create_formation(self, formation_type: str, **kwargs) -> bool:
        """
        Create robot formation.
        
        Args:
            formation_type: Type of formation (line, circle, grid)
            **kwargs: Formation-specific parameters
            
        Returns:
            True if formation created successfully
        """
        try:
            if formation_type == "line":
                return await self._create_line_formation(**kwargs)
            elif formation_type == "circle":
                return await self._create_circle_formation(**kwargs)
            elif formation_type == "grid":
                return await self._create_grid_formation(**kwargs)
            else:
                self.logger.error(f"Unknown formation type: {formation_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to create formation: {e}")
            return False
    
    async def _create_line_formation(self, spacing: float = 1.0, **kwargs) -> bool:
        """Create line formation."""
        robot_ids = list(self.robots.keys())
        
        for i, robot_id in enumerate(robot_ids):
            target_x = (i - len(robot_ids) / 2) * spacing
            target_y = 0.0
            
            command = SimpleRobotCommand(
                robot_id=robot_id,
                action="navigate",
                parameters={"target_position": {"x": target_x, "y": target_y, "z": 0.0}},
                priority=1,
                timeout=30.0
            )
            
            await self.send_robot_command(robot_id, command)
        
        self.logger.info(f"Line formation created with spacing {spacing}")
        return True
    
    async def _create_circle_formation(self, radius: float = 2.0, **kwargs) -> bool:
        """Create circle formation."""
        import math
        
        robot_ids = list(self.robots.keys())
        num_robots = len(robot_ids)
        
        for i, robot_id in enumerate(robot_ids):
            angle = (2 * math.pi * i) / num_robots
            target_x = radius * math.cos(angle)
            target_y = radius * math.sin(angle)
            
            command = SimpleRobotCommand(
                robot_id=robot_id,
                action="navigate",
                parameters={"target_position": {"x": target_x, "y": target_y, "z": 0.0}},
                priority=1,
                timeout=30.0
            )
            
            await self.send_robot_command(robot_id, command)
        
        self.logger.info(f"Circle formation created with radius {radius}")
        return True
    
    async def _create_grid_formation(self, spacing: float = 1.0, **kwargs) -> bool:
        """Create grid formation."""
        robot_ids = list(self.robots.keys())
        robots_per_row = int(len(robot_ids) ** 0.5) + 1
        
        for i, robot_id in enumerate(robot_ids):
            row = i // robots_per_row
            col = i % robots_per_row
            
            target_x = (col - robots_per_row / 2) * spacing
            target_y = (row - robots_per_row / 2) * spacing
            
            command = SimpleRobotCommand(
                robot_id=robot_id,
                action="navigate",
                parameters={"target_position": {"x": target_x, "y": target_y, "z": 0.0}},
                priority=1,
                timeout=30.0
            )
            
            await self.send_robot_command(robot_id, command)
        
        self.logger.info(f"Grid formation created with spacing {spacing}")
        return True
    
    async def initialize(self) -> bool:
        """Initialize the Webots manager."""
        try:
            self.logger.info("Initializing WebotsManager")
            
            # Check if Webots is installed
            if not Path(self.webots_config.webots_path).exists():
                self.logger.warning(f"Webots not found at: {self.webots_config.webots_path}")
                self.logger.info("Please install Webots from: https://cyberbotics.com/")
                return False
            
            # Ensure project structure
            self._ensure_project_structure()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WebotsManager: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the Webots manager."""
        try:
            self.logger.info("Starting WebotsManager")
            return await self.initialize()
        except Exception as e:
            self.logger.error(f"Failed to start WebotsManager: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the Webots manager and any running simulation."""
        try:
            self.logger.info("Stopping WebotsManager")
            if self.simulation_running:
                await self.stop_simulation()
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop WebotsManager: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the Webots manager."""
        try:
            webots_available = Path(self.webots_config.webots_path).exists()
            
            return {
                'status': 'healthy' if webots_available else 'unhealthy',
                'webots_available': webots_available,
                'simulation_running': self.simulation_running,
                'robot_count': len(self.robots),
                'uptime': self._get_uptime() if self.simulation_running else 0,
                'project_path': str(self.project_root)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'simulation_running': False
            }
    
    def cleanup(self):
        """Clean up resources when shutting down."""
        if self.simulation_running:
            asyncio.create_task(self.stop_simulation())
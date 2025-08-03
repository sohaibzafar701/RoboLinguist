"""
Webots Robot Spawner for ChatGPT Robotics.

This module handles robot spawning and management in Webots simulations,
providing dynamic robot creation and configuration capabilities.
"""

import asyncio
import json
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from core.base_component import BaseComponent
from core.data_models import RobotState
from config.config_manager import ConfigManager
from .webots_manager import WebotsManager, RobotInfo


@dataclass
class RobotSpawnConfig:
    """Configuration for spawning a robot in Webots."""
    robot_id: str
    robot_type: str = "e-puck"
    position: Dict[str, float] = None
    orientation: Dict[str, float] = None
    controller: str = "fleet_controller"
    initial_battery: float = 100.0
    capabilities: List[str] = None


@dataclass
class SpawnedRobotInfo:
    """Information about a spawned robot in Webots."""
    robot_id: str
    robot_type: str
    spawn_time: datetime
    position: Dict[str, float]
    status: str
    controller: str
    capabilities: List[str]


class WebotsRobotSpawner(BaseComponent):
    """
    Robot spawner for Webots simulations.
    
    Manages robot spawning, positioning, and initial configuration
    in Webots simulation environments.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Robot type configurations
        self.robot_types = {
            "e-puck": {
                "model_name": "E-puck",
                "capabilities": ["navigation", "sensing", "communication"],
                "sensors": ["distance_sensors", "camera", "accelerometer"],
                "max_speed": 0.5,
                "battery_capacity": 100.0,
                "size": {"radius": 0.037, "height": 0.055}
            },
            "turtlebot3": {
                "model_name": "TurtleBot3Burger",
                "capabilities": ["navigation", "lidar", "vision"],
                "sensors": ["lidar", "camera", "imu"],
                "max_speed": 0.22,
                "battery_capacity": 150.0,
                "size": {"width": 0.138, "depth": 0.178, "height": 0.192}
            },
            "pioneer3dx": {
                "model_name": "Pioneer3dx",
                "capabilities": ["navigation", "manipulation", "sensing"],
                "sensors": ["sonar", "camera", "laser"],
                "max_speed": 1.2,
                "battery_capacity": 200.0,
                "size": {"width": 0.44, "depth": 0.38, "height": 0.22}
            }
        }
        
        # Spawn tracking
        self.spawned_robots: Dict[str, SpawnedRobotInfo] = {}
        self.spawn_positions: List[Dict[str, float]] = []
        self.next_spawn_index = 0
        
        # Default spawn positions for arena environment
        self._initialize_spawn_positions()
        
        self.logger.info("WebotsRobotSpawner initialized")
    
    def set_webots_manager(self, webots_manager) -> None:
        """Set reference to Webots manager."""
        self.webots_manager = webots_manager
        self.logger.info("Webots manager reference established")
    
    def _initialize_spawn_positions(self) -> None:
        """Initialize default spawn positions for robots."""
        # Grid of spawn positions in 10x10 arena
        positions = []
        
        # Create a 5x4 grid of positions
        for row in range(4):
            for col in range(5):
                x = (col - 2) * 1.5  # Spread across X axis
                y = (row - 1.5) * 1.5  # Spread across Y axis
                positions.append({"x": x, "y": y, "z": 0.0, "yaw": 0.0})
        
        self.spawn_positions = positions
    
    async def spawn_robot(self, config: RobotSpawnConfig, 
                         webots_manager: WebotsManager) -> bool:
        """
        Spawn a robot in the Webots simulation.
        
        Args:
            config: Robot spawn configuration
            webots_manager: Webots simulation manager instance
            
        Returns:
            True if robot spawned successfully
        """
        try:
            # Validate robot type
            if config.robot_type not in self.robot_types:
                self.logger.error(f"Unknown robot type: {config.robot_type}")
                return False
            
            # Check if robot ID already exists
            if config.robot_id in self.spawned_robots:
                self.logger.error(f"Robot {config.robot_id} already exists")
                return False
            
            # Determine spawn position
            spawn_position = self._get_spawn_position(config.position)
            
            # Get robot type info
            robot_info = self.robot_types[config.robot_type]
            
            self.logger.info(f"Spawning robot {config.robot_id} of type {config.robot_type}")
            self.logger.info(f"Position: {spawn_position}")
            
            # Create robot entry for world file (in real implementation, this would
            # dynamically add robot to running simulation)
            robot_entry = self._generate_robot_entry(config, spawn_position)
            
            # Track spawned robot
            spawned_info = SpawnedRobotInfo(
                robot_id=config.robot_id,
                robot_type=config.robot_type,
                spawn_time=datetime.now(),
                position=spawn_position,
                status="active",
                controller=config.controller,
                capabilities=config.capabilities or robot_info["capabilities"]
            )
            
            self.spawned_robots[config.robot_id] = spawned_info
            
            # Add to webots manager's robot tracking
            webots_robot_info = RobotInfo(
                robot_id=config.robot_id,
                robot_type=config.robot_type,
                position=spawn_position,
                controller=config.controller
            )
            
            webots_manager.robots[config.robot_id] = webots_robot_info
            
            # Create initial robot state
            robot_state = RobotState(
                robot_id=config.robot_id,
                position=spawn_position,
                status="idle",
                battery_level=config.initial_battery,
                last_command_time=datetime.now(),
                is_moving=False
            )
            
            webots_manager.robot_states[config.robot_id] = robot_state
            
            self.logger.info(f"Successfully spawned robot {config.robot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error spawning robot {config.robot_id}: {e}")
            return False
    
    def _generate_robot_entry(self, config: RobotSpawnConfig, 
                            position: Dict[str, float]) -> str:
        """Generate Webots world file entry for robot."""
        robot_type_info = self.robot_types[config.robot_type]
        model_name = robot_type_info["model_name"]
        
        # Get orientation
        orientation = config.orientation or {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
        
        robot_entry = f'''
{model_name} {{
  translation {position["x"]} {position["y"]} {position["z"]}
  rotation 0 0 1 {orientation["yaw"]}
  name "{config.robot_id}"
  controller "{config.controller}"
}}'''
        
        return robot_entry
    
    async def spawn_multiple_robots(self, robot_count: int, 
                                  webots_manager: WebotsManager,
                                  robot_type: str = "e-puck",
                                  name_prefix: str = "robot") -> List[str]:
        """
        Spawn multiple robots in the simulation.
        
        Args:
            robot_count: Number of robots to spawn
            robot_type: Type of robots to spawn
            webots_manager: Webots simulation manager instance
            name_prefix: Prefix for robot names
            
        Returns:
            List of successfully spawned robot IDs
        """
        spawned_robot_ids = []
        
        try:
            self.logger.info(f"Spawning {robot_count} robots of type {robot_type}")
            
            # Create spawn tasks
            for i in range(robot_count):
                robot_id = f"{name_prefix}_{i}"
                
                config = RobotSpawnConfig(
                    robot_id=robot_id,
                    robot_type=robot_type,
                    position=None  # Will use automatic positioning
                )
                
                success = await self.spawn_robot(config, webots_manager)
                if success:
                    spawned_robot_ids.append(robot_id)
                
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.1)
            
            self.logger.info(f"Successfully spawned {len(spawned_robot_ids)}/{robot_count} robots")
            
            return spawned_robot_ids
            
        except Exception as e:
            self.logger.error(f"Error spawning multiple robots: {e}")
            return spawned_robot_ids
    
    async def remove_robot(self, robot_id: str, 
                          webots_manager: WebotsManager) -> bool:
        """
        Remove a robot from the simulation.
        
        Args:
            robot_id: ID of robot to remove
            webots_manager: Webots simulation manager instance
            
        Returns:
            True if robot removed successfully
        """
        try:
            if robot_id not in self.spawned_robots:
                self.logger.warning(f"Robot {robot_id} not found in spawner registry")
                return False
            
            # Remove from tracking
            del self.spawned_robots[robot_id]
            
            # Remove from webots manager
            if robot_id in webots_manager.robots:
                del webots_manager.robots[robot_id]
            
            if robot_id in webots_manager.robot_states:
                del webots_manager.robot_states[robot_id]
            
            self.logger.info(f"Successfully removed robot {robot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error removing robot {robot_id}: {e}")
            return False
    
    def get_spawned_robots(self) -> Dict[str, SpawnedRobotInfo]:
        """Get information about all spawned robots."""
        return self.spawned_robots.copy()
    
    def get_robot_info(self, robot_id: str) -> Optional[SpawnedRobotInfo]:
        """Get information about a specific robot."""
        return self.spawned_robots.get(robot_id)
    
    def get_available_robot_types(self) -> Dict[str, Dict[str, Any]]:
        """Get available robot types and their capabilities."""
        return self.robot_types.copy()
    
    def get_robot_capabilities(self, robot_type: str) -> List[str]:
        """Get capabilities of a specific robot type."""
        if robot_type in self.robot_types:
            return self.robot_types[robot_type]["capabilities"]
        return []
    
    def _get_spawn_position(self, requested_position: Optional[Dict[str, float]]) -> Dict[str, float]:
        """
        Get spawn position for robot.
        
        Args:
            requested_position: Requested position or None for automatic
            
        Returns:
            Position dictionary with x, y, z, yaw
        """
        if requested_position:
            # Use requested position
            position = {
                "x": requested_position.get("x", 0.0),
                "y": requested_position.get("y", 0.0),
                "z": requested_position.get("z", 0.0),
                "yaw": requested_position.get("yaw", 0.0)
            }
            return position
        
        # Use automatic positioning
        if self.next_spawn_index < len(self.spawn_positions):
            position = self.spawn_positions[self.next_spawn_index].copy()
            self.next_spawn_index += 1
            return position
        
        # Generate position if we've used all predefined positions
        extra_index = self.next_spawn_index - len(self.spawn_positions)
        position = {
            "x": -4.0 + (extra_index % 8) * 1.0,
            "y": -4.0 + (extra_index // 8) * 1.0,
            "z": 0.0,
            "yaw": 0.0
        }
        self.next_spawn_index += 1
        
        return position
    
    def reset_spawn_positions(self) -> None:
        """Reset spawn position counter."""
        self.next_spawn_index = 0
    
    def add_custom_spawn_position(self, position: Dict[str, float]) -> None:
        """Add a custom spawn position to the list."""
        self.spawn_positions.append(position)
    
    def set_spawn_positions(self, positions: List[Dict[str, float]]) -> None:
        """Set custom spawn positions."""
        self.spawn_positions = positions
        self.next_spawn_index = 0
    
    def get_spawn_summary(self) -> Dict[str, Any]:
        """Get summary of spawning status."""
        robot_types_count = {}
        for robot_info in self.spawned_robots.values():
            robot_type = robot_info.robot_type
            robot_types_count[robot_type] = robot_types_count.get(robot_type, 0) + 1
        
        return {
            "total_robots": len(self.spawned_robots),
            "robot_types": robot_types_count,
            "available_spawn_positions": len(self.spawn_positions) - self.next_spawn_index,
            "next_spawn_index": self.next_spawn_index,
            "spawned_robots": list(self.spawned_robots.keys())
        }
    
    async def validate_robot_spawning(self, robot_count: int, 
                                    webots_manager: WebotsManager) -> Dict[str, Any]:
        """
        Validate if robot spawning is possible.
        
        Args:
            robot_count: Number of robots to validate
            webots_manager: Webots simulation manager instance
            
        Returns:
            Validation result with status and details
        """
        validation_result = {
            "can_spawn": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
        
        try:
            # Check simulation status
            sim_status = webots_manager.get_simulation_status()
            if not sim_status["running"]:
                validation_result["can_spawn"] = False
                validation_result["errors"].append("Simulation is not running")
            
            # Check robot count limits
            current_robot_count = len(self.spawned_robots)
            total_robots = current_robot_count + robot_count
            
            if total_robots > 50:  # Webots practical limit
                validation_result["can_spawn"] = False
                validation_result["errors"].append(f"Total robot count ({total_robots}) exceeds limit (50)")
            elif total_robots > 20:
                validation_result["warnings"].append(f"High robot count ({total_robots}) may impact performance")
            
            # Check spawn positions
            available_positions = len(self.spawn_positions) - self.next_spawn_index
            if robot_count > available_positions:
                validation_result["warnings"].append(
                    f"Not enough predefined spawn positions ({available_positions} available, {robot_count} requested)"
                )
                validation_result["recommendations"].append("Consider adding custom spawn positions")
            
            # Check system resources
            if total_robots > 10:
                validation_result["recommendations"].append("Consider reducing graphics quality for better performance")
            
            return validation_result
            
        except Exception as e:
            validation_result["can_spawn"] = False
            validation_result["errors"].append(f"Validation error: {e}")
            return validation_result
    
    def generate_world_robots_section(self, robot_configs: List[RobotSpawnConfig]) -> str:
        """
        Generate robots section for Webots world file.
        
        Args:
            robot_configs: List of robot configurations
            
        Returns:
            World file robots section
        """
        robots_section = "\n# Robot Fleet\n"
        
        for config in robot_configs:
            position = self._get_spawn_position(config.position)
            robot_entry = self._generate_robot_entry(config, position)
            robots_section += robot_entry + "\n"
        
        return robots_section
    
    def create_formation_spawn_configs(self, robot_count: int, 
                                     formation_type: str = "grid",
                                     robot_type: str = "e-puck",
                                     **kwargs) -> List[RobotSpawnConfig]:
        """
        Create robot spawn configurations in a formation.
        
        Args:
            robot_count: Number of robots
            formation_type: Type of formation (grid, line, circle)
            robot_type: Type of robots
            **kwargs: Formation-specific parameters
            
        Returns:
            List of robot spawn configurations
        """
        configs = []
        
        if formation_type == "grid":
            spacing = kwargs.get("spacing", 1.0)
            robots_per_row = int(math.sqrt(robot_count)) + 1
            
            for i in range(robot_count):
                row = i // robots_per_row
                col = i % robots_per_row
                
                x = (col - robots_per_row / 2) * spacing
                y = (row - robots_per_row / 2) * spacing
                
                config = RobotSpawnConfig(
                    robot_id=f"robot_{i}",
                    robot_type=robot_type,
                    position={"x": x, "y": y, "z": 0.0, "yaw": 0.0}
                )
                configs.append(config)
        
        elif formation_type == "line":
            spacing = kwargs.get("spacing", 1.0)
            
            for i in range(robot_count):
                x = (i - robot_count / 2) * spacing
                y = 0.0
                
                config = RobotSpawnConfig(
                    robot_id=f"robot_{i}",
                    robot_type=robot_type,
                    position={"x": x, "y": y, "z": 0.0, "yaw": 0.0}
                )
                configs.append(config)
        
        elif formation_type == "circle":
            radius = kwargs.get("radius", 2.0)
            
            for i in range(robot_count):
                angle = (2 * math.pi * i) / robot_count
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                
                config = RobotSpawnConfig(
                    robot_id=f"robot_{i}",
                    robot_type=robot_type,
                    position={"x": x, "y": y, "z": 0.0, "yaw": angle}
                )
                configs.append(config)
        
        return configs
    
    async def initialize(self) -> bool:
        """Initialize the robot spawner."""
        try:
            self.logger.info("Initializing WebotsRobotSpawner")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize WebotsRobotSpawner: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the robot spawner."""
        return await self.initialize()
    
    async def stop(self) -> bool:
        """Stop the robot spawner and clean up."""
        try:
            self.logger.info("Stopping WebotsRobotSpawner")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop WebotsRobotSpawner: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            return {
                'status': 'healthy',
                'spawned_robots': len(self.spawned_robots),
                'spawn_history_count': len(self.spawn_history),
                'webots_manager_connected': self.webots_manager is not None
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
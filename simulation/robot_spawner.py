"""
Robot Spawner

Manages instantiation and spawning of multiple TIAGo robots in Gazebo simulation.
"""

import subprocess
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from core.base_component import BaseComponent
from core.data_models import RobotState
from config.config_manager import ConfigManager


@dataclass
class SpawnConfig:
    """Configuration for spawning a robot."""
    robot_id: str
    model_name: str = "tiago"
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    orientation: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    namespace: Optional[str] = None


class RobotSpawner(BaseComponent):
    """
    Manages spawning and despawning of TIAGo robots in Gazebo simulation.
    """
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__("RobotSpawner", config_manager)
        self.spawned_robots: Dict[str, Dict[str, Any]] = {}
        
        # Get robot configuration
        self.robot_config = self.config.get('robots', {})
        self.default_model = self.robot_config.get('default_model', 'tiago')
        self.model_path = self.robot_config.get('model_path', 'models')
        
        # Predefined spawn positions for warehouse layout
        self.warehouse_positions = [
            (2.0, 2.0, 0.0),    # Robot 1
            (-2.0, 2.0, 0.0),   # Robot 2
            (2.0, -2.0, 0.0),   # Robot 3
            (-2.0, -2.0, 0.0),  # Robot 4
            (0.0, 0.0, 0.0),    # Robot 5 (center)
        ]
    
    def spawn_robot(self, spawn_config: SpawnConfig) -> bool:
        """
        Spawn a single robot in the Gazebo simulation.
        
        Args:
            spawn_config: Configuration for the robot to spawn
            
        Returns:
            bool: True if robot spawned successfully
        """
        if spawn_config.robot_id in self.spawned_robots:
            self.logger.warning(f"Robot {spawn_config.robot_id} is already spawned")
            return True
            
        try:
            # Build spawn command using ROS2 service call
            cmd = [
                "ros2", "service", "call",
                "/spawn_entity",
                "gazebo_msgs/srv/SpawnEntity",
                f"{{name: '{spawn_config.robot_id}', "
                f"xml: '{self._get_robot_urdf(spawn_config.model_name)}', "
                f"initial_pose: {{position: {{x: {spawn_config.position[0]}, "
                f"y: {spawn_config.position[1]}, z: {spawn_config.position[2]}}}, "
                f"orientation: {{x: {spawn_config.orientation[0]}, "
                f"y: {spawn_config.orientation[1]}, z: {spawn_config.orientation[2]}, "
                f"w: {spawn_config.orientation[3]}}}}}}}"
            ]
            
            self.logger.info(f"Spawning robot {spawn_config.robot_id} at position {spawn_config.position}")
            
            # Execute spawn command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Store robot information
                self.spawned_robots[spawn_config.robot_id] = {
                    'model_name': spawn_config.model_name,
                    'position': spawn_config.position,
                    'orientation': spawn_config.orientation,
                    'namespace': spawn_config.namespace,
                    'spawn_time': time.time()
                }
                
                self.logger.info(f"Successfully spawned robot {spawn_config.robot_id}")
                return True
            else:
                self.logger.error(f"Failed to spawn robot {spawn_config.robot_id}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Exception while spawning robot {spawn_config.robot_id}: {e}")
            return False
    
    def spawn_multiple_robots(self, count: int = 3, 
                            model_name: str = "tiago") -> List[str]:
        """
        Spawn multiple TIAGo robots in warehouse configuration.
        
        Args:
            count: Number of robots to spawn (max 5)
            model_name: Model name to use for all robots
            
        Returns:
            List[str]: List of successfully spawned robot IDs
        """
        count = min(count, len(self.warehouse_positions))
        spawned_ids = []
        
        self.logger.info(f"Spawning {count} robots in warehouse configuration")
        
        for i in range(count):
            robot_id = f"tiago_{i+1}"
            position = self.warehouse_positions[i]
            
            spawn_config = SpawnConfig(
                robot_id=robot_id,
                model_name=model_name,
                position=position,
                namespace=f"robot_{i+1}"
            )
            
            if self.spawn_robot(spawn_config):
                spawned_ids.append(robot_id)
            else:
                self.logger.warning(f"Failed to spawn robot {robot_id}")
                
            # Small delay between spawns to avoid conflicts
            time.sleep(2)
        
        self.logger.info(f"Successfully spawned {len(spawned_ids)} out of {count} robots")
        return spawned_ids
    
    def despawn_robot(self, robot_id: str) -> bool:
        """
        Remove a robot from the Gazebo simulation.
        
        Args:
            robot_id: ID of the robot to remove
            
        Returns:
            bool: True if robot was removed successfully
        """
        if robot_id not in self.spawned_robots:
            self.logger.warning(f"Robot {robot_id} is not currently spawned")
            return True
            
        try:
            # Build despawn command using ROS2 service call
            cmd = [
                "ros2", "service", "call",
                "/delete_entity",
                "gazebo_msgs/srv/DeleteEntity",
                f"{{name: '{robot_id}'}}"
            ]
            
            self.logger.info(f"Despawning robot {robot_id}")
            
            # Execute despawn command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                # Remove from tracking
                del self.spawned_robots[robot_id]
                self.logger.info(f"Successfully despawned robot {robot_id}")
                return True
            else:
                self.logger.error(f"Failed to despawn robot {robot_id}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Exception while despawning robot {robot_id}: {e}")
            return False
    
    def despawn_all_robots(self) -> bool:
        """
        Remove all spawned robots from the simulation.
        
        Returns:
            bool: True if all robots were removed successfully
        """
        if not self.spawned_robots:
            self.logger.info("No robots to despawn")
            return True
            
        success = True
        robot_ids = list(self.spawned_robots.keys())
        
        self.logger.info(f"Despawning {len(robot_ids)} robots")
        
        for robot_id in robot_ids:
            if not self.despawn_robot(robot_id):
                success = False
                
        return success
    
    def get_spawned_robots(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all currently spawned robots.
        
        Returns:
            Dict containing information about spawned robots
        """
        return self.spawned_robots.copy()
    
    def get_robot_count(self) -> int:
        """
        Get the number of currently spawned robots.
        
        Returns:
            int: Number of spawned robots
        """
        return len(self.spawned_robots)
    
    def is_robot_spawned(self, robot_id: str) -> bool:
        """
        Check if a specific robot is currently spawned.
        
        Args:
            robot_id: ID of the robot to check
            
        Returns:
            bool: True if robot is spawned
        """
        return robot_id in self.spawned_robots
    
    def get_robot_info(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific spawned robot.
        
        Args:
            robot_id: ID of the robot
            
        Returns:
            Dict containing robot information or None if not found
        """
        return self.spawned_robots.get(robot_id)
    
    def _get_robot_urdf(self, model_name: str) -> str:
        """
        Get the URDF content for a robot model.
        
        Args:
            model_name: Name of the robot model
            
        Returns:
            str: URDF content as string
        """
        # In a real implementation, this would load the actual URDF file
        # For now, return a placeholder that represents the TIAGo model
        return f"""<?xml version="1.0"?>
<robot name="{model_name}">
  <link name="base_link">
    <visual>
      <geometry>
        <box size="0.6 0.4 0.2"/>
      </geometry>
      <material name="blue">
        <color rgba="0 0 1 1"/>
      </material>
    </visual>
    <collision>
      <geometry>
        <box size="0.6 0.4 0.2"/>
      </geometry>
    </collision>
  </link>
</robot>"""
    
    def cleanup(self):
        """Clean up resources when shutting down."""
        self.despawn_all_robots()
        super().cleanup()
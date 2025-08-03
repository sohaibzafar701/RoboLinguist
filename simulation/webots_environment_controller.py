"""
Webots Environment Controller for ChatGPT Robotics.

This module provides dynamic environment control capabilities for Webots simulations,
including obstacle management, environment state persistence, and real-time modifications.
"""

import asyncio
import json
import logging
import math
import random
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

from core.base_component import BaseComponent
from config.config_manager import ConfigManager


@dataclass
class EnvironmentObject:
    """Represents an object in the simulation environment."""
    object_id: str
    object_type: str  # box, cylinder, sphere, wall, custom
    position: Dict[str, float]  # x, y, z
    rotation: Dict[str, float]  # roll, pitch, yaw
    size: Dict[str, float]  # dimensions based on type
    color: Dict[str, float] = None  # r, g, b, a
    material: str = "default"
    physics_enabled: bool = True
    collision_enabled: bool = True
    created_time: datetime = None
    
    def __post_init__(self):
        if self.color is None:
            self.color = {"r": 0.5, "g": 0.5, "b": 0.5, "a": 1.0}
        if self.created_time is None:
            self.created_time = datetime.now()


@dataclass
class EnvironmentState:
    """Complete state of the simulation environment."""
    state_id: str
    timestamp: datetime
    objects: Dict[str, EnvironmentObject]
    lighting: Dict[str, Any]
    physics_settings: Dict[str, Any]
    arena_bounds: Dict[str, float]
    description: str = ""
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ObstaclePattern:
    """Predefined obstacle placement pattern."""
    pattern_name: str
    description: str
    objects: List[EnvironmentObject]
    difficulty_level: int  # 1-5 scale
    recommended_robot_count: int


class WebotsEnvironmentController(BaseComponent):
    """
    Advanced environment controller for Webots simulations.
    
    Provides dynamic environment manipulation, obstacle management,
    state persistence, and intelligent environment generation.
    """
    
    def __init__(self, config_manager):
        super().__init__("WebotsEnvironmentController", config_manager.get('environment', {}))
        self.config_manager = config_manager
        
        # Environment state
        self.current_objects: Dict[str, EnvironmentObject] = {}
        self.environment_states: Dict[str, EnvironmentState] = {}
        self.active_state_id: Optional[str] = None
        
        # Configuration
        self.arena_bounds = self.config.get('arena_bounds', {
            'x_min': -5.0, 'x_max': 5.0,
            'y_min': -5.0, 'y_max': 5.0,
            'z_min': 0.0, 'z_max': 3.0
        })
        
        self.max_objects = self.config.get('max_objects', 100)
        self.auto_cleanup = self.config.get('auto_cleanup', True)
        
        # Object templates
        self.object_templates = self._initialize_object_templates()
        
        # Predefined patterns
        self.obstacle_patterns = self._initialize_obstacle_patterns()
        
        # Statistics
        self.stats = {
            'objects_created': 0,
            'objects_removed': 0,
            'states_saved': 0,
            'states_loaded': 0,
            'patterns_applied': 0
        }
        
        # Webots integration
        self.webots_manager = None
        self.world_file_path = None
        
        self.logger.info("WebotsEnvironmentController initialized")
    
    def set_webots_manager(self, webots_manager) -> None:
        """Set reference to Webots manager."""
        self.webots_manager = webots_manager
        self.logger.info("Webots manager reference established")
    
    def _initialize_object_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize predefined object templates."""
        return {
            "small_box": {
                "object_type": "box",
                "size": {"width": 0.5, "height": 0.5, "depth": 0.5},
                "color": {"r": 0.8, "g": 0.4, "b": 0.2, "a": 1.0},
                "material": "wood"
            },
            "large_box": {
                "object_type": "box",
                "size": {"width": 1.0, "height": 1.0, "depth": 1.0},
                "color": {"r": 0.6, "g": 0.3, "b": 0.1, "a": 1.0},
                "material": "wood"
            },
            "cylinder_obstacle": {
                "object_type": "cylinder",
                "size": {"radius": 0.3, "height": 1.0},
                "color": {"r": 0.2, "g": 0.6, "b": 0.8, "a": 1.0},
                "material": "metal"
            },
            "sphere_marker": {
                "object_type": "sphere",
                "size": {"radius": 0.2},
                "color": {"r": 1.0, "g": 0.2, "b": 0.2, "a": 0.8},
                "material": "plastic"
            },
            "wall_segment": {
                "object_type": "box",
                "size": {"width": 2.0, "height": 1.5, "depth": 0.1},
                "color": {"r": 0.7, "g": 0.7, "b": 0.7, "a": 1.0},
                "material": "concrete"
            },
            "ramp": {
                "object_type": "box",
                "size": {"width": 2.0, "height": 0.1, "depth": 1.0},
                "color": {"r": 0.4, "g": 0.4, "b": 0.6, "a": 1.0},
                "material": "metal"
            }
        }
    
    def _initialize_obstacle_patterns(self) -> Dict[str, ObstaclePattern]:
        """Initialize predefined obstacle patterns."""
        patterns = {}
        
        # Simple maze pattern
        maze_objects = []
        for i in range(4):
            for j in range(4):
                if (i + j) % 2 == 0 and i != 0 and j != 0:
                    obj = EnvironmentObject(
                        object_id=f"maze_wall_{i}_{j}",
                        object_type="box",
                        position={"x": (i-2)*1.5, "y": (j-2)*1.5, "z": 0.75},
                        rotation={"roll": 0, "pitch": 0, "yaw": 0},
                        size={"width": 0.2, "height": 1.5, "depth": 0.2},
                        color={"r": 0.6, "g": 0.6, "b": 0.6, "a": 1.0}
                    )
                    maze_objects.append(obj)
        
        patterns["simple_maze"] = ObstaclePattern(
            pattern_name="simple_maze",
            description="Simple maze with wall obstacles",
            objects=maze_objects,
            difficulty_level=3,
            recommended_robot_count=5
        )
        
        # Scattered obstacles
        scattered_objects = []
        for i in range(8):
            angle = (2 * math.pi * i) / 8
            radius = 2.0 + random.uniform(-0.5, 0.5)
            
            obj = EnvironmentObject(
                object_id=f"scattered_obs_{i}",
                object_type="cylinder",
                position={
                    "x": radius * math.cos(angle),
                    "y": radius * math.sin(angle),
                    "z": 0.5
                },
                rotation={"roll": 0, "pitch": 0, "yaw": 0},
                size={"radius": 0.3, "height": 1.0},
                color={"r": 0.8, "g": 0.2, "b": 0.2, "a": 1.0}
            )
            scattered_objects.append(obj)
        
        patterns["scattered_obstacles"] = ObstaclePattern(
            pattern_name="scattered_obstacles",
            description="Randomly scattered cylindrical obstacles",
            objects=scattered_objects,
            difficulty_level=2,
            recommended_robot_count=8
        )
        
        # Warehouse layout
        warehouse_objects = []
        
        # Create shelving units
        for row in range(3):
            for col in range(4):
                if col % 2 == 0:  # Only even columns for aisles
                    obj = EnvironmentObject(
                        object_id=f"shelf_{row}_{col}",
                        object_type="box",
                        position={
                            "x": (col - 1.5) * 1.5,
                            "y": (row - 1) * 2.0,
                            "z": 1.0
                        },
                        rotation={"roll": 0, "pitch": 0, "yaw": 0},
                        size={"width": 1.0, "height": 2.0, "depth": 0.3},
                        color={"r": 0.5, "g": 0.3, "b": 0.1, "a": 1.0}
                    )
                    warehouse_objects.append(obj)
        
        patterns["warehouse_layout"] = ObstaclePattern(
            pattern_name="warehouse_layout",
            description="Warehouse with shelving units and aisles",
            objects=warehouse_objects,
            difficulty_level=4,
            recommended_robot_count=10
        )
        
        return patterns
    
    async def add_object(self, object_config: Dict[str, Any], 
                        template_name: Optional[str] = None) -> bool:
        """
        Add an object to the environment.
        
        Args:
            object_config: Object configuration dictionary
            template_name: Optional template to use as base
            
        Returns:
            True if object added successfully
        """
        try:
            if len(self.current_objects) >= self.max_objects:
                self.logger.error(f"Maximum object limit ({self.max_objects}) reached")
                return False
            
            # Apply template if specified
            if template_name and template_name in self.object_templates:
                template = self.object_templates[template_name].copy()
                # Merge template with provided config
                for key, value in object_config.items():
                    if key in template and isinstance(value, dict) and isinstance(template[key], dict):
                        template[key].update(value)
                    else:
                        template[key] = value
                object_config = template
            
            # Create environment object
            env_object = EnvironmentObject(
                object_id=object_config['object_id'],
                object_type=object_config.get('object_type', 'box'),
                position=object_config.get('position', {'x': 0, 'y': 0, 'z': 0}),
                rotation=object_config.get('rotation', {'roll': 0, 'pitch': 0, 'yaw': 0}),
                size=object_config.get('size', {'width': 1, 'height': 1, 'depth': 1}),
                color=object_config.get('color', {'r': 0.5, 'g': 0.5, 'b': 0.5, 'a': 1.0}),
                material=object_config.get('material', 'default'),
                physics_enabled=object_config.get('physics_enabled', True),
                collision_enabled=object_config.get('collision_enabled', True)
            )
            
            # Validate position
            if not self._validate_object_position(env_object):
                self.logger.error(f"Invalid position for object {env_object.object_id}")
                return False
            
            # Add to simulation (simulated for now)
            success = await self._add_object_to_simulation(env_object)
            
            if success:
                self.current_objects[env_object.object_id] = env_object
                self.stats['objects_created'] += 1
                
                self.logger.info(f"✅ Added object {env_object.object_id} at position "
                               f"({env_object.position['x']:.2f}, {env_object.position['y']:.2f})")
                return True
            else:
                self.logger.error(f"Failed to add object {env_object.object_id} to simulation")
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding object: {e}")
            return False
    
    async def remove_object(self, object_id: str) -> bool:
        """
        Remove an object from the environment.
        
        Args:
            object_id: ID of object to remove
            
        Returns:
            True if object removed successfully
        """
        try:
            if object_id not in self.current_objects:
                self.logger.warning(f"Object {object_id} not found")
                return False
            
            # Remove from simulation
            success = await self._remove_object_from_simulation(object_id)
            
            if success:
                del self.current_objects[object_id]
                self.stats['objects_removed'] += 1
                
                self.logger.info(f"🗑️ Removed object {object_id}")
                return True
            else:
                self.logger.error(f"Failed to remove object {object_id} from simulation")
                return False
                
        except Exception as e:
            self.logger.error(f"Error removing object {object_id}: {e}")
            return False
    
    async def move_object(self, object_id: str, new_position: Dict[str, float],
                         new_rotation: Optional[Dict[str, float]] = None) -> bool:
        """
        Move an object to a new position.
        
        Args:
            object_id: ID of object to move
            new_position: New position coordinates
            new_rotation: Optional new rotation
            
        Returns:
            True if object moved successfully
        """
        try:
            if object_id not in self.current_objects:
                self.logger.error(f"Object {object_id} not found")
                return False
            
            env_object = self.current_objects[object_id]
            
            # Create temporary object for validation
            temp_object = EnvironmentObject(
                object_id=env_object.object_id,
                object_type=env_object.object_type,
                position=new_position,
                rotation=new_rotation or env_object.rotation,
                size=env_object.size
            )
            
            if not self._validate_object_position(temp_object):
                self.logger.error(f"Invalid new position for object {object_id}")
                return False
            
            # Move in simulation
            success = await self._move_object_in_simulation(object_id, new_position, new_rotation)
            
            if success:
                env_object.position = new_position.copy()
                if new_rotation:
                    env_object.rotation = new_rotation.copy()
                
                self.logger.info(f"📍 Moved object {object_id} to "
                               f"({new_position['x']:.2f}, {new_position['y']:.2f})")
                return True
            else:
                self.logger.error(f"Failed to move object {object_id} in simulation")
                return False
                
        except Exception as e:
            self.logger.error(f"Error moving object {object_id}: {e}")
            return False
    
    async def apply_obstacle_pattern(self, pattern_name: str, 
                                   offset: Optional[Dict[str, float]] = None,
                                   scale: float = 1.0) -> bool:
        """
        Apply a predefined obstacle pattern to the environment.
        
        Args:
            pattern_name: Name of pattern to apply
            offset: Optional position offset for the pattern
            scale: Scale factor for the pattern
            
        Returns:
            True if pattern applied successfully
        """
        try:
            if pattern_name not in self.obstacle_patterns:
                self.logger.error(f"Unknown obstacle pattern: {pattern_name}")
                return False
            
            pattern = self.obstacle_patterns[pattern_name]
            offset = offset or {"x": 0, "y": 0, "z": 0}
            
            self.logger.info(f"🎭 Applying obstacle pattern: {pattern_name}")
            self.logger.info(f"   Description: {pattern.description}")
            self.logger.info(f"   Difficulty: {pattern.difficulty_level}/5")
            self.logger.info(f"   Recommended robots: {pattern.recommended_robot_count}")
            
            success_count = 0
            
            for obj in pattern.objects:
                # Apply offset and scale
                scaled_position = {
                    "x": obj.position["x"] * scale + offset["x"],
                    "y": obj.position["y"] * scale + offset["y"],
                    "z": obj.position["z"] * scale + offset["z"]
                }
                
                scaled_size = {}
                for key, value in obj.size.items():
                    scaled_size[key] = value * scale
                
                # Create object configuration
                object_config = {
                    "object_id": f"{pattern_name}_{obj.object_id}",
                    "object_type": obj.object_type,
                    "position": scaled_position,
                    "rotation": obj.rotation,
                    "size": scaled_size,
                    "color": obj.color,
                    "material": obj.material,
                    "physics_enabled": obj.physics_enabled,
                    "collision_enabled": obj.collision_enabled
                }
                
                if await self.add_object(object_config):
                    success_count += 1
                
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.05)
            
            if success_count > 0:
                self.stats['patterns_applied'] += 1
                self.logger.info(f"✅ Applied pattern {pattern_name}: {success_count}/{len(pattern.objects)} objects")
                return True
            else:
                self.logger.error(f"Failed to apply pattern {pattern_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error applying obstacle pattern {pattern_name}: {e}")
            return False
    
    async def clear_environment(self, keep_arena: bool = True) -> bool:
        """
        Clear all objects from the environment.
        
        Args:
            keep_arena: Whether to keep arena boundaries
            
        Returns:
            True if environment cleared successfully
        """
        try:
            object_ids = list(self.current_objects.keys())
            
            if not object_ids:
                self.logger.info("Environment already clear")
                return True
            
            self.logger.info(f"🧹 Clearing environment: {len(object_ids)} objects")
            
            # Remove objects in parallel
            removal_tasks = [self.remove_object(obj_id) for obj_id in object_ids]
            results = await asyncio.gather(*removal_tasks, return_exceptions=True)
            
            success_count = sum(1 for result in results if result is True)
            success_rate = success_count / len(object_ids) * 100
            
            self.logger.info(f"✅ Environment cleared: {success_count}/{len(object_ids)} objects ({success_rate:.1f}%)")
            
            return success_count == len(object_ids)
            
        except Exception as e:
            self.logger.error(f"Error clearing environment: {e}")
            return False
    
    async def save_environment_state(self, state_id: str, description: str = "") -> bool:
        """
        Save current environment state.
        
        Args:
            state_id: Unique identifier for the state
            description: Optional description
            
        Returns:
            True if state saved successfully
        """
        try:
            # Create environment state
            env_state = EnvironmentState(
                state_id=state_id,
                timestamp=datetime.now(),
                objects=self.current_objects.copy(),
                lighting={"ambient": 0.5, "directional": 0.8},  # Simplified
                physics_settings={"gravity": -9.81, "timestep": 0.032},
                arena_bounds=self.arena_bounds.copy(),
                description=description
            )
            
            # Save to memory
            self.environment_states[state_id] = env_state
            
            # Save to file
            success = await self._save_state_to_file(env_state)
            
            if success:
                self.stats['states_saved'] += 1
                self.logger.info(f"💾 Saved environment state: {state_id}")
                return True
            else:
                self.logger.error(f"Failed to save state {state_id} to file")
                return False
                
        except Exception as e:
            self.logger.error(f"Error saving environment state {state_id}: {e}")
            return False
    
    async def load_environment_state(self, state_id: str) -> bool:
        """
        Load a previously saved environment state.
        
        Args:
            state_id: ID of state to load
            
        Returns:
            True if state loaded successfully
        """
        try:
            # Try to load from memory first
            if state_id not in self.environment_states:
                # Try to load from file
                success = await self._load_state_from_file(state_id)
                if not success:
                    self.logger.error(f"Environment state {state_id} not found")
                    return False
            
            env_state = self.environment_states[state_id]
            
            self.logger.info(f"📂 Loading environment state: {state_id}")
            self.logger.info(f"   Description: {env_state.description}")
            self.logger.info(f"   Objects: {len(env_state.objects)}")
            self.logger.info(f"   Saved: {env_state.timestamp}")
            
            # Clear current environment
            await self.clear_environment()
            
            # Recreate objects
            success_count = 0
            for obj_id, env_object in env_state.objects.items():
                object_config = {
                    "object_id": obj_id,
                    "object_type": env_object.object_type,
                    "position": env_object.position,
                    "rotation": env_object.rotation,
                    "size": env_object.size,
                    "color": env_object.color,
                    "material": env_object.material,
                    "physics_enabled": env_object.physics_enabled,
                    "collision_enabled": env_object.collision_enabled
                }
                
                if await self.add_object(object_config):
                    success_count += 1
                
                await asyncio.sleep(0.02)  # Small delay
            
            if success_count > 0:
                self.active_state_id = state_id
                self.stats['states_loaded'] += 1
                self.logger.info(f"✅ Loaded state {state_id}: {success_count}/{len(env_state.objects)} objects")
                return True
            else:
                self.logger.error(f"Failed to load any objects from state {state_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error loading environment state {state_id}: {e}")
            return False
    
    def _validate_object_position(self, env_object: EnvironmentObject) -> bool:
        """Validate if object position is within bounds and doesn't collide."""
        try:
            pos = env_object.position
            
            # Check arena bounds
            if not (self.arena_bounds['x_min'] <= pos['x'] <= self.arena_bounds['x_max'] and
                    self.arena_bounds['y_min'] <= pos['y'] <= self.arena_bounds['y_max'] and
                    self.arena_bounds['z_min'] <= pos['z'] <= self.arena_bounds['z_max']):
                return False
            
            # Check collision with existing objects (simplified)
            for existing_id, existing_obj in self.current_objects.items():
                if existing_id == env_object.object_id:
                    continue
                
                distance = math.sqrt(
                    (pos['x'] - existing_obj.position['x'])**2 +
                    (pos['y'] - existing_obj.position['y'])**2
                )
                
                # Simple collision check based on object sizes
                min_distance = 0.5  # Minimum separation
                if distance < min_distance:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating object position: {e}")
            return False
    
    async def _add_object_to_simulation(self, env_object: EnvironmentObject) -> bool:
        """Add object to Webots simulation."""
        try:
            # In real implementation, this would use Webots supervisor API
            # to dynamically add objects to the running simulation
            await asyncio.sleep(0.01)  # Simulate processing time
            return True
        except Exception as e:
            self.logger.error(f"Failed to add object to simulation: {e}")
            return False
    
    async def _remove_object_from_simulation(self, object_id: str) -> bool:
        """Remove object from Webots simulation."""
        try:
            # In real implementation, this would remove the object node
            await asyncio.sleep(0.01)  # Simulate processing time
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove object from simulation: {e}")
            return False
    
    async def _move_object_in_simulation(self, object_id: str, 
                                       new_position: Dict[str, float],
                                       new_rotation: Optional[Dict[str, float]]) -> bool:
        """Move object in Webots simulation."""
        try:
            # In real implementation, this would update object position in Webots
            await asyncio.sleep(0.01)  # Simulate processing time
            return True
        except Exception as e:
            self.logger.error(f"Failed to move object in simulation: {e}")
            return False
    
    async def _save_state_to_file(self, env_state: EnvironmentState) -> bool:
        """Save environment state to file."""
        try:
            states_dir = Path("environment_states")
            states_dir.mkdir(exist_ok=True)
            
            state_file = states_dir / f"{env_state.state_id}.json"
            
            # Convert to serializable format
            state_data = {
                "state_id": env_state.state_id,
                "timestamp": env_state.timestamp.isoformat(),
                "description": env_state.description,
                "lighting": env_state.lighting,
                "physics_settings": env_state.physics_settings,
                "arena_bounds": env_state.arena_bounds,
                "objects": {}
            }
            
            for obj_id, env_object in env_state.objects.items():
                obj_data = asdict(env_object)
                obj_data['created_time'] = env_object.created_time.isoformat()
                state_data["objects"][obj_id] = obj_data
            
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save state to file: {e}")
            return False
    
    async def _load_state_from_file(self, state_id: str) -> bool:
        """Load environment state from file."""
        try:
            state_file = Path("environment_states") / f"{state_id}.json"
            
            if not state_file.exists():
                return False
            
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            # Reconstruct objects
            objects = {}
            for obj_id, obj_data in state_data["objects"].items():
                obj_data['created_time'] = datetime.fromisoformat(obj_data['created_time'])
                objects[obj_id] = EnvironmentObject(**obj_data)
            
            # Create environment state
            env_state = EnvironmentState(
                state_id=state_data["state_id"],
                timestamp=datetime.fromisoformat(state_data["timestamp"]),
                objects=objects,
                lighting=state_data["lighting"],
                physics_settings=state_data["physics_settings"],
                arena_bounds=state_data["arena_bounds"],
                description=state_data["description"]
            )
            
            self.environment_states[state_id] = env_state
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load state from file: {e}")
            return False
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get comprehensive environment information."""
        return {
            "current_objects": len(self.current_objects),
            "object_types": self._get_object_type_distribution(),
            "arena_bounds": self.arena_bounds,
            "active_state": self.active_state_id,
            "saved_states": len(self.environment_states),
            "available_patterns": list(self.obstacle_patterns.keys()),
            "available_templates": list(self.object_templates.keys()),
            "statistics": self.stats.copy()
        }
    
    def _get_object_type_distribution(self) -> Dict[str, int]:
        """Get distribution of object types in current environment."""
        distribution = {}
        for env_object in self.current_objects.values():
            obj_type = env_object.object_type
            distribution[obj_type] = distribution.get(obj_type, 0) + 1
        return distribution
    
    def get_available_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available obstacle patterns."""
        pattern_info = {}
        for name, pattern in self.obstacle_patterns.items():
            pattern_info[name] = {
                "description": pattern.description,
                "difficulty_level": pattern.difficulty_level,
                "recommended_robot_count": pattern.recommended_robot_count,
                "object_count": len(pattern.objects)
            }
        return pattern_info
    
    def get_object_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get available object templates."""
        return self.object_templates.copy()
    
    async def generate_random_environment(self, complexity: int = 3, 
                                        object_count: Optional[int] = None) -> bool:
        """
        Generate a random environment with specified complexity.
        
        Args:
            complexity: Complexity level (1-5)
            object_count: Optional specific object count
            
        Returns:
            True if environment generated successfully
        """
        try:
            complexity = max(1, min(5, complexity))  # Clamp to 1-5
            
            if object_count is None:
                object_count = complexity * 3 + random.randint(2, 8)
            
            self.logger.info(f"🎲 Generating random environment (complexity: {complexity}, objects: {object_count})")
            
            # Clear existing environment
            await self.clear_environment()
            
            # Generate objects
            success_count = 0
            template_names = list(self.object_templates.keys())
            
            for i in range(object_count):
                # Choose random template
                template_name = random.choice(template_names)
                
                # Generate random position
                position = {
                    "x": random.uniform(self.arena_bounds['x_min'] + 1, self.arena_bounds['x_max'] - 1),
                    "y": random.uniform(self.arena_bounds['y_min'] + 1, self.arena_bounds['y_max'] - 1),
                    "z": random.uniform(0.1, 2.0)
                }
                
                # Generate random rotation
                rotation = {
                    "roll": 0,
                    "pitch": 0,
                    "yaw": random.uniform(0, 2 * math.pi)
                }
                
                # Create object configuration
                object_config = {
                    "object_id": f"random_obj_{i}",
                    "position": position,
                    "rotation": rotation
                }
                
                if await self.add_object(object_config, template_name):
                    success_count += 1
                
                await asyncio.sleep(0.02)  # Small delay
            
            success_rate = success_count / object_count * 100
            self.logger.info(f"✅ Generated random environment: {success_count}/{object_count} objects ({success_rate:.1f}%)")
            
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error generating random environment: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on environment controller."""
        try:
            return {
                "status": "healthy",
                "current_objects": len(self.current_objects),
                "max_objects": self.max_objects,
                "capacity_used": (len(self.current_objects) / self.max_objects) * 100,
                "saved_states": len(self.environment_states),
                "webots_connected": self.webots_manager is not None,
                "statistics": self.stats.copy()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "current_objects": len(self.current_objects) if hasattr(self, 'current_objects') else 0
            }
    
    async def initialize(self) -> bool:
        """Initialize the environment controller."""
        try:
            self.logger.info("Initializing WebotsEnvironmentController")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize WebotsEnvironmentController: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the environment controller."""
        return await self.initialize()
    
    async def stop(self) -> bool:
        """Stop the environment controller and clean up."""
        try:
            self.logger.info("Stopping WebotsEnvironmentController")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop WebotsEnvironmentController: {e}")
            return False
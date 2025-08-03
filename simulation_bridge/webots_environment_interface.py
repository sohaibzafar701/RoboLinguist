"""
Webots Environment Interface

This interface manages the Webots simulation environment,
including obstacles, objects, and world state.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class WebotsEnvironmentInterface:
    """Interface for managing Webots simulation environment."""
    
    def __init__(self, bridge_config):
        self.bridge_config = bridge_config
        self.supervisor = None
        self.environment_objects = {}
        self.environment_state = {}
        self.running = False
        
        logger.info("Webots Environment Interface initialized")
    
    async def initialize(self):
        """Initialize the environment interface."""
        logger.info("Initializing Webots Environment Interface...")
        
        try:
            # Environment interface will be connected through robot interface
            # For now, we'll track environment state
            self.environment_state = {
                'objects': {},
                'obstacles': {},
                'markers': {},
                'boundaries': {
                    'x_min': -5.0, 'x_max': 5.0,
                    'y_min': -5.0, 'y_max': 5.0,
                    'z_min': 0.0, 'z_max': 3.0
                }
            }
            
            self.running = True
            logger.info("Webots Environment Interface ready")
            
        except Exception as e:
            logger.error(f"Environment initialization failed: {e}")
            raise
    
    async def add_obstacle(self, obstacle_id: str, position: Tuple[float, float, float], 
                          size: Tuple[float, float, float]) -> Dict[str, Any]:
        """Add an obstacle to the environment."""
        try:
            obstacle_info = {
                'id': obstacle_id,
                'position': position,
                'size': size,
                'type': 'obstacle',
                'timestamp': asyncio.get_event_loop().time()
            }
            
            self.environment_state['obstacles'][obstacle_id] = obstacle_info
            
            logger.info(f"Added obstacle {obstacle_id} at {position}")
            
            return {
                'success': True,
                'obstacle_id': obstacle_id,
                'position': position,
                'size': size
            }
            
        except Exception as e:
            logger.error(f"Add obstacle failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def remove_obstacle(self, obstacle_id: str) -> Dict[str, Any]:
        """Remove an obstacle from the environment."""
        try:
            if obstacle_id in self.environment_state['obstacles']:
                del self.environment_state['obstacles'][obstacle_id]
                logger.info(f"Removed obstacle {obstacle_id}")
                
                return {
                    'success': True,
                    'obstacle_id': obstacle_id
                }
            else:
                return {
                    'success': False,
                    'error': f'Obstacle {obstacle_id} not found'
                }
                
        except Exception as e:
            logger.error(f"Remove obstacle failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def add_marker(self, marker_id: str, position: Tuple[float, float, float], 
                        color: Tuple[float, float, float] = (1.0, 1.0, 0.0)) -> Dict[str, Any]:
        """Add a visual marker to the environment."""
        try:
            marker_info = {
                'id': marker_id,
                'position': position,
                'color': color,
                'type': 'marker',
                'timestamp': asyncio.get_event_loop().time()
            }
            
            self.environment_state['markers'][marker_id] = marker_info
            
            logger.info(f"Added marker {marker_id} at {position}")
            
            return {
                'success': True,
                'marker_id': marker_id,
                'position': position,
                'color': color
            }
            
        except Exception as e:
            logger.error(f"Add marker failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def remove_marker(self, marker_id: str) -> Dict[str, Any]:
        """Remove a marker from the environment."""
        try:
            if marker_id in self.environment_state['markers']:
                del self.environment_state['markers'][marker_id]
                logger.info(f"Removed marker {marker_id}")
                
                return {
                    'success': True,
                    'marker_id': marker_id
                }
            else:
                return {
                    'success': False,
                    'error': f'Marker {marker_id} not found'
                }
                
        except Exception as e:
            logger.error(f"Remove marker failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_environment_info(self) -> Dict[str, Any]:
        """Get current environment information."""
        try:
            return {
                'boundaries': self.environment_state['boundaries'],
                'obstacle_count': len(self.environment_state['obstacles']),
                'marker_count': len(self.environment_state['markers']),
                'object_count': len(self.environment_state['objects']),
                'obstacles': list(self.environment_state['obstacles'].keys()),
                'markers': list(self.environment_state['markers'].keys()),
                'objects': list(self.environment_state['objects'].keys())
            }
            
        except Exception as e:
            logger.error(f"Get environment info failed: {e}")
            return {'error': str(e)}
    
    async def check_collision(self, position: Tuple[float, float, float], 
                            radius: float = 0.1) -> Dict[str, Any]:
        """Check if a position would collide with obstacles."""
        try:
            x, y, z = position
            collisions = []
            
            # Check boundaries
            bounds = self.environment_state['boundaries']
            if (x < bounds['x_min'] or x > bounds['x_max'] or
                y < bounds['y_min'] or y > bounds['y_max'] or
                z < bounds['z_min'] or z > bounds['z_max']):
                collisions.append('boundary')
            
            # Check obstacles
            for obstacle_id, obstacle in self.environment_state['obstacles'].items():
                obs_x, obs_y, obs_z = obstacle['position']
                obs_w, obs_h, obs_d = obstacle['size']
                
                # Simple box collision check
                if (abs(x - obs_x) < (obs_w/2 + radius) and
                    abs(y - obs_y) < (obs_h/2 + radius) and
                    abs(z - obs_z) < (obs_d/2 + radius)):
                    collisions.append(obstacle_id)
            
            return {
                'collision': len(collisions) > 0,
                'collisions': collisions,
                'position': position
            }
            
        except Exception as e:
            logger.error(f"Collision check failed: {e}")
            return {'error': str(e)}
    
    async def find_free_position(self, preferred_position: Tuple[float, float, float], 
                                search_radius: float = 2.0) -> Optional[Tuple[float, float, float]]:
        """Find a free position near the preferred position."""
        try:
            import random
            import math
            
            pref_x, pref_y, pref_z = preferred_position
            
            # Try the preferred position first
            collision_result = await self.check_collision(preferred_position)
            if not collision_result.get('collision', True):
                return preferred_position
            
            # Search in expanding circles
            for radius in [0.5, 1.0, 1.5, 2.0]:
                for _ in range(20):  # Try 20 random positions at this radius
                    angle = random.uniform(0, 2 * math.pi)
                    x = pref_x + radius * math.cos(angle)
                    y = pref_y + radius * math.sin(angle)
                    z = pref_z
                    
                    test_position = (x, y, z)
                    collision_result = await self.check_collision(test_position)
                    
                    if not collision_result.get('collision', True):
                        return test_position
            
            logger.warning(f"Could not find free position near {preferred_position}")
            return None
            
        except Exception as e:
            logger.error(f"Find free position failed: {e}")
            return None
    
    async def save_environment_state(self, state_name: str) -> Dict[str, Any]:
        """Save current environment state."""
        try:
            saved_state = {
                'name': state_name,
                'timestamp': asyncio.get_event_loop().time(),
                'obstacles': self.environment_state['obstacles'].copy(),
                'markers': self.environment_state['markers'].copy(),
                'objects': self.environment_state['objects'].copy(),
                'boundaries': self.environment_state['boundaries'].copy()
            }
            
            # In a real implementation, this would be saved to file
            logger.info(f"Saved environment state: {state_name}")
            
            return {
                'success': True,
                'state_name': state_name,
                'object_count': len(saved_state['obstacles']) + len(saved_state['markers']) + len(saved_state['objects'])
            }
            
        except Exception as e:
            logger.error(f"Save environment state failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def load_environment_state(self, state_name: str) -> Dict[str, Any]:
        """Load a saved environment state."""
        try:
            # In a real implementation, this would load from file
            logger.info(f"Loading environment state: {state_name}")
            
            return {
                'success': True,
                'state_name': state_name,
                'message': 'Environment state loading simulated'
            }
            
        except Exception as e:
            logger.error(f"Load environment state failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def reset_environment(self) -> Dict[str, Any]:
        """Reset environment to initial state."""
        try:
            # Clear all dynamic objects
            self.environment_state['obstacles'].clear()
            self.environment_state['markers'].clear()
            self.environment_state['objects'].clear()
            
            logger.info("Environment reset to initial state")
            
            return {
                'success': True,
                'message': 'Environment reset complete'
            }
            
        except Exception as e:
            logger.error(f"Reset environment failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_environment_status(self) -> Dict[str, Any]:
        """Get environment status."""
        try:
            return {
                'running': self.running,
                'total_objects': (len(self.environment_state['obstacles']) + 
                                len(self.environment_state['markers']) + 
                                len(self.environment_state['objects'])),
                'obstacles': len(self.environment_state['obstacles']),
                'markers': len(self.environment_state['markers']),
                'objects': len(self.environment_state['objects']),
                'boundaries': self.environment_state['boundaries']
            }
            
        except Exception as e:
            logger.error(f"Get environment status failed: {e}")
            return {'error': str(e)}
    
    async def shutdown(self):
        """Shutdown the environment interface."""
        logger.info("Shutting down Webots Environment Interface...")
        
        self.running = False
        
        # Clear all state
        self.environment_objects.clear()
        self.environment_state.clear()
        
        logger.info("Webots Environment Interface shutdown complete")
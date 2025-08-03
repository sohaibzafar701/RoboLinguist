"""
Webots Robot Interface

This interface bridges between the real robot system and Webots simulation.
It translates ROS2-style robot commands to Webots API calls.
"""

import asyncio
import logging
import math
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class WebotsRobotInterface:
    """Interface for controlling robots in Webots simulation."""
    
    def __init__(self, bridge_config):
        self.bridge_config = bridge_config
        self.supervisor = None
        self.robots = {}  # robot_id -> robot_node
        self.robot_states = {}  # robot_id -> current state
        self.timestep = 16
        self.running = False
        
        # Setup Webots API
        self._setup_webots_api()
        
        logger.info("Webots Robot Interface initialized")
    
    def _setup_webots_api(self):
        """Setup Webots Python API."""
        import platform
        
        # Set robot name for supervisor
        os.environ['WEBOTS_ROBOT_NAME'] = 'fleet_supervisor'
        
        # Common Webots installation paths
        webots_install_paths = []
        
        if platform.system() == "Windows":
            webots_install_paths = [
                r"C:\Program Files\Webots",
                r"C:\Program Files (x86)\Webots",
                r"C:\Users\{}\AppData\Local\Programs\Webots".format(os.getenv('USERNAME', '')),
            ]
        elif platform.system() == "Darwin":
            webots_install_paths = [
                "/Applications/Webots.app",
            ]
        else:
            webots_install_paths = [
                "/usr/local/webots",
                "/opt/webots",
                "/snap/webots/current/usr/share/webots",
            ]
        
        # Check if WEBOTS_HOME is already set
        webots_home = os.getenv('WEBOTS_HOME')
        if webots_home and os.path.exists(webots_home):
            python_path = os.path.join(webots_home, 'lib', 'controller', 'python')
            if os.path.exists(python_path):
                if python_path not in sys.path:
                    sys.path.insert(0, python_path)
                logger.info(f"Using WEBOTS_HOME: {webots_home}")
                return
        
        # Try to find Webots installation
        for install_path in webots_install_paths:
            if os.path.exists(install_path):
                os.environ['WEBOTS_HOME'] = install_path
                python_path = os.path.join(install_path, 'lib', 'controller', 'python')
                if os.path.exists(python_path):
                    if python_path not in sys.path:
                        sys.path.insert(0, python_path)
                    logger.info(f"Found Webots installation: {install_path}")
                    return
        
        logger.warning("Could not find Webots installation")
    
    async def initialize(self):
        """Initialize the Webots robot interface."""
        logger.info("Initializing Webots Robot Interface...")
        
        try:
            # Import Webots controller
            from controller import Supervisor
            
            # Connect to Webots supervisor
            self.supervisor = Supervisor()
            self.timestep = int(self.supervisor.getBasicTimeStep())
            
            # Discover robots in simulation
            await self._discover_robots()
            
            self.running = True
            logger.info("Webots Robot Interface ready")
            
        except ImportError as e:
            logger.error(f"Webots API not available: {e}")
            raise
        except Exception as e:
            logger.error(f"Webots initialization failed: {e}")
            raise
    
    async def _discover_robots(self):
        """Discover all robots in the Webots simulation."""
        logger.info("Discovering robots in Webots...")
        
        for i in range(self.bridge_config.robot_count):
            robot_name = f"robot_{i}"
            robot_node = self.supervisor.getFromDef(robot_name)
            
            if robot_node:
                self.robots[str(i)] = robot_node
                
                # Initialize robot state
                position = robot_node.getPosition()
                self.robot_states[str(i)] = {
                    'position': position,
                    'orientation': (0.0, 0.0, 0.0, 1.0),  # Default quaternion (no rotation)
                    'target_position': None,
                    'status': 'idle',
                    'is_moving': False
                }
                
                logger.info(f"Found {robot_name} at ({position[0]:.2f}, {position[1]:.2f})")
            else:
                logger.warning(f"Could not find {robot_name}")
        
        logger.info(f"Discovered {len(self.robots)} robots")
    
    async def get_available_robots(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available robots."""
        robot_info = {}
        
        for robot_id, robot_node in self.robots.items():
            if robot_node:
                position = robot_node.getPosition()
                robot_info[robot_id] = {
                    'position': position,
                    'orientation': (0.0, 0.0, 0.0, 1.0),  # Default quaternion (no rotation)
                    'status': self.robot_states[robot_id]['status'],
                    'capabilities': ['navigate', 'formation']
                }
        
        return robot_info
    
    async def move_robot(self, robot_id: str, target_x: float, target_y: float) -> Dict[str, Any]:
        """Move a single robot to target position."""
        try:
            if robot_id not in self.robots:
                return {'success': False, 'error': f'Robot {robot_id} not found'}
            
            # Set target position
            self.robot_states[robot_id]['target_position'] = (target_x, target_y)
            self.robot_states[robot_id]['status'] = 'moving'
            self.robot_states[robot_id]['is_moving'] = True
            
            logger.info(f"Robot {robot_id} moving to ({target_x:.2f}, {target_y:.2f})")
            
            # Start movement (will be updated in simulation step)
            await self._update_robot_movement(robot_id)
            
            return {
                'success': True,
                'robot_id': robot_id,
                'target': (target_x, target_y)
            }
            
        except Exception as e:
            logger.error(f"Move robot failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def move_all_robots(self, target_x: float, target_y: float) -> Dict[str, Any]:
        """Move all robots to target area with spread."""
        try:
            results = []
            
            for i, robot_id in enumerate(self.robots.keys()):
                # Spread robots around target
                offset_x = (i % 5 - 2) * 0.5
                offset_y = (i // 5 - 1) * 0.5
                
                result = await self.move_robot(
                    robot_id, 
                    target_x + offset_x, 
                    target_y + offset_y
                )
                results.append(result)
            
            success_count = sum(1 for r in results if r['success'])
            
            return {
                'success': success_count > 0,
                'moved_robots': success_count,
                'total_robots': len(results),
                'target': (target_x, target_y)
            }
            
        except Exception as e:
            logger.error(f"Move all robots failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def create_formation(self, formation_type: str, **kwargs) -> Dict[str, Any]:
        """Create robot formation."""
        try:
            logger.info(f"Creating {formation_type} formation...")
            
            # Filter out 'formation' parameter if it exists (it's redundant with formation_type)
            filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'formation'}
            
            if formation_type == 'circle':
                return await self._create_circle_formation(**filtered_kwargs)
            elif formation_type == 'line':
                return await self._create_line_formation(**filtered_kwargs)
            elif formation_type == 'grid':
                return await self._create_grid_formation(**filtered_kwargs)
            elif formation_type == 'spread':
                return await self._create_spread_formation(**filtered_kwargs)
            else:
                return {'success': False, 'error': f'Unknown formation: {formation_type}'}
                
        except Exception as e:
            logger.error(f"Formation creation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _create_circle_formation(self, radius: float = 3.0, center_x: float = 0.0, center_y: float = 0.0) -> Dict[str, Any]:
        """Create circle formation."""
        results = []
        robot_count = len(self.robots)
        
        for i, robot_id in enumerate(self.robots.keys()):
            angle = (2 * math.pi * i) / robot_count
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            result = await self.move_robot(robot_id, x, y)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count > 0,
            'formation': 'circle',
            'robots_positioned': success_count,
            'total_robots': len(results)
        }
    
    async def _create_line_formation(self, spacing: float = 1.0, start_x: float = -4.5, y: float = 0.0) -> Dict[str, Any]:
        """Create line formation."""
        results = []
        
        for i, robot_id in enumerate(self.robots.keys()):
            x = start_x + i * spacing
            result = await self.move_robot(robot_id, x, y)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count > 0,
            'formation': 'line',
            'robots_positioned': success_count,
            'total_robots': len(results)
        }
    
    async def _create_grid_formation(self, spacing: float = 1.0, cols: int = 5) -> Dict[str, Any]:
        """Create grid formation."""
        results = []
        
        for i, robot_id in enumerate(self.robots.keys()):
            x = -2 + (i % cols) * spacing
            y = -0.5 + (i // cols) * spacing
            result = await self.move_robot(robot_id, x, y)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count > 0,
            'formation': 'grid',
            'robots_positioned': success_count,
            'total_robots': len(results)
        }
    
    async def _create_spread_formation(self, area_size: float = 6.0) -> Dict[str, Any]:
        """Create spread formation."""
        import random
        results = []
        
        for robot_id in self.robots.keys():
            x = random.uniform(-area_size, area_size)
            y = random.uniform(-area_size, area_size)
            result = await self.move_robot(robot_id, x, y)
            results.append(result)
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'success': success_count > 0,
            'formation': 'spread',
            'robots_positioned': success_count,
            'total_robots': len(results)
        }
    
    async def stop_robot(self, robot_id: str) -> Dict[str, Any]:
        """Stop a specific robot."""
        try:
            if robot_id not in self.robots:
                return {'success': False, 'error': f'Robot {robot_id} not found'}
            
            self.robot_states[robot_id]['target_position'] = None
            self.robot_states[robot_id]['status'] = 'stopped'
            self.robot_states[robot_id]['is_moving'] = False
            
            logger.info(f"Robot {robot_id} stopped")
            
            return {
                'success': True,
                'robot_id': robot_id,
                'status': 'stopped'
            }
            
        except Exception as e:
            logger.error(f"Stop robot failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def stop_all_robots(self) -> Dict[str, Any]:
        """Stop all robots."""
        try:
            results = []
            
            for robot_id in self.robots.keys():
                result = await self.stop_robot(robot_id)
                results.append(result)
            
            success_count = sum(1 for r in results if r['success'])
            
            return {
                'success': success_count > 0,
                'stopped_robots': success_count,
                'total_robots': len(results)
            }
            
        except Exception as e:
            logger.error(f"Stop all robots failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _update_robot_movement(self, robot_id: str, speed: float = 0.1):
        """Update robot movement towards target."""
        if robot_id not in self.robots or robot_id not in self.robot_states:
            return
        
        robot_node = self.robots[robot_id]
        robot_state = self.robot_states[robot_id]
        
        if not robot_state['target_position'] or robot_state['status'] != 'moving':
            return
        
        # Get current position
        current_pos = robot_node.getPosition()
        target_x, target_y = robot_state['target_position']
        
        # Calculate direction
        dx = target_x - current_pos[0]
        dy = target_y - current_pos[1]
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance < 0.1:  # Reached target
            robot_state['status'] = 'idle'
            robot_state['target_position'] = None
            robot_state['is_moving'] = False
            logger.info(f"Robot {robot_id} reached target")
        else:
            # Move towards target
            move_x = current_pos[0] + (dx / distance) * speed
            move_y = current_pos[1] + (dy / distance) * speed
            
            # Update position in Webots
            robot_node.getField('translation').setSFVec3f([move_x, move_y, current_pos[2]])
            
            # Update state
            robot_state['position'] = (move_x, move_y, current_pos[2])
    
    async def step_simulation(self):
        """Step the simulation and update all robots."""
        if not self.supervisor or not self.running:
            return False
        
        try:
            # Step Webots simulation
            if self.supervisor.step(self.timestep) == -1:
                return False
            
            # Update all moving robots
            for robot_id in self.robots.keys():
                if self.robot_states[robot_id]['is_moving']:
                    await self._update_robot_movement(robot_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Simulation step failed: {e}")
            return False
    
    async def get_robot_state(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a robot."""
        if robot_id not in self.robot_states:
            return None
        
        return self.robot_states[robot_id].copy()
    
    async def get_all_robot_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all robots."""
        return {robot_id: state.copy() for robot_id, state in self.robot_states.items()}
    
    async def get_simulation_status(self) -> Dict[str, Any]:
        """Get simulation status."""
        if not self.supervisor:
            return {'connected': False}
        
        try:
            moving_count = sum(1 for state in self.robot_states.values() if state['is_moving'])
            idle_count = sum(1 for state in self.robot_states.values() if state['status'] == 'idle')
            stopped_count = sum(1 for state in self.robot_states.values() if state['status'] == 'stopped')
            
            return {
                'connected': True,
                'running': self.running,
                'simulation_time': self.supervisor.getTime(),
                'timestep': self.timestep,
                'robot_count': len(self.robots),
                'robots_moving': moving_count,
                'robots_idle': idle_count,
                'robots_stopped': stopped_count
            }
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {'connected': False, 'error': str(e)}
    
    async def shutdown(self):
        """Shutdown the robot interface."""
        logger.info("Shutting down Webots Robot Interface...")
        
        self.running = False
        
        # Stop all robots
        await self.stop_all_robots()
        
        # Clear state
        self.robots.clear()
        self.robot_states.clear()
        
        logger.info("Webots Robot Interface shutdown complete")
"""
ROS2 Simulation Bridge

Main coordinator that bridges the real ChatGPT for Robots system
with Webots simulation environment using ROS2 topics.

This creates a ROS2 layer that makes Webots simulation appear as real ROS2 robots
to the core components (Tasks 1-6), which remain completely unchanged.

Architecture:
Core Components (unchanged) ←→ ROS2 Topics ←→ ROS2 Bridge ←→ Webots
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Import simulation interfaces
from .webots_robot_interface import WebotsRobotInterface
from .webots_environment_interface import WebotsEnvironmentInterface
from .simulation_state_manager import SimulationStateManager
from .ros2_bridge_node import ROS2BridgeManager

logger = logging.getLogger(__name__)


@dataclass
class BridgeConfig:
    """Configuration for the simulation bridge."""
    use_simulation: bool = True
    webots_world_file: str = "webots_working_demo/minimal_fleet_world.wbt"
    robot_count: int = 10
    update_rate_hz: float = 10.0
    enable_safety: bool = True
    enable_distributed: bool = True


class ROS2SimulationBridge:
    """
    Main bridge between real system and Webots simulation using ROS2.
    
    This creates ROS2 nodes that publish/subscribe to standard robot topics,
    making Webots simulation appear as real ROS2 robots to core components.
    
    The core components (Tasks 1-6) remain completely unchanged and use ROS2 normally.
    """
    
    def __init__(self, bridge_config: Optional[BridgeConfig] = None):
        """Initialize the simulation bridge."""
        self.bridge_config = bridge_config or BridgeConfig()
        
        # Initialize simulation interfaces
        self._init_simulation_interfaces()
        
        # Initialize ROS2 bridge
        self.ros2_bridge = None
        
        # Bridge state
        self.running = False
        self.robot_states = {}
        
        logger.info("ROS2 Simulation Bridge initialized")
    
    def _init_simulation_interfaces(self):
        """Initialize simulation interfaces."""
        logger.info("Initializing simulation interfaces...")
        
        # Webots interfaces
        self.robot_interface = WebotsRobotInterface(self.bridge_config)
        self.environment_interface = WebotsEnvironmentInterface(self.bridge_config)
        self.state_manager = SimulationStateManager(self.bridge_config)
        
        logger.info("Simulation interfaces initialized")
    
    async def initialize(self):
        """Initialize the complete bridge system."""
        logger.info("Initializing ROS2 Simulation Bridge...")
        
        try:
            # Initialize simulation components
            await self._initialize_simulation_components()
            
            # Initialize ROS2 bridge
            await self._initialize_ros2_bridge()
            
            # Start simulation loop
            await self._start_simulation_loop()
            
            self.running = True
            logger.info("ROS2 Simulation Bridge ready!")
            logger.info("Core components can now connect via standard ROS2 topics")
            
        except Exception as e:
            logger.error(f"Bridge initialization failed: {e}")
            raise
    
    async def _initialize_simulation_components(self):
        """Initialize simulation components."""
        logger.info("Starting simulation components...")
        
        # Initialize Webots interfaces
        await self.robot_interface.initialize()
        await self.environment_interface.initialize()
        await self.state_manager.initialize()
        
        logger.info("Simulation components started")
    
    async def _initialize_ros2_bridge(self):
        """Initialize ROS2 bridge nodes."""
        logger.info("Starting ROS2 bridge...")
        
        # Create ROS2 bridge manager
        self.ros2_bridge = ROS2BridgeManager(self.robot_interface)
        
        # Initialize ROS2 nodes
        await self.ros2_bridge.initialize()
        
        logger.info("ROS2 bridge started")
        logger.info("Available ROS2 topics:")
        
        # Log available topics for core components to use
        robot_topics = self.ros2_bridge.get_all_robot_topics()
        for robot_id, topics in robot_topics.items():
            logger.info(f"  Robot {robot_id}:")
            logger.info(f"    cmd_vel: {topics.cmd_vel}")
            logger.info(f"    odom: {topics.odom}")
            logger.info(f"    battery: {topics.battery}")
            logger.info(f"    status: {topics.status}")
            logger.info(f"    goal: {topics.goal}")
        
        fleet_topics = self.ros2_bridge.get_fleet_topics()
        logger.info("  Fleet topics:")
        for topic_name, topic_path in fleet_topics.items():
            logger.info(f"    {topic_name}: {topic_path}")
    
    async def _start_simulation_loop(self):
        """Start the simulation update loop."""
        logger.info("Starting simulation loop...")
        
        # Create background task for simulation stepping
        self.simulation_task = asyncio.create_task(self._simulation_loop())
        
        logger.info("Simulation loop started")
    
    async def _simulation_loop(self):
        """Main simulation loop."""
        while self.running:
            try:
                # Step Webots simulation
                step_success = await self.robot_interface.step_simulation()
                
                if not step_success:
                    logger.warning("Simulation step failed")
                    break
                
                # Update robot states
                await self._update_robot_states()
                
                # Small delay to prevent excessive CPU usage
                await asyncio.sleep(0.01)  # ~100Hz update rate
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulation loop error: {e}")
                await asyncio.sleep(0.1)
        
        logger.info("Simulation loop stopped")
    
    async def _update_robot_states(self):
        """Update robot states from Webots."""
        try:
            # Get all robot states from Webots
            webots_states = await self.robot_interface.get_all_robot_states()
            
            # Update our internal state tracking
            self.robot_states.update(webots_states)
            
            # The ROS2 bridge nodes will automatically publish these states
            # to ROS2 topics that the core components can subscribe to
            
        except Exception as e:
            logger.error(f"Robot state update failed: {e}")
    
    async def get_available_robots(self) -> Dict[str, Any]:
        """Get information about available robots."""
        return await self.robot_interface.get_available_robots()
    
    def get_ros2_topics(self) -> Dict[str, Any]:
        """Get all available ROS2 topics for core components to use."""
        if not self.ros2_bridge:
            return {}
        
        return {
            'robot_topics': self.ros2_bridge.get_all_robot_topics(),
            'fleet_topics': self.ros2_bridge.get_fleet_topics()
        }
    
    async def send_fleet_command(self, command_type: str, **params) -> Dict[str, Any]:
        """Send a fleet-level command through ROS2."""
        try:
            if command_type == 'formation':
                return await self.robot_interface.create_formation(
                    params.get('formation', 'circle'), **params)
            elif command_type == 'move_all':
                return await self.robot_interface.move_all_robots(
                    params.get('x', 0.0), params.get('y', 0.0))
            elif command_type == 'stop_all':
                return await self.robot_interface.stop_all_robots()
            else:
                return {'success': False, 'error': f'Unknown command: {command_type}'}
                
        except Exception as e:
            logger.error(f"Fleet command failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        try:
            return {
                'bridge_running': self.running,
                'robot_count': len(self.robot_states),
                'robots': self.robot_states,
                'simulation': await self.robot_interface.get_simulation_status(),
                'ros2_bridge': self.ros2_bridge is not None,
                'available_topics': self.get_ros2_topics()
            }
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {'error': str(e)}
    
    async def emergency_stop_all(self):
        """Trigger emergency stop for all robots."""
        logger.warning("Emergency stop triggered!")
        
        # Stop all robots in simulation
        await self.robot_interface.stop_all_robots()
        
        # The ROS2 bridge will publish emergency stop to ROS2 topics
        # that the core components can subscribe to
    
    async def shutdown(self):
        """Shutdown the bridge system."""
        logger.info("Shutting down ROS2 Simulation Bridge...")
        
        self.running = False
        
        try:
            # Cancel simulation loop
            if hasattr(self, 'simulation_task'):
                self.simulation_task.cancel()
                try:
                    await self.simulation_task
                except asyncio.CancelledError:
                    pass
            
            # Shutdown ROS2 bridge
            if self.ros2_bridge:
                await self.ros2_bridge.shutdown()
            
            # Shutdown simulation components
            await self.robot_interface.shutdown()
            await self.environment_interface.shutdown()
            await self.state_manager.shutdown()
            
            logger.info("Bridge shutdown complete")
            
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
"""
ROS2 Subscriber component for receiving robot state updates and sensor data.

Handles subscription to ROS2 topics for real-time robot monitoring.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import json

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.subscription import Subscription
    from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
    from sensor_msgs.msg import BatteryState, LaserScan
    from nav_msgs.msg import OccupancyGrid, Odometry
    from std_msgs.msg import String, Bool
    ROS2_AVAILABLE = True
except ImportError:
    # Mock ROS2 classes for testing without ROS2 installation
    ROS2_AVAILABLE = False
    Node = object
    Subscription = object

from core.base_component import BaseComponent
from core.data_models import RobotState, RobotStatus


class ROS2Subscriber(BaseComponent):
    """
    Subscribes to ROS2 topics for robot state monitoring and sensor data.
    
    Provides real-time updates on robot positions, battery levels, and status.
    """
    
    def __init__(self, node_name: str = "chatgpt_robots_subscriber"):
        super().__init__(node_name)
        self.node_name = node_name
        self.node: Optional[Node] = None
        self.subscriptions: Dict[str, Subscription] = {}
        self.robot_states: Dict[str, RobotState] = {}
        self.state_callbacks: List[Callable[[str, RobotState], None]] = []
        
    async def initialize(self) -> bool:
        """Initialize ROS2 node and subscriptions."""
        try:
            if not ROS2_AVAILABLE:
                self.logger.warning("ROS2 not available, running in mock mode")
                self.is_initialized = True
                return True
                
            if not rclpy.ok():
                rclpy.init()
                
            self.node = Node(self.node_name)
            
            # Create global subscriptions
            self.subscriptions = {
                'robot_registry': self.node.create_subscription(
                    String, '/robot_registry', self._robot_registry_callback, 10
                ),
                'system_status': self.node.create_subscription(
                    String, '/system_status', self._system_status_callback, 10
                )
            }
            
            self.is_initialized = True
            self.logger.info(f"ROS2Subscriber initialized with node: {self.node_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize ROS2Subscriber: {e}")
            return False
    
    async def subscribe_to_robot(self, robot_id: str) -> bool:
        """
        Subscribe to all relevant topics for a specific robot.
        
        Args:
            robot_id: Robot identifier to subscribe to
            
        Returns:
            bool: True if subscriptions created successfully
        """
        if not self.is_initialized:
            self.logger.error("Subscriber not initialized")
            return False
            
        try:
            if not ROS2_AVAILABLE:
                self.logger.info(f"Mock: Subscribing to robot {robot_id}")
                # Create mock robot state
                self.robot_states[robot_id] = RobotState(
                    robot_id=robot_id,
                    position=(0.0, 0.0, 0.0),
                    orientation=(0.0, 0.0, 0.0, 1.0),
                    status=RobotStatus.IDLE,
                    battery_level=100.0,
                    current_task=None
                )
                return True
            
            # Subscribe to robot-specific topics
            robot_subs = {
                f'{robot_id}_odom': self.node.create_subscription(
                    Odometry, f'/{robot_id}/odom', 
                    lambda msg, rid=robot_id: self._odometry_callback(rid, msg), 10
                ),
                f'{robot_id}_battery': self.node.create_subscription(
                    BatteryState, f'/{robot_id}/battery_state',
                    lambda msg, rid=robot_id: self._battery_callback(rid, msg), 10
                ),
                f'{robot_id}_status': self.node.create_subscription(
                    String, f'/{robot_id}/robot_status',
                    lambda msg, rid=robot_id: self._robot_status_callback(rid, msg), 10
                ),
                f'{robot_id}_task': self.node.create_subscription(
                    String, f'/{robot_id}/current_task',
                    lambda msg, rid=robot_id: self._task_status_callback(rid, msg), 10
                )
            }
            
            self.subscriptions.update(robot_subs)
            
            # Initialize robot state if not exists
            if robot_id not in self.robot_states:
                self.robot_states[robot_id] = RobotState(
                    robot_id=robot_id,
                    position=(0.0, 0.0, 0.0),
                    orientation=(0.0, 0.0, 0.0, 1.0),
                    status=RobotStatus.IDLE,
                    battery_level=100.0,
                    current_task=None
                )
            
            self.logger.info(f"Subscribed to robot {robot_id} topics")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to robot {robot_id}: {e}")
            return False
    
    def _odometry_callback(self, robot_id: str, msg) -> None:
        """Handle odometry updates for robot position and orientation."""
        try:
            if robot_id not in self.robot_states:
                return
                
            # Extract position
            position = (
                msg.pose.pose.position.x,
                msg.pose.pose.position.y,
                msg.pose.pose.position.z
            )
            
            # Extract orientation
            orientation = (
                msg.pose.pose.orientation.x,
                msg.pose.pose.orientation.y,
                msg.pose.pose.orientation.z,
                msg.pose.pose.orientation.w
            )
            
            # Update robot state
            self.robot_states[robot_id].position = position
            self.robot_states[robot_id].orientation = orientation
            self.robot_states[robot_id].last_update = datetime.now()
            
            # Notify callbacks
            self._notify_state_callbacks(robot_id)
            
        except Exception as e:
            self.logger.error(f"Error processing odometry for {robot_id}: {e}")
    
    def _battery_callback(self, robot_id: str, msg) -> None:
        """Handle battery state updates."""
        try:
            if robot_id not in self.robot_states:
                return
                
            # Convert battery voltage to percentage (simplified)
            battery_percentage = min(100.0, max(0.0, (msg.voltage - 10.0) / 2.6 * 100.0))
            
            self.robot_states[robot_id].battery_level = battery_percentage
            self.robot_states[robot_id].last_update = datetime.now()
            
            # Notify callbacks
            self._notify_state_callbacks(robot_id)
            
        except Exception as e:
            self.logger.error(f"Error processing battery state for {robot_id}: {e}")
    
    def _robot_status_callback(self, robot_id: str, msg) -> None:
        """Handle robot status updates."""
        try:
            if robot_id not in self.robot_states:
                return
                
            # Parse status from message
            status_str = msg.data.lower()
            if status_str in ['idle', 'moving', 'executing', 'error']:
                self.robot_states[robot_id].status = RobotStatus(status_str)
                self.robot_states[robot_id].last_update = datetime.now()
                
                # Notify callbacks
                self._notify_state_callbacks(robot_id)
            
        except Exception as e:
            self.logger.error(f"Error processing robot status for {robot_id}: {e}")
    
    def _task_status_callback(self, robot_id: str, msg) -> None:
        """Handle current task updates."""
        try:
            if robot_id not in self.robot_states:
                return
                
            task_id = msg.data if msg.data != "none" else None
            self.robot_states[robot_id].current_task = task_id
            self.robot_states[robot_id].last_update = datetime.now()
            
            # Notify callbacks
            self._notify_state_callbacks(robot_id)
            
        except Exception as e:
            self.logger.error(f"Error processing task status for {robot_id}: {e}")
    
    def _robot_registry_callback(self, msg) -> None:
        """Handle robot registry updates."""
        try:
            registry_data = json.loads(msg.data)
            for robot_info in registry_data.get('robots', []):
                robot_id = robot_info.get('robot_id')
                if robot_id and robot_id not in self.robot_states:
                    # Auto-subscribe to new robots
                    asyncio.create_task(self.subscribe_to_robot(robot_id))
                    
        except Exception as e:
            self.logger.error(f"Error processing robot registry: {e}")
    
    def _system_status_callback(self, msg) -> None:
        """Handle system-wide status updates."""
        try:
            status_data = json.loads(msg.data)
            self.logger.info(f"System status update: {status_data}")
            
        except Exception as e:
            self.logger.error(f"Error processing system status: {e}")
    
    def _notify_state_callbacks(self, robot_id: str) -> None:
        """Notify all registered callbacks of state changes."""
        try:
            robot_state = self.robot_states.get(robot_id)
            if robot_state:
                for callback in self.state_callbacks:
                    try:
                        callback(robot_id, robot_state)
                    except Exception as e:
                        self.logger.error(f"Error in state callback: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error notifying state callbacks: {e}")
    
    def add_state_callback(self, callback: Callable[[str, RobotState], None]) -> None:
        """
        Add a callback function to be called when robot states change.
        
        Args:
            callback: Function that takes (robot_id, robot_state) as parameters
        """
        self.state_callbacks.append(callback)
        self.logger.info("Added state callback")
    
    def remove_state_callback(self, callback: Callable[[str, RobotState], None]) -> None:
        """
        Remove a previously added state callback.
        
        Args:
            callback: Callback function to remove
        """
        if callback in self.state_callbacks:
            self.state_callbacks.remove(callback)
            self.logger.info("Removed state callback")
    
    def get_robot_state(self, robot_id: str) -> Optional[RobotState]:
        """
        Get current state of a specific robot.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            RobotState or None if robot not found
        """
        return self.robot_states.get(robot_id)
    
    def get_all_robot_states(self) -> Dict[str, RobotState]:
        """
        Get current states of all known robots.
        
        Returns:
            Dictionary mapping robot_id to RobotState
        """
        return self.robot_states.copy()
    
    def get_available_robots(self) -> List[str]:
        """
        Get list of robot IDs that are currently available.
        
        Returns:
            List of available robot IDs
        """
        available = []
        for robot_id, state in self.robot_states.items():
            if state.is_available():
                available.append(robot_id)
        return available
    
    async def spin_once(self) -> None:
        """Process one round of ROS2 callbacks."""
        if self.node and ROS2_AVAILABLE:
            rclpy.spin_once(self.node, timeout_sec=0.1)
    
    async def spin_background(self) -> None:
        """Run ROS2 spinning in background task."""
        if not self.node or not ROS2_AVAILABLE:
            return
            
        try:
            while self.is_initialized:
                rclpy.spin_once(self.node, timeout_sec=0.1)
                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
                
        except Exception as e:
            self.logger.error(f"Error in background spinning: {e}")
    
    async def start(self) -> bool:
        """Start the subscriber component."""
        if not self.is_initialized:
            return await self.initialize()
        return True
    
    async def stop(self) -> bool:
        """Stop the subscriber component."""
        return await self.shutdown()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the subscriber."""
        return {
            'component': 'ROS2Subscriber',
            'initialized': self.is_initialized,
            'ros2_available': ROS2_AVAILABLE,
            'node_name': self.node_name,
            'subscription_count': len(self.subscriptions),
            'robot_count': len(self.robot_states),
            'callback_count': len(self.state_callbacks),
            'status': 'healthy' if self.is_initialized else 'not_initialized'
        }
    
    async def shutdown(self) -> bool:
        """Shutdown the subscriber and cleanup resources."""
        try:
            self.is_initialized = False
            
            if self.node and ROS2_AVAILABLE:
                self.node.destroy_node()
                
            if ROS2_AVAILABLE and rclpy.ok():
                rclpy.shutdown()
                
            self.robot_states.clear()
            self.state_callbacks.clear()
            self.logger.info("ROS2Subscriber shutdown complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            return False
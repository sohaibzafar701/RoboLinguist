"""
Navigation Interface for robot movement commands and path planning.

Provides high-level navigation capabilities using ROS2 Navigation2 stack.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.action import ActionClient
    from nav2_msgs.action import NavigateToPose
    from geometry_msgs.msg import PoseStamped, Point, Quaternion
    from nav_msgs.msg import Path
    from std_msgs.msg import Header
    ROS2_AVAILABLE = True
except ImportError:
    # Mock ROS2 classes for testing without ROS2 installation
    ROS2_AVAILABLE = False
    Node = object
    ActionClient = object
    
    # Mock geometry_msgs classes
    class Point:
        def __init__(self):
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
    
    class Quaternion:
        def __init__(self):
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            self.w = 1.0

from core.base_component import BaseComponent
from core.data_models import RobotCommand, RobotState, ActionType


class NavigationStatus(str, Enum):
    """Navigation task status."""
    IDLE = "idle"
    PLANNING = "planning"
    NAVIGATING = "navigating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NavigationInterface(BaseComponent):
    """
    High-level interface for robot navigation using ROS2 Navigation2.
    
    Handles path planning, goal setting, and navigation monitoring.
    """
    
    def __init__(self, node_name: str = "chatgpt_robots_navigation"):
        super().__init__(node_name)
        self.node_name = node_name
        self.node: Optional[Node] = None
        self.action_clients: Dict[str, ActionClient] = {}
        self.navigation_goals: Dict[str, Dict[str, Any]] = {}
        self.navigation_status: Dict[str, NavigationStatus] = {}
        
    async def initialize(self) -> bool:
        """Initialize ROS2 node and navigation clients."""
        try:
            if not ROS2_AVAILABLE:
                self.logger.warning("ROS2 not available, running in mock mode")
                self.is_initialized = True
                return True
                
            if not rclpy.ok():
                rclpy.init()
                
            self.node = Node(self.node_name)
            self.is_initialized = True
            self.logger.info(f"NavigationInterface initialized with node: {self.node_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize NavigationInterface: {e}")
            return False
    
    async def navigate_to_pose(self, robot_id: str, target_x: float, target_y: float, 
                             target_z: float = 0.0, target_yaw: float = 0.0) -> bool:
        """
        Send navigation goal to a specific robot.
        
        Args:
            robot_id: Target robot identifier
            target_x: Target X coordinate
            target_y: Target Y coordinate
            target_z: Target Z coordinate (default: 0.0)
            target_yaw: Target yaw angle in radians (default: 0.0)
            
        Returns:
            bool: True if goal was sent successfully
        """
        if not self.is_initialized:
            self.logger.error("NavigationInterface not initialized")
            return False
            
        try:
            if not ROS2_AVAILABLE:
                self.logger.info(f"Mock: Navigating {robot_id} to ({target_x}, {target_y}, {target_z})")
                self.navigation_status[robot_id] = NavigationStatus.NAVIGATING
                
                # Store goal information in mock mode
                self.navigation_goals[robot_id] = {
                    'target_x': target_x,
                    'target_y': target_y,
                    'target_z': target_z,
                    'target_yaw': target_yaw,
                    'start_time': datetime.now(),
                    'future': None  # No future in mock mode
                }
                
                # Simulate navigation completion after 2 seconds
                asyncio.create_task(self._mock_navigation_completion(robot_id))
                return True
            
            # Create action client for robot if not exists
            if robot_id not in self.action_clients:
                action_topic = f'/{robot_id}/navigate_to_pose'
                self.action_clients[robot_id] = ActionClient(
                    self.node, NavigateToPose, action_topic
                )
            
            action_client = self.action_clients[robot_id]
            
            # Wait for action server
            if not action_client.wait_for_server(timeout_sec=5.0):
                self.logger.error(f"Navigation action server not available for {robot_id}")
                return False
            
            # Create navigation goal
            goal_msg = NavigateToPose.Goal()
            
            # Set header
            goal_msg.pose.header = Header()
            goal_msg.pose.header.stamp = self.node.get_clock().now().to_msg()
            goal_msg.pose.header.frame_id = "map"
            
            # Set position
            goal_msg.pose.pose.position = Point()
            goal_msg.pose.pose.position.x = float(target_x)
            goal_msg.pose.pose.position.y = float(target_y)
            goal_msg.pose.pose.position.z = float(target_z)
            
            # Convert yaw to quaternion
            goal_msg.pose.pose.orientation = self._yaw_to_quaternion(target_yaw)
            
            # Send goal
            self.navigation_status[robot_id] = NavigationStatus.PLANNING
            future = action_client.send_goal_async(
                goal_msg, 
                feedback_callback=lambda feedback: self._navigation_feedback_callback(robot_id, feedback)
            )
            
            # Store goal information
            self.navigation_goals[robot_id] = {
                'target_x': target_x,
                'target_y': target_y,
                'target_z': target_z,
                'target_yaw': target_yaw,
                'start_time': datetime.now(),
                'future': future
            }
            
            # Handle goal response asynchronously
            asyncio.create_task(self._handle_navigation_response(robot_id, future))
            
            self.logger.info(f"Sent navigation goal to {robot_id}: ({target_x}, {target_y}, {target_z})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send navigation goal to {robot_id}: {e}")
            self.navigation_status[robot_id] = NavigationStatus.FAILED
            return False
    
    async def _mock_navigation_completion(self, robot_id: str) -> None:
        """Mock navigation completion for testing."""
        await asyncio.sleep(2.0)  # Simulate navigation time
        self.navigation_status[robot_id] = NavigationStatus.SUCCEEDED
        self.logger.info(f"Mock navigation completed for {robot_id}")
    
    def _yaw_to_quaternion(self, yaw: float) -> Quaternion:
        """Convert yaw angle to quaternion."""
        import math
        
        quat = Quaternion()
        quat.x = 0.0
        quat.y = 0.0
        quat.z = math.sin(yaw / 2.0)
        quat.w = math.cos(yaw / 2.0)
        return quat
    
    async def _handle_navigation_response(self, robot_id: str, future) -> None:
        """Handle navigation goal response asynchronously."""
        try:
            goal_handle = await future
            if not goal_handle.accepted:
                self.logger.error(f"Navigation goal rejected for {robot_id}")
                self.navigation_status[robot_id] = NavigationStatus.FAILED
                return
            
            self.logger.info(f"Navigation goal accepted for {robot_id}")
            self.navigation_status[robot_id] = NavigationStatus.NAVIGATING
            
            # Wait for result
            result_future = goal_handle.get_result_async()
            result = await result_future
            
            if result.status == 4:  # SUCCEEDED
                self.navigation_status[robot_id] = NavigationStatus.SUCCEEDED
                self.logger.info(f"Navigation succeeded for {robot_id}")
            else:
                self.navigation_status[robot_id] = NavigationStatus.FAILED
                self.logger.error(f"Navigation failed for {robot_id} with status: {result.status}")
                
        except Exception as e:
            self.logger.error(f"Error handling navigation response for {robot_id}: {e}")
            self.navigation_status[robot_id] = NavigationStatus.FAILED
    
    def _navigation_feedback_callback(self, robot_id: str, feedback) -> None:
        """Handle navigation feedback."""
        try:
            # Log navigation progress
            if hasattr(feedback.feedback, 'distance_remaining'):
                distance = feedback.feedback.distance_remaining
                self.logger.debug(f"Navigation feedback for {robot_id}: {distance:.2f}m remaining")
                
        except Exception as e:
            self.logger.error(f"Error processing navigation feedback for {robot_id}: {e}")
    
    async def cancel_navigation(self, robot_id: str) -> bool:
        """
        Cancel ongoing navigation for a robot.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            bool: True if cancellation was successful
        """
        if not self.is_initialized:
            self.logger.error("NavigationInterface not initialized")
            return False
            
        try:
            if not ROS2_AVAILABLE:
                self.logger.info(f"Mock: Cancelling navigation for {robot_id}")
                self.navigation_status[robot_id] = NavigationStatus.CANCELLED
                return True
            
            if robot_id not in self.action_clients:
                self.logger.warning(f"No active navigation for {robot_id}")
                return True
            
            # Cancel the goal if it exists
            goal_info = self.navigation_goals.get(robot_id)
            if goal_info and 'future' in goal_info:
                future = goal_info['future']
                if not future.done():
                    future.cancel()
            
            self.navigation_status[robot_id] = NavigationStatus.CANCELLED
            self.logger.info(f"Cancelled navigation for {robot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel navigation for {robot_id}: {e}")
            return False
    
    def get_navigation_status(self, robot_id: str) -> NavigationStatus:
        """
        Get current navigation status for a robot.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            NavigationStatus: Current navigation status
        """
        return self.navigation_status.get(robot_id, NavigationStatus.IDLE)
    
    def is_navigation_active(self, robot_id: str) -> bool:
        """
        Check if robot is currently navigating.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            bool: True if navigation is active
        """
        status = self.get_navigation_status(robot_id)
        return status in [NavigationStatus.PLANNING, NavigationStatus.NAVIGATING]
    
    async def wait_for_navigation_completion(self, robot_id: str, timeout: float = 30.0) -> bool:
        """
        Wait for navigation to complete.
        
        Args:
            robot_id: Robot identifier
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if navigation completed successfully
        """
        start_time = datetime.now()
        timeout_delta = timedelta(seconds=timeout)
        
        while datetime.now() - start_time < timeout_delta:
            status = self.get_navigation_status(robot_id)
            
            if status == NavigationStatus.SUCCEEDED:
                return True
            elif status in [NavigationStatus.FAILED, NavigationStatus.CANCELLED]:
                return False
            
            await asyncio.sleep(0.1)
        
        self.logger.warning(f"Navigation timeout for {robot_id}")
        return False
    
    async def execute_navigation_command(self, command: RobotCommand) -> bool:
        """
        Execute a navigation command from a RobotCommand object.
        
        Args:
            command: RobotCommand with navigation parameters
            
        Returns:
            bool: True if command was executed successfully
        """
        if command.action_type != ActionType.NAVIGATE:
            self.logger.error(f"Invalid action type for navigation: {command.action_type}")
            return False
        
        params = command.parameters
        target_x = params.get('target_x', 0.0)
        target_y = params.get('target_y', 0.0)
        target_z = params.get('target_z', 0.0)
        target_yaw = params.get('target_yaw', 0.0)
        
        return await self.navigate_to_pose(
            command.robot_id, target_x, target_y, target_z, target_yaw
        )
    
    def get_navigation_metrics(self, robot_id: str) -> Dict[str, Any]:
        """
        Get navigation performance metrics for a robot.
        
        Args:
            robot_id: Robot identifier
            
        Returns:
            Dictionary containing navigation metrics
        """
        goal_info = self.navigation_goals.get(robot_id, {})
        status = self.get_navigation_status(robot_id)
        
        metrics = {
            'robot_id': robot_id,
            'status': status.value,
            'has_active_goal': robot_id in self.navigation_goals,
            'goal_start_time': goal_info.get('start_time'),
            'target_position': {
                'x': goal_info.get('target_x'),
                'y': goal_info.get('target_y'),
                'z': goal_info.get('target_z')
            }
        }
        
        # Calculate elapsed time if navigation is active
        if goal_info.get('start_time'):
            elapsed = datetime.now() - goal_info['start_time']
            metrics['elapsed_time_seconds'] = elapsed.total_seconds()
        
        return metrics
    
    async def start(self) -> bool:
        """Start the navigation interface component."""
        if not self.is_initialized:
            return await self.initialize()
        return True
    
    async def stop(self) -> bool:
        """Stop the navigation interface component."""
        return await self.shutdown()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the navigation interface."""
        active_navigations = sum(1 for status in self.navigation_status.values() 
                               if status in [NavigationStatus.PLANNING, NavigationStatus.NAVIGATING])
        
        return {
            'component': 'NavigationInterface',
            'initialized': self.is_initialized,
            'ros2_available': ROS2_AVAILABLE,
            'node_name': self.node_name,
            'action_client_count': len(self.action_clients),
            'active_navigations': active_navigations,
            'total_robots': len(self.navigation_status),
            'status': 'healthy' if self.is_initialized else 'not_initialized'
        }
    
    async def shutdown(self) -> bool:
        """Shutdown the navigation interface and cleanup resources."""
        try:
            # Cancel all active navigations
            for robot_id in list(self.navigation_status.keys()):
                if self.is_navigation_active(robot_id):
                    await self.cancel_navigation(robot_id)
            
            self.is_initialized = False
            
            if self.node and ROS2_AVAILABLE:
                self.node.destroy_node()
                
            if ROS2_AVAILABLE and rclpy.ok():
                rclpy.shutdown()
                
            self.action_clients.clear()
            self.navigation_goals.clear()
            self.navigation_status.clear()
            
            self.logger.info("NavigationInterface shutdown complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            return False
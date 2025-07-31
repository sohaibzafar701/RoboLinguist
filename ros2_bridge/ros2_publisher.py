"""
ROS2 Publisher component for publishing commands to ROS2 topics.

Handles publishing robot commands and navigation goals to the ROS2 ecosystem.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.publisher import Publisher
    from geometry_msgs.msg import PoseStamped, Twist
    from nav_msgs.msg import OccupancyGrid
    from std_msgs.msg import String, Bool
    ROS2_AVAILABLE = True
except ImportError:
    # Mock ROS2 classes for testing without ROS2 installation
    ROS2_AVAILABLE = False
    Node = object
    Publisher = object

from core.base_component import BaseComponent
from core.data_models import RobotCommand, ActionType


class ROS2Publisher(BaseComponent):
    """
    Publishes commands and navigation goals to ROS2 topics.
    
    Handles translation of internal command structures to ROS2 messages
    and manages topic publishing for robot control.
    """
    
    def __init__(self, node_name: str = "chatgpt_robots_publisher"):
        super().__init__(node_name)
        self.node_name = node_name
        self.node: Optional[Node] = None
        self.publishers: Dict[str, Publisher] = {}
        
    async def initialize(self) -> bool:
        """Initialize ROS2 node and publishers."""
        try:
            if not ROS2_AVAILABLE:
                self.logger.warning("ROS2 not available, running in mock mode")
                self.is_initialized = True
                return True
                
            if not rclpy.ok():
                rclpy.init()
                
            self.node = Node(self.node_name)
            
            # Create publishers for different command types
            self.publishers = {
                'navigation_goal': self.node.create_publisher(
                    PoseStamped, '/move_base_simple/goal', 10
                ),
                'cmd_vel': self.node.create_publisher(
                    Twist, '/cmd_vel', 10
                ),
                'emergency_stop': self.node.create_publisher(
                    Bool, '/emergency_stop', 10
                ),
                'robot_command': self.node.create_publisher(
                    String, '/robot_command', 10
                )
            }
            
            self.is_initialized = True
            self.logger.info(f"ROS2Publisher initialized with node: {self.node_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize ROS2Publisher: {e}")
            return False
    
    async def publish_navigation_goal(self, robot_id: str, target_x: float, target_y: float, 
                                    target_z: float = 0.0) -> bool:
        """
        Publish navigation goal for a specific robot.
        
        Args:
            robot_id: Target robot identifier
            target_x: Target X coordinate
            target_y: Target Y coordinate  
            target_z: Target Z coordinate (default: 0.0)
            
        Returns:
            bool: True if published successfully
        """
        if not self.is_initialized:
            self.logger.error("Publisher not initialized")
            return False
            
        try:
            if not ROS2_AVAILABLE:
                self.logger.info(f"Mock: Publishing navigation goal for {robot_id} to ({target_x}, {target_y}, {target_z})")
                return True
                
            # Create PoseStamped message
            goal_msg = PoseStamped()
            goal_msg.header.stamp = self.node.get_clock().now().to_msg()
            goal_msg.header.frame_id = "map"
            
            # Set position
            goal_msg.pose.position.x = float(target_x)
            goal_msg.pose.position.y = float(target_y)
            goal_msg.pose.position.z = float(target_z)
            
            # Set orientation (facing forward)
            goal_msg.pose.orientation.x = 0.0
            goal_msg.pose.orientation.y = 0.0
            goal_msg.pose.orientation.z = 0.0
            goal_msg.pose.orientation.w = 1.0
            
            # Publish to robot-specific topic
            topic_name = f"/{robot_id}/move_base_simple/goal"
            if topic_name not in self.publishers:
                self.publishers[topic_name] = self.node.create_publisher(
                    PoseStamped, topic_name, 10
                )
            
            self.publishers[topic_name].publish(goal_msg)
            self.logger.info(f"Published navigation goal for {robot_id} to ({target_x}, {target_y}, {target_z})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to publish navigation goal: {e}")
            return False
    
    async def publish_velocity_command(self, robot_id: str, linear_x: float, 
                                     angular_z: float) -> bool:
        """
        Publish velocity command for direct robot control.
        
        Args:
            robot_id: Target robot identifier
            linear_x: Linear velocity in X direction
            angular_z: Angular velocity around Z axis
            
        Returns:
            bool: True if published successfully
        """
        if not self.is_initialized:
            self.logger.error("Publisher not initialized")
            return False
            
        try:
            if not ROS2_AVAILABLE:
                self.logger.info(f"Mock: Publishing velocity command for {robot_id}: linear_x={linear_x}, angular_z={angular_z}")
                return True
                
            # Create Twist message
            vel_msg = Twist()
            vel_msg.linear.x = float(linear_x)
            vel_msg.linear.y = 0.0
            vel_msg.linear.z = 0.0
            vel_msg.angular.x = 0.0
            vel_msg.angular.y = 0.0
            vel_msg.angular.z = float(angular_z)
            
            # Publish to robot-specific topic
            topic_name = f"/{robot_id}/cmd_vel"
            if topic_name not in self.publishers:
                self.publishers[topic_name] = self.node.create_publisher(
                    Twist, topic_name, 10
                )
            
            self.publishers[topic_name].publish(vel_msg)
            self.logger.info(f"Published velocity command for {robot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to publish velocity command: {e}")
            return False
    
    async def publish_robot_command(self, command: RobotCommand) -> bool:
        """
        Publish a structured robot command.
        
        Args:
            command: RobotCommand object to publish
            
        Returns:
            bool: True if published successfully
        """
        if not self.is_initialized:
            self.logger.error("Publisher not initialized")
            return False
            
        try:
            # Route command based on action type
            if command.action_type == ActionType.NAVIGATE:
                return await self._publish_navigation_command(command)
            elif command.action_type == ActionType.MANIPULATE:
                return await self._publish_manipulation_command(command)
            elif command.action_type == ActionType.INSPECT:
                return await self._publish_inspection_command(command)
            else:
                self.logger.error(f"Unknown action type: {command.action_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to publish robot command: {e}")
            return False
    
    async def _publish_navigation_command(self, command: RobotCommand) -> bool:
        """Publish navigation-specific command."""
        params = command.parameters
        return await self.publish_navigation_goal(
            command.robot_id,
            params.get('target_x', 0.0),
            params.get('target_y', 0.0),
            params.get('target_z', 0.0)
        )
    
    async def _publish_manipulation_command(self, command: RobotCommand) -> bool:
        """Publish manipulation-specific command."""
        if not ROS2_AVAILABLE:
            self.logger.info(f"Mock: Publishing manipulation command for {command.robot_id}")
            return True
            
        # Create manipulation command message
        cmd_msg = String()
        cmd_msg.data = f"manipulate:{command.parameters.get('object_id')}:{command.parameters.get('action')}"
        
        topic_name = f"/{command.robot_id}/manipulation_command"
        if topic_name not in self.publishers:
            self.publishers[topic_name] = self.node.create_publisher(
                String, topic_name, 10
            )
        
        self.publishers[topic_name].publish(cmd_msg)
        self.logger.info(f"Published manipulation command for {command.robot_id}")
        return True
    
    async def _publish_inspection_command(self, command: RobotCommand) -> bool:
        """Publish inspection-specific command."""
        if not ROS2_AVAILABLE:
            self.logger.info(f"Mock: Publishing inspection command for {command.robot_id}")
            return True
            
        # Create inspection command message
        cmd_msg = String()
        cmd_msg.data = f"inspect:{command.parameters.get('target_location')}"
        
        topic_name = f"/{command.robot_id}/inspection_command"
        if topic_name not in self.publishers:
            self.publishers[topic_name] = self.node.create_publisher(
                String, topic_name, 10
            )
        
        self.publishers[topic_name].publish(cmd_msg)
        self.logger.info(f"Published inspection command for {command.robot_id}")
        return True
    
    async def publish_emergency_stop(self) -> bool:
        """
        Publish emergency stop signal to all robots.
        
        Returns:
            bool: True if published successfully
        """
        if not self.is_initialized:
            self.logger.error("Publisher not initialized")
            return False
            
        try:
            if not ROS2_AVAILABLE:
                self.logger.warning("Mock: Publishing emergency stop signal")
                return True
                
            # Create emergency stop message
            stop_msg = Bool()
            stop_msg.data = True
            
            # Publish to global emergency stop topic
            self.publishers['emergency_stop'].publish(stop_msg)
            self.logger.warning("Published emergency stop signal")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to publish emergency stop: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the publisher component."""
        if not self.is_initialized:
            return await self.initialize()
        return True
    
    async def stop(self) -> bool:
        """Stop the publisher component."""
        return await self.shutdown()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the publisher."""
        return {
            'component': 'ROS2Publisher',
            'initialized': self.is_initialized,
            'ros2_available': ROS2_AVAILABLE,
            'node_name': self.node_name,
            'publisher_count': len(self.publishers),
            'status': 'healthy' if self.is_initialized else 'not_initialized'
        }
    
    async def shutdown(self) -> bool:
        """Shutdown the publisher and cleanup resources."""
        try:
            if self.node and ROS2_AVAILABLE:
                self.node.destroy_node()
                
            if ROS2_AVAILABLE and rclpy.ok():
                rclpy.shutdown()
                
            self.is_initialized = False
            self.logger.info("ROS2Publisher shutdown complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            return False
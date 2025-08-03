"""
ROS2 Bridge Node for Webots Simulation

This creates actual ROS2 nodes that publish and subscribe to standard ROS2 topics,
making the Webots simulation appear as real ROS2 robots to our core components.

The core components (Tasks 1-6) remain completely unchanged and use standard ROS2.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import json

# ROS2 imports (will be mocked if not available)
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import MultiThreadedExecutor
    from std_msgs.msg import String, Float32, Bool
    from geometry_msgs.msg import Twist, PoseStamped, Pose, Point, Quaternion
    from sensor_msgs.msg import BatteryState
    from nav_msgs.msg import Odometry
    ROS2_AVAILABLE = True
except ImportError:
    # Mock ROS2 for testing without ROS2 installation
    ROS2_AVAILABLE = False
    
    class Node:
        def __init__(self, name): 
            self.name = name
            self.logger = logging.getLogger(name)
        def get_logger(self): 
            return self.logger
        def create_publisher(self, msg_type, topic, qos): 
            return MockPublisher()
        def create_subscription(self, msg_type, topic, callback, qos): 
            return MockSubscription()
        def create_timer(self, period, callback): 
            return MockTimer()
    
    class MockPublisher:
        def publish(self, msg): pass
    
    class MockSubscription:
        pass
    
    class MockTimer:
        pass
    
    # Mock message types
    class String:
        def __init__(self): self.data = ""
    class Float32:
        def __init__(self): self.data = 0.0
    class Bool:
        def __init__(self): self.data = False
    class Twist:
        def __init__(self): 
            self.linear = type('', (), {'x': 0.0, 'y': 0.0, 'z': 0.0})()
            self.angular = type('', (), {'x': 0.0, 'y': 0.0, 'z': 0.0})()
    class Point:
        def __init__(self): self.x = self.y = self.z = 0.0
    class Quaternion:
        def __init__(self): self.x = self.y = self.z = 0.0; self.w = 1.0
    class Pose:
        def __init__(self): self.position = Point(); self.orientation = Quaternion()
    class PoseStamped:
        def __init__(self): self.pose = Pose()
    class BatteryState:
        def __init__(self): self.percentage = 1.0; self.voltage = 12.0
    class Odometry:
        def __init__(self): self.pose = type('', (), {'pose': Pose()})()

logger = logging.getLogger(__name__)


@dataclass
class RobotTopics:
    """Standard ROS2 topics for a robot."""
    cmd_vel: str
    odom: str
    battery: str
    status: str
    goal: str
    
    @classmethod
    def for_robot(cls, robot_id: str):
        """Create topic names for a specific robot."""
        return cls(
            cmd_vel=f"/{robot_id}/cmd_vel",
            odom=f"/{robot_id}/odom", 
            battery=f"/{robot_id}/battery_state",
            status=f"/{robot_id}/status",
            goal=f"/{robot_id}/move_base_simple/goal"
        )


class RobotBridgeNode(Node):
    """ROS2 node that bridges a single robot between ROS2 and Webots."""
    
    def __init__(self, robot_id: str, webots_interface, update_callback: Optional[Callable] = None):
        super().__init__(f'robot_bridge_{robot_id}')
        
        self.robot_id = robot_id
        self.webots_interface = webots_interface
        self.update_callback = update_callback
        
        # Robot state
        self.current_pose = Pose()
        self.current_twist = Twist()
        self.battery_level = 100.0
        self.robot_status = "idle"
        
        # Create topics
        self.topics = RobotTopics.for_robot(robot_id)
        
        # Create ROS2 publishers (what we send to ROS2 system)
        self.odom_pub = self.create_publisher(Odometry, self.topics.odom, 10)
        self.battery_pub = self.create_publisher(BatteryState, self.topics.battery, 10)
        self.status_pub = self.create_publisher(String, self.topics.status, 10)
        
        # Create ROS2 subscribers (what we receive from ROS2 system)
        self.cmd_vel_sub = self.create_subscription(
            Twist, self.topics.cmd_vel, self._cmd_vel_callback, 10)
        self.goal_sub = self.create_subscription(
            PoseStamped, self.topics.goal, self._goal_callback, 10)
        
        # Create timer for publishing robot state
        self.state_timer = self.create_timer(0.1, self._publish_state)  # 10Hz
        
        self.get_logger().info(f'Robot bridge node started for {robot_id}')
    
    def _cmd_vel_callback(self, msg: Twist):
        """Handle velocity commands from ROS2 system."""
        try:
            self.current_twist = msg
            
            # Convert ROS2 Twist to Webots movement
            # For simplicity, we'll convert linear velocity to target position
            if abs(msg.linear.x) > 0.01 or abs(msg.linear.y) > 0.01:
                # Get current position from Webots
                current_state = asyncio.run_coroutine_threadsafe(
                    self.webots_interface.get_robot_state(self.robot_id),
                    asyncio.get_event_loop()
                ).result()
                
                if current_state:
                    current_pos = current_state['position']
                    # Move in direction of velocity command
                    target_x = current_pos[0] + msg.linear.x * 0.5  # Scale factor
                    target_y = current_pos[1] + msg.linear.y * 0.5
                    
                    # Send movement command to Webots
                    asyncio.run_coroutine_threadsafe(
                        self.webots_interface.move_robot(self.robot_id, target_x, target_y),
                        asyncio.get_event_loop()
                    )
                    
                    self.robot_status = "moving"
            else:
                # Stop command
                asyncio.run_coroutine_threadsafe(
                    self.webots_interface.stop_robot(self.robot_id),
                    asyncio.get_event_loop()
                )
                self.robot_status = "idle"
                
            self.get_logger().debug(f'Received cmd_vel: linear=({msg.linear.x}, {msg.linear.y})')
            
        except Exception as e:
            self.get_logger().error(f'cmd_vel callback failed: {e}')
    
    def _goal_callback(self, msg: PoseStamped):
        """Handle navigation goals from ROS2 system."""
        try:
            goal_pose = msg.pose
            target_x = goal_pose.position.x
            target_y = goal_pose.position.y
            
            # Send navigation goal to Webots
            asyncio.run_coroutine_threadsafe(
                self.webots_interface.move_robot(self.robot_id, target_x, target_y),
                asyncio.get_event_loop()
            )
            
            self.robot_status = "navigating"
            
            self.get_logger().info(f'Received navigation goal: ({target_x}, {target_y})')
            
        except Exception as e:
            self.get_logger().error(f'goal callback failed: {e}')
    
    def _publish_state(self):
        """Publish robot state to ROS2 topics."""
        try:
            # Get current state from Webots
            current_state = asyncio.run_coroutine_threadsafe(
                self.webots_interface.get_robot_state(self.robot_id),
                asyncio.get_event_loop()
            ).result()
            
            if not current_state:
                return
            
            # Update pose from Webots state
            webots_pos = current_state['position']
            self.current_pose.position.x = float(webots_pos[0])
            self.current_pose.position.y = float(webots_pos[1])
            self.current_pose.position.z = float(webots_pos[2])
            
            # Update status
            self.robot_status = current_state.get('status', 'idle')
            
            # Publish odometry
            odom_msg = Odometry()
            odom_msg.pose.pose = self.current_pose
            odom_msg.twist.twist = self.current_twist
            self.odom_pub.publish(odom_msg)
            
            # Publish battery state
            battery_msg = BatteryState()
            battery_msg.percentage = self.battery_level / 100.0
            battery_msg.voltage = 12.0  # Simulated
            self.battery_pub.publish(battery_msg)
            
            # Publish status
            status_msg = String()
            status_msg.data = self.robot_status
            self.status_pub.publish(status_msg)
            
            # Trigger update callback if provided
            if self.update_callback:
                self.update_callback(self.robot_id, current_state)
                
        except Exception as e:
            self.get_logger().error(f'State publishing failed: {e}')


class FleetBridgeNode(Node):
    """ROS2 node that manages fleet-level operations."""
    
    def __init__(self, webots_interface):
        super().__init__('fleet_bridge')
        
        self.webots_interface = webots_interface
        
        # Fleet-level publishers
        self.fleet_status_pub = self.create_publisher(String, '/fleet/status', 10)
        self.fleet_command_pub = self.create_publisher(String, '/fleet/command_result', 10)
        
        # Fleet-level subscribers
        self.fleet_cmd_sub = self.create_subscription(
            String, '/fleet/command', self._fleet_command_callback, 10)
        self.emergency_stop_sub = self.create_subscription(
            Bool, '/fleet/emergency_stop', self._emergency_stop_callback, 10)
        
        # Timer for fleet status
        self.status_timer = self.create_timer(1.0, self._publish_fleet_status)  # 1Hz
        
        self.get_logger().info('Fleet bridge node started')
    
    def _fleet_command_callback(self, msg: String):
        """Handle fleet-level commands."""
        try:
            command_data = json.loads(msg.data)
            command_type = command_data.get('type')
            
            if command_type == 'formation':
                # Handle formation commands
                formation_type = command_data.get('formation', 'circle')
                params = command_data.get('params', {})
                
                result = asyncio.run_coroutine_threadsafe(
                    self.webots_interface.create_formation(formation_type, **params),
                    asyncio.get_event_loop()
                ).result()
                
                # Publish result
                result_msg = String()
                result_msg.data = json.dumps(result)
                self.fleet_command_pub.publish(result_msg)
                
            elif command_type == 'move_all':
                # Handle move all robots command
                target_x = command_data.get('x', 0.0)
                target_y = command_data.get('y', 0.0)
                
                result = asyncio.run_coroutine_threadsafe(
                    self.webots_interface.move_all_robots(target_x, target_y),
                    asyncio.get_event_loop()
                ).result()
                
                # Publish result
                result_msg = String()
                result_msg.data = json.dumps(result)
                self.fleet_command_pub.publish(result_msg)
                
            self.get_logger().info(f'Executed fleet command: {command_type}')
            
        except Exception as e:
            self.get_logger().error(f'Fleet command failed: {e}')
    
    def _emergency_stop_callback(self, msg: Bool):
        """Handle emergency stop commands."""
        try:
            if msg.data:
                # Emergency stop all robots
                asyncio.run_coroutine_threadsafe(
                    self.webots_interface.stop_all_robots(),
                    asyncio.get_event_loop()
                )
                
                self.get_logger().warning('Emergency stop activated!')
            
        except Exception as e:
            self.get_logger().error(f'Emergency stop failed: {e}')
    
    def _publish_fleet_status(self):
        """Publish fleet status."""
        try:
            # Get fleet status from Webots
            status = asyncio.run_coroutine_threadsafe(
                self.webots_interface.get_simulation_status(),
                asyncio.get_event_loop()
            ).result()
            
            # Publish status
            status_msg = String()
            status_msg.data = json.dumps(status)
            self.fleet_status_pub.publish(status_msg)
            
        except Exception as e:
            self.get_logger().error(f'Fleet status publishing failed: {e}')


class ROS2BridgeManager:
    """Manages all ROS2 bridge nodes for the simulation."""
    
    def __init__(self, webots_interface):
        self.webots_interface = webots_interface
        self.robot_nodes = {}
        self.fleet_node = None
        self.executor = None
        self.executor_thread = None
        self.running = False
        
        logger.info("ROS2 Bridge Manager initialized")
    
    async def initialize(self):
        """Initialize the ROS2 bridge."""
        logger.info("Initializing ROS2 Bridge...")
        
        try:
            if not ROS2_AVAILABLE:
                logger.warning("ROS2 not available, using mock implementation")
            else:
                # Initialize ROS2
                rclpy.init()
            
            # Create executor for running nodes
            if ROS2_AVAILABLE:
                self.executor = MultiThreadedExecutor()
            
            # Get available robots from Webots
            robots = await self.webots_interface.get_available_robots()
            
            # Create bridge node for each robot
            for robot_id in robots.keys():
                await self._create_robot_bridge(robot_id)
            
            # Create fleet bridge node
            self.fleet_node = FleetBridgeNode(self.webots_interface)
            if self.executor:
                self.executor.add_node(self.fleet_node)
            
            # Start executor in separate thread
            if self.executor:
                self.executor_thread = threading.Thread(target=self._run_executor)
                self.executor_thread.daemon = True
                self.executor_thread.start()
            
            self.running = True
            logger.info(f"ROS2 Bridge ready with {len(self.robot_nodes)} robot bridges")
            
        except Exception as e:
            logger.error(f"ROS2 Bridge initialization failed: {e}")
            raise
    
    async def _create_robot_bridge(self, robot_id: str):
        """Create ROS2 bridge for a specific robot."""
        try:
            # Create robot bridge node
            robot_node = RobotBridgeNode(
                robot_id, 
                self.webots_interface,
                self._robot_update_callback
            )
            
            self.robot_nodes[robot_id] = robot_node
            
            # Add to executor
            if self.executor:
                self.executor.add_node(robot_node)
            
            logger.info(f"Created ROS2 bridge for robot {robot_id}")
            
        except Exception as e:
            logger.error(f"Failed to create robot bridge for {robot_id}: {e}")
    
    def _robot_update_callback(self, robot_id: str, state: Dict[str, Any]):
        """Callback for robot state updates."""
        # This can be used to trigger additional processing
        pass
    
    def _run_executor(self):
        """Run the ROS2 executor in a separate thread."""
        try:
            if self.executor:
                self.executor.spin()
        except Exception as e:
            logger.error(f"ROS2 executor failed: {e}")
    
    def get_robot_topics(self, robot_id: str) -> Optional[RobotTopics]:
        """Get ROS2 topics for a specific robot."""
        if robot_id in self.robot_nodes:
            return self.robot_nodes[robot_id].topics
        return None
    
    def get_all_robot_topics(self) -> Dict[str, RobotTopics]:
        """Get ROS2 topics for all robots."""
        return {
            robot_id: node.topics 
            for robot_id, node in self.robot_nodes.items()
        }
    
    def get_fleet_topics(self) -> Dict[str, str]:
        """Get fleet-level ROS2 topics."""
        return {
            'fleet_command': '/fleet/command',
            'fleet_status': '/fleet/status',
            'fleet_command_result': '/fleet/command_result',
            'emergency_stop': '/fleet/emergency_stop'
        }
    
    async def shutdown(self):
        """Shutdown the ROS2 bridge."""
        logger.info("Shutting down ROS2 Bridge...")
        
        self.running = False
        
        try:
            # Shutdown executor
            if self.executor:
                self.executor.shutdown()
            
            # Wait for executor thread
            if self.executor_thread and self.executor_thread.is_alive():
                self.executor_thread.join(timeout=5.0)
            
            # Destroy nodes
            for robot_node in self.robot_nodes.values():
                if hasattr(robot_node, 'destroy_node'):
                    robot_node.destroy_node()
            
            if self.fleet_node and hasattr(self.fleet_node, 'destroy_node'):
                self.fleet_node.destroy_node()
            
            # Shutdown ROS2
            if ROS2_AVAILABLE:
                rclpy.shutdown()
            
            logger.info("ROS2 Bridge shutdown complete")
            
        except Exception as e:
            logger.error(f"ROS2 Bridge shutdown error: {e}")
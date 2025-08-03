"""
Robot Registry and Monitoring System.

Manages robot registration, health monitoring, and capability discovery
for the ChatGPT for Robots fleet control system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import threading
import time

from core.data_models import RobotState, RobotStatus
from core.base_component import BaseComponent


class RobotCapability(str, Enum):
    """Robot capability types."""
    NAVIGATION = "navigation"
    MANIPULATION = "manipulation"
    INSPECTION = "inspection"
    LIFTING = "lifting"
    SENSING = "sensing"


@dataclass
class RobotInfo:
    """Extended robot information including capabilities and health."""
    robot_id: str
    state: RobotState
    capabilities: Set[RobotCapability] = field(default_factory=set)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    registration_time: datetime = field(default_factory=datetime.now)
    heartbeat_interval: float = 5.0  # seconds
    is_healthy: bool = True
    consecutive_missed_heartbeats: int = 0
    max_missed_heartbeats: int = 3
    
    def update_heartbeat(self) -> None:
        """Update the last heartbeat timestamp."""
        self.last_heartbeat = datetime.now()
        self.consecutive_missed_heartbeats = 0
        self.is_healthy = True
    
    def check_health(self) -> bool:
        """Check if robot is healthy based on heartbeat."""
        time_since_heartbeat = datetime.now() - self.last_heartbeat
        expected_interval = timedelta(seconds=self.heartbeat_interval * 2)  # Allow 2x interval
        
        if time_since_heartbeat > expected_interval:
            self.consecutive_missed_heartbeats += 1
            if self.consecutive_missed_heartbeats >= self.max_missed_heartbeats:
                self.is_healthy = False
                return False
        
        return self.is_healthy
    
    def is_available_for_task(self) -> bool:
        """Check if robot is available for new tasks."""
        return (self.is_healthy and 
                self.state.is_available() and 
                self.state.status == RobotStatus.IDLE)


class RobotRegistry(BaseComponent):
    """
    Registry for managing robot fleet with health monitoring and capability discovery.
    
    Handles robot registration, heartbeat monitoring, capability tracking,
    and provides fleet status information.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the robot registry."""
        super().__init__("robot_registry", config or {})
        self._robots: Dict[str, RobotInfo] = {}
        self._lock = threading.RLock()
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._heartbeat_timeout = self.config.get('heartbeat_timeout', 10.0)
        self._health_check_interval = self.config.get('health_check_interval', 2.0)
    
    async def initialize(self) -> bool:
        """Initialize the robot registry."""
        try:
            self.logger.info("Initializing robot registry")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize robot registry: {e}")
            return False
        
    async def start(self) -> bool:
        """Start the robot registry and health monitoring."""
        try:
            self._start_health_monitoring()
            self.logger.info("Robot registry started with health monitoring")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start robot registry: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the robot registry and health monitoring."""
        try:
            self._stop_health_monitoring()
            self.logger.info("Robot registry stopped")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop robot registry: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the robot registry."""
        try:
            with self._lock:
                total_robots = len(self._robots)
                healthy_robots = len(self.get_healthy_robots())
                
                return {
                    'component': 'robot_registry',
                    'status': 'healthy' if self._monitoring_active else 'unhealthy',
                    'monitoring_active': self._monitoring_active,
                    'total_robots': total_robots,
                    'healthy_robots': healthy_robots,
                    'unhealthy_robots': total_robots - healthy_robots,
                    'timestamp': datetime.now()
                }
        except Exception as e:
            return {
                'component': 'robot_registry',
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def register_robot(self, robot_id: str, initial_state: RobotState, 
                      capabilities: Optional[Set[RobotCapability]] = None) -> bool:
        """
        Register a new robot with the fleet.
        
        Args:
            robot_id: Unique identifier for the robot
            initial_state: Initial state of the robot
            capabilities: Set of robot capabilities
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            with self._lock:
                if robot_id in self._robots:
                    self.logger.warning(f"Robot {robot_id} already registered, updating info")
                
                robot_info = RobotInfo(
                    robot_id=robot_id,
                    state=initial_state,
                    capabilities=capabilities or set(),
                    heartbeat_interval=self._heartbeat_timeout / 2
                )
                
                self._robots[robot_id] = robot_info
                self.logger.info(f"Robot {robot_id} registered with capabilities: {capabilities}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to register robot {robot_id}: {e}")
            return False
    
    def unregister_robot(self, robot_id: str) -> bool:
        """
        Unregister a robot from the fleet.
        
        Args:
            robot_id: ID of robot to unregister
            
        Returns:
            True if unregistration successful, False otherwise
        """
        try:
            with self._lock:
                if robot_id not in self._robots:
                    self.logger.warning(f"Robot {robot_id} not found for unregistration")
                    return False
                
                del self._robots[robot_id]
                self.logger.info(f"Robot {robot_id} unregistered")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to unregister robot {robot_id}: {e}")
            return False
    
    def update_robot_state(self, robot_id: str, state: RobotState) -> bool:
        """
        Update the state of a registered robot.
        
        Args:
            robot_id: ID of robot to update
            state: New robot state
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            with self._lock:
                if robot_id not in self._robots:
                    self.logger.warning(f"Robot {robot_id} not registered, cannot update state")
                    return False
                
                self._robots[robot_id].state = state
                self._robots[robot_id].update_heartbeat()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update robot {robot_id} state: {e}")
            return False
    
    def heartbeat(self, robot_id: str) -> bool:
        """
        Record a heartbeat from a robot.
        
        Args:
            robot_id: ID of robot sending heartbeat
            
        Returns:
            True if heartbeat recorded, False otherwise
        """
        try:
            with self._lock:
                if robot_id not in self._robots:
                    self.logger.warning(f"Heartbeat from unregistered robot {robot_id}")
                    return False
                
                self._robots[robot_id].update_heartbeat()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to record heartbeat for robot {robot_id}: {e}")
            return False
    
    def get_robot_info(self, robot_id: str) -> Optional[RobotInfo]:
        """
        Get information about a specific robot.
        
        Args:
            robot_id: ID of robot to query
            
        Returns:
            RobotInfo if found, None otherwise
        """
        with self._lock:
            return self._robots.get(robot_id)
    
    def get_all_robots(self) -> Dict[str, RobotInfo]:
        """
        Get information about all registered robots.
        
        Returns:
            Dictionary mapping robot IDs to RobotInfo
        """
        with self._lock:
            return self._robots.copy()
    
    def get_available_robots(self) -> List[str]:
        """
        Get list of robots available for new tasks.
        
        Returns:
            List of robot IDs that are available
        """
        with self._lock:
            return [robot_id for robot_id, info in self._robots.items() 
                   if info.is_available_for_task()]
    
    def get_robots_by_capability(self, capability: RobotCapability) -> List[str]:
        """
        Get robots that have a specific capability.
        
        Args:
            capability: Required capability
            
        Returns:
            List of robot IDs with the capability
        """
        with self._lock:
            return [robot_id for robot_id, info in self._robots.items()
                   if capability in info.capabilities and info.is_healthy]
    
    def get_healthy_robots(self) -> List[str]:
        """
        Get list of healthy robots.
        
        Returns:
            List of robot IDs that are healthy
        """
        with self._lock:
            return [robot_id for robot_id, info in self._robots.items() 
                   if info.is_healthy]
    
    def get_fleet_status(self) -> Dict[str, Any]:
        """
        Get overall fleet status summary.
        
        Returns:
            Dictionary with fleet statistics
        """
        with self._lock:
            total_robots = len(self._robots)
            healthy_robots = len(self.get_healthy_robots())
            available_robots = len(self.get_available_robots())
            
            status_counts = {}
            for info in self._robots.values():
                status = info.state.status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            capability_counts = {}
            for info in self._robots.values():
                for cap in info.capabilities:
                    capability_counts[cap] = capability_counts.get(cap, 0) + 1
            
            return {
                'total_robots': total_robots,
                'healthy_robots': healthy_robots,
                'available_robots': available_robots,
                'unhealthy_robots': total_robots - healthy_robots,
                'status_distribution': status_counts,
                'capability_distribution': capability_counts,
                'timestamp': datetime.now()
            }
    
    def discover_robot_capabilities(self, robot_id: str) -> Set[RobotCapability]:
        """
        Discover capabilities of a robot (placeholder for actual discovery logic).
        
        Args:
            robot_id: ID of robot to discover capabilities for
            
        Returns:
            Set of discovered capabilities
        """
        # In a real implementation, this would query the robot's ROS2 interfaces
        # to discover available services, topics, and actions
        
        # For now, return a default set based on robot type
        if robot_id.startswith('tiago'):
            return {RobotCapability.NAVIGATION, RobotCapability.MANIPULATION, 
                   RobotCapability.INSPECTION, RobotCapability.SENSING}
        elif robot_id.startswith('mobile'):
            return {RobotCapability.NAVIGATION, RobotCapability.SENSING}
        else:
            return {RobotCapability.NAVIGATION}
    
    def _start_health_monitoring(self) -> None:
        """Start the health monitoring thread."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def _stop_health_monitoring(self) -> None:
        """Stop the health monitoring thread."""
        self._monitoring_active = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
    
    def _health_monitor_loop(self) -> None:
        """Main health monitoring loop."""
        while self._monitoring_active:
            try:
                self._check_robot_health()
                time.sleep(self._health_check_interval)
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(1.0)  # Brief pause before retrying
    
    def _check_robot_health(self) -> None:
        """Check health of all registered robots."""
        with self._lock:
            unhealthy_robots = []
            for robot_id, info in self._robots.items():
                if not info.check_health():
                    unhealthy_robots.append(robot_id)
            
            if unhealthy_robots:
                self.logger.warning(f"Unhealthy robots detected: {unhealthy_robots}")
    
    async def shutdown(self) -> None:
        """Shutdown the robot registry and clean up resources."""
        try:
            self.logger.info("Shutting down Robot Registry...")
            
            # Stop health monitoring
            self._stop_health_monitoring()
            
            # Clear robot registry
            with self._lock:
                self._robots.clear()
            
            self.logger.info("Robot Registry shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during Robot Registry shutdown: {e}")
            raise
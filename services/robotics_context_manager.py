"""
Robotics Context Manager

Aggregates real-time system context for context-aware command translation.
Collects robot states, environment data, and world information to provide
rich contextual information to the LLM for accurate command generation.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

from core.data_models import RobotState, RobotStatus
from task_orchestrator.robot_registry import RobotRegistry


logger = logging.getLogger(__name__)


class ContextType(str, Enum):
    """Types of context information."""
    ROBOT_STATES = "robot_states"
    ENVIRONMENT = "environment"
    WORLD = "world"
    CAPABILITIES = "capabilities"


@dataclass
class RobotContextInfo:
    """Contextual information about a single robot."""
    robot_id: str
    position: Tuple[float, float, float]
    orientation: Tuple[float, float, float, float]
    status: str
    battery_level: float
    capabilities: List[str]
    is_available: bool
    last_command: Optional[str] = None
    
    def to_context_string(self) -> str:
        """Convert to human-readable context string for LLM."""
        return (f"Robot {self.robot_id}: "
                f"Position({self.position[0]:.1f}, {self.position[1]:.1f}, {self.position[2]:.1f}), "
                f"Status={self.status}, Battery={self.battery_level:.0f}%, "
                f"Available={'Yes' if self.is_available else 'No'}")


@dataclass
class EnvironmentContext:
    """Environmental context information."""
    boundaries: Dict[str, float]  # min_x, max_x, min_y, max_y, min_z, max_z
    obstacles: List[Dict[str, Any]]
    reference_points: Dict[str, Tuple[float, float, float]]
    dynamic_objects: List[Dict[str, Any]]
    
    def to_context_string(self) -> str:
        """Convert to human-readable context string for LLM."""
        bounds = self.boundaries
        context = f"Environment: Boundaries(x: {bounds.get('min_x', -10):.1f} to {bounds.get('max_x', 10):.1f}, "
        context += f"y: {bounds.get('min_y', -10):.1f} to {bounds.get('max_y', 10):.1f})"
        
        if self.reference_points:
            context += f", Reference points: {list(self.reference_points.keys())}"
        
        if self.obstacles:
            context += f", Obstacles: {len(self.obstacles)} detected"
            
        return context


@dataclass
class WorldContext:
    """World/simulation context information."""
    world_type: str  # "webots", "gazebo", "real_world"
    simulation_time: float
    gravity: Tuple[float, float, float]
    physics_enabled: bool
    time_step: float
    
    def to_context_string(self) -> str:
        """Convert to human-readable context string for LLM."""
        return (f"World: {self.world_type}, "
                f"Physics={'Enabled' if self.physics_enabled else 'Disabled'}, "
                f"Time={self.simulation_time:.1f}s")


@dataclass
class SystemContext:
    """Complete system context for command translation."""
    robots: Dict[str, RobotContextInfo]
    environment: EnvironmentContext
    world: WorldContext
    timestamp: datetime
    context_version: str
    
    def get_available_robots(self) -> List[str]:
        """Get list of available robot IDs."""
        return [robot_id for robot_id, robot in self.robots.items() 
                if robot.is_available]
    
    def get_robot_positions(self) -> Dict[str, Tuple[float, float, float]]:
        """Get current positions of all robots."""
        return {robot_id: robot.position for robot_id, robot in self.robots.items()}
    
    def to_llm_context_string(self) -> str:
        """Convert complete context to LLM-friendly string."""
        context_parts = []
        
        # World context
        context_parts.append("=== CURRENT SYSTEM STATE ===")
        context_parts.append(self.world.to_context_string())
        context_parts.append("")
        
        # Environment context
        context_parts.append("=== ENVIRONMENT ===")
        context_parts.append(self.environment.to_context_string())
        context_parts.append("")
        
        # Robot states
        context_parts.append("=== ROBOT FLEET STATUS ===")
        context_parts.append(f"Total robots: {len(self.robots)}")
        context_parts.append(f"Available robots: {len(self.get_available_robots())}")
        context_parts.append("")
        
        for robot_id, robot in self.robots.items():
            context_parts.append(robot.to_context_string())
        
        context_parts.append("")
        context_parts.append("=== COMMAND GUIDELINES ===")
        context_parts.append("- Use exact robot positions shown above")
        context_parts.append("- Only command available robots")
        context_parts.append("- Stay within environment boundaries")
        context_parts.append("- Use numeric coordinates only (no expressions)")
        
        return "\n".join(context_parts)


class RoboticsContextManager:
    """
    Manages and aggregates real-time robotics system context.
    
    Collects information from various system components to provide
    comprehensive situational awareness for context-aware command translation.
    """
    
    def __init__(self, robot_registry: Optional[RobotRegistry] = None):
        self.robot_registry = robot_registry
        self.simulation_bridge = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Context cache
        self._cached_context: Optional[SystemContext] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 1.0  # Cache for 1 second
        
        # Real-time update tracking
        self._update_callbacks: List[callable] = []
        self._auto_update_enabled = True
        self._update_task: Optional[asyncio.Task] = None
        self._update_interval = 0.5  # Update every 500ms
        
        # Default context values
        self._default_environment = EnvironmentContext(
            boundaries={"min_x": -10.0, "max_x": 10.0, "min_y": -10.0, "max_y": 10.0, "min_z": 0.0, "max_z": 5.0},
            obstacles=[],
            reference_points={"center": (0.0, 0.0, 0.0), "origin": (0.0, 0.0, 0.0)},
            dynamic_objects=[]
        )
        
        self._default_world = WorldContext(
            world_type="webots",
            simulation_time=0.0,
            gravity=(0.0, 0.0, -9.81),
            physics_enabled=True,
            time_step=0.016
        )
        
        self.logger.info("RoboticsContextManager initialized")
    
    def set_robot_registry(self, robot_registry: RobotRegistry) -> None:
        """Set the robot registry for context gathering."""
        self.robot_registry = robot_registry
        self.logger.info("Robot registry connected to context manager")
    
    def set_environment_interface(self, env_interface) -> None:
        """Set the environment interface for context gathering."""
        self.environment_interface = env_interface
        self.logger.info("Environment interface connected to context manager")
    
    def set_world_interface(self, world_interface) -> None:
        """Set the world interface for context gathering."""
        self.world_interface = world_interface
        self.logger.info("World interface connected to context manager")
    
    def get_system_context(self, force_refresh: bool = False) -> SystemContext:
        """
        Get complete system context for command translation.
        
        Args:
            force_refresh: Force refresh of cached context
            
        Returns:
            Complete system context
        """
        # Check cache validity
        if not force_refresh and self._is_cache_valid():
            self.logger.debug("Returning cached context")
            return self._cached_context
        
        start_time = time.time()
        
        try:
            # Gather context from all sources
            robots_context = self._gather_robot_context()
            environment_context = self._gather_environment_context()
            world_context = self._gather_world_context()
            
            # Create complete context
            context = SystemContext(
                robots=robots_context,
                environment=environment_context,
                world=world_context,
                timestamp=datetime.now(),
                context_version="1.0"
            )
            
            # Update cache
            self._cached_context = context
            self._cache_timestamp = datetime.now()
            
            elapsed_time = time.time() - start_time
            self.logger.debug(f"Context gathered in {elapsed_time:.3f}s - "
                            f"{len(robots_context)} robots, "
                            f"{len(environment_context.obstacles)} obstacles")
            
            return context
            
        except Exception as e:
            self.logger.error(f"Failed to gather system context: {e}")
            # Return minimal context to prevent system failure
            return self._get_minimal_context()
    
    def _gather_robot_context(self) -> Dict[str, RobotContextInfo]:
        """Gather context information about all robots."""
        robots_context = {}
        
        if not self.robot_registry:
            self.logger.warning("No robot registry available for context")
            return robots_context
        
        try:
            # Get all registered robots
            robot_infos = self.robot_registry.get_all_robots()
            
            for robot_id, robot_info in robot_infos.items():
                robot_state = robot_info.state
                robots_context[robot_id] = RobotContextInfo(
                    robot_id=robot_id,
                    position=robot_state.position,
                    orientation=robot_state.orientation,
                    status=robot_state.status,
                    battery_level=robot_state.battery_level,
                    capabilities=["navigate", "formation"],  # Default capabilities
                    is_available=(robot_state.status == RobotStatus.IDLE and robot_state.battery_level > 10.0),
                    last_command=robot_state.current_task
                )
                
        except Exception as e:
            self.logger.error(f"Failed to gather robot context: {e}")
        
        return robots_context
    
    def _gather_environment_context(self) -> EnvironmentContext:
        """Gather environmental context information."""
        try:
            # TODO: Integrate with actual environment interface when available
            # For now, return default environment context
            return self._default_environment
            
        except Exception as e:
            self.logger.error(f"Failed to gather environment context: {e}")
            return self._default_environment
    
    def _gather_world_context(self) -> WorldContext:
        """Gather world/simulation context information."""
        try:
            # TODO: Integrate with actual world interface when available
            # For now, return default world context with current time
            world_context = WorldContext(
                world_type="webots",
                simulation_time=time.time(),
                gravity=(0.0, 0.0, -9.81),
                physics_enabled=True,
                time_step=0.016
            )
            return world_context
            
        except Exception as e:
            self.logger.error(f"Failed to gather world context: {e}")
            return self._default_world
    
    def _is_cache_valid(self) -> bool:
        """Check if cached context is still valid."""
        if not self._cached_context or not self._cache_timestamp:
            return False
        
        age = (datetime.now() - self._cache_timestamp).total_seconds()
        return age < self._cache_ttl_seconds
    
    def _get_minimal_context(self) -> SystemContext:
        """Get minimal context for fallback scenarios."""
        return SystemContext(
            robots={},
            environment=self._default_environment,
            world=self._default_world,
            timestamp=datetime.now(),
            context_version="1.0-minimal"
        )
    
    def invalidate_cache(self) -> None:
        """Invalidate the context cache to force refresh."""
        self._cached_context = None
        self._cache_timestamp = None
        self.logger.debug("Context cache invalidated")
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of current context for debugging."""
        context = self.get_system_context()
        
        return {
            "timestamp": context.timestamp.isoformat(),
            "robot_count": len(context.robots),
            "available_robots": len(context.get_available_robots()),
            "world_type": context.world.world_type,
            "environment_boundaries": context.environment.boundaries,
            "cache_age_seconds": (datetime.now() - self._cache_timestamp).total_seconds() if self._cache_timestamp else None
        }  
  # Real-time integration methods
    
    def connect_robot_registry(self, robot_registry) -> None:
        """Connect to robot registry for live robot state updates."""
        self.robot_registry = robot_registry
        self.logger.info("Connected to robot registry for real-time updates")
        
        # Invalidate cache when registry changes
        self.invalidate_cache()
    
    def connect_simulation_bridge(self, simulation_bridge) -> None:
        """Connect to simulation bridge for real-time environment data."""
        self.simulation_bridge = simulation_bridge
        self.logger.info("Connected to simulation bridge for real-time updates")
        
        # Invalidate cache when bridge changes
        self.invalidate_cache()
    
    def add_update_callback(self, callback: callable) -> None:
        """Add callback to be called when context updates."""
        self._update_callbacks.append(callback)
        self.logger.debug(f"Added context update callback: {callback.__name__}")
    
    def remove_update_callback(self, callback: callable) -> None:
        """Remove context update callback."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)
            self.logger.debug(f"Removed context update callback: {callback.__name__}")
    
    async def start_auto_updates(self) -> None:
        """Start automatic context updates."""
        if self._update_task and not self._update_task.done():
            self.logger.warning("Auto-updates already running")
            return
        
        self._auto_update_enabled = True
        self._update_task = asyncio.create_task(self._update_loop())
        self.logger.info(f"Started auto-updates with {self._update_interval}s interval")
    
    async def stop_auto_updates(self) -> None:
        """Stop automatic context updates."""
        self._auto_update_enabled = False
        
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped auto-updates")
    
    async def _update_loop(self) -> None:
        """Main update loop for real-time context updates."""
        self.logger.debug("Starting context update loop")
        
        while self._auto_update_enabled:
            try:
                # Check for context changes
                old_context = self._cached_context
                new_context = self.get_system_context(force_refresh=True)
                
                # Trigger callbacks if context changed significantly
                if self._context_changed(old_context, new_context):
                    await self._trigger_update_callbacks(new_context)
                
                await asyncio.sleep(self._update_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in context update loop: {e}")
                await asyncio.sleep(self._update_interval)
        
        self.logger.debug("Context update loop stopped")
    
    def _context_changed(self, old_context: Optional[SystemContext], 
                        new_context: SystemContext) -> bool:
        """Check if context has changed significantly."""
        if not old_context:
            return True
        
        # Check robot count changes
        if len(old_context.robots) != len(new_context.robots):
            return True
        
        # Check robot availability changes
        old_available = set(old_context.get_available_robots())
        new_available = set(new_context.get_available_robots())
        if old_available != new_available:
            return True
        
        # Check robot position changes (threshold-based)
        position_threshold = 0.1  # meters
        for robot_id in old_context.robots:
            if robot_id in new_context.robots:
                old_pos = old_context.robots[robot_id].position
                new_pos = new_context.robots[robot_id].position
                
                # Calculate distance
                distance = ((old_pos[0] - new_pos[0])**2 + 
                           (old_pos[1] - new_pos[1])**2 + 
                           (old_pos[2] - new_pos[2])**2)**0.5
                
                if distance > position_threshold:
                    return True
        
        return False
    
    async def _trigger_update_callbacks(self, context: SystemContext) -> None:
        """Trigger all registered update callbacks."""
        for callback in self._update_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(context)
                else:
                    callback(context)
            except Exception as e:
                self.logger.error(f"Error in update callback {callback.__name__}: {e}")
    
    def get_real_time_robot_states(self) -> Dict[str, RobotState]:
        """Get real-time robot states from registry."""
        if not self.robot_registry:
            return {}
        
        try:
            return self.robot_registry.get_all_robot_states()
        except Exception as e:
            self.logger.error(f"Failed to get real-time robot states: {e}")
            return {}
    
    def get_simulation_environment_data(self) -> Dict[str, Any]:
        """Get real-time environment data from simulation bridge."""
        if not self.simulation_bridge:
            return {}
        
        try:
            # Get environment data from simulation bridge
            if hasattr(self.simulation_bridge, 'get_environment_state'):
                return self.simulation_bridge.get_environment_state()
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Failed to get simulation environment data: {e}")
            return {}
    
    def validate_context_data(self, context: SystemContext) -> List[str]:
        """Validate context data and return list of issues."""
        issues = []
        
        # Check for stale data
        age = (datetime.now() - context.timestamp).total_seconds()
        if age > 10.0:  # 10 seconds threshold
            issues.append(f"Context data is stale ({age:.1f}s old)")
        
        # Check robot data consistency
        for robot_id, robot in context.robots.items():
            if not robot.is_available and robot.status == RobotStatus.IDLE:
                issues.append(f"Robot {robot_id} marked unavailable but status is idle")
            
            if robot.battery_level < 0 or robot.battery_level > 100:
                issues.append(f"Robot {robot_id} has invalid battery level: {robot.battery_level}")
        
        # Check environment boundaries
        bounds = context.environment.boundaries
        if bounds.get('min_x', 0) >= bounds.get('max_x', 0):
            issues.append("Invalid environment boundaries: min_x >= max_x")
        
        if bounds.get('min_y', 0) >= bounds.get('max_y', 0):
            issues.append("Invalid environment boundaries: min_y >= max_y")
        
        return issues
    
    async def handle_context_update_trigger(self, trigger_source: str, data: Dict[str, Any]) -> None:
        """Handle external context update triggers."""
        self.logger.debug(f"Context update triggered by {trigger_source}")
        
        # Invalidate cache to force refresh
        self.invalidate_cache()
        
        # Get fresh context
        fresh_context = self.get_system_context(force_refresh=True)
        
        # Trigger callbacks
        await self._trigger_update_callbacks(fresh_context)
        
        self.logger.debug(f"Context update completed for trigger: {trigger_source}")
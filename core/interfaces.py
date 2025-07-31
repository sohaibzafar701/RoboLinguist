"""
Core interfaces for the ChatGPT for Robots system.

Defines abstract base classes that establish contracts for all major components.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .data_models import RobotCommand, RobotState, Task, PerformanceMetrics


class ICommandTranslator(ABC):
    """Interface for translating natural language to robot commands."""
    
    @abstractmethod
    async def translate_command(self, natural_language: str) -> RobotCommand:
        """Translate natural language input to structured robot command."""
        pass
    
    @abstractmethod
    async def validate_translation(self, command: RobotCommand) -> bool:
        """Validate that the translated command is properly structured."""
        pass


class ISafetyValidator(ABC):
    """Interface for validating command safety."""
    
    @abstractmethod
    async def validate_command(self, command: RobotCommand) -> bool:
        """Validate that a command meets safety requirements."""
        pass
    
    @abstractmethod
    async def emergency_stop(self) -> None:
        """Trigger emergency stop for all robots."""
        pass
    
    @abstractmethod
    async def get_safety_violations(self, command: RobotCommand) -> List[str]:
        """Get list of safety violations for a command."""
        pass


class ITaskManager(ABC):
    """Interface for managing task distribution and execution."""
    
    @abstractmethod
    async def assign_task(self, task: Task) -> bool:
        """Assign a task to an available robot."""
        pass
    
    @abstractmethod
    async def get_task_status(self, task_id: str) -> str:
        """Get the current status of a task."""
        pass
    
    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or pending task."""
        pass
    
    @abstractmethod
    async def get_available_robots(self) -> List[str]:
        """Get list of available robot IDs."""
        pass


class IRobotController(ABC):
    """Interface for controlling individual robots."""
    
    @abstractmethod
    async def send_command(self, robot_id: str, command: RobotCommand) -> bool:
        """Send a command to a specific robot."""
        pass
    
    @abstractmethod
    async def get_robot_state(self, robot_id: str) -> RobotState:
        """Get current state of a robot."""
        pass
    
    @abstractmethod
    async def is_robot_available(self, robot_id: str) -> bool:
        """Check if a robot is available for new tasks."""
        pass


class ISimulationManager(ABC):
    """Interface for managing simulation environment."""
    
    @abstractmethod
    async def start_simulation(self) -> bool:
        """Start the simulation environment."""
        pass
    
    @abstractmethod
    async def stop_simulation(self) -> bool:
        """Stop the simulation environment."""
        pass
    
    @abstractmethod
    async def spawn_robot(self, robot_id: str, position: tuple) -> bool:
        """Spawn a robot in the simulation at specified position."""
        pass
    
    @abstractmethod
    async def get_simulation_state(self) -> Dict[str, Any]:
        """Get current state of the simulation."""
        pass
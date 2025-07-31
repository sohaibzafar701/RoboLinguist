"""
Data models for the ChatGPT for Robots system.

Defines the core data structures used throughout the system with Pydantic validation.
"""

from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class ActionType(str, Enum):
    """Valid action types for robot commands."""
    NAVIGATE = "navigate"
    MANIPULATE = "manipulate"
    INSPECT = "inspect"


class RobotStatus(str, Enum):
    """Valid robot status values."""
    IDLE = "idle"
    MOVING = "moving"
    EXECUTING = "executing"
    ERROR = "error"


class TaskStatus(str, Enum):
    """Valid task status values."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class RobotCommand(BaseModel):
    """Represents a command to be executed by a robot."""
    command_id: str = Field(..., min_length=1, description="Unique identifier for the command")
    robot_id: str = Field(..., min_length=1, description="ID of the target robot")
    action_type: ActionType = Field(..., description="Type of action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")
    priority: int = Field(..., ge=0, le=10, description="Command priority (0-10)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Command creation timestamp")
    safety_validated: bool = Field(default=False, description="Whether command passed safety validation")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v, info):
        """Validate parameters based on action type."""
        action_type = info.data.get('action_type')
        if action_type == ActionType.NAVIGATE:
            required_params = ['target_x', 'target_y']
            for param in required_params:
                if param not in v:
                    raise ValueError(f"Navigate command missing required parameter: {param}")
        elif action_type == ActionType.MANIPULATE:
            required_params = ['object_id', 'action']
            for param in required_params:
                if param not in v:
                    raise ValueError(f"Manipulate command missing required parameter: {param}")
        elif action_type == ActionType.INSPECT:
            required_params = ['target_location']
            for param in required_params:
                if param not in v:
                    raise ValueError(f"Inspect command missing required parameter: {param}")
        return v

    def is_valid(self) -> bool:
        """Check if the command is valid and ready for execution."""
        return self.safety_validated and bool(self.command_id and self.robot_id)


class RobotState(BaseModel):
    """Represents the current state of a robot."""
    robot_id: str = Field(..., min_length=1, description="Unique robot identifier")
    position: Tuple[float, float, float] = Field(..., description="Robot position (x, y, z)")
    orientation: Tuple[float, float, float, float] = Field(..., description="Robot orientation quaternion (x, y, z, w)")
    status: RobotStatus = Field(..., description="Current robot status")
    battery_level: float = Field(..., ge=0.0, le=100.0, description="Battery level percentage")
    current_task: Optional[str] = Field(None, description="ID of currently executing task")
    last_update: datetime = Field(default_factory=datetime.now, description="Last state update timestamp")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator('orientation')
    @classmethod
    def validate_quaternion(cls, v):
        """Validate quaternion normalization."""
        x, y, z, w = v
        magnitude = (x**2 + y**2 + z**2 + w**2) ** 0.5
        if abs(magnitude - 1.0) > 0.01:  # Allow small floating point errors
            raise ValueError(f"Quaternion must be normalized, magnitude: {magnitude}")
        return v

    def is_available(self) -> bool:
        """Check if robot is available for new tasks."""
        return self.status == RobotStatus.IDLE and self.battery_level > 10.0


class Task(BaseModel):
    """Represents a task to be executed by the robot fleet."""
    task_id: str = Field(..., min_length=1, description="Unique task identifier")
    description: str = Field(..., min_length=1, description="Human-readable task description")
    assigned_robot: Optional[str] = Field(None, description="ID of assigned robot")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current task status")
    created_at: datetime = Field(default_factory=datetime.now, description="Task creation timestamp")
    estimated_duration: int = Field(..., gt=0, description="Estimated duration in seconds")
    dependencies: List[str] = Field(default_factory=list, description="List of prerequisite task IDs")

    model_config = ConfigDict(use_enum_values=True)

    def can_start(self, completed_tasks: List[str]) -> bool:
        """Check if task can start based on dependencies."""
        return all(dep in completed_tasks for dep in self.dependencies)

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]


class PerformanceMetrics(BaseModel):
    """Represents system performance metrics."""
    command_accuracy: float = Field(..., ge=0.0, le=1.0, description="Command translation accuracy (0-1)")
    average_response_time: float = Field(..., gt=0.0, description="Average response time in milliseconds")
    task_completion_rate: float = Field(..., ge=0.0, le=1.0, description="Task completion rate (0-1)")
    system_uptime: float = Field(..., ge=0.0, le=100.0, description="System uptime percentage")
    active_robots: int = Field(..., ge=0, description="Number of active robots")
    commands_processed: int = Field(..., ge=0, description="Total commands processed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Metrics collection timestamp")

    model_config = ConfigDict()

    def get_efficiency_score(self) -> float:
        """Calculate overall system efficiency score."""
        return (self.command_accuracy * 0.3 + 
                self.task_completion_rate * 0.4 + 
                (self.system_uptime / 100.0) * 0.3)
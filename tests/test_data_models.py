"""
Unit tests for core data models.

Tests validation, serialization, and business logic for all data model classes.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from pydantic import ValidationError

from core.data_models import (
    RobotCommand, RobotState, Task, PerformanceMetrics,
    ActionType, RobotStatus, TaskStatus
)


class TestRobotCommand:
    """Test cases for RobotCommand model."""

    def test_valid_robot_command_creation(self):
        """Test creating a valid robot command."""
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0},
            priority=5
        )
        
        assert command.command_id == "cmd_001"
        assert command.robot_id == "robot_1"
        assert command.action_type == ActionType.NAVIGATE
        assert command.parameters == {"target_x": 1.0, "target_y": 2.0}
        assert command.priority == 5
        assert not command.safety_validated
        assert isinstance(command.timestamp, datetime)

    def test_navigate_command_validation(self):
        """Test navigation command parameter validation."""
        # Valid navigate command
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0, "target_z": 0.0},
            priority=5
        )
        assert command.action_type == ActionType.NAVIGATE

        # Missing required parameters
        with pytest.raises(ValidationError) as exc_info:
            RobotCommand(
                command_id="cmd_002",
                robot_id="robot_1",
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 1.0},  # Missing target_y
                priority=5
            )
        assert "Navigate command missing required parameter: target_y" in str(exc_info.value)

    def test_manipulate_command_validation(self):
        """Test manipulation command parameter validation."""
        # Valid manipulate command
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.MANIPULATE,
            parameters={"object_id": "box_1", "action": "pick"},
            priority=7
        )
        assert command.action_type == ActionType.MANIPULATE

        # Missing required parameters
        with pytest.raises(ValidationError) as exc_info:
            RobotCommand(
                command_id="cmd_002",
                robot_id="robot_1",
                action_type=ActionType.MANIPULATE,
                parameters={"object_id": "box_1"},  # Missing action
                priority=7
            )
        assert "Manipulate command missing required parameter: action" in str(exc_info.value)

    def test_inspect_command_validation(self):
        """Test inspection command parameter validation."""
        # Valid inspect command
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.INSPECT,
            parameters={"target_location": "shelf_A"},
            priority=3
        )
        assert command.action_type == ActionType.INSPECT

        # Missing required parameters
        with pytest.raises(ValidationError) as exc_info:
            RobotCommand(
                command_id="cmd_002",
                robot_id="robot_1",
                action_type=ActionType.INSPECT,
                parameters={},  # Missing target_location
                priority=3
            )
        assert "Inspect command missing required parameter: target_location" in str(exc_info.value)

    def test_priority_validation(self):
        """Test command priority validation."""
        # Valid priority
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0},
            priority=0
        )
        assert command.priority == 0

        # Invalid priority - too low
        with pytest.raises(ValidationError):
            RobotCommand(
                command_id="cmd_002",
                robot_id="robot_1",
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 1.0, "target_y": 2.0},
                priority=-1
            )

        # Invalid priority - too high
        with pytest.raises(ValidationError):
            RobotCommand(
                command_id="cmd_003",
                robot_id="robot_1",
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 1.0, "target_y": 2.0},
                priority=11
            )

    def test_empty_command_id_validation(self):
        """Test that empty command_id is rejected."""
        with pytest.raises(ValidationError):
            RobotCommand(
                command_id="",
                robot_id="robot_1",
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 1.0, "target_y": 2.0},
                priority=5
            )

    def test_is_valid_method(self):
        """Test the is_valid method."""
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0},
            priority=5
        )
        
        # Initially not valid (not safety validated)
        assert not command.is_valid()
        
        # Valid after safety validation
        command.safety_validated = True
        assert command.is_valid()

    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0},
            priority=5
        )
        
        # Serialize to JSON
        json_data = command.model_dump_json()
        assert isinstance(json_data, str)
        
        # Deserialize from JSON
        command_dict = command.model_dump()
        new_command = RobotCommand(**command_dict)
        assert new_command.command_id == command.command_id
        assert new_command.action_type == command.action_type


class TestRobotState:
    """Test cases for RobotState model."""

    def test_valid_robot_state_creation(self):
        """Test creating a valid robot state."""
        state = RobotState(
            robot_id="robot_1",
            position=(1.0, 2.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.IDLE,
            battery_level=85.5,
            current_task="task_001"
        )
        
        assert state.robot_id == "robot_1"
        assert state.position == (1.0, 2.0, 0.0)
        assert state.orientation == (0.0, 0.0, 0.0, 1.0)
        assert state.status == RobotStatus.IDLE
        assert state.battery_level == 85.5
        assert state.current_task == "task_001"
        assert isinstance(state.last_update, datetime)

    def test_battery_level_validation(self):
        """Test battery level validation."""
        # Valid battery levels
        for level in [0.0, 50.0, 100.0]:
            state = RobotState(
                robot_id="robot_1",
                position=(0.0, 0.0, 0.0),
                orientation=(0.0, 0.0, 0.0, 1.0),
                status=RobotStatus.IDLE,
                battery_level=level
            )
            assert state.battery_level == level

        # Invalid battery levels
        for level in [-1.0, 101.0]:
            with pytest.raises(ValidationError):
                RobotState(
                    robot_id="robot_1",
                    position=(0.0, 0.0, 0.0),
                    orientation=(0.0, 0.0, 0.0, 1.0),
                    status=RobotStatus.IDLE,
                    battery_level=level
                )

    def test_quaternion_validation(self):
        """Test quaternion normalization validation."""
        # Valid normalized quaternion
        state = RobotState(
            robot_id="robot_1",
            position=(0.0, 0.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.IDLE,
            battery_level=50.0
        )
        assert state.orientation == (0.0, 0.0, 0.0, 1.0)

        # Invalid non-normalized quaternion
        with pytest.raises(ValidationError) as exc_info:
            RobotState(
                robot_id="robot_1",
                position=(0.0, 0.0, 0.0),
                orientation=(1.0, 1.0, 1.0, 1.0),  # Not normalized
                status=RobotStatus.IDLE,
                battery_level=50.0
            )
        assert "Quaternion must be normalized" in str(exc_info.value)

    def test_is_available_method(self):
        """Test the is_available method."""
        # Available robot (idle with good battery)
        state = RobotState(
            robot_id="robot_1",
            position=(0.0, 0.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.IDLE,
            battery_level=50.0
        )
        assert state.is_available()

        # Not available - low battery
        state.battery_level = 5.0
        assert not state.is_available()

        # Not available - busy status
        state.battery_level = 50.0
        state.status = RobotStatus.EXECUTING
        assert not state.is_available()


class TestTask:
    """Test cases for Task model."""

    def test_valid_task_creation(self):
        """Test creating a valid task."""
        task = Task(
            task_id="task_001",
            description="Navigate to shelf A",
            estimated_duration=120,
            dependencies=["task_000"]
        )
        
        assert task.task_id == "task_001"
        assert task.description == "Navigate to shelf A"
        assert task.status == TaskStatus.PENDING
        assert task.estimated_duration == 120
        assert task.dependencies == ["task_000"]
        assert task.assigned_robot is None
        assert isinstance(task.created_at, datetime)

    def test_estimated_duration_validation(self):
        """Test estimated duration validation."""
        # Valid duration
        task = Task(
            task_id="task_001",
            description="Test task",
            estimated_duration=1
        )
        assert task.estimated_duration == 1

        # Invalid duration
        with pytest.raises(ValidationError):
            Task(
                task_id="task_002",
                description="Test task",
                estimated_duration=0
            )

        with pytest.raises(ValidationError):
            Task(
                task_id="task_003",
                description="Test task",
                estimated_duration=-10
            )

    def test_can_start_method(self):
        """Test the can_start method."""
        # Task with no dependencies
        task = Task(
            task_id="task_001",
            description="Test task",
            estimated_duration=60
        )
        assert task.can_start([])

        # Task with satisfied dependencies
        task_with_deps = Task(
            task_id="task_002",
            description="Test task with deps",
            estimated_duration=60,
            dependencies=["task_001"]
        )
        assert task_with_deps.can_start(["task_001"])
        assert not task_with_deps.can_start([])

        # Task with multiple dependencies
        task_multi_deps = Task(
            task_id="task_003",
            description="Test task with multiple deps",
            estimated_duration=60,
            dependencies=["task_001", "task_002"]
        )
        assert task_multi_deps.can_start(["task_001", "task_002"])
        assert not task_multi_deps.can_start(["task_001"])

    def test_is_terminal_method(self):
        """Test the is_terminal method."""
        task = Task(
            task_id="task_001",
            description="Test task",
            estimated_duration=60
        )
        
        # Non-terminal states
        for status in [TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.EXECUTING]:
            task.status = status
            assert not task.is_terminal()

        # Terminal states
        for status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            task.status = status
            assert task.is_terminal()


class TestPerformanceMetrics:
    """Test cases for PerformanceMetrics model."""

    def test_valid_metrics_creation(self):
        """Test creating valid performance metrics."""
        metrics = PerformanceMetrics(
            command_accuracy=0.95,
            average_response_time=250.5,
            task_completion_rate=0.88,
            system_uptime=99.5,
            active_robots=5,
            commands_processed=1000
        )
        
        assert metrics.command_accuracy == 0.95
        assert metrics.average_response_time == 250.5
        assert metrics.task_completion_rate == 0.88
        assert metrics.system_uptime == 99.5
        assert metrics.active_robots == 5
        assert metrics.commands_processed == 1000
        assert isinstance(metrics.timestamp, datetime)

    def test_accuracy_validation(self):
        """Test accuracy field validation."""
        # Valid accuracy values
        for accuracy in [0.0, 0.5, 1.0]:
            metrics = PerformanceMetrics(
                command_accuracy=accuracy,
                average_response_time=100.0,
                task_completion_rate=0.8,
                system_uptime=95.0,
                active_robots=3,
                commands_processed=500
            )
            assert metrics.command_accuracy == accuracy

        # Invalid accuracy values
        for accuracy in [-0.1, 1.1]:
            with pytest.raises(ValidationError):
                PerformanceMetrics(
                    command_accuracy=accuracy,
                    average_response_time=100.0,
                    task_completion_rate=0.8,
                    system_uptime=95.0,
                    active_robots=3,
                    commands_processed=500
                )

    def test_completion_rate_validation(self):
        """Test task completion rate validation."""
        # Valid completion rates
        for rate in [0.0, 0.5, 1.0]:
            metrics = PerformanceMetrics(
                command_accuracy=0.9,
                average_response_time=100.0,
                task_completion_rate=rate,
                system_uptime=95.0,
                active_robots=3,
                commands_processed=500
            )
            assert metrics.task_completion_rate == rate

        # Invalid completion rates
        for rate in [-0.1, 1.1]:
            with pytest.raises(ValidationError):
                PerformanceMetrics(
                    command_accuracy=0.9,
                    average_response_time=100.0,
                    task_completion_rate=rate,
                    system_uptime=95.0,
                    active_robots=3,
                    commands_processed=500
                )

    def test_uptime_validation(self):
        """Test system uptime validation."""
        # Valid uptime values
        for uptime in [0.0, 50.0, 100.0]:
            metrics = PerformanceMetrics(
                command_accuracy=0.9,
                average_response_time=100.0,
                task_completion_rate=0.8,
                system_uptime=uptime,
                active_robots=3,
                commands_processed=500
            )
            assert metrics.system_uptime == uptime

        # Invalid uptime values
        for uptime in [-1.0, 101.0]:
            with pytest.raises(ValidationError):
                PerformanceMetrics(
                    command_accuracy=0.9,
                    average_response_time=100.0,
                    task_completion_rate=0.8,
                    system_uptime=uptime,
                    active_robots=3,
                    commands_processed=500
                )

    def test_get_efficiency_score_method(self):
        """Test the get_efficiency_score method."""
        metrics = PerformanceMetrics(
            command_accuracy=0.9,  # 30% weight
            average_response_time=100.0,
            task_completion_rate=0.8,  # 40% weight
            system_uptime=95.0,  # 30% weight (as 0.95)
            active_robots=3,
            commands_processed=500
        )
        
        expected_score = (0.9 * 0.3) + (0.8 * 0.4) + (0.95 * 0.3)
        assert abs(metrics.get_efficiency_score() - expected_score) < 0.001

    def test_negative_counts_validation(self):
        """Test validation of count fields."""
        # Valid counts
        metrics = PerformanceMetrics(
            command_accuracy=0.9,
            average_response_time=100.0,
            task_completion_rate=0.8,
            system_uptime=95.0,
            active_robots=0,
            commands_processed=0
        )
        assert metrics.active_robots == 0
        assert metrics.commands_processed == 0

        # Invalid negative counts
        with pytest.raises(ValidationError):
            PerformanceMetrics(
                command_accuracy=0.9,
                average_response_time=100.0,
                task_completion_rate=0.8,
                system_uptime=95.0,
                active_robots=-1,
                commands_processed=500
            )

        with pytest.raises(ValidationError):
            PerformanceMetrics(
                command_accuracy=0.9,
                average_response_time=100.0,
                task_completion_rate=0.8,
                system_uptime=95.0,
                active_robots=3,
                commands_processed=-1
            )
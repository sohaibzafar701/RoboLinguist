"""
Unit tests for command structure validation.

Tests validation schemas and rules for different robot command action types.
"""

import pytest
from pydantic import ValidationError

from core.data_models import RobotCommand, ActionType
from core.command_validation import (
    CommandValidator, NavigationParameters, ManipulationParameters, 
    InspectionParameters
)


class TestNavigationParameters:
    """Test cases for navigation parameter validation."""

    def test_valid_navigation_parameters(self):
        """Test valid navigation parameters."""
        params = NavigationParameters(
            target_x=1.0,
            target_y=2.0,
            target_z=0.5,
            max_speed=1.5,
            tolerance=0.2,
            avoid_obstacles=True
        )
        
        assert params.target_x == 1.0
        assert params.target_y == 2.0
        assert params.target_z == 0.5
        assert params.max_speed == 1.5
        assert params.tolerance == 0.2
        assert params.avoid_obstacles is True

    def test_minimal_navigation_parameters(self):
        """Test navigation with only required parameters."""
        params = NavigationParameters(
            target_x=1.0,
            target_y=2.0
        )
        
        assert params.target_x == 1.0
        assert params.target_y == 2.0
        assert params.target_z == 0.0  # Default value
        assert params.max_speed == 1.0  # Default value
        assert params.tolerance == 0.1  # Default value
        assert params.avoid_obstacles is True  # Default value

    def test_coordinate_bounds_validation(self):
        """Test coordinate bounds validation."""
        # Valid coordinates within bounds
        params = NavigationParameters(target_x=999.0, target_y=-999.0)
        assert params.target_x == 999.0
        assert params.target_y == -999.0

        # Invalid coordinates exceeding bounds
        with pytest.raises(ValidationError) as exc_info:
            NavigationParameters(target_x=1001.0, target_y=0.0)
        assert "exceeds maximum range" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            NavigationParameters(target_x=0.0, target_y=-1001.0)
        assert "exceeds maximum range" in str(exc_info.value)

    def test_speed_validation(self):
        """Test speed parameter validation."""
        # Valid speeds
        for speed in [0.1, 1.0, 5.0]:
            params = NavigationParameters(
                target_x=1.0, target_y=2.0, max_speed=speed
            )
            assert params.max_speed == speed

        # Invalid speeds
        for speed in [0.05, 5.1]:
            with pytest.raises(ValidationError):
                NavigationParameters(
                    target_x=1.0, target_y=2.0, max_speed=speed
                )

    def test_tolerance_validation(self):
        """Test tolerance parameter validation."""
        # Valid tolerances
        for tolerance in [0.01, 0.5, 1.0]:
            params = NavigationParameters(
                target_x=1.0, target_y=2.0, tolerance=tolerance
            )
            assert params.tolerance == tolerance

        # Invalid tolerances
        for tolerance in [0.005, 1.1]:
            with pytest.raises(ValidationError):
                NavigationParameters(
                    target_x=1.0, target_y=2.0, tolerance=tolerance
                )


class TestManipulationParameters:
    """Test cases for manipulation parameter validation."""

    def test_valid_manipulation_parameters(self):
        """Test valid manipulation parameters."""
        params = ManipulationParameters(
            object_id="box_001",
            action="pick",
            force_limit=15.0,
            precision=0.005,
            timeout=60
        )
        
        assert params.object_id == "box_001"
        assert params.action == "pick"
        assert params.force_limit == 15.0
        assert params.precision == 0.005
        assert params.timeout == 60

    def test_minimal_manipulation_parameters(self):
        """Test manipulation with only required parameters."""
        params = ManipulationParameters(
            object_id="box_001",
            action="pick"
        )
        
        assert params.object_id == "box_001"
        assert params.action == "pick"
        assert params.force_limit == 10.0  # Default value
        assert params.precision == 0.01  # Default value
        assert params.timeout == 30  # Default value

    def test_action_validation(self):
        """Test manipulation action validation."""
        # Valid actions
        valid_actions = ['pick', 'place', 'push', 'pull', 'rotate', 'grasp', 'release']
        for action in valid_actions:
            params = ManipulationParameters(
                object_id="box_001",
                action=action
            )
            assert params.action == action.lower()

        # Test case insensitive
        params = ManipulationParameters(
            object_id="box_001",
            action="PICK"
        )
        assert params.action == "pick"

        # Invalid action
        with pytest.raises(ValidationError) as exc_info:
            ManipulationParameters(
                object_id="box_001",
                action="invalid_action"
            )
        assert "not supported" in str(exc_info.value)

    def test_object_id_validation(self):
        """Test object ID validation."""
        # Valid object IDs
        valid_ids = ["box_001", "shelf-A", "item123", "object_test-1"]
        for obj_id in valid_ids:
            params = ManipulationParameters(
                object_id=obj_id,
                action="pick"
            )
            assert params.object_id == obj_id

        # Invalid object IDs
        invalid_ids = ["box 001", "shelf@A", "item#123", "object!"]
        for obj_id in invalid_ids:
            with pytest.raises(ValidationError) as exc_info:
                ManipulationParameters(
                    object_id=obj_id,
                    action="pick"
                )
            assert "alphanumeric characters" in str(exc_info.value)

    def test_force_limit_validation(self):
        """Test force limit validation."""
        # Valid force limits
        for force in [0.1, 50.0, 100.0]:
            params = ManipulationParameters(
                object_id="box_001",
                action="pick",
                force_limit=force
            )
            assert params.force_limit == force

        # Invalid force limits
        for force in [0.05, 101.0]:
            with pytest.raises(ValidationError):
                ManipulationParameters(
                    object_id="box_001",
                    action="pick",
                    force_limit=force
                )


class TestInspectionParameters:
    """Test cases for inspection parameter validation."""

    def test_valid_inspection_parameters(self):
        """Test valid inspection parameters."""
        params = InspectionParameters(
            target_location="shelf_A",
            inspection_type="thermal",
            duration=30,
            resolution="high",
            save_data=False
        )
        
        assert params.target_location == "shelf_A"
        assert params.inspection_type == "thermal"
        assert params.duration == 30
        assert params.resolution == "high"
        assert params.save_data is False

    def test_minimal_inspection_parameters(self):
        """Test inspection with only required parameters."""
        params = InspectionParameters(
            target_location="shelf_A"
        )
        
        assert params.target_location == "shelf_A"
        assert params.inspection_type == "visual"  # Default value
        assert params.duration == 10  # Default value
        assert params.resolution == "medium"  # Default value
        assert params.save_data is True  # Default value

    def test_inspection_type_validation(self):
        """Test inspection type validation."""
        # Valid inspection types
        valid_types = ['visual', 'thermal', 'depth', 'lidar', 'ultrasonic']
        for inspection_type in valid_types:
            params = InspectionParameters(
                target_location="shelf_A",
                inspection_type=inspection_type
            )
            assert params.inspection_type == inspection_type.lower()

        # Test case insensitive
        params = InspectionParameters(
            target_location="shelf_A",
            inspection_type="VISUAL"
        )
        assert params.inspection_type == "visual"

        # Invalid inspection type
        with pytest.raises(ValidationError) as exc_info:
            InspectionParameters(
                target_location="shelf_A",
                inspection_type="invalid_type"
            )
        assert "not supported" in str(exc_info.value)

    def test_resolution_validation(self):
        """Test resolution validation."""
        # Valid resolutions
        valid_resolutions = ['low', 'medium', 'high', 'ultra']
        for resolution in valid_resolutions:
            params = InspectionParameters(
                target_location="shelf_A",
                resolution=resolution
            )
            assert params.resolution == resolution.lower()

        # Test case insensitive
        params = InspectionParameters(
            target_location="shelf_A",
            resolution="HIGH"
        )
        assert params.resolution == "high"

        # Invalid resolution
        with pytest.raises(ValidationError) as exc_info:
            InspectionParameters(
                target_location="shelf_A",
                resolution="invalid_resolution"
            )
        assert "not supported" in str(exc_info.value)

    def test_duration_validation(self):
        """Test duration validation."""
        # Valid durations
        for duration in [1, 150, 300]:
            params = InspectionParameters(
                target_location="shelf_A",
                duration=duration
            )
            assert params.duration == duration

        # Invalid durations
        for duration in [0, 301]:
            with pytest.raises(ValidationError):
                InspectionParameters(
                    target_location="shelf_A",
                    duration=duration
                )


class TestCommandValidator:
    """Test cases for the main CommandValidator class."""

    def test_validate_navigation_command(self):
        """Test validation of navigation commands."""
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0},
            priority=5
        )
        
        assert CommandValidator.validate_command_structure(command) is True

    def test_validate_manipulation_command(self):
        """Test validation of manipulation commands."""
        command = RobotCommand(
            command_id="cmd_002",
            robot_id="robot_1",
            action_type=ActionType.MANIPULATE,
            parameters={"object_id": "box_001", "action": "pick"},
            priority=7
        )
        
        assert CommandValidator.validate_command_structure(command) is True

    def test_validate_inspection_command(self):
        """Test validation of inspection commands."""
        command = RobotCommand(
            command_id="cmd_003",
            robot_id="robot_1",
            action_type=ActionType.INSPECT,
            parameters={"target_location": "shelf_A"},
            priority=3
        )
        
        assert CommandValidator.validate_command_structure(command) is True

    def test_validate_invalid_command_structure(self):
        """Test validation of invalid command structures."""
        # Missing required parameters - should fail at RobotCommand creation
        with pytest.raises(ValidationError) as exc_info:
            RobotCommand(
                command_id="cmd_004",
                robot_id="robot_1",
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 1.0},  # Missing target_y
                priority=5
            )
        assert "missing required parameter" in str(exc_info.value)

    def test_validate_parameter_schema(self):
        """Test parameter schema validation."""
        # Valid navigation parameters
        params = {"target_x": 1.0, "target_y": 2.0, "max_speed": 1.5}
        validated = CommandValidator.validate_parameter_schema(
            ActionType.NAVIGATE, params
        )
        assert validated["target_x"] == 1.0
        assert validated["target_y"] == 2.0
        assert validated["max_speed"] == 1.5

        # Invalid parameters
        invalid_params = {"target_x": 1.0}  # Missing target_y
        with pytest.raises(ValidationError) as exc_info:
            CommandValidator.validate_parameter_schema(
                ActionType.NAVIGATE, invalid_params
            )
        assert "Field required" in str(exc_info.value)

    def test_get_required_parameters(self):
        """Test getting required parameters for action types."""
        nav_required = CommandValidator.get_required_parameters(ActionType.NAVIGATE)
        assert nav_required == ['target_x', 'target_y']

        manip_required = CommandValidator.get_required_parameters(ActionType.MANIPULATE)
        assert manip_required == ['object_id', 'action']

        inspect_required = CommandValidator.get_required_parameters(ActionType.INSPECT)
        assert inspect_required == ['target_location']

    def test_get_optional_parameters(self):
        """Test getting optional parameters for action types."""
        nav_optional = CommandValidator.get_optional_parameters(ActionType.NAVIGATE)
        assert 'target_z' in nav_optional
        assert 'max_speed' in nav_optional
        assert nav_optional['target_z'] == 0.0

        manip_optional = CommandValidator.get_optional_parameters(ActionType.MANIPULATE)
        assert 'force_limit' in manip_optional
        assert 'precision' in manip_optional
        assert manip_optional['force_limit'] == 10.0

        inspect_optional = CommandValidator.get_optional_parameters(ActionType.INSPECT)
        assert 'inspection_type' in inspect_optional
        assert 'duration' in inspect_optional
        assert inspect_optional['inspection_type'] == 'visual'

    def test_validate_safety_constraints_navigation(self):
        """Test safety constraint validation for navigation commands."""
        # Safe navigation command
        safe_command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0, "max_speed": 1.5},
            priority=5
        )
        violations = CommandValidator.validate_safety_constraints(safe_command)
        assert len(violations) == 0

        # Unsafe navigation command - excessive speed
        unsafe_command = RobotCommand(
            command_id="cmd_002",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0, "max_speed": 3.0},
            priority=5
        )
        violations = CommandValidator.validate_safety_constraints(unsafe_command)
        assert len(violations) > 0
        assert "exceeds safety limit" in violations[0]

        # Unsafe navigation command - dangerous Z coordinate
        unsafe_z_command = RobotCommand(
            command_id="cmd_003",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0, "target_z": -2.0},
            priority=5
        )
        violations = CommandValidator.validate_safety_constraints(unsafe_z_command)
        assert len(violations) > 0
        assert "dangerously low" in violations[0]

    def test_validate_safety_constraints_manipulation(self):
        """Test safety constraint validation for manipulation commands."""
        # Safe manipulation command
        safe_command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.MANIPULATE,
            parameters={"object_id": "box_001", "action": "pick", "force_limit": 20.0},
            priority=7
        )
        violations = CommandValidator.validate_safety_constraints(safe_command)
        assert len(violations) == 0

        # Unsafe manipulation command - excessive force
        unsafe_command = RobotCommand(
            command_id="cmd_002",
            robot_id="robot_1",
            action_type=ActionType.MANIPULATE,
            parameters={"object_id": "box_001", "action": "pick", "force_limit": 60.0},
            priority=7
        )
        violations = CommandValidator.validate_safety_constraints(unsafe_command)
        assert len(violations) > 0
        assert "exceeds safety limit" in violations[0]

        # Unsafe manipulation command - human object
        human_command = RobotCommand(
            command_id="cmd_003",
            robot_id="robot_1",
            action_type=ActionType.MANIPULATE,
            parameters={"object_id": "human_001", "action": "pick"},
            priority=7
        )
        violations = CommandValidator.validate_safety_constraints(human_command)
        assert len(violations) > 0
        assert "prohibited" in violations[0]

    def test_validate_safety_constraints_inspection(self):
        """Test safety constraint validation for inspection commands."""
        # Safe inspection command
        safe_command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.INSPECT,
            parameters={"target_location": "shelf_A", "duration": 60},
            priority=3
        )
        violations = CommandValidator.validate_safety_constraints(safe_command)
        assert len(violations) == 0

        # Unsafe inspection command - excessive duration
        unsafe_command = RobotCommand(
            command_id="cmd_002",
            robot_id="robot_1",
            action_type=ActionType.INSPECT,
            parameters={"target_location": "shelf_A", "duration": 180},
            priority=3
        )
        violations = CommandValidator.validate_safety_constraints(unsafe_command)
        assert len(violations) > 0
        assert "exceeds safety limit" in violations[0]
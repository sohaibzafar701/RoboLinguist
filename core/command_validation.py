"""
Command structure validation for robot commands.

Provides detailed validation schemas and rules for different action types.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator, ValidationError
from enum import Enum

from .data_models import ActionType, RobotCommand


class NavigationParameters(BaseModel):
    """Validation schema for navigation command parameters."""
    target_x: float = Field(..., description="Target X coordinate")
    target_y: float = Field(..., description="Target Y coordinate")
    target_z: Optional[float] = Field(0.0, description="Target Z coordinate (optional)")
    max_speed: Optional[float] = Field(1.0, ge=0.1, le=5.0, description="Maximum speed in m/s")
    tolerance: Optional[float] = Field(0.1, ge=0.01, le=1.0, description="Position tolerance in meters")
    avoid_obstacles: Optional[bool] = Field(True, description="Enable obstacle avoidance")

    @field_validator('target_x', 'target_y', 'target_z')
    @classmethod
    def validate_coordinates(cls, v):
        """Validate coordinate values are within reasonable bounds."""
        if abs(v) > 1000.0:  # 1km limit
            raise ValueError(f"Coordinate value {v} exceeds maximum range of ±1000m")
        return v


class ManipulationParameters(BaseModel):
    """Validation schema for manipulation command parameters."""
    object_id: str = Field(..., min_length=1, description="ID of object to manipulate")
    action: str = Field(..., description="Manipulation action to perform")
    force_limit: Optional[float] = Field(10.0, ge=0.1, le=100.0, description="Force limit in Newtons")
    precision: Optional[float] = Field(0.01, ge=0.001, le=0.1, description="Precision in meters")
    timeout: Optional[int] = Field(30, ge=1, le=300, description="Timeout in seconds")

    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        """Validate manipulation action is supported."""
        valid_actions = ['pick', 'place', 'push', 'pull', 'rotate', 'grasp', 'release']
        if v.lower() not in valid_actions:
            raise ValueError(f"Action '{v}' not supported. Valid actions: {valid_actions}")
        return v.lower()

    @field_validator('object_id')
    @classmethod
    def validate_object_id(cls, v):
        """Validate object ID format."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Object ID must contain only alphanumeric characters, hyphens, and underscores")
        return v


class InspectionParameters(BaseModel):
    """Validation schema for inspection command parameters."""
    target_location: str = Field(..., min_length=1, description="Location to inspect")
    inspection_type: Optional[str] = Field("visual", description="Type of inspection")
    duration: Optional[int] = Field(10, ge=1, le=300, description="Inspection duration in seconds")
    resolution: Optional[str] = Field("medium", description="Sensor resolution")
    save_data: Optional[bool] = Field(True, description="Save inspection data")

    @field_validator('inspection_type')
    @classmethod
    def validate_inspection_type(cls, v):
        """Validate inspection type is supported."""
        valid_types = ['visual', 'thermal', 'depth', 'lidar', 'ultrasonic']
        if v.lower() not in valid_types:
            raise ValueError(f"Inspection type '{v}' not supported. Valid types: {valid_types}")
        return v.lower()

    @field_validator('resolution')
    @classmethod
    def validate_resolution(cls, v):
        """Validate resolution setting."""
        valid_resolutions = ['low', 'medium', 'high', 'ultra']
        if v.lower() not in valid_resolutions:
            raise ValueError(f"Resolution '{v}' not supported. Valid resolutions: {valid_resolutions}")
        return v.lower()


class CommandValidator:
    """Main command validation class."""

    @staticmethod
    def validate_command_structure(command: RobotCommand) -> bool:
        """
        Validate the complete structure of a robot command.
        
        Args:
            command: RobotCommand instance to validate
            
        Returns:
            bool: True if command structure is valid
            
        Raises:
            ValidationError: If command structure is invalid
        """
        try:
            # Validate basic command structure (already done by Pydantic)
            if not command.command_id or not command.robot_id:
                raise ValidationError("Command ID and Robot ID are required")

            # Validate action-specific parameters
            if command.action_type == ActionType.NAVIGATE:
                NavigationParameters(**command.parameters)
            elif command.action_type == ActionType.MANIPULATE:
                ManipulationParameters(**command.parameters)
            elif command.action_type == ActionType.INSPECT:
                InspectionParameters(**command.parameters)
            else:
                raise ValidationError(f"Unknown action type: {command.action_type}")

            return True

        except ValidationError as e:
            raise e

    @staticmethod
    def validate_parameter_schema(action_type: ActionType, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize parameters for a specific action type.
        
        Args:
            action_type: Type of action to validate parameters for
            parameters: Raw parameters dictionary
            
        Returns:
            Dict[str, Any]: Validated and normalized parameters
            
        Raises:
            ValidationError: If parameters are invalid
        """
        try:
            if action_type == ActionType.NAVIGATE:
                validated = NavigationParameters(**parameters)
                return validated.model_dump()
            elif action_type == ActionType.MANIPULATE:
                validated = ManipulationParameters(**parameters)
                return validated.model_dump()
            elif action_type == ActionType.INSPECT:
                validated = InspectionParameters(**parameters)
                return validated.model_dump()
            else:
                raise ValidationError(f"Unknown action type: {action_type}")

        except ValidationError as e:
            raise e

    @staticmethod
    def get_required_parameters(action_type: ActionType) -> List[str]:
        """
        Get list of required parameters for an action type.
        
        Args:
            action_type: Action type to get requirements for
            
        Returns:
            List[str]: List of required parameter names
        """
        if action_type == ActionType.NAVIGATE:
            return ['target_x', 'target_y']
        elif action_type == ActionType.MANIPULATE:
            return ['object_id', 'action']
        elif action_type == ActionType.INSPECT:
            return ['target_location']
        else:
            return []

    @staticmethod
    def get_optional_parameters(action_type: ActionType) -> Dict[str, Any]:
        """
        Get dictionary of optional parameters with their default values.
        
        Args:
            action_type: Action type to get optional parameters for
            
        Returns:
            Dict[str, Any]: Dictionary of optional parameters and defaults
        """
        if action_type == ActionType.NAVIGATE:
            return {
                'target_z': 0.0,
                'max_speed': 1.0,
                'tolerance': 0.1,
                'avoid_obstacles': True
            }
        elif action_type == ActionType.MANIPULATE:
            return {
                'force_limit': 10.0,
                'precision': 0.01,
                'timeout': 30
            }
        elif action_type == ActionType.INSPECT:
            return {
                'inspection_type': 'visual',
                'duration': 10,
                'resolution': 'medium',
                'save_data': True
            }
        else:
            return {}

    @staticmethod
    def validate_safety_constraints(command: RobotCommand) -> List[str]:
        """
        Check command against safety constraints.
        
        Args:
            command: Command to validate
            
        Returns:
            List[str]: List of safety violations (empty if safe)
        """
        violations = []

        if command.action_type == ActionType.NAVIGATE:
            params = NavigationParameters(**command.parameters)
            
            # Check for dangerous speeds
            if params.max_speed and params.max_speed > 2.0:
                violations.append(f"Navigation speed {params.max_speed} m/s exceeds safety limit of 2.0 m/s")
            
            # Check for dangerous coordinates (e.g., negative Z in some contexts)
            if params.target_z and params.target_z < -1.0:
                violations.append(f"Target Z coordinate {params.target_z} is dangerously low")

        elif command.action_type == ActionType.MANIPULATE:
            params = ManipulationParameters(**command.parameters)
            
            # Check for excessive force
            if params.force_limit and params.force_limit > 50.0:
                violations.append(f"Force limit {params.force_limit} N exceeds safety limit of 50 N")
            
            # Check for dangerous actions on certain objects
            if 'human' in params.object_id.lower() or 'person' in params.object_id.lower():
                violations.append("Manipulation of human/person objects is prohibited")

        elif command.action_type == ActionType.INSPECT:
            params = InspectionParameters(**command.parameters)
            
            # Check for excessive inspection duration
            if params.duration and params.duration > 120:
                violations.append(f"Inspection duration {params.duration}s exceeds safety limit of 120s")

        return violations
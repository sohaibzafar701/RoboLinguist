"""
Unit tests for ROS2Publisher component.

Tests ROS2 command publishing functionality with mocked ROS2 nodes.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from ros2_bridge.ros2_publisher import ROS2Publisher
from core.data_models import RobotCommand, ActionType


class TestROS2Publisher:
    """Test cases for ROS2Publisher component."""
    
    @pytest.fixture
    def publisher(self):
        """Create ROS2Publisher instance for testing."""
        return ROS2Publisher("test_publisher")
    
    @pytest.mark.asyncio
    async def test_initialization_without_ros2(self, publisher):
        """Test publisher initialization without ROS2 installation."""
        # Should initialize successfully in mock mode
        result = await publisher.initialize()
        assert result is True
        assert publisher.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_initialization_error_handling(self, publisher):
        """Test publisher initialization error handling."""
        # Mock an initialization error
        with patch.object(publisher, 'initialize', side_effect=Exception("Test error")):
            try:
                result = await publisher.initialize()
                assert False, "Should have raised an exception"
            except Exception as e:
                assert str(e) == "Test error"
    
    @pytest.mark.asyncio
    async def test_publish_navigation_goal_mock_mode(self, publisher):
        """Test navigation goal publishing in mock mode."""
        await publisher.initialize()
        
        result = await publisher.publish_navigation_goal("robot_1", 1.0, 2.0, 0.5)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_navigation_goal_with_coordinates(self, publisher):
        """Test navigation goal publishing with different coordinates."""
        await publisher.initialize()
        
        # Test with various coordinate combinations
        test_cases = [
            (0.0, 0.0, 0.0),
            (-1.5, 2.3, 1.0),
            (10.0, -5.0, 0.5)
        ]
        
        for x, y, z in test_cases:
            result = await publisher.publish_navigation_goal("robot_test", x, y, z)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_velocity_command_mock_mode(self, publisher):
        """Test velocity command publishing in mock mode."""
        await publisher.initialize()
        
        result = await publisher.publish_velocity_command("robot_1", 0.5, 0.2)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_robot_command_navigation(self, publisher):
        """Test publishing navigation robot command."""
        await publisher.initialize()
        
        command = RobotCommand(
            command_id="cmd_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0, "target_z": 0.0},
            priority=5,
            safety_validated=True
        )
        
        result = await publisher.publish_robot_command(command)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_robot_command_manipulation(self, publisher):
        """Test publishing manipulation robot command."""
        await publisher.initialize()
        
        command = RobotCommand(
            command_id="cmd_002",
            robot_id="robot_1",
            action_type=ActionType.MANIPULATE,
            parameters={"object_id": "box_1", "action": "pick"},
            priority=7,
            safety_validated=True
        )
        
        result = await publisher.publish_robot_command(command)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_robot_command_inspection(self, publisher):
        """Test publishing inspection robot command."""
        await publisher.initialize()
        
        command = RobotCommand(
            command_id="cmd_003",
            robot_id="robot_1",
            action_type=ActionType.INSPECT,
            parameters={"target_location": "shelf_A"},
            priority=3,
            safety_validated=True
        )
        
        result = await publisher.publish_robot_command(command)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_robot_command_unknown_action(self, publisher):
        """Test publishing robot command with unknown action type."""
        await publisher.initialize()
        
        # Create command with valid parameters first
        command = RobotCommand(
            command_id="cmd_004",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 2.0},
            priority=5,
            safety_validated=True
        )
        # Modify action type after creation to bypass validation
        command.action_type = "unknown"
        
        result = await publisher.publish_robot_command(command)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_emergency_stop(self, publisher):
        """Test emergency stop publishing."""
        await publisher.initialize()
        
        result = await publisher.publish_emergency_stop()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_publish_without_initialization(self, publisher):
        """Test publishing without initialization should fail."""
        result = await publisher.publish_navigation_goal("robot_1", 1.0, 2.0)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_shutdown(self, publisher):
        """Test publisher shutdown."""
        await publisher.initialize()
        assert publisher.is_initialized is True
        
        await publisher.shutdown()
        
        assert publisher.is_initialized is False
    
    @pytest.mark.asyncio
    async def test_health_check(self, publisher):
        """Test publisher health check functionality."""
        # Before initialization
        health = await publisher.health_check()
        assert health['component'] == 'ROS2Publisher'
        assert health['initialized'] is False
        assert health['status'] == 'not_initialized'
        
        # After initialization
        await publisher.initialize()
        health = await publisher.health_check()
        assert health['initialized'] is True
        assert health['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_error_handling_in_publish(self, publisher):
        """Test error handling during publishing."""
        await publisher.initialize()
        
        # Mock an exception during publishing
        with patch.object(publisher, '_publish_navigation_command', 
                         side_effect=Exception("Test error")):
            command = RobotCommand(
                command_id="cmd_005",
                robot_id="robot_1",
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 1.0, "target_y": 2.0},
                priority=5,
                safety_validated=True
            )
            
            result = await publisher.publish_robot_command(command)
            
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__])
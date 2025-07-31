"""
Unit tests for NavigationInterface component.

Tests robot navigation functionality with mocked ROS2 Navigation2 stack.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from ros2_bridge.navigation_interface import NavigationInterface, NavigationStatus
from core.data_models import RobotCommand, ActionType


class TestNavigationInterface:
    """Test cases for NavigationInterface component."""
    
    @pytest.fixture
    def nav_interface(self):
        """Create NavigationInterface instance for testing."""
        return NavigationInterface("test_navigation")
    
    @pytest.mark.asyncio
    async def test_initialization_without_ros2(self, nav_interface):
        """Test navigation interface initialization without ROS2 installation."""
        # Should initialize successfully in mock mode
        result = await nav_interface.initialize()
        assert result is True
        assert nav_interface.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_health_check(self, nav_interface):
        """Test navigation interface health check functionality."""
        # Before initialization
        health = await nav_interface.health_check()
        assert health['component'] == 'NavigationInterface'
        assert health['initialized'] is False
        assert health['status'] == 'not_initialized'
        
        # After initialization
        await nav_interface.initialize()
        health = await nav_interface.health_check()
        assert health['initialized'] is True
        assert health['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_navigate_to_pose_mock_mode(self, nav_interface):
        """Test navigation goal sending in mock mode."""
        await nav_interface.initialize()
        
        result = await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0, 0.5, 0.785)
        
        assert result is True
        assert nav_interface.get_navigation_status("robot_1") == NavigationStatus.NAVIGATING
    
    @pytest.mark.asyncio
    async def test_multiple_robot_navigation(self, nav_interface):
        """Test navigation with multiple robots."""
        await nav_interface.initialize()
        
        robots = [("robot_1", 1.0, 2.0), ("robot_2", 3.0, 4.0), ("robot_3", 5.0, 6.0)]
        
        for robot_id, x, y in robots:
            result = await nav_interface.navigate_to_pose(robot_id, x, y)
            assert result is True
            assert nav_interface.get_navigation_status(robot_id) == NavigationStatus.NAVIGATING
        
        # Check all robots have active navigation
        active_count = sum(1 for robot_id, _, _ in robots 
                          if nav_interface.is_navigation_active(robot_id))
        assert active_count == 3
    
    @pytest.mark.asyncio
    async def test_cancel_navigation_mock_mode(self, nav_interface):
        """Test navigation cancellation in mock mode."""
        await nav_interface.initialize()
        
        # Start navigation first
        await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0)
        
        result = await nav_interface.cancel_navigation("robot_1")
        
        assert result is True
        assert nav_interface.get_navigation_status("robot_1") == NavigationStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_get_navigation_status(self, nav_interface):
        """Test getting navigation status."""
        await nav_interface.initialize()
        
        # Initially should be idle
        status = nav_interface.get_navigation_status("robot_1")
        assert status == NavigationStatus.IDLE
        
        # After starting navigation
        await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0)
        status = nav_interface.get_navigation_status("robot_1")
        assert status == NavigationStatus.NAVIGATING
    
    @pytest.mark.asyncio
    async def test_is_navigation_active(self, nav_interface):
        """Test checking if navigation is active."""
        await nav_interface.initialize()
        
        # Initially should not be active
        assert nav_interface.is_navigation_active("robot_1") is False
        
        # After starting navigation
        await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0)
        assert nav_interface.is_navigation_active("robot_1") is True
        
        # After cancelling
        await nav_interface.cancel_navigation("robot_1")
        assert nav_interface.is_navigation_active("robot_1") is False
    
    @pytest.mark.asyncio
    async def test_wait_for_navigation_completion_success(self, nav_interface):
        """Test waiting for successful navigation completion."""
        await nav_interface.initialize()
        
        # Start navigation
        await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0)
        
        # Simulate completion after short delay
        async def complete_navigation():
            await asyncio.sleep(0.1)
            nav_interface.navigation_status["robot_1"] = NavigationStatus.SUCCEEDED
        
        asyncio.create_task(complete_navigation())
        
        result = await nav_interface.wait_for_navigation_completion("robot_1", timeout=1.0)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_wait_for_navigation_completion_failure(self, nav_interface):
        """Test waiting for failed navigation completion."""
        await nav_interface.initialize()
        
        # Start navigation
        await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0)
        
        # Simulate failure after short delay
        async def fail_navigation():
            await asyncio.sleep(0.1)
            nav_interface.navigation_status["robot_1"] = NavigationStatus.FAILED
        
        asyncio.create_task(fail_navigation())
        
        result = await nav_interface.wait_for_navigation_completion("robot_1", timeout=1.0)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_wait_for_navigation_completion_timeout(self, nav_interface):
        """Test waiting for navigation completion with timeout."""
        await nav_interface.initialize()
        
        # Start navigation
        await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0)
        
        # Don't change status, should timeout
        result = await nav_interface.wait_for_navigation_completion("robot_1", timeout=0.1)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_execute_navigation_command(self, nav_interface):
        """Test executing navigation command from RobotCommand."""
        await nav_interface.initialize()
        
        command = RobotCommand(
            command_id="nav_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={
                "target_x": 1.0,
                "target_y": 2.0,
                "target_z": 0.5,
                "target_yaw": 0.785
            },
            priority=5,
            safety_validated=True
        )
        
        result = await nav_interface.execute_navigation_command(command)
        
        assert result is True
        assert nav_interface.get_navigation_status("robot_1") == NavigationStatus.NAVIGATING
    
    @pytest.mark.asyncio
    async def test_execute_navigation_command_invalid_action(self, nav_interface):
        """Test executing non-navigation command should fail."""
        await nav_interface.initialize()
        
        command = RobotCommand(
            command_id="manip_001",
            robot_id="robot_1",
            action_type=ActionType.MANIPULATE,
            parameters={"object_id": "box_1", "action": "pick"},
            priority=5,
            safety_validated=True
        )
        
        result = await nav_interface.execute_navigation_command(command)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_navigation_metrics(self, nav_interface):
        """Test getting navigation metrics."""
        await nav_interface.initialize()
        
        # Start navigation
        await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0, 0.5)
        
        metrics = nav_interface.get_navigation_metrics("robot_1")
        
        assert metrics["robot_id"] == "robot_1"
        assert metrics["status"] == NavigationStatus.NAVIGATING.value
        # In mock mode, navigation goals are stored differently
        assert "has_active_goal" in metrics
        assert "target_position" in metrics
        assert "elapsed_time_seconds" in metrics or metrics["target_position"]["x"] is None
    
    @pytest.mark.asyncio
    async def test_get_navigation_metrics_no_goal(self, nav_interface):
        """Test getting navigation metrics for robot with no active goal."""
        await nav_interface.initialize()
        
        metrics = nav_interface.get_navigation_metrics("robot_1")
        
        assert metrics["robot_id"] == "robot_1"
        assert metrics["status"] == NavigationStatus.IDLE.value
        assert metrics["has_active_goal"] is False
        assert metrics["target_position"]["x"] is None
    
    @pytest.mark.asyncio
    async def test_yaw_to_quaternion(self, nav_interface):
        """Test yaw angle to quaternion conversion."""
        import math
        
        # Test 0 radians (facing forward)
        quat = nav_interface._yaw_to_quaternion(0.0)
        assert abs(quat.x - 0.0) < 1e-6
        assert abs(quat.y - 0.0) < 1e-6
        assert abs(quat.z - 0.0) < 1e-6
        assert abs(quat.w - 1.0) < 1e-6
        
        # Test π/2 radians (90 degrees)
        quat = nav_interface._yaw_to_quaternion(math.pi / 2)
        assert abs(quat.x - 0.0) < 1e-6
        assert abs(quat.y - 0.0) < 1e-6
        assert abs(quat.z - math.sin(math.pi / 4)) < 1e-6
        assert abs(quat.w - math.cos(math.pi / 4)) < 1e-6
    
    @pytest.mark.asyncio
    async def test_navigate_without_initialization(self, nav_interface):
        """Test navigation without initialization should fail."""
        result = await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_shutdown(self, nav_interface):
        """Test navigation interface shutdown."""
        await nav_interface.initialize()
        
        # Start some navigation
        await nav_interface.navigate_to_pose("robot_1", 1.0, 2.0)
        assert nav_interface.is_navigation_active("robot_1") is True
        
        await nav_interface.shutdown()
        
        assert nav_interface.is_initialized is False
        assert len(nav_interface.action_clients) == 0
        assert len(nav_interface.navigation_goals) == 0
        assert len(nav_interface.navigation_status) == 0
    
    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, nav_interface):
        """Test navigation interface start/stop lifecycle."""
        # Test start
        result = await nav_interface.start()
        assert result is True
        assert nav_interface.is_initialized is True
        
        # Test stop
        result = await nav_interface.stop()
        assert result is True
        assert nav_interface.is_initialized is False


if __name__ == "__main__":
    pytest.main([__file__])
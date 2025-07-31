"""
Unit tests for ROS2Subscriber component.

Tests ROS2 topic subscription and robot state monitoring with mocked ROS2 nodes.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from ros2_bridge.ros2_subscriber import ROS2Subscriber
from core.data_models import RobotState, RobotStatus


class TestROS2Subscriber:
    """Test cases for ROS2Subscriber component."""
    
    @pytest.fixture
    def subscriber(self):
        """Create ROS2Subscriber instance for testing."""
        return ROS2Subscriber("test_subscriber")
    
    @pytest.mark.asyncio
    async def test_initialization_without_ros2(self, subscriber):
        """Test subscriber initialization without ROS2 installation."""
        # Should initialize successfully in mock mode
        result = await subscriber.initialize()
        assert result is True
        assert subscriber.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_health_check(self, subscriber):
        """Test subscriber health check functionality."""
        # Before initialization
        health = await subscriber.health_check()
        assert health['component'] == 'ROS2Subscriber'
        assert health['initialized'] is False
        assert health['status'] == 'not_initialized'
        
        # After initialization
        await subscriber.initialize()
        health = await subscriber.health_check()
        assert health['initialized'] is True
        assert health['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_subscribe_to_robot_mock_mode(self, subscriber):
        """Test robot subscription in mock mode."""
        await subscriber.initialize()
        
        result = await subscriber.subscribe_to_robot("robot_1")
        
        assert result is True
        assert "robot_1" in subscriber.robot_states
        assert subscriber.robot_states["robot_1"].robot_id == "robot_1"
        assert subscriber.robot_states["robot_1"].status == RobotStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_multiple_robot_subscriptions(self, subscriber):
        """Test subscribing to multiple robots."""
        await subscriber.initialize()
        
        robot_ids = ["robot_1", "robot_2", "robot_3"]
        
        for robot_id in robot_ids:
            result = await subscriber.subscribe_to_robot(robot_id)
            assert result is True
            assert robot_id in subscriber.robot_states
        
        # Check all robots are tracked
        assert len(subscriber.robot_states) == 3
        all_states = subscriber.get_all_robot_states()
        assert len(all_states) == 3
    
    @pytest.mark.asyncio
    async def test_get_robot_state(self, subscriber):
        """Test getting robot state."""
        await subscriber.initialize()
        await subscriber.subscribe_to_robot("robot_1")
        
        state = subscriber.get_robot_state("robot_1")
        
        assert state is not None
        assert state.robot_id == "robot_1"
        assert isinstance(state, RobotState)
    
    @pytest.mark.asyncio
    async def test_get_robot_state_nonexistent(self, subscriber):
        """Test getting state for non-existent robot."""
        await subscriber.initialize()
        
        state = subscriber.get_robot_state("nonexistent")
        
        assert state is None
    
    @pytest.mark.asyncio
    async def test_get_all_robot_states(self, subscriber):
        """Test getting all robot states."""
        await subscriber.initialize()
        await subscriber.subscribe_to_robot("robot_1")
        await subscriber.subscribe_to_robot("robot_2")
        
        states = subscriber.get_all_robot_states()
        
        assert len(states) == 2
        assert "robot_1" in states
        assert "robot_2" in states
    
    @pytest.mark.asyncio
    async def test_get_available_robots(self, subscriber):
        """Test getting available robots."""
        await subscriber.initialize()
        await subscriber.subscribe_to_robot("robot_1")
        await subscriber.subscribe_to_robot("robot_2")
        
        # Mock one robot as busy
        subscriber.robot_states["robot_2"].status = RobotStatus.MOVING
        
        available = subscriber.get_available_robots()
        
        assert "robot_1" in available
        assert "robot_2" not in available
    
    @pytest.mark.asyncio
    async def test_state_callbacks(self, subscriber):
        """Test state change callbacks."""
        await subscriber.initialize()
        
        callback_called = False
        callback_robot_id = None
        callback_state = None
        
        def test_callback(robot_id, state):
            nonlocal callback_called, callback_robot_id, callback_state
            callback_called = True
            callback_robot_id = robot_id
            callback_state = state
        
        subscriber.add_state_callback(test_callback)
        await subscriber.subscribe_to_robot("robot_1")
        
        # Simulate state change
        subscriber._notify_state_callbacks("robot_1")
        
        assert callback_called is True
        assert callback_robot_id == "robot_1"
        assert callback_state is not None
    
    @pytest.mark.asyncio
    async def test_remove_state_callback(self, subscriber):
        """Test removing state callbacks."""
        await subscriber.initialize()
        
        def test_callback(robot_id, state):
            pass
        
        subscriber.add_state_callback(test_callback)
        assert len(subscriber.state_callbacks) == 1
        
        subscriber.remove_state_callback(test_callback)
        assert len(subscriber.state_callbacks) == 0
    
    @pytest.mark.asyncio
    async def test_odometry_callback(self, subscriber):
        """Test odometry message processing."""
        await subscriber.initialize()
        await subscriber.subscribe_to_robot("robot_1")
        
        # Create mock odometry message
        mock_msg = Mock()
        mock_msg.pose.pose.position.x = 1.0
        mock_msg.pose.pose.position.y = 2.0
        mock_msg.pose.pose.position.z = 0.5
        mock_msg.pose.pose.orientation.x = 0.0
        mock_msg.pose.pose.orientation.y = 0.0
        mock_msg.pose.pose.orientation.z = 0.0
        mock_msg.pose.pose.orientation.w = 1.0
        
        # Process callback
        subscriber._odometry_callback("robot_1", mock_msg)
        
        # Check state update
        state = subscriber.get_robot_state("robot_1")
        assert state.position == (1.0, 2.0, 0.5)
        assert state.orientation == (0.0, 0.0, 0.0, 1.0)
    
    @pytest.mark.asyncio
    async def test_battery_callback(self, subscriber):
        """Test battery state message processing."""
        await subscriber.initialize()
        await subscriber.subscribe_to_robot("robot_1")
        
        # Create mock battery message
        mock_msg = Mock()
        mock_msg.voltage = 12.0  # Should result in ~77% battery
        
        # Process callback
        subscriber._battery_callback("robot_1", mock_msg)
        
        # Check state update
        state = subscriber.get_robot_state("robot_1")
        assert 70.0 <= state.battery_level <= 85.0  # Approximate range
    
    @pytest.mark.asyncio
    async def test_robot_status_callback(self, subscriber):
        """Test robot status message processing."""
        await subscriber.initialize()
        await subscriber.subscribe_to_robot("robot_1")
        
        # Create mock status message
        mock_msg = Mock()
        mock_msg.data = "moving"
        
        # Process callback
        subscriber._robot_status_callback("robot_1", mock_msg)
        
        # Check state update
        state = subscriber.get_robot_state("robot_1")
        assert state.status == RobotStatus.MOVING
    
    @pytest.mark.asyncio
    async def test_task_status_callback(self, subscriber):
        """Test task status message processing."""
        await subscriber.initialize()
        await subscriber.subscribe_to_robot("robot_1")
        
        # Create mock task message
        mock_msg = Mock()
        mock_msg.data = "task_123"
        
        # Process callback
        subscriber._task_status_callback("robot_1", mock_msg)
        
        # Check state update
        state = subscriber.get_robot_state("robot_1")
        assert state.current_task == "task_123"
    
    @pytest.mark.asyncio
    async def test_subscribe_without_initialization(self, subscriber):
        """Test subscribing without initialization should fail."""
        result = await subscriber.subscribe_to_robot("robot_1")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_shutdown(self, subscriber):
        """Test subscriber shutdown."""
        await subscriber.initialize()
        await subscriber.subscribe_to_robot("robot_1")
        assert subscriber.is_initialized is True
        
        await subscriber.shutdown()
        
        assert subscriber.is_initialized is False
        assert len(subscriber.robot_states) == 0
        assert len(subscriber.state_callbacks) == 0
    
    @pytest.mark.asyncio
    async def test_spin_functionality(self, subscriber):
        """Test ROS2 spinning functionality in mock mode."""
        await subscriber.initialize()
        
        # Test spin_once (should not raise errors in mock mode)
        await subscriber.spin_once()
        
        # Test background spinning setup (should not raise errors)
        # Note: We don't actually run the background task to avoid infinite loop
        assert subscriber.is_initialized is True


if __name__ == "__main__":
    pytest.main([__file__])
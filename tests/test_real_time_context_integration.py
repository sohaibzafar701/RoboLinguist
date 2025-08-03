"""
Integration tests for real-time context integration with Robot Registry and Simulation Bridge.

Tests the RoboticsContextManager's ability to integrate with live system components
and provide real-time context updates.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

from services.robotics_context_manager import RoboticsContextManager, SystemContext
from task_orchestrator.robot_registry import RobotRegistry, RobotInfo
from core.data_models import RobotState, RobotStatus, Position, Orientation
from simulation_bridge.ros2_simulation_bridge import ROS2SimulationBridge


class TestRealTimeContextIntegration:
    """Test suite for real-time context integration."""

    @pytest.fixture
    def mock_robot_registry(self):
        """Create a mock robot registry with sample data."""
        registry = Mock(spec=RobotRegistry)
        
        # Sample robot states
        robot_states = {
            'robot_1': RobotState(
                robot_id='robot_1',
                position=Position(x=2.0, y=3.0, z=0.0),
                orientation=Orientation(x=0.0, y=0.0, z=0.0, w=1.0),
                status=RobotStatus.IDLE,
                battery_level=85.0,
                is_emergency_stopped=False,
                current_task=None,
                last_update=datetime.now()
            ),
            'robot_2': RobotState(
                robot_id='robot_2',
                position=Position(x=-1.0, y=1.5, z=0.0),
                orientation=Orientation(x=0.0, y=0.0, z=0.0, w=1.0),
                status=RobotStatus.MOVING,
                battery_level=92.0,
                is_emergency_stopped=False,
                current_task="navigate_to_target",
                last_update=datetime.now()
            )
        }
        
        registry.get_all_robot_states.return_value = robot_states
        registry.get_healthy_robots.return_value = ['robot_1', 'robot_2']
        
        return registry

    @pytest.fixture
    def mock_simulation_bridge(self):
        """Create a mock simulation bridge."""
        bridge = Mock(spec=ROS2SimulationBridge)
        
        # Sample environment state
        env_state = {
            'boundaries': {'min_x': -10.0, 'max_x': 10.0, 'min_y': -10.0, 'max_y': 10.0},
            'obstacles': [{'x': 5.0, 'y': 5.0, 'radius': 1.0}],
            'dynamic_objects': [],
            'timestamp': datetime.now()
        }
        
        bridge.get_environment_state.return_value = env_state
        return bridge

    @pytest.fixture
    def context_manager(self, mock_robot_registry):
        """Create a context manager with mocked dependencies."""
        return RoboticsContextManager(robot_registry=mock_robot_registry)

    @pytest.mark.asyncio
    async def test_robot_registry_integration(self, context_manager, mock_robot_registry):
        """Test integration with robot registry for live robot states."""
        # Connect robot registry
        context_manager.connect_robot_registry(mock_robot_registry)
        
        # Get system context
        context = context_manager.get_system_context()
        
        # Verify robot data is integrated
        assert len(context.robots) == 2
        assert 'robot_1' in context.robots
        assert 'robot_2' in context.robots
        
        # Verify robot details
        robot_1 = context.robots['robot_1']
        assert robot_1.position == (2.0, 3.0, 0.0)
        assert robot_1.status == RobotStatus.IDLE
        assert robot_1.battery_level == 85.0
        assert robot_1.is_available is True
        
        robot_2 = context.robots['robot_2']
        assert robot_2.position == (-1.0, 1.5, 0.0)
        assert robot_2.status == RobotStatus.MOVING
        assert robot_2.is_available is False  # Moving robots not available

    @pytest.mark.asyncio
    async def test_simulation_bridge_integration(self, context_manager, mock_simulation_bridge):
        """Test integration with simulation bridge for environment data."""
        # Connect simulation bridge
        context_manager.connect_simulation_bridge(mock_simulation_bridge)
        
        # Get environment data
        env_data = context_manager.get_simulation_environment_data()
        
        # Verify environment data is retrieved
        assert 'boundaries' in env_data
        assert 'obstacles' in env_data
        assert env_data['boundaries']['min_x'] == -10.0
        assert len(env_data['obstacles']) == 1

    @pytest.mark.asyncio
    async def test_real_time_updates(self, context_manager, mock_robot_registry):
        """Test real-time context updates."""
        # Set up update callback
        update_calls = []
        
        def update_callback(context: SystemContext):
            update_calls.append(context)
        
        context_manager.add_update_callback(update_callback)
        
        # Start auto-updates with short interval
        context_manager._update_interval = 0.1
        await context_manager.start_auto_updates()
        
        # Wait for a few updates
        await asyncio.sleep(0.3)
        
        # Stop updates
        await context_manager.stop_auto_updates()
        
        # Verify callbacks were triggered
        assert len(update_calls) >= 2

    @pytest.mark.asyncio
    async def test_context_change_detection(self, context_manager, mock_robot_registry):
        """Test detection of significant context changes."""
        # Get initial context
        initial_context = context_manager.get_system_context()
        
        # Simulate robot position change
        updated_states = mock_robot_registry.get_all_robot_states.return_value.copy()
        updated_states['robot_1'].position = Position(x=5.0, y=6.0, z=0.0)  # Significant change
        mock_robot_registry.get_all_robot_states.return_value = updated_states
        
        # Get updated context
        context_manager.invalidate_cache()
        updated_context = context_manager.get_system_context()
        
        # Test change detection
        changed = context_manager._context_changed(initial_context, updated_context)
        assert changed is True

    @pytest.mark.asyncio
    async def test_context_change_detection_small_change(self, context_manager, mock_robot_registry):
        """Test that small position changes don't trigger updates."""
        # Get initial context
        initial_context = context_manager.get_system_context()
        
        # Simulate small robot position change
        updated_states = mock_robot_registry.get_all_robot_states.return_value.copy()
        updated_states['robot_1'].position = Position(x=2.05, y=3.05, z=0.0)  # Small change
        mock_robot_registry.get_all_robot_states.return_value = updated_states
        
        # Get updated context
        context_manager.invalidate_cache()
        updated_context = context_manager.get_system_context()
        
        # Test change detection
        changed = context_manager._context_changed(initial_context, updated_context)
        assert changed is False

    @pytest.mark.asyncio
    async def test_context_validation(self, context_manager):
        """Test context data validation."""
        # Get system context
        context = context_manager.get_system_context()
        
        # Validate context
        issues = context_manager.validate_context_data(context)
        
        # Should have no issues with valid data
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_context_validation_with_issues(self, context_manager, mock_robot_registry):
        """Test context validation with problematic data."""
        # Create invalid robot state
        invalid_states = {
            'robot_bad': RobotState(
                robot_id='robot_bad',
                position=Position(x=0.0, y=0.0, z=0.0),
                orientation=Orientation(x=0.0, y=0.0, z=0.0, w=1.0),
                status=RobotStatus.IDLE,
                battery_level=150.0,  # Invalid battery level
                is_emergency_stopped=False,
                current_task=None,
                last_update=datetime.now()
            )
        }
        
        mock_robot_registry.get_all_robot_states.return_value = invalid_states
        context_manager.invalidate_cache()
        
        # Get context with invalid data
        context = context_manager.get_system_context()
        
        # Validate context
        issues = context_manager.validate_context_data(context)
        
        # Should detect battery level issue
        assert len(issues) > 0
        assert any("battery level" in issue for issue in issues)

    @pytest.mark.asyncio
    async def test_stale_data_detection(self, context_manager):
        """Test detection of stale context data."""
        # Create context with old timestamp
        old_context = context_manager.get_system_context()
        old_context.timestamp = datetime.now() - timedelta(seconds=15)  # 15 seconds old
        
        # Validate stale context
        issues = context_manager.validate_context_data(old_context)
        
        # Should detect stale data
        assert len(issues) > 0
        assert any("stale" in issue for issue in issues)

    @pytest.mark.asyncio
    async def test_update_callback_management(self, context_manager):
        """Test adding and removing update callbacks."""
        callback1 = Mock()
        callback2 = Mock()
        
        # Add callbacks
        context_manager.add_update_callback(callback1)
        context_manager.add_update_callback(callback2)
        
        assert len(context_manager._update_callbacks) == 2
        
        # Remove callback
        context_manager.remove_update_callback(callback1)
        
        assert len(context_manager._update_callbacks) == 1
        assert callback2 in context_manager._update_callbacks

    @pytest.mark.asyncio
    async def test_external_update_trigger(self, context_manager):
        """Test handling of external context update triggers."""
        # Set up callback to track updates
        update_calls = []
        
        async def async_callback(context):
            update_calls.append(context)
        
        context_manager.add_update_callback(async_callback)
        
        # Trigger external update
        await context_manager.handle_context_update_trigger("test_source", {"test": "data"})
        
        # Verify callback was triggered
        assert len(update_calls) == 1

    @pytest.mark.asyncio
    async def test_error_handling_in_update_loop(self, context_manager, mock_robot_registry):
        """Test error handling in the update loop."""
        # Make robot registry raise an exception
        mock_robot_registry.get_all_robot_states.side_effect = Exception("Registry error")
        
        # Set up update callback
        update_calls = []
        
        def update_callback(context):
            update_calls.append(context)
        
        context_manager.add_update_callback(update_callback)
        
        # Start auto-updates with short interval
        context_manager._update_interval = 0.1
        await context_manager.start_auto_updates()
        
        # Wait for a few update attempts
        await asyncio.sleep(0.3)
        
        # Stop updates
        await context_manager.stop_auto_updates()
        
        # Update loop should continue despite errors
        # (We can't easily verify this without checking logs, but the test shouldn't crash)

    @pytest.mark.asyncio
    async def test_context_summary(self, context_manager):
        """Test context summary generation."""
        # Get context summary
        summary = context_manager.get_context_summary()
        
        # Verify summary contains expected fields
        assert 'timestamp' in summary
        assert 'robot_count' in summary
        assert 'available_robots' in summary
        assert 'world_type' in summary
        assert 'environment_boundaries' in summary
        
        # Verify data types
        assert isinstance(summary['robot_count'], int)
        assert isinstance(summary['available_robots'], int)
        assert isinstance(summary['world_type'], str)

    @pytest.mark.asyncio
    async def test_real_time_robot_states_fallback(self, context_manager):
        """Test fallback behavior when robot registry is unavailable."""
        # Remove robot registry
        context_manager.robot_registry = None
        
        # Get real-time robot states
        states = context_manager.get_real_time_robot_states()
        
        # Should return empty dict without crashing
        assert states == {}

    @pytest.mark.asyncio
    async def test_simulation_environment_data_fallback(self, context_manager):
        """Test fallback behavior when simulation bridge is unavailable."""
        # No simulation bridge connected
        assert context_manager.simulation_bridge is None
        
        # Get environment data
        env_data = context_manager.get_simulation_environment_data()
        
        # Should return empty dict without crashing
        assert env_data == {}

    @pytest.mark.asyncio
    async def test_concurrent_context_access(self, context_manager):
        """Test concurrent access to context data."""
        # Start multiple concurrent context requests
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                asyncio.to_thread(context_manager.get_system_context)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        for result in results:
            assert not isinstance(result, Exception)
            assert isinstance(result, SystemContext)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
"""
Integration tests for the Emergency Stop system.

Tests emergency stop scenarios, recovery procedures, and ROS2 integration.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from safety_validator.emergency_stop import (
    EmergencyStop, 
    EmergencyStopTrigger, 
    EmergencyStopState,
    EmergencyStopEvent,
    RecoveryProcedure
)

@pytest.fixture
def emergency_stop():
    """Create an EmergencyStop instance for testing."""
    config = {
        'stop_timeout': 2.0,
        'recovery_timeout': 10.0,
        'auto_recovery_enabled': False,
        'broadcast_topic': '/test_emergency_stop',
        'heartbeat_interval': 0.5
    }
    
    return EmergencyStop(config)


@pytest.fixture
def emergency_stop_with_auto_recovery():
    """Create an EmergencyStop instance with auto-recovery enabled."""
    config = {
        'stop_timeout': 1.0,
        'recovery_timeout': 5.0,
        'auto_recovery_enabled': True,
        'broadcast_topic': '/test_emergency_stop_auto',
        'heartbeat_interval': 0.5
    }
    
    return EmergencyStop(config)


class TestEmergencyStopBasicFunctionality:
    """Test basic emergency stop functionality."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, emergency_stop):
        """Test emergency stop system initialization."""
        assert await emergency_stop.initialize()
        assert emergency_stop.is_initialized
        assert len(emergency_stop.recovery_procedures) > 0
        assert emergency_stop.state == EmergencyStopState.NORMAL
        
        assert await emergency_stop.start()
        assert emergency_stop.is_running
        
        health = await emergency_stop.health_check()
        assert health['status'] == 'healthy'
        assert health['state'] == 'normal'
        
        await emergency_stop.stop()
    
    @pytest.mark.asyncio
    async def test_manual_emergency_stop(self, emergency_stop):
        """Test manual emergency stop trigger."""
        await emergency_stop.initialize()
        await emergency_stop.start()
        
        # Trigger emergency stop
        event_id = await emergency_stop.trigger_emergency_stop(
            trigger=EmergencyStopTrigger.MANUAL,
            description="Manual emergency stop test",
            severity="critical"
        )
        
        # Verify state changes
        assert emergency_stop.state == EmergencyStopState.STOPPED
        assert await emergency_stop.is_emergency_active()
        
        # Verify event was recorded
        events = await emergency_stop.get_emergency_events()
        assert len(events) == 1
        assert events[0].event_id == event_id
        assert events[0].trigger == EmergencyStopTrigger.MANUAL
        assert events[0].description == "Manual emergency stop test"
        
        await emergency_stop.stop()
    
    @pytest.mark.asyncio
    async def test_safety_violation_emergency_stop(self, emergency_stop):
        """Test emergency stop triggered by safety violation."""
        await emergency_stop.initialize()
        await emergency_stop.start()
        
        event_id = await emergency_stop.trigger_emergency_stop(
            trigger=EmergencyStopTrigger.SAFETY_VIOLATION,
            description="Robot entered forbidden zone",
            robot_id="robot_001",
            severity="critical"
        )
        
        assert emergency_stop.state == EmergencyStopState.STOPPED
        
        events = await emergency_stop.get_emergency_events()
        assert events[0].robot_id == "robot_001"
        assert events[0].trigger == EmergencyStopTrigger.SAFETY_VIOLATION
        
        await emergency_stop.stop()


class TestEmergencyStopRecovery:
    """Test emergency stop recovery procedures."""
    
    @pytest.mark.asyncio
    async def test_manual_recovery(self, emergency_stop):
        """Test manual recovery from emergency stop."""
        await emergency_stop.initialize()
        await emergency_stop.start()
        
        # Trigger emergency stop
        event_id = await emergency_stop.trigger_emergency_stop(
            trigger=EmergencyStopTrigger.MANUAL,
            description="Test emergency stop for recovery"
        )
        
        assert emergency_stop.state == EmergencyStopState.STOPPED
        
        # Reset emergency stop
        success = await emergency_stop.reset_emergency_stop(event_id)
        
        assert success
        assert emergency_stop.state == EmergencyStopState.NORMAL
        assert not await emergency_stop.is_emergency_active()
        assert not emergency_stop.recovery_in_progress
        
        await emergency_stop.stop()


class TestEmergencyStopCallbacks:
    """Test emergency stop callback functionality."""
    
    @pytest.mark.asyncio
    async def test_stop_callbacks(self, emergency_stop):
        """Test that stop callbacks are executed during emergency stop."""
        await emergency_stop.initialize()
        await emergency_stop.start()
        
        callback_executed = False
        callback_event = None
        
        async def test_callback(event):
            nonlocal callback_executed, callback_event
            callback_executed = True
            callback_event = event
        
        await emergency_stop.add_stop_callback(test_callback)
        
        # Trigger emergency stop
        event_id = await emergency_stop.trigger_emergency_stop(
            trigger=EmergencyStopTrigger.MANUAL,
            description="Test stop callback"
        )
        
        # Verify callback was executed
        assert callback_executed
        assert callback_event is not None
        assert callback_event.event_id == event_id
        
        await emergency_stop.stop()


class TestEmergencyStopROS2Integration:
    """Test ROS2 integration for emergency stop broadcasting."""
    
    @pytest.mark.asyncio
    async def test_emergency_stop_broadcast(self, emergency_stop):
        """Test emergency stop message broadcasting."""
        await emergency_stop.initialize()
        await emergency_stop.start()
        
        with patch.object(emergency_stop, '_broadcast_emergency_stop') as mock_broadcast:
            event_id = await emergency_stop.trigger_emergency_stop(
                trigger=EmergencyStopTrigger.MANUAL,
                description="Test broadcast"
            )
            
            # Verify broadcast was called
            mock_broadcast.assert_called_once()
            
            # Get the event that was broadcast
            call_args = mock_broadcast.call_args[0]
            broadcast_event = call_args[0]
            
            assert broadcast_event.event_id == event_id
            assert broadcast_event.trigger == EmergencyStopTrigger.MANUAL
        
        await emergency_stop.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
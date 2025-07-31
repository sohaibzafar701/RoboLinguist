"""
Integration tests for RobotRegistry with simulated robot nodes.

Tests robot registration, health monitoring, capability discovery,
and fleet management functionality.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import Set

from task_orchestrator.robot_registry import RobotRegistry, RobotInfo, RobotCapability
from core.data_models import RobotState, RobotStatus


class TestRobotRegistry:
    """Test suite for RobotRegistry functionality."""
    
    @pytest.fixture
    def registry(self):
        """Create a RobotRegistry instance for testing."""
        config = {
            'heartbeat_timeout': 2.0,
            'health_check_interval': 0.5
        }
        return RobotRegistry(config)
    
    @pytest.fixture
    def sample_robot_state(self):
        """Create a sample robot state for testing."""
        return RobotState(
            robot_id="test_robot_1",
            position=(1.0, 2.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.IDLE,
            battery_level=85.0,
            current_task=None
        )
    
    @pytest.fixture
    def sample_capabilities(self):
        """Create sample robot capabilities."""
        return {RobotCapability.NAVIGATION, RobotCapability.INSPECTION}
    
    @pytest.mark.asyncio
    async def test_registry_lifecycle(self, registry):
        """Test registry start and stop lifecycle."""
        assert not registry._monitoring_active
        
        await registry.start()
        assert registry._monitoring_active
        assert registry._monitor_thread is not None
        assert registry._monitor_thread.is_alive()
        
        await registry.stop()
        assert not registry._monitoring_active
    
    def test_robot_registration(self, registry, sample_robot_state, sample_capabilities):
        """Test robot registration functionality."""
        robot_id = "test_robot_1"
        
        # Test successful registration
        result = registry.register_robot(robot_id, sample_robot_state, sample_capabilities)
        assert result is True
        
        # Verify robot is registered
        robot_info = registry.get_robot_info(robot_id)
        assert robot_info is not None
        assert robot_info.robot_id == robot_id
        assert robot_info.state == sample_robot_state
        assert robot_info.capabilities == sample_capabilities
        
        # Test re-registration (should update existing)
        new_state = RobotState(
            robot_id=robot_id,
            position=(2.0, 3.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.MOVING,
            battery_level=75.0
        )
        
        result = registry.register_robot(robot_id, new_state)
        assert result is True
        
        updated_info = registry.get_robot_info(robot_id)
        assert updated_info.state == new_state
    
    def test_robot_unregistration(self, registry, sample_robot_state):
        """Test robot unregistration functionality."""
        robot_id = "test_robot_1"
        
        # Register robot first
        registry.register_robot(robot_id, sample_robot_state)
        assert registry.get_robot_info(robot_id) is not None
        
        # Test successful unregistration
        result = registry.unregister_robot(robot_id)
        assert result is True
        assert registry.get_robot_info(robot_id) is None
        
        # Test unregistering non-existent robot
        result = registry.unregister_robot("non_existent")
        assert result is False
    
    def test_robot_state_update(self, registry, sample_robot_state):
        """Test robot state update functionality."""
        robot_id = "test_robot_1"
        
        # Register robot first
        registry.register_robot(robot_id, sample_robot_state)
        
        # Update state
        new_state = RobotState(
            robot_id=robot_id,
            position=(5.0, 6.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.EXECUTING,
            battery_level=60.0,
            current_task="task_123"
        )
        
        result = registry.update_robot_state(robot_id, new_state)
        assert result is True
        
        # Verify state was updated
        robot_info = registry.get_robot_info(robot_id)
        assert robot_info.state == new_state
        
        # Test updating non-existent robot
        result = registry.update_robot_state("non_existent", new_state)
        assert result is False
    
    def test_heartbeat_functionality(self, registry, sample_robot_state):
        """Test robot heartbeat functionality."""
        robot_id = "test_robot_1"
        
        # Register robot first
        registry.register_robot(robot_id, sample_robot_state)
        robot_info = registry.get_robot_info(robot_id)
        initial_heartbeat = robot_info.last_heartbeat
        
        # Wait a bit and send heartbeat
        time.sleep(0.1)
        result = registry.heartbeat(robot_id)
        assert result is True
        
        # Verify heartbeat was updated
        updated_info = registry.get_robot_info(robot_id)
        assert updated_info.last_heartbeat > initial_heartbeat
        assert updated_info.is_healthy is True
        assert updated_info.consecutive_missed_heartbeats == 0
        
        # Test heartbeat for non-existent robot
        result = registry.heartbeat("non_existent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, registry, sample_robot_state):
        """Test automated health monitoring."""
        robot_id = "test_robot_1"
        
        # Start registry with short intervals for testing
        await registry.start()
        
        # Register robot
        registry.register_robot(robot_id, sample_robot_state)
        robot_info = registry.get_robot_info(robot_id)
        assert robot_info.is_healthy is True
        
        # Simulate missed heartbeats by setting old timestamp
        old_time = datetime.now() - timedelta(seconds=10)
        robot_info.last_heartbeat = old_time
        robot_info.consecutive_missed_heartbeats = 3
        
        # Wait for health check to run
        await asyncio.sleep(1.0)
        
        # Robot should be marked as unhealthy
        updated_info = registry.get_robot_info(robot_id)
        assert updated_info.is_healthy is False
        
        await registry.stop()
    
    def test_available_robots_query(self, registry):
        """Test querying available robots."""
        # Create robots with different states
        idle_robot = RobotState(
            robot_id="idle_robot",
            position=(0.0, 0.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.IDLE,
            battery_level=80.0
        )
        
        busy_robot = RobotState(
            robot_id="busy_robot",
            position=(1.0, 1.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.EXECUTING,
            battery_level=70.0
        )
        
        low_battery_robot = RobotState(
            robot_id="low_battery_robot",
            position=(2.0, 2.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.IDLE,
            battery_level=5.0  # Below 10% threshold
        )
        
        # Register robots
        registry.register_robot("idle_robot", idle_robot)
        registry.register_robot("busy_robot", busy_robot)
        registry.register_robot("low_battery_robot", low_battery_robot)
        
        # Query available robots
        available = registry.get_available_robots()
        assert "idle_robot" in available
        assert "busy_robot" not in available
        assert "low_battery_robot" not in available
    
    def test_capability_queries(self, registry, sample_robot_state):
        """Test capability-based robot queries."""
        # Register robots with different capabilities
        nav_robot_caps = {RobotCapability.NAVIGATION}
        manip_robot_caps = {RobotCapability.NAVIGATION, RobotCapability.MANIPULATION}
        full_robot_caps = {RobotCapability.NAVIGATION, RobotCapability.MANIPULATION, 
                          RobotCapability.INSPECTION}
        
        registry.register_robot("nav_robot", sample_robot_state, nav_robot_caps)
        registry.register_robot("manip_robot", sample_robot_state, manip_robot_caps)
        registry.register_robot("full_robot", sample_robot_state, full_robot_caps)
        
        # Query by capability
        nav_robots = registry.get_robots_by_capability(RobotCapability.NAVIGATION)
        assert len(nav_robots) == 3
        assert all(robot in nav_robots for robot in ["nav_robot", "manip_robot", "full_robot"])
        
        manip_robots = registry.get_robots_by_capability(RobotCapability.MANIPULATION)
        assert len(manip_robots) == 2
        assert all(robot in manip_robots for robot in ["manip_robot", "full_robot"])
        
        inspect_robots = registry.get_robots_by_capability(RobotCapability.INSPECTION)
        assert len(inspect_robots) == 1
        assert "full_robot" in inspect_robots
    
    def test_fleet_status(self, registry):
        """Test fleet status reporting."""
        # Register robots with various states
        states = [
            RobotState(robot_id="robot1", position=(0,0,0), orientation=(0,0,0,1), 
                      status=RobotStatus.IDLE, battery_level=80.0),
            RobotState(robot_id="robot2", position=(1,1,0), orientation=(0,0,0,1), 
                      status=RobotStatus.MOVING, battery_level=70.0),
            RobotState(robot_id="robot3", position=(2,2,0), orientation=(0,0,0,1), 
                      status=RobotStatus.ERROR, battery_level=60.0)
        ]
        
        capabilities = [
            {RobotCapability.NAVIGATION},
            {RobotCapability.NAVIGATION, RobotCapability.MANIPULATION},
            {RobotCapability.INSPECTION}
        ]
        
        for i, (state, caps) in enumerate(zip(states, capabilities)):
            registry.register_robot(f"robot{i+1}", state, caps)
        
        # Get fleet status
        status = registry.get_fleet_status()
        
        assert status['total_robots'] == 3
        assert status['healthy_robots'] == 3  # All healthy initially
        assert status['available_robots'] == 1  # Only idle robot available
        assert status['status_distribution'][RobotStatus.IDLE] == 1
        assert status['status_distribution'][RobotStatus.MOVING] == 1
        assert status['status_distribution'][RobotStatus.ERROR] == 1
        assert status['capability_distribution'][RobotCapability.NAVIGATION] == 2
        assert status['capability_distribution'][RobotCapability.MANIPULATION] == 1
        assert status['capability_distribution'][RobotCapability.INSPECTION] == 1
    
    def test_capability_discovery(self, registry):
        """Test robot capability discovery."""
        # Test TIAGo robot discovery
        tiago_caps = registry.discover_robot_capabilities("tiago_001")
        expected_tiago = {RobotCapability.NAVIGATION, RobotCapability.MANIPULATION,
                         RobotCapability.INSPECTION, RobotCapability.SENSING}
        assert tiago_caps == expected_tiago
        
        # Test mobile robot discovery
        mobile_caps = registry.discover_robot_capabilities("mobile_001")
        expected_mobile = {RobotCapability.NAVIGATION, RobotCapability.SENSING}
        assert mobile_caps == expected_mobile
        
        # Test generic robot discovery
        generic_caps = registry.discover_robot_capabilities("generic_001")
        expected_generic = {RobotCapability.NAVIGATION}
        assert generic_caps == expected_generic


class TestRobotInfo:
    """Test suite for RobotInfo functionality."""
    
    @pytest.fixture
    def robot_info(self):
        """Create a RobotInfo instance for testing."""
        state = RobotState(
            robot_id="test_robot",
            position=(0.0, 0.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=RobotStatus.IDLE,
            battery_level=80.0
        )
        return RobotInfo(
            robot_id="test_robot",
            state=state,
            capabilities={RobotCapability.NAVIGATION},
            heartbeat_interval=1.0,
            max_missed_heartbeats=2
        )
    
    def test_heartbeat_update(self, robot_info):
        """Test heartbeat update functionality."""
        initial_time = robot_info.last_heartbeat
        initial_missed = robot_info.consecutive_missed_heartbeats = 1
        robot_info.is_healthy = False
        
        # Update heartbeat
        time.sleep(0.1)
        robot_info.update_heartbeat()
        
        # Verify updates
        assert robot_info.last_heartbeat > initial_time
        assert robot_info.consecutive_missed_heartbeats == 0
        assert robot_info.is_healthy is True
    
    def test_health_check(self, robot_info):
        """Test health check functionality."""
        # Robot should be healthy initially
        assert robot_info.check_health() is True
        assert robot_info.is_healthy is True
        
        # Simulate old heartbeat
        robot_info.last_heartbeat = datetime.now() - timedelta(seconds=5)
        robot_info.consecutive_missed_heartbeats = 2
        
        # Health check should mark as unhealthy
        assert robot_info.check_health() is False
        assert robot_info.is_healthy is False
    
    def test_availability_check(self, robot_info):
        """Test robot availability for tasks."""
        # Should be available initially (healthy, idle, good battery)
        assert robot_info.is_available_for_task() is True
        
        # Test unhealthy robot
        robot_info.is_healthy = False
        assert robot_info.is_available_for_task() is False
        
        # Reset health, test busy robot
        robot_info.is_healthy = True
        robot_info.state.status = RobotStatus.EXECUTING
        assert robot_info.is_available_for_task() is False
        
        # Reset status, test low battery
        robot_info.state.status = RobotStatus.IDLE
        robot_info.state.battery_level = 5.0
        assert robot_info.is_available_for_task() is False


class TestIntegrationScenarios:
    """Integration test scenarios with multiple simulated robots."""
    
    @pytest.mark.asyncio
    async def test_multi_robot_fleet_simulation(self):
        """Test complete fleet simulation with multiple robots."""
        registry = RobotRegistry({
            'heartbeat_timeout': 1.0,
            'health_check_interval': 0.2
        })
        
        await registry.start()
        
        try:
            # Simulate robot fleet registration
            robot_configs = [
                ("tiago_001", RobotStatus.IDLE, 90.0, {RobotCapability.NAVIGATION, RobotCapability.MANIPULATION}),
                ("tiago_002", RobotStatus.IDLE, 85.0, {RobotCapability.NAVIGATION, RobotCapability.INSPECTION}),
                ("mobile_001", RobotStatus.MOVING, 70.0, {RobotCapability.NAVIGATION}),
                ("mobile_002", RobotStatus.ERROR, 45.0, {RobotCapability.NAVIGATION, RobotCapability.SENSING})
            ]
            
            # Register all robots
            for robot_id, status, battery, capabilities in robot_configs:
                state = RobotState(
                    robot_id=robot_id,
                    position=(0.0, 0.0, 0.0),
                    orientation=(0.0, 0.0, 0.0, 1.0),
                    status=status,
                    battery_level=battery
                )
                registry.register_robot(robot_id, state, capabilities)
            
            # Verify fleet status
            status = registry.get_fleet_status()
            assert status['total_robots'] == 4
            assert status['healthy_robots'] == 4
            
            # Simulate heartbeats for all robots to keep them healthy
            for _ in range(5):
                for robot_id, _, _, _ in robot_configs:
                    registry.heartbeat(robot_id)
                await asyncio.sleep(0.1)
            
            # Test capability-based task assignment with healthy robots
            nav_robots = registry.get_robots_by_capability(RobotCapability.NAVIGATION)
            assert len(nav_robots) >= 2  # At least healthy navigation robots
            
            manip_robots = registry.get_robots_by_capability(RobotCapability.MANIPULATION)
            assert len(manip_robots) >= 1  # At least one manipulation robot
            
            # Now simulate some robots going offline (no heartbeats)
            await asyncio.sleep(2.0)  # Wait for health check to detect missing heartbeats
            
            # Check that robots without heartbeats are marked unhealthy
            updated_status = registry.get_fleet_status()
            assert updated_status['unhealthy_robots'] > 0
            
        finally:
            await registry.stop()
    
    @pytest.mark.asyncio
    async def test_robot_failure_recovery(self):
        """Test robot failure detection and recovery."""
        registry = RobotRegistry({
            'heartbeat_timeout': 0.5,
            'health_check_interval': 0.1
        })
        
        await registry.start()
        
        try:
            # Register robot
            state = RobotState(
                robot_id="test_robot",
                position=(0.0, 0.0, 0.0),
                orientation=(0.0, 0.0, 0.0, 1.0),
                status=RobotStatus.IDLE,
                battery_level=80.0
            )
            registry.register_robot("test_robot", state)
            
            # Robot should be healthy and available initially
            assert "test_robot" in registry.get_healthy_robots()
            assert "test_robot" in registry.get_available_robots()
            
            # Simulate robot failure (stop sending heartbeats)
            await asyncio.sleep(1.5)  # Wait longer than heartbeat timeout
            
            # Robot should be marked unhealthy
            assert "test_robot" not in registry.get_healthy_robots()
            assert "test_robot" not in registry.get_available_robots()
            
            # Simulate robot recovery (resume heartbeats)
            registry.heartbeat("test_robot")
            
            # Robot should be healthy again
            assert "test_robot" in registry.get_healthy_robots()
            assert "test_robot" in registry.get_available_robots()
            
        finally:
            await registry.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
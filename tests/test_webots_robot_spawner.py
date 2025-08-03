#!/usr/bin/env python3
"""
Test suite for WebotsRobotSpawner.

Tests robot spawning, formation patterns, collision avoidance,
and integration with the Webots simulation system.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Import the component to test
from simulation.webots_robot_spawner import (
    WebotsRobotSpawner,
    RobotSpawnConfig,
    SpawnedRobotInfo
)
from simulation.webots_manager import WebotsManager
from config.config_manager import ConfigManager


class TestWebotsRobotSpawner:
    """Test suite for WebotsRobotSpawner."""
    
    @pytest.fixture
    def config_manager(self):
        """Create mock config manager."""
        config = {
            'robot_spawner': {
                'spawn_config': {
                    'robot_type': 'e-puck',
                    'controller': 'fleet_controller',
                    'spawn_pattern': 'grid',
                    'spacing': 1.0,
                    'max_robots': 20
                }
            }
        }
        
        mock_config = Mock(spec=ConfigManager)
        mock_config.get.side_effect = lambda key, default=None: config.get(key, default)
        return mock_config
    
    @pytest.fixture
    def robot_spawner(self, config_manager):
        """Create WebotsRobotSpawner instance."""
        return WebotsRobotSpawner(config_manager)
    
    @pytest.fixture
    def mock_webots_manager(self):
        """Create mock Webots manager."""
        mock_manager = Mock(spec=WebotsManager)
        mock_manager.robots = {}
        mock_manager.robot_states = {}
        mock_manager.get_simulation_status.return_value = {
            'running': True,
            'robot_count': 0
        }
        return mock_manager
    
    @pytest.fixture
    def sample_spawn_config(self):
        """Sample spawn configuration for testing."""
        return RobotSpawnConfig(
            robot_id='test_robot_1',
            robot_type='e-puck',
            position={'x': 1.0, 'y': 2.0, 'z': 0.0, 'yaw': 0.0},
            controller='fleet_controller',
            initial_battery=100.0
        )
    
    def test_initialization(self, robot_spawner):
        """Test robot spawner initialization."""
        assert robot_spawner.component_name == "WebotsRobotSpawner"
        assert len(robot_spawner.spawned_robots) == 0
        assert len(robot_spawner.spawn_history) == 0
        assert len(robot_spawner.robot_types) > 0
        assert 'e-puck' in robot_spawner.robot_types
        assert len(robot_spawner.spawn_positions) > 0
    
    def test_robot_spawn_config_dataclass(self):
        """Test RobotSpawnConfig dataclass."""
        config = RobotSpawnConfig(
            robot_id='test_robot',
            robot_type='turtlebot3',
            position={'x': 1.0, 'y': 2.0, 'z': 0.0},
            controller='custom_controller',
            initial_battery=85.0
        )
        
        assert config.robot_id == 'test_robot'
        assert config.robot_type == 'turtlebot3'
        assert config.position['x'] == 1.0
        assert config.controller == 'custom_controller'
        assert config.initial_battery == 85.0
        assert config.capabilities is None  # default
    
    def test_spawned_robot_info_dataclass(self):
        """Test SpawnedRobotInfo dataclass."""
        info = SpawnedRobotInfo(
            robot_id='test_robot',
            robot_type='e-puck',
            spawn_time=datetime.now(),
            position={'x': 0, 'y': 0, 'z': 0},
            status='active',
            controller='fleet_controller',
            capabilities=['navigation', 'sensing']
        )
        
        assert info.robot_id == 'test_robot'
        assert info.robot_type == 'e-puck'
        assert info.status == 'active'
        assert 'navigation' in info.capabilities
    
    def test_webots_manager_integration(self, robot_spawner, mock_webots_manager):
        """Test Webots manager integration."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        assert robot_spawner.webots_manager == mock_webots_manager
    
    def test_initialize_spawn_positions(self, robot_spawner):
        """Test spawn position initialization."""
        positions = robot_spawner.spawn_positions
        
        assert len(positions) == 20  # 5x4 grid
        
        # Check that positions are different
        unique_positions = set((pos['x'], pos['y']) for pos in positions)
        assert len(unique_positions) == len(positions)
        
        # Check that all positions have required keys
        for pos in positions:
            assert 'x' in pos
            assert 'y' in pos
            assert 'z' in pos
            assert 'yaw' in pos
    
    @pytest.mark.asyncio
    async def test_spawn_robot_success(self, robot_spawner, mock_webots_manager, sample_spawn_config):
        """Test successful robot spawning."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        success = await robot_spawner.spawn_robot(sample_spawn_config, mock_webots_manager)
        
        assert success is True
        assert sample_spawn_config.robot_id in robot_spawner.spawned_robots
        assert len(robot_spawner.spawn_history) == 1
        
        # Check that robot was added to webots manager
        assert sample_spawn_config.robot_id in mock_webots_manager.robots
        assert sample_spawn_config.robot_id in mock_webots_manager.robot_states
    
    @pytest.mark.asyncio
    async def test_spawn_robot_duplicate_id(self, robot_spawner, mock_webots_manager, sample_spawn_config):
        """Test spawning robot with duplicate ID."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        # Spawn first robot
        await robot_spawner.spawn_robot(sample_spawn_config, mock_webots_manager)
        
        # Try to spawn with same ID
        success = await robot_spawner.spawn_robot(sample_spawn_config, mock_webots_manager)
        
        assert success is False
        assert len(robot_spawner.spawned_robots) == 1  # Should still be 1
    
    @pytest.mark.asyncio
    async def test_spawn_robot_unknown_type(self, robot_spawner, mock_webots_manager):
        """Test spawning robot with unknown type."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        config = RobotSpawnConfig(
            robot_id='test_robot',
            robot_type='unknown_robot_type',
            position={'x': 0, 'y': 0, 'z': 0}
        )
        
        success = await robot_spawner.spawn_robot(config, mock_webots_manager)
        assert success is False
    
    @pytest.mark.asyncio
    async def test_spawn_multiple_robots_success(self, robot_spawner, mock_webots_manager):
        """Test spawning multiple robots."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        spawned_ids = await robot_spawner.spawn_multiple_robots(
            robot_count=3,
            webots_manager=mock_webots_manager,
            robot_type='e-puck',
            name_prefix='test_robot'
        )
        
        assert len(spawned_ids) == 3
        assert 'test_robot_0' in spawned_ids
        assert 'test_robot_2' in spawned_ids
        assert len(robot_spawner.spawned_robots) == 3
    
    @pytest.mark.asyncio
    async def test_spawn_multiple_robots_zero_count(self, robot_spawner, mock_webots_manager):
        """Test spawning zero robots."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        spawned_ids = await robot_spawner.spawn_multiple_robots(
            robot_count=0,
            webots_manager=mock_webots_manager
        )
        
        assert len(spawned_ids) == 0
    
    @pytest.mark.asyncio
    async def test_remove_robot_success(self, robot_spawner, mock_webots_manager, sample_spawn_config):
        """Test successful robot removal."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        # First spawn a robot
        await robot_spawner.spawn_robot(sample_spawn_config, mock_webots_manager)
        
        # Then remove it
        success = await robot_spawner.remove_robot(sample_spawn_config.robot_id, mock_webots_manager)
        
        assert success is True
        assert sample_spawn_config.robot_id not in robot_spawner.spawned_robots
        assert sample_spawn_config.robot_id not in mock_webots_manager.robots
        assert sample_spawn_config.robot_id not in mock_webots_manager.robot_states
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_robot(self, robot_spawner, mock_webots_manager):
        """Test removing non-existent robot."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        success = await robot_spawner.remove_robot('nonexistent_robot', mock_webots_manager)
        assert success is False
    
    def test_get_spawned_robots(self, robot_spawner):
        """Test getting spawned robots information."""
        # Add a spawned robot manually for testing
        robot_info = SpawnedRobotInfo(
            robot_id='test_robot',
            robot_type='e-puck',
            spawn_time=datetime.now(),
            position={'x': 0, 'y': 0, 'z': 0},
            status='active',
            controller='fleet_controller',
            capabilities=['navigation']
        )
        robot_spawner.spawned_robots['test_robot'] = robot_info
        
        spawned_robots = robot_spawner.get_spawned_robots()
        
        assert len(spawned_robots) == 1
        assert 'test_robot' in spawned_robots
        assert spawned_robots['test_robot'] == robot_info
    
    def test_get_robot_info(self, robot_spawner):
        """Test getting specific robot information."""
        # Add a spawned robot manually for testing
        robot_info = SpawnedRobotInfo(
            robot_id='test_robot',
            robot_type='e-puck',
            spawn_time=datetime.now(),
            position={'x': 0, 'y': 0, 'z': 0},
            status='active',
            controller='fleet_controller',
            capabilities=['navigation']
        )
        robot_spawner.spawned_robots['test_robot'] = robot_info
        
        retrieved_info = robot_spawner.get_robot_info('test_robot')
        assert retrieved_info == robot_info
        
        # Test non-existent robot
        assert robot_spawner.get_robot_info('nonexistent') is None
    
    def test_get_available_robot_types(self, robot_spawner):
        """Test getting available robot types."""
        robot_types = robot_spawner.get_available_robot_types()
        
        assert len(robot_types) > 0
        assert 'e-puck' in robot_types
        assert 'turtlebot3' in robot_types
        assert 'pioneer3dx' in robot_types
        
        # Check structure
        epuck_info = robot_types['e-puck']
        assert 'model_name' in epuck_info
        assert 'capabilities' in epuck_info
        assert 'sensors' in epuck_info
        assert 'max_speed' in epuck_info
    
    def test_get_robot_capabilities(self, robot_spawner):
        """Test getting robot capabilities."""
        capabilities = robot_spawner.get_robot_capabilities('e-puck')
        
        assert len(capabilities) > 0
        assert 'navigation' in capabilities
        assert 'sensing' in capabilities
        
        # Test unknown robot type
        unknown_capabilities = robot_spawner.get_robot_capabilities('unknown_type')
        assert len(unknown_capabilities) == 0
    
    def test_get_spawn_position_requested(self, robot_spawner):
        """Test getting spawn position with requested position."""
        requested_pos = {'x': 5.0, 'y': 3.0, 'z': 1.0, 'yaw': 1.57}
        
        position = robot_spawner._get_spawn_position(requested_pos)
        
        assert position == requested_pos
    
    def test_get_spawn_position_automatic(self, robot_spawner):
        """Test getting spawn position automatically."""
        # Reset spawn index
        robot_spawner.reset_spawn_positions()
        
        # Get first automatic position
        position1 = robot_spawner._get_spawn_position(None)
        position2 = robot_spawner._get_spawn_position(None)
        
        # Should be different positions
        assert position1 != position2
        
        # Should use predefined positions
        assert position1 in robot_spawner.spawn_positions
        assert position2 in robot_spawner.spawn_positions
    
    def test_get_spawn_position_overflow(self, robot_spawner):
        """Test getting spawn position when predefined positions are exhausted."""
        # Set spawn index beyond predefined positions
        robot_spawner.next_spawn_index = len(robot_spawner.spawn_positions) + 5
        
        position = robot_spawner._get_spawn_position(None)
        
        # Should generate a new position
        assert position not in robot_spawner.spawn_positions
        assert 'x' in position
        assert 'y' in position
        assert 'z' in position
        assert 'yaw' in position
    
    def test_reset_spawn_positions(self, robot_spawner):
        """Test resetting spawn positions."""
        robot_spawner.next_spawn_index = 10
        
        robot_spawner.reset_spawn_positions()
        
        assert robot_spawner.next_spawn_index == 0
    
    def test_add_custom_spawn_position(self, robot_spawner):
        """Test adding custom spawn position."""
        initial_count = len(robot_spawner.spawn_positions)
        custom_pos = {'x': 10.0, 'y': 10.0, 'z': 0.0, 'yaw': 0.0}
        
        robot_spawner.add_custom_spawn_position(custom_pos)
        
        assert len(robot_spawner.spawn_positions) == initial_count + 1
        assert custom_pos in robot_spawner.spawn_positions
    
    def test_set_spawn_positions(self, robot_spawner):
        """Test setting custom spawn positions."""
        custom_positions = [
            {'x': 1.0, 'y': 1.0, 'z': 0.0, 'yaw': 0.0},
            {'x': 2.0, 'y': 2.0, 'z': 0.0, 'yaw': 0.0}
        ]
        
        robot_spawner.set_spawn_positions(custom_positions)
        
        assert robot_spawner.spawn_positions == custom_positions
        assert robot_spawner.next_spawn_index == 0
    
    def test_get_spawn_summary(self, robot_spawner):
        """Test getting spawn summary."""
        # Add some spawned robots manually for testing
        robot_info1 = SpawnedRobotInfo(
            robot_id='robot_1',
            robot_type='e-puck',
            spawn_time=datetime.now(),
            position={'x': 0, 'y': 0, 'z': 0},
            status='active',
            controller='fleet_controller',
            capabilities=['navigation']
        )
        robot_info2 = SpawnedRobotInfo(
            robot_id='robot_2',
            robot_type='turtlebot3',
            spawn_time=datetime.now(),
            position={'x': 1, 'y': 1, 'z': 0},
            status='active',
            controller='fleet_controller',
            capabilities=['navigation']
        )
        
        robot_spawner.spawned_robots['robot_1'] = robot_info1
        robot_spawner.spawned_robots['robot_2'] = robot_info2
        robot_spawner.next_spawn_index = 5
        
        summary = robot_spawner.get_spawn_summary()
        
        assert summary['total_robots'] == 2
        assert summary['robot_types']['e-puck'] == 1
        assert summary['robot_types']['turtlebot3'] == 1
        assert summary['next_spawn_index'] == 5
        assert 'robot_1' in summary['spawned_robots']
        assert 'robot_2' in summary['spawned_robots']
    
    @pytest.mark.asyncio
    async def test_validate_robot_spawning_healthy(self, robot_spawner, mock_webots_manager):
        """Test robot spawning validation - healthy state."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        validation = await robot_spawner.validate_robot_spawning(5, mock_webots_manager)
        
        assert validation['can_spawn'] is True
        assert len(validation['errors']) == 0
    
    @pytest.mark.asyncio
    async def test_validate_robot_spawning_simulation_not_running(self, robot_spawner, mock_webots_manager):
        """Test robot spawning validation - simulation not running."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        mock_webots_manager.get_simulation_status.return_value = {'running': False}
        
        validation = await robot_spawner.validate_robot_spawning(5, mock_webots_manager)
        
        assert validation['can_spawn'] is False
        assert any('not running' in error for error in validation['errors'])
    
    @pytest.mark.asyncio
    async def test_validate_robot_spawning_too_many_robots(self, robot_spawner, mock_webots_manager):
        """Test robot spawning validation - too many robots."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        validation = await robot_spawner.validate_robot_spawning(100, mock_webots_manager)
        
        assert validation['can_spawn'] is False
        assert any('exceeds limit' in error for error in validation['errors'])
    
    @pytest.mark.asyncio
    async def test_validate_robot_spawning_high_count_warning(self, robot_spawner, mock_webots_manager):
        """Test robot spawning validation - high count warning."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        validation = await robot_spawner.validate_robot_spawning(25, mock_webots_manager)
        
        assert validation['can_spawn'] is True
        assert len(validation['warnings']) > 0
        assert any('High robot count' in warning for warning in validation['warnings'])
    
    def test_generate_robot_entry(self, robot_spawner, sample_spawn_config):
        """Test robot entry generation for world file."""
        position = {'x': 1.0, 'y': 2.0, 'z': 0.0, 'yaw': 0.0}
        
        entry = robot_spawner._generate_robot_entry(sample_spawn_config, position)
        
        assert 'E-puck' in entry  # Model name
        assert 'test_robot_1' in entry  # Robot ID
        assert 'fleet_controller' in entry  # Controller
        assert '1.0 2.0 0.0' in entry  # Position
    
    def test_generate_world_robots_section(self, robot_spawner):
        """Test world robots section generation."""
        configs = [
            RobotSpawnConfig(
                robot_id='robot_0',
                robot_type='e-puck',
                position={'x': 0, 'y': 0, 'z': 0}
            ),
            RobotSpawnConfig(
                robot_id='robot_1',
                robot_type='e-puck',
                position={'x': 1, 'y': 0, 'z': 0}
            )
        ]
        
        section = robot_spawner.generate_world_robots_section(configs)
        
        assert '# Robot Fleet' in section
        assert 'robot_0' in section
        assert 'robot_1' in section
        assert 'E-puck' in section
    
    def test_create_formation_spawn_configs_grid(self, robot_spawner):
        """Test creating grid formation spawn configs."""
        configs = robot_spawner.create_formation_spawn_configs(
            robot_count=4,
            formation_type='grid',
            robot_type='e-puck',
            spacing=2.0
        )
        
        assert len(configs) == 4
        assert all(config.robot_type == 'e-puck' for config in configs)
        assert all(config.robot_id.startswith('robot_') for config in configs)
        
        # Check that positions are different
        positions = [(config.position['x'], config.position['y']) for config in configs]
        assert len(set(positions)) == 4
    
    def test_create_formation_spawn_configs_line(self, robot_spawner):
        """Test creating line formation spawn configs."""
        configs = robot_spawner.create_formation_spawn_configs(
            robot_count=3,
            formation_type='line',
            robot_type='turtlebot3',
            spacing=1.5
        )
        
        assert len(configs) == 3
        assert all(config.robot_type == 'turtlebot3' for config in configs)
        
        # Check line formation (all y should be 0)
        assert all(config.position['y'] == 0.0 for config in configs)
        
        # Check spacing
        x_positions = sorted([config.position['x'] for config in configs])
        assert abs(x_positions[1] - x_positions[0] - 1.5) < 0.01
    
    def test_create_formation_spawn_configs_circle(self, robot_spawner):
        """Test creating circle formation spawn configs."""
        configs = robot_spawner.create_formation_spawn_configs(
            robot_count=4,
            formation_type='circle',
            robot_type='pioneer3dx',
            radius=3.0
        )
        
        assert len(configs) == 4
        assert all(config.robot_type == 'pioneer3dx' for config in configs)
        
        # Check that robots are positioned on circle
        for config in configs:
            distance = (config.position['x']**2 + config.position['y']**2)**0.5
            assert abs(distance - 3.0) < 0.01
    
    def test_robot_types_configuration(self, robot_spawner):
        """Test robot types configuration."""
        robot_types = robot_spawner.robot_types
        
        # Check that all required robot types are present
        required_types = ['e-puck', 'turtlebot3', 'pioneer3dx']
        for robot_type in required_types:
            assert robot_type in robot_types
            
            type_info = robot_types[robot_type]
            assert 'model_name' in type_info
            assert 'capabilities' in type_info
            assert 'sensors' in type_info
            assert 'max_speed' in type_info
            assert 'battery_capacity' in type_info
            assert 'size' in type_info
    
    @pytest.mark.asyncio
    async def test_error_handling_in_spawn_robot(self, robot_spawner, mock_webots_manager):
        """Test error handling in spawn_robot method."""
        robot_spawner.set_webots_manager(mock_webots_manager)
        
        # Create config that will cause an error
        config = RobotSpawnConfig(
            robot_id='test_robot',
            robot_type='e-puck'
        )
        
        # Mock an exception in robot state creation
        with patch('core.data_models.RobotState', side_effect=Exception("Test error")):
            success = await robot_spawner.spawn_robot(config, mock_webots_manager)
            assert success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
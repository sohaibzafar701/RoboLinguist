#!/usr/bin/env python3
"""
Test suite for WebotsEnvironmentController.

Tests environment manipulation, obstacle management, state persistence,
and integration with the Webots simulation system.
"""

import asyncio
import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Import the component to test
from simulation.webots_environment_controller import (
    WebotsEnvironmentController,
    EnvironmentObject,
    EnvironmentState,
    ObstaclePattern
)
from config.config_manager import ConfigManager


class TestWebotsEnvironmentController:
    """Test suite for WebotsEnvironmentController."""
    
    @pytest.fixture
    def config_manager(self):
        """Create mock config manager."""
        config = {
            'environment': {
                'arena_bounds': {
                    'x_min': -5.0, 'x_max': 5.0,
                    'y_min': -5.0, 'y_max': 5.0,
                    'z_min': 0.0, 'z_max': 3.0
                },
                'max_objects': 50,
                'auto_cleanup': True
            }
        }
        
        mock_config = Mock(spec=ConfigManager)
        mock_config.get.side_effect = lambda key, default=None: config.get(key, default)
        return mock_config
    
    @pytest.fixture
    def environment_controller(self, config_manager):
        """Create environment controller instance."""
        return WebotsEnvironmentController(config_manager)
    
    @pytest.fixture
    def mock_webots_manager(self):
        """Create mock Webots manager."""
        mock_manager = Mock()
        mock_manager.get_simulation_status.return_value = {
            'running': True,
            'robot_count': 5
        }
        return mock_manager
    
    @pytest.fixture
    def sample_object_config(self):
        """Sample object configuration for testing."""
        return {
            'object_id': 'test_box_1',
            'object_type': 'box',
            'position': {'x': 1.0, 'y': 2.0, 'z': 0.5},
            'rotation': {'roll': 0, 'pitch': 0, 'yaw': 0},
            'size': {'width': 0.5, 'height': 0.5, 'depth': 0.5},
            'color': {'r': 1.0, 'g': 0.0, 'b': 0.0, 'a': 1.0},
            'material': 'plastic'
        }
    
    def test_initialization(self, environment_controller):
        """Test environment controller initialization."""
        assert environment_controller.component_name == "WebotsEnvironmentController"
        assert len(environment_controller.current_objects) == 0
        assert len(environment_controller.environment_states) == 0
        assert environment_controller.max_objects == 50
        assert len(environment_controller.object_templates) > 0
        assert len(environment_controller.obstacle_patterns) > 0
    
    def test_webots_manager_integration(self, environment_controller, mock_webots_manager):
        """Test Webots manager integration."""
        environment_controller.set_webots_manager(mock_webots_manager)
        assert environment_controller.webots_manager == mock_webots_manager
    
    @pytest.mark.asyncio
    async def test_add_object_success(self, environment_controller, sample_object_config):
        """Test successful object addition."""
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True) as mock_add:
            success = await environment_controller.add_object(sample_object_config)
            
            assert success is True
            assert sample_object_config['object_id'] in environment_controller.current_objects
            assert environment_controller.stats['objects_created'] == 1
            mock_add.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_object_with_template(self, environment_controller):
        """Test object addition using template."""
        object_config = {
            'object_id': 'test_small_box',
            'position': {'x': 0.0, 'y': 0.0, 'z': 0.0}
        }
        
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            success = await environment_controller.add_object(object_config, 'small_box')
            
            assert success is True
            added_object = environment_controller.current_objects['test_small_box']
            assert added_object.object_type == 'box'
            assert added_object.size['width'] == 0.5  # From template
    
    @pytest.mark.asyncio
    async def test_add_object_max_limit(self, environment_controller, sample_object_config):
        """Test object addition when max limit is reached."""
        # Set max objects to 1
        environment_controller.max_objects = 1
        
        # Add first object
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            success1 = await environment_controller.add_object(sample_object_config)
            assert success1 is True
        
        # Try to add second object (should fail)
        sample_object_config['object_id'] = 'test_box_2'
        success2 = await environment_controller.add_object(sample_object_config)
        assert success2 is False
    
    @pytest.mark.asyncio
    async def test_remove_object_success(self, environment_controller, sample_object_config):
        """Test successful object removal."""
        # First add an object
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            await environment_controller.add_object(sample_object_config)
        
        # Then remove it
        with patch.object(environment_controller, '_remove_object_from_simulation', 
                         return_value=True) as mock_remove:
            success = await environment_controller.remove_object(sample_object_config['object_id'])
            
            assert success is True
            assert sample_object_config['object_id'] not in environment_controller.current_objects
            assert environment_controller.stats['objects_removed'] == 1
            mock_remove.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_object(self, environment_controller):
        """Test removal of non-existent object."""
        success = await environment_controller.remove_object('nonexistent_object')
        assert success is False
    
    @pytest.mark.asyncio
    async def test_move_object_success(self, environment_controller, sample_object_config):
        """Test successful object movement."""
        # First add an object
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            await environment_controller.add_object(sample_object_config)
        
        # Then move it
        new_position = {'x': 2.0, 'y': 3.0, 'z': 1.0}
        new_rotation = {'roll': 0, 'pitch': 0, 'yaw': 1.57}
        
        with patch.object(environment_controller, '_move_object_in_simulation', 
                         return_value=True) as mock_move:
            success = await environment_controller.move_object(
                sample_object_config['object_id'], new_position, new_rotation
            )
            
            assert success is True
            moved_object = environment_controller.current_objects[sample_object_config['object_id']]
            assert moved_object.position == new_position
            assert moved_object.rotation == new_rotation
            mock_move.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_obstacle_pattern(self, environment_controller):
        """Test applying obstacle pattern."""
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            success = await environment_controller.apply_obstacle_pattern('simple_maze')
            
            assert success is True
            assert environment_controller.stats['patterns_applied'] == 1
            assert len(environment_controller.current_objects) > 0
    
    @pytest.mark.asyncio
    async def test_apply_unknown_pattern(self, environment_controller):
        """Test applying unknown obstacle pattern."""
        success = await environment_controller.apply_obstacle_pattern('unknown_pattern')
        assert success is False
    
    @pytest.mark.asyncio
    async def test_clear_environment(self, environment_controller, sample_object_config):
        """Test environment clearing."""
        # Add some objects first
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            await environment_controller.add_object(sample_object_config)
            
            sample_object_config['object_id'] = 'test_box_2'
            await environment_controller.add_object(sample_object_config)
        
        # Clear environment
        with patch.object(environment_controller, '_remove_object_from_simulation', 
                         return_value=True):
            success = await environment_controller.clear_environment()
            
            assert success is True
            assert len(environment_controller.current_objects) == 0
    
    @pytest.mark.asyncio
    async def test_save_environment_state(self, environment_controller, sample_object_config):
        """Test environment state saving."""
        # Add an object first
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            await environment_controller.add_object(sample_object_config)
        
        # Save state
        with patch.object(environment_controller, '_save_state_to_file', 
                         return_value=True):
            success = await environment_controller.save_environment_state(
                'test_state', 'Test state description'
            )
            
            assert success is True
            assert 'test_state' in environment_controller.environment_states
            assert environment_controller.stats['states_saved'] == 1
    
    @pytest.mark.asyncio
    async def test_load_environment_state(self, environment_controller, sample_object_config):
        """Test environment state loading."""
        # Create and save a state first
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            await environment_controller.add_object(sample_object_config)
        
        with patch.object(environment_controller, '_save_state_to_file', 
                         return_value=True):
            await environment_controller.save_environment_state('test_state')
        
        # Clear environment
        with patch.object(environment_controller, '_remove_object_from_simulation', 
                         return_value=True):
            await environment_controller.clear_environment()
        
        # Load state
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            success = await environment_controller.load_environment_state('test_state')
            
            assert success is True
            assert len(environment_controller.current_objects) == 1
            assert environment_controller.stats['states_loaded'] == 1
            assert environment_controller.active_state_id == 'test_state'
    
    @pytest.mark.asyncio
    async def test_load_nonexistent_state(self, environment_controller):
        """Test loading non-existent state."""
        with patch.object(environment_controller, '_load_state_from_file', 
                         return_value=False):
            success = await environment_controller.load_environment_state('nonexistent_state')
            assert success is False
    
    def test_validate_object_position_valid(self, environment_controller):
        """Test object position validation - valid position."""
        env_object = EnvironmentObject(
            object_id='test_obj',
            object_type='box',
            position={'x': 1.0, 'y': 1.0, 'z': 0.5},
            rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
            size={'width': 0.5, 'height': 0.5, 'depth': 0.5}
        )
        
        assert environment_controller._validate_object_position(env_object) is True
    
    def test_validate_object_position_out_of_bounds(self, environment_controller):
        """Test object position validation - out of bounds."""
        env_object = EnvironmentObject(
            object_id='test_obj',
            object_type='box',
            position={'x': 10.0, 'y': 1.0, 'z': 0.5},  # x out of bounds
            rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
            size={'width': 0.5, 'height': 0.5, 'depth': 0.5}
        )
        
        assert environment_controller._validate_object_position(env_object) is False
    
    def test_validate_object_position_collision(self, environment_controller, sample_object_config):
        """Test object position validation - collision detection."""
        # Add first object
        env_object1 = EnvironmentObject(
            object_id='test_obj_1',
            object_type='box',
            position={'x': 1.0, 'y': 1.0, 'z': 0.5},
            rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
            size={'width': 0.5, 'height': 0.5, 'depth': 0.5}
        )
        environment_controller.current_objects['test_obj_1'] = env_object1
        
        # Try to add second object too close
        env_object2 = EnvironmentObject(
            object_id='test_obj_2',
            object_type='box',
            position={'x': 1.1, 'y': 1.1, 'z': 0.5},  # Too close
            rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
            size={'width': 0.5, 'height': 0.5, 'depth': 0.5}
        )
        
        assert environment_controller._validate_object_position(env_object2) is False
    
    @pytest.mark.asyncio
    async def test_generate_random_environment(self, environment_controller):
        """Test random environment generation."""
        with patch.object(environment_controller, '_add_object_to_simulation', 
                         return_value=True):
            success = await environment_controller.generate_random_environment(
                complexity=3, object_count=5
            )
            
            assert success is True
            assert len(environment_controller.current_objects) == 5
    
    def test_get_environment_info(self, environment_controller, sample_object_config):
        """Test environment information retrieval."""
        # Add an object
        env_object = EnvironmentObject(**sample_object_config)
        environment_controller.current_objects[sample_object_config['object_id']] = env_object
        
        info = environment_controller.get_environment_info()
        
        assert info['current_objects'] == 1
        assert 'box' in info['object_types']
        assert info['object_types']['box'] == 1
        assert 'arena_bounds' in info
        assert 'available_patterns' in info
        assert 'available_templates' in info
        assert 'statistics' in info
    
    def test_get_available_patterns(self, environment_controller):
        """Test getting available obstacle patterns."""
        patterns = environment_controller.get_available_patterns()
        
        assert len(patterns) > 0
        assert 'simple_maze' in patterns
        assert 'description' in patterns['simple_maze']
        assert 'difficulty_level' in patterns['simple_maze']
        assert 'recommended_robot_count' in patterns['simple_maze']
    
    def test_get_object_templates(self, environment_controller):
        """Test getting object templates."""
        templates = environment_controller.get_object_templates()
        
        assert len(templates) > 0
        assert 'small_box' in templates
        assert 'object_type' in templates['small_box']
        assert 'size' in templates['small_box']
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, environment_controller):
        """Test health check - healthy state."""
        health = await environment_controller.health_check()
        
        assert health['status'] == 'healthy'
        assert 'current_objects' in health
        assert 'max_objects' in health
        assert 'capacity_used' in health
        assert 'statistics' in health
    
    @pytest.mark.asyncio
    async def test_save_and_load_state_file_operations(self, environment_controller):
        """Test actual file save/load operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the states directory
            with patch('simulation.webots_environment_controller.Path') as mock_path:
                mock_states_dir = Mock()
                mock_states_dir.mkdir = Mock()
                mock_path.return_value = mock_states_dir
                
                # Create test state
                test_object = EnvironmentObject(
                    object_id='test_obj',
                    object_type='box',
                    position={'x': 1.0, 'y': 1.0, 'z': 0.5},
                    rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
                    size={'width': 0.5, 'height': 0.5, 'depth': 0.5}
                )
                
                env_state = EnvironmentState(
                    state_id='test_state',
                    timestamp=datetime.now(),
                    objects={'test_obj': test_object},
                    lighting={'ambient': 0.5},
                    physics_settings={'gravity': -9.81},
                    arena_bounds={'x_min': -5, 'x_max': 5, 'y_min': -5, 'y_max': 5}
                )
                
                # Test save operation
                with patch('builtins.open', create=True) as mock_open:
                    mock_file = Mock()
                    mock_open.return_value.__enter__.return_value = mock_file
                    
                    success = await environment_controller._save_state_to_file(env_state)
                    assert success is True
                    mock_open.assert_called_once()
    
    def test_object_type_distribution(self, environment_controller):
        """Test object type distribution calculation."""
        # Add objects of different types
        obj1 = EnvironmentObject(
            object_id='box1', object_type='box',
            position={'x': 0, 'y': 0, 'z': 0},
            rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
            size={'width': 1, 'height': 1, 'depth': 1}
        )
        obj2 = EnvironmentObject(
            object_id='cylinder1', object_type='cylinder',
            position={'x': 1, 'y': 0, 'z': 0},
            rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
            size={'radius': 0.5, 'height': 1}
        )
        obj3 = EnvironmentObject(
            object_id='box2', object_type='box',
            position={'x': 2, 'y': 0, 'z': 0},
            rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
            size={'width': 1, 'height': 1, 'depth': 1}
        )
        
        environment_controller.current_objects['box1'] = obj1
        environment_controller.current_objects['cylinder1'] = obj2
        environment_controller.current_objects['box2'] = obj3
        
        distribution = environment_controller._get_object_type_distribution()
        
        assert distribution['box'] == 2
        assert distribution['cylinder'] == 1
    
    @pytest.mark.asyncio
    async def test_simulation_integration_methods(self, environment_controller):
        """Test simulation integration methods."""
        # Test add object to simulation
        env_object = EnvironmentObject(
            object_id='test_obj',
            object_type='box',
            position={'x': 1.0, 'y': 1.0, 'z': 0.5},
            rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
            size={'width': 0.5, 'height': 0.5, 'depth': 0.5}
        )
        
        success = await environment_controller._add_object_to_simulation(env_object)
        assert success is True
        
        # Test remove object from simulation
        success = await environment_controller._remove_object_from_simulation('test_obj')
        assert success is True
        
        # Test move object in simulation
        new_position = {'x': 2.0, 'y': 2.0, 'z': 1.0}
        success = await environment_controller._move_object_in_simulation(
            'test_obj', new_position, None
        )
        assert success is True


@pytest.mark.asyncio
async def test_environment_object_dataclass():
    """Test EnvironmentObject dataclass functionality."""
    obj = EnvironmentObject(
        object_id='test_obj',
        object_type='box',
        position={'x': 1.0, 'y': 1.0, 'z': 0.5},
        rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
        size={'width': 0.5, 'height': 0.5, 'depth': 0.5}
    )
    
    # Test default values
    assert obj.color == {"r": 0.5, "g": 0.5, "b": 0.5, "a": 1.0}
    assert obj.material == "default"
    assert obj.physics_enabled is True
    assert obj.collision_enabled is True
    assert obj.created_time is not None


@pytest.mark.asyncio
async def test_environment_state_dataclass():
    """Test EnvironmentState dataclass functionality."""
    test_object = EnvironmentObject(
        object_id='test_obj',
        object_type='box',
        position={'x': 1.0, 'y': 1.0, 'z': 0.5},
        rotation={'roll': 0, 'pitch': 0, 'yaw': 0},
        size={'width': 0.5, 'height': 0.5, 'depth': 0.5}
    )
    
    state = EnvironmentState(
        state_id='test_state',
        timestamp=datetime.now(),
        objects={'test_obj': test_object},
        lighting={'ambient': 0.5},
        physics_settings={'gravity': -9.81},
        arena_bounds={'x_min': -5, 'x_max': 5, 'y_min': -5, 'y_max': 5}
    )
    
    assert state.state_id == 'test_state'
    assert len(state.objects) == 1
    assert 'test_obj' in state.objects


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
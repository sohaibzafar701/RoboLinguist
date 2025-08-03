#!/usr/bin/env python3
"""
Test suite for WebotsManager.

Tests simulation lifecycle, robot management, formation control,
and integration with the ChatGPT robotics system.
"""

import asyncio
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import the component to test
from simulation.webots_manager import WebotsManager, WebotsConfig, RobotInfo
from config.config_manager import ConfigManager
from core.data_models import RobotCommand, RobotState


class TestWebotsManager:
    """Test suite for WebotsManager."""
    
    @pytest.fixture
    def config_manager(self):
        """Create mock config manager."""
        config = {
            'simulation': {
                'webots': {
                    'webots_path': 'C:\\Program Files\\Webots',
                    'project_path': 'webots_simulation',
                    'world_file': 'test_world.wbt',
                    'robot_count': 5,
                    'enable_gui': False
                }
            }
        }
        
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: config.get(key, default)
        return mock_config
    
    @pytest.fixture
    def webots_manager(self, config_manager):
        """Create WebotsManager instance."""
        return WebotsManager(config_manager)
    
    @pytest.fixture
    def sample_robot_command(self):
        """Sample robot command for testing."""
        return RobotCommand(
            robot_id="test_robot_0",
            action="navigate",
            parameters={"target_position": {"x": 1.0, "y": 2.0, "z": 0.0}},
            priority=1,
            timeout=30.0
        )
    
    def test_initialization(self, webots_manager):
        """Test WebotsManager initialization."""
        assert webots_manager.component_name == "WebotsManager"
        assert not webots_manager.simulation_running
        assert len(webots_manager.robots) == 0
        assert len(webots_manager.robot_states) == 0
        assert webots_manager.webots_config.robot_count == 5
        assert webots_manager.webots_config.enable_gui is False
    
    def test_webots_config_dataclass(self):
        """Test WebotsConfig dataclass."""
        config = WebotsConfig(
            world_file="test.wbt",
            robot_count=10,
            enable_gui=True
        )
        
        assert config.world_file == "test.wbt"
        assert config.robot_count == 10
        assert config.enable_gui is True
        assert config.simulation_mode == "realtime"  # default
    
    def test_robot_info_dataclass(self):
        """Test RobotInfo dataclass."""
        robot_info = RobotInfo(
            robot_id="test_robot",
            robot_type="e-puck",
            status="active",
            controller="fleet_controller"
        )
        
        assert robot_info.robot_id == "test_robot"
        assert robot_info.robot_type == "e-puck"
        assert robot_info.status == "active"
        assert robot_info.controller == "fleet_controller"
        assert robot_info.position == {"x": 0.0, "y": 0.0, "z": 0.0}  # default
    
    @pytest.mark.asyncio
    async def test_start_simulation_success(self, webots_manager):
        """Test successful simulation start."""
        with patch.object(webots_manager, '_start_webots_process', return_value=True) as mock_start, \
             patch.object(webots_manager, '_create_default_world') as mock_create_world, \
             patch.object(webots_manager, '_initialize_robots') as mock_init_robots, \
             patch.object(webots_manager, '_notify_status_callbacks') as mock_notify:
            
            success = await webots_manager.start_simulation("test_world.wbt", 3)
            
            assert success is True
            assert webots_manager.simulation_running is True
            assert webots_manager._start_time is not None
            mock_start.assert_called_once()
            mock_init_robots.assert_called_once_with(3)
            mock_notify.assert_called_once_with("simulation_started")
    
    @pytest.mark.asyncio
    async def test_start_simulation_already_running(self, webots_manager):
        """Test starting simulation when already running."""
        webots_manager.simulation_running = True
        
        success = await webots_manager.start_simulation()
        
        assert success is True  # Should return True but not start again
    
    @pytest.mark.asyncio
    async def test_stop_simulation_success(self, webots_manager):
        """Test successful simulation stop."""
        # Set up running simulation
        webots_manager.simulation_running = True
        webots_manager._start_time = 123456789.0
        webots_manager.robots = {"robot_0": Mock()}
        webots_manager.robot_states = {"robot_0": Mock()}
        
        with patch.object(webots_manager, '_notify_status_callbacks') as mock_notify:
            success = await webots_manager.stop_simulation()
            
            assert success is True
            assert webots_manager.simulation_running is False
            assert webots_manager._start_time is None
            assert len(webots_manager.robots) == 0
            assert len(webots_manager.robot_states) == 0
            mock_notify.assert_called_once_with("simulation_stopped")
    
    @pytest.mark.asyncio
    async def test_stop_simulation_not_running(self, webots_manager):
        """Test stopping simulation when not running."""
        success = await webots_manager.stop_simulation()
        assert success is True
    
    @pytest.mark.asyncio
    async def test_send_robot_command_success(self, webots_manager, sample_robot_command):
        """Test successful robot command sending."""
        # Set up simulation and robot
        webots_manager.simulation_running = True
        webots_manager.robot_states["test_robot_0"] = RobotState(
            robot_id="test_robot_0",
            position={"x": 0, "y": 0, "z": 0},
            status="idle",
            battery_level=100.0,
            last_command_time=datetime.now(),
            is_moving=False
        )
        
        with patch.object(webots_manager, '_simulate_command_execution') as mock_simulate:
            success = await webots_manager.send_robot_command("test_robot_0", sample_robot_command)
            
            assert success is True
            robot_state = webots_manager.robot_states["test_robot_0"]
            assert robot_state.status == "executing"
            assert robot_state.is_moving is True
    
    @pytest.mark.asyncio
    async def test_send_robot_command_simulation_not_running(self, webots_manager, sample_robot_command):
        """Test sending command when simulation not running."""
        success = await webots_manager.send_robot_command("test_robot_0", sample_robot_command)
        assert success is False
    
    @pytest.mark.asyncio
    async def test_send_robot_command_robot_not_found(self, webots_manager, sample_robot_command):
        """Test sending command to non-existent robot."""
        webots_manager.simulation_running = True
        
        success = await webots_manager.send_robot_command("nonexistent_robot", sample_robot_command)
        assert success is False
    
    def test_get_robot_state(self, webots_manager):
        """Test getting robot state."""
        # Add a robot state
        robot_state = RobotState(
            robot_id="test_robot",
            position={"x": 1, "y": 2, "z": 0},
            status="idle",
            battery_level=85.0,
            last_command_time=datetime.now(),
            is_moving=False
        )
        webots_manager.robot_states["test_robot"] = robot_state
        
        retrieved_state = webots_manager.get_robot_state("test_robot")
        assert retrieved_state == robot_state
        
        # Test non-existent robot
        assert webots_manager.get_robot_state("nonexistent") is None
    
    def test_get_all_robot_states(self, webots_manager):
        """Test getting all robot states."""
        # Add multiple robot states
        for i in range(3):
            robot_state = RobotState(
                robot_id=f"robot_{i}",
                position={"x": i, "y": 0, "z": 0},
                status="idle",
                battery_level=100.0,
                last_command_time=datetime.now(),
                is_moving=False
            )
            webots_manager.robot_states[f"robot_{i}"] = robot_state
        
        all_states = webots_manager.get_all_robot_states()
        assert len(all_states) == 3
        assert "robot_0" in all_states
        assert "robot_2" in all_states
    
    def test_get_simulation_status(self, webots_manager):
        """Test getting simulation status."""
        # Set up some state
        webots_manager.simulation_running = True
        webots_manager.world_loaded = True
        webots_manager.robots = {"robot_0": Mock(), "robot_1": Mock()}
        webots_manager._start_time = 123456789.0
        
        with patch('time.time', return_value=123456799.0):  # 10 seconds later
            status = webots_manager.get_simulation_status()
            
            assert status["running"] is True
            assert status["world_loaded"] is True
            assert status["robot_count"] == 2
            assert status["uptime"] == 10.0
            assert "webots_path" in status
            assert "project_path" in status
    
    @pytest.mark.asyncio
    async def test_create_line_formation(self, webots_manager):
        """Test line formation creation."""
        # Set up robots
        webots_manager.simulation_running = True
        for i in range(3):
            webots_manager.robot_states[f"robot_{i}"] = RobotState(
                robot_id=f"robot_{i}",
                position={"x": 0, "y": 0, "z": 0},
                status="idle",
                battery_level=100.0,
                last_command_time=datetime.now(),
                is_moving=False
            )
        
        with patch.object(webots_manager, 'send_robot_command', return_value=True) as mock_send:
            success = await webots_manager._create_line_formation(spacing=1.5)
            
            assert success is True
            assert mock_send.call_count == 3
            
            # Check that robots are positioned in a line
            calls = mock_send.call_args_list
            positions = [call[0][1].parameters["target_position"] for call in calls]
            
            # Should be spaced 1.5 units apart in X
            assert positions[0]["x"] == -1.5  # (0 - 3/2) * 1.5
            assert positions[1]["x"] == 0.0   # (1 - 3/2) * 1.5
            assert positions[2]["x"] == 1.5   # (2 - 3/2) * 1.5
    
    @pytest.mark.asyncio
    async def test_create_circle_formation(self, webots_manager):
        """Test circle formation creation."""
        # Set up robots
        webots_manager.simulation_running = True
        for i in range(4):
            webots_manager.robot_states[f"robot_{i}"] = RobotState(
                robot_id=f"robot_{i}",
                position={"x": 0, "y": 0, "z": 0},
                status="idle",
                battery_level=100.0,
                last_command_time=datetime.now(),
                is_moving=False
            )
        
        with patch.object(webots_manager, 'send_robot_command', return_value=True) as mock_send:
            success = await webots_manager._create_circle_formation(radius=2.0)
            
            assert success is True
            assert mock_send.call_count == 4
            
            # Check that robots are positioned in a circle
            calls = mock_send.call_args_list
            positions = [call[0][1].parameters["target_position"] for call in calls]
            
            # First robot should be at (2, 0) - radius * cos(0)
            assert abs(positions[0]["x"] - 2.0) < 0.01
            assert abs(positions[0]["y"] - 0.0) < 0.01
    
    @pytest.mark.asyncio
    async def test_create_grid_formation(self, webots_manager):
        """Test grid formation creation."""
        # Set up robots
        webots_manager.simulation_running = True
        for i in range(4):
            webots_manager.robot_states[f"robot_{i}"] = RobotState(
                robot_id=f"robot_{i}",
                position={"x": 0, "y": 0, "z": 0},
                status="idle",
                battery_level=100.0,
                last_command_time=datetime.now(),
                is_moving=False
            )
        
        with patch.object(webots_manager, 'send_robot_command', return_value=True) as mock_send:
            success = await webots_manager._create_grid_formation(spacing=1.0)
            
            assert success is True
            assert mock_send.call_count == 4
    
    @pytest.mark.asyncio
    async def test_create_formation_public_method(self, webots_manager):
        """Test public create_formation method."""
        webots_manager.simulation_running = True
        webots_manager.robot_states["robot_0"] = Mock()
        
        with patch.object(webots_manager, '_create_line_formation', return_value=True) as mock_line:
            success = await webots_manager.create_formation("line", spacing=2.0)
            assert success is True
            mock_line.assert_called_once_with(spacing=2.0)
        
        with patch.object(webots_manager, '_create_circle_formation', return_value=True) as mock_circle:
            success = await webots_manager.create_formation("circle", radius=3.0)
            assert success is True
            mock_circle.assert_called_once_with(radius=3.0)
        
        # Test unknown formation type
        success = await webots_manager.create_formation("unknown_formation")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_emergency_stop_all_robots(self, webots_manager):
        """Test emergency stop functionality."""
        # Set up robots
        for i in range(3):
            robot_state = RobotState(
                robot_id=f"robot_{i}",
                position={"x": i, "y": 0, "z": 0},
                status="moving",
                battery_level=100.0,
                last_command_time=datetime.now(),
                is_moving=True
            )
            webots_manager.robot_states[f"robot_{i}"] = robot_state
        
        webots_manager.command_queue = [Mock(), Mock()]  # Some queued commands
        
        await webots_manager.emergency_stop_all_robots()
        
        # Check that all robots are stopped
        for robot_state in webots_manager.robot_states.values():
            assert robot_state.status == "emergency_stop"
            assert robot_state.is_moving is False
        
        # Check that command queue is cleared
        assert len(webots_manager.command_queue) == 0
    
    @pytest.mark.asyncio
    async def test_initialize_robots(self, webots_manager):
        """Test robot initialization."""
        await webots_manager._initialize_robots(5)
        
        assert len(webots_manager.robot_states) == 5
        assert len(webots_manager.robots) == 5
        
        # Check robot naming
        assert "robot_0" in webots_manager.robot_states
        assert "robot_4" in webots_manager.robot_states
        
        # Check initial positions are different
        positions = [state.position for state in webots_manager.robot_states.values()]
        unique_positions = set((pos["x"], pos["y"]) for pos in positions)
        assert len(unique_positions) == 5  # All positions should be unique
    
    def test_get_initial_position(self, webots_manager):
        """Test initial position calculation."""
        # Test grid positioning
        pos_0 = webots_manager._get_initial_position(0)
        pos_1 = webots_manager._get_initial_position(1)
        pos_4 = webots_manager._get_initial_position(4)
        
        # Positions should be different
        assert pos_0 != pos_1
        assert pos_1 != pos_4
        
        # All should have z=0 and yaw=0
        for pos in [pos_0, pos_1, pos_4]:
            assert pos["z"] == 0.0
            assert pos["yaw"] == 0.0
    
    @pytest.mark.asyncio
    async def test_simulate_command_execution(self, webots_manager):
        """Test command execution simulation."""
        # Set up robot state
        robot_state = RobotState(
            robot_id="test_robot",
            position={"x": 0, "y": 0, "z": 0},
            status="executing",
            battery_level=100.0,
            last_command_time=datetime.now(),
            is_moving=True
        )
        webots_manager.robot_states["test_robot"] = robot_state
        
        # Create navigation command
        command = RobotCommand(
            robot_id="test_robot",
            action="navigate",
            parameters={"target_position": {"x": 1.0, "y": 1.0, "z": 0.0}},
            priority=1,
            timeout=30.0
        )
        
        # Execute simulation (should complete quickly in test)
        await webots_manager._simulate_command_execution("test_robot", command)
        
        # Check that robot state was updated
        assert robot_state.status == "idle"
        assert robot_state.is_moving is False
        assert robot_state.position["x"] == 1.0
        assert robot_state.position["y"] == 1.0
    
    def test_get_uptime(self, webots_manager):
        """Test uptime calculation."""
        # No start time
        assert webots_manager._get_uptime() == 0.0
        
        # With start time
        webots_manager._start_time = 123456789.0
        with patch('time.time', return_value=123456799.0):  # 10 seconds later
            assert webots_manager._get_uptime() == 10.0
    
    def test_add_status_callback(self, webots_manager):
        """Test adding status callbacks."""
        callback1 = Mock()
        callback2 = Mock()
        
        webots_manager.add_status_callback(callback1)
        webots_manager.add_status_callback(callback2)
        
        assert len(webots_manager.status_callbacks) == 2
        assert callback1 in webots_manager.status_callbacks
        assert callback2 in webots_manager.status_callbacks
    
    @pytest.mark.asyncio
    async def test_notify_status_callbacks(self, webots_manager):
        """Test status callback notification."""
        # Add sync and async callbacks
        sync_callback = Mock()
        async_callback = AsyncMock()
        
        webots_manager.add_status_callback(sync_callback)
        webots_manager.add_status_callback(async_callback)
        
        await webots_manager._notify_status_callbacks("test_event")
        
        # Check that both callbacks were called
        sync_callback.assert_called_once()
        async_callback.assert_called_once()
        
        # Check call arguments
        args = sync_callback.call_args[0]
        assert args[0] == "test_event"
        assert isinstance(args[1], dict)  # Status dict
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, webots_manager):
        """Test health check - healthy state."""
        webots_manager.simulation_running = True
        webots_manager.robots = {"robot_0": Mock()}
        webots_manager._start_time = 123456789.0
        
        with patch('time.time', return_value=123456799.0), \
             patch('pathlib.Path.exists', return_value=True):
            
            health = await webots_manager.health_check()
            
            assert health['status'] == 'healthy'
            assert health['webots_available'] is True
            assert health['simulation_running'] is True
            assert health['robot_count'] == 1
            assert health['uptime'] == 10.0
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, webots_manager):
        """Test health check - unhealthy state."""
        with patch('pathlib.Path.exists', return_value=False):
            health = await webots_manager.health_check()
            
            assert health['status'] == 'unhealthy'
            assert health['webots_available'] is False
    
    @pytest.mark.asyncio
    async def test_initialize_method(self, webots_manager):
        """Test initialize method."""
        with patch('pathlib.Path.exists', return_value=True):
            success = await webots_manager.initialize()
            assert success is True
        
        with patch('pathlib.Path.exists', return_value=False):
            success = await webots_manager.initialize()
            assert success is False
    
    @pytest.mark.asyncio
    async def test_start_method(self, webots_manager):
        """Test start method."""
        with patch.object(webots_manager, 'initialize', return_value=True):
            success = await webots_manager.start()
            assert success is True
    
    @pytest.mark.asyncio
    async def test_stop_method(self, webots_manager):
        """Test stop method."""
        webots_manager.simulation_running = True
        
        with patch.object(webots_manager, 'stop_simulation', return_value=True):
            success = await webots_manager.stop()
            assert success is True
    
    def test_cleanup_method(self, webots_manager):
        """Test cleanup method."""
        webots_manager.simulation_running = True
        
        # Should not raise exception
        webots_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_world_file_creation(self, webots_manager):
        """Test world file creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            world_path = Path(temp_dir) / "test_world.wbt"
            
            await webots_manager._create_default_world(world_path, 3)
            
            assert world_path.exists()
            
            # Check world file content
            content = world_path.read_text()
            assert "WorldInfo" in content
            assert "E-puck" in content
            assert "robot_0" in content
            assert "robot_2" in content
    
    def test_generate_world_content(self, webots_manager):
        """Test world content generation."""
        content = webots_manager._generate_world_content(2)
        
        assert "WorldInfo" in content
        assert "TexturedBackground" in content
        assert "RectangleArena" in content
        assert "E-puck" in content
        assert "robot_0" in content
        assert "robot_1" in content
        assert "fleet_controller" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
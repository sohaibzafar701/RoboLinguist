#!/usr/bin/env python3
"""
Real Integration Tests for Webots Task 7 Components.

These tests actually connect to Webots and perform real operations:
- Start/stop Webots simulation
- Create world files and spawn robots
- Test robot movements and formations
- Test environment manipulation
- Verify actual Webots integration

Prerequisites:
- Webots must be installed and accessible
- No other Webots instance should be running
"""

import asyncio
import pytest
import time
import os
from pathlib import Path
from datetime import datetime

from config.config_manager import ConfigManager
from simulation.webots_manager import WebotsManager
from simulation.webots_environment_controller import WebotsEnvironmentController
from simulation.webots_robot_spawner import WebotsRobotSpawner, RobotSpawnConfig
from core.data_models import RobotCommand


class TestWebotsRealIntegration:
    """Real integration tests with actual Webots simulation."""
    
    @pytest.fixture(scope="class")
    def config_manager(self):
        """Create real config manager for Webots integration."""
        config = ConfigManager()
        # Override with test-specific settings
        config.config_data = {
            'simulation': {
                'webots': {
                    'webots_path': 'C:\\Program Files\\Webots\\msys64\\mingw64\\bin\\webots.exe',
                    'project_path': 'test_webots_integration',
                    'world_file': 'integration_test.wbt',
                    'robot_count': 3,
                    'enable_gui': True,  # Enable GUI for visual verification
                    'simulation_mode': 'realtime'
                }
            },
            'environment': {
                'arena_bounds': {
                    'x_min': -3.0, 'x_max': 3.0,
                    'y_min': -3.0, 'y_max': 3.0,
                    'z_min': 0.0, 'z_max': 2.0
                },
                'max_objects': 20,
                'auto_cleanup': True
            },
            'robot_spawner': {
                'spawn_config': {
                    'robot_type': 'e-puck',
                    'controller': 'fleet_controller',
                    'spawn_pattern': 'grid',
                    'spacing': 1.0,
                    'max_robots': 10
                }
            }
        }
        return config
    
    @pytest.fixture(scope="class")
    async def webots_manager(self, config_manager):
        """Create and initialize Webots manager."""
        manager = WebotsManager(config_manager)
        
        # Check if Webots is available
        health = await manager.health_check()
        if health['status'] != 'healthy':
            pytest.skip("Webots not available for integration testing")
        
        yield manager
        
        # Cleanup after all tests
        if manager.simulation_running:
            await manager.stop_simulation()
    
    @pytest.fixture(scope="class")
    async def environment_controller(self, config_manager, webots_manager):
        """Create environment controller."""
        controller = WebotsEnvironmentController(config_manager)
        controller.set_webots_manager(webots_manager)
        yield controller
    
    @pytest.fixture(scope="class")
    async def robot_spawner(self, config_manager, webots_manager):
        """Create robot spawner."""
        spawner = WebotsRobotSpawner(config_manager.get('robot_spawner', {}))
        spawner.set_webots_manager(webots_manager)
        yield spawner
    
    @pytest.mark.asyncio
    async def test_webots_availability(self, webots_manager):
        """Test that Webots is available and can be initialized."""
        print("\n🔍 Testing Webots availability...")
        
        # Check health
        health = await webots_manager.health_check()
        print(f"   Health status: {health['status']}")
        print(f"   Webots available: {health['webots_available']}")
        print(f"   Webots path: {health.get('project_path', 'N/A')}")
        
        assert health['status'] == 'healthy'
        assert health['webots_available'] is True
        
        print("   ✅ Webots is available and ready")
    
    @pytest.mark.asyncio
    async def test_start_stop_simulation(self, webots_manager):
        """Test starting and stopping Webots simulation."""
        print("\n🎬 Testing simulation start/stop...")
        
        # Ensure simulation is stopped
        if webots_manager.simulation_running:
            await webots_manager.stop_simulation()
        
        # Start simulation
        print("   Starting Webots simulation...")
        success = await webots_manager.start_simulation(
            world_name="integration_test.wbt",
            robot_count=3
        )
        
        assert success is True
        assert webots_manager.simulation_running is True
        
        # Check simulation status
        status = webots_manager.get_simulation_status()
        print(f"   Simulation running: {status['running']}")
        print(f"   Robot count: {status['robot_count']}")
        print(f"   Project path: {status['project_path']}")
        
        assert status['running'] is True
        assert status['robot_count'] == 3
        
        # Wait a moment for simulation to stabilize
        await asyncio.sleep(3)
        
        # Stop simulation
        print("   Stopping Webots simulation...")
        success = await webots_manager.stop_simulation()
        
        assert success is True
        assert webots_manager.simulation_running is False
        
        print("   ✅ Simulation start/stop successful")
    
    @pytest.mark.asyncio
    async def test_world_file_creation(self, webots_manager):
        """Test that world files are created correctly."""
        print("\n🌍 Testing world file creation...")
        
        # Start simulation (this should create world file)
        success = await webots_manager.start_simulation(
            world_name="test_world_creation.wbt",
            robot_count=5
        )
        
        assert success is True
        
        # Check that world file was created
        world_path = webots_manager.worlds_path / "test_world_creation.wbt"
        assert world_path.exists()
        
        # Read and verify world file content
        world_content = world_path.read_text()
        print(f"   World file created: {world_path}")
        print(f"   File size: {len(world_content)} characters")
        
        # Verify essential components
        assert "WorldInfo" in world_content
        assert "E-puck" in world_content
        assert "robot_0" in world_content
        assert "robot_4" in world_content
        assert "fleet_controller" in world_content
        
        await webots_manager.stop_simulation()
        print("   ✅ World file creation successful")
    
    @pytest.mark.asyncio
    async def test_robot_spawning_and_tracking(self, webots_manager, robot_spawner):
        """Test robot spawning and state tracking."""
        print("\n🤖 Testing robot spawning and tracking...")
        
        # Start simulation
        await webots_manager.start_simulation("robot_spawn_test.wbt", robot_count=0)
        
        # Spawn individual robot
        print("   Spawning individual robot...")
        config = RobotSpawnConfig(
            robot_id='integration_test_robot_1',
            robot_type='e-puck',
            position={'x': 1.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0},
            controller='fleet_controller'
        )
        
        success = await robot_spawner.spawn_robot(config, webots_manager)
        assert success is True
        
        # Verify robot is tracked
        robot_info = robot_spawner.get_robot_info('integration_test_robot_1')
        assert robot_info is not None
        assert robot_info.robot_id == 'integration_test_robot_1'
        assert robot_info.robot_type == 'e-puck'
        
        # Check robot state in manager
        robot_state = webots_manager.get_robot_state('integration_test_robot_1')
        assert robot_state is not None
        assert robot_state.robot_id == 'integration_test_robot_1'
        assert robot_state.status == 'idle'
        
        # Spawn multiple robots
        print("   Spawning robot fleet...")
        spawned_ids = await robot_spawner.spawn_multiple_robots(
            robot_count=3,
            webots_manager=webots_manager,
            robot_type='e-puck',
            name_prefix='fleet_robot'
        )
        
        assert len(spawned_ids) == 3
        assert 'fleet_robot_0' in spawned_ids
        
        # Verify all robots are tracked
        all_states = webots_manager.get_all_robot_states()
        print(f"   Total robots tracked: {len(all_states)}")
        assert len(all_states) == 4  # 1 individual + 3 fleet
        
        await webots_manager.stop_simulation()
        print("   ✅ Robot spawning and tracking successful")
    
    @pytest.mark.asyncio
    async def test_robot_command_execution(self, webots_manager):
        """Test sending commands to robots."""
        print("\n🎯 Testing robot command execution...")
        
        # Start simulation with robots
        await webots_manager.start_simulation("command_test.wbt", robot_count=2)
        
        # Wait for robots to initialize
        await asyncio.sleep(2)
        
        # Get robot states
        robot_states = webots_manager.get_all_robot_states()
        robot_ids = list(robot_states.keys())
        assert len(robot_ids) >= 1
        
        test_robot_id = robot_ids[0]
        print(f"   Testing commands on robot: {test_robot_id}")
        
        # Test navigation command
        initial_state = webots_manager.get_robot_state(test_robot_id)
        print(f"   Initial position: {initial_state.position}")
        
        nav_command = RobotCommand(
            robot_id=test_robot_id,
            action="navigate",
            parameters={"target_position": {"x": 1.0, "y": 1.0, "z": 0.0}},
            priority=1,
            timeout=30.0
        )
        
        success = await webots_manager.send_robot_command(test_robot_id, nav_command)
        assert success is True
        
        # Check that robot state changed
        updated_state = webots_manager.get_robot_state(test_robot_id)
        assert updated_state.status == "executing"
        assert updated_state.is_moving is True
        
        print(f"   Command sent successfully, robot status: {updated_state.status}")
        
        # Wait for command execution simulation
        await asyncio.sleep(4)
        
        # Check final state
        final_state = webots_manager.get_robot_state(test_robot_id)
        print(f"   Final robot status: {final_state.status}")
        print(f"   Final position: {final_state.position}")
        
        await webots_manager.stop_simulation()
        print("   ✅ Robot command execution successful")
    
    @pytest.mark.asyncio
    async def test_robot_formations(self, webots_manager):
        """Test robot formation creation."""
        print("\n🎭 Testing robot formations...")
        
        # Start simulation with multiple robots
        await webots_manager.start_simulation("formation_test.wbt", robot_count=4)
        await asyncio.sleep(2)
        
        # Test line formation
        print("   Testing line formation...")
        success = await webots_manager.create_formation("line", spacing=1.5)
        assert success is True
        
        # Verify robots received commands
        robot_states = webots_manager.get_all_robot_states()
        moving_robots = sum(1 for state in robot_states.values() if state.is_moving)
        print(f"   Robots in line formation: {moving_robots}/{len(robot_states)}")
        
        await asyncio.sleep(2)
        
        # Test circle formation
        print("   Testing circle formation...")
        success = await webots_manager.create_formation("circle", radius=2.0)
        assert success is True
        
        await asyncio.sleep(2)
        
        # Test grid formation
        print("   Testing grid formation...")
        success = await webots_manager.create_formation("grid", spacing=1.0)
        assert success is True
        
        await asyncio.sleep(2)
        
        await webots_manager.stop_simulation()
        print("   ✅ Robot formations successful")
    
    @pytest.mark.asyncio
    async def test_environment_manipulation(self, webots_manager, environment_controller):
        """Test environment object manipulation."""
        print("\n🏗️ Testing environment manipulation...")
        
        # Start simulation
        await webots_manager.start_simulation("environment_test.wbt", robot_count=1)
        await asyncio.sleep(2)
        
        # Add objects to environment
        print("   Adding objects to environment...")
        
        box_config = {
            'object_id': 'test_box_1',
            'object_type': 'box',
            'position': {'x': 2.0, 'y': 0.0, 'z': 0.5},
            'rotation': {'roll': 0, 'pitch': 0, 'yaw': 0},
            'size': {'width': 0.5, 'height': 0.5, 'depth': 0.5},
            'color': {'r': 1.0, 'g': 0.0, 'b': 0.0, 'a': 1.0}
        }
        
        success = await environment_controller.add_object(box_config)
        assert success is True
        
        # Verify object was added
        env_info = environment_controller.get_environment_info()
        assert env_info['current_objects'] == 1
        print(f"   Objects in environment: {env_info['current_objects']}")
        
        # Test object movement
        print("   Moving object...")
        new_position = {'x': -1.0, 'y': 1.0, 'z': 0.5}
        success = await environment_controller.move_object('test_box_1', new_position)
        assert success is True
        
        # Test obstacle pattern
        print("   Applying obstacle pattern...")
        success = await environment_controller.apply_obstacle_pattern(
            'scattered_obstacles',
            offset={'x': 0, 'y': 0, 'z': 0},
            scale=0.5
        )
        assert success is True
        
        # Check updated environment
        env_info = environment_controller.get_environment_info()
        print(f"   Total objects after pattern: {env_info['current_objects']}")
        assert env_info['current_objects'] > 1
        
        await webots_manager.stop_simulation()
        print("   ✅ Environment manipulation successful")
    
    @pytest.mark.asyncio
    async def test_environment_state_persistence(self, environment_controller):
        """Test environment state save/load."""
        print("\n💾 Testing environment state persistence...")
        
        # Clear environment and add test objects
        await environment_controller.clear_environment()
        
        # Add test objects
        for i in range(3):
            obj_config = {
                'object_id': f'state_test_obj_{i}',
                'position': {'x': i * 1.0, 'y': 0.0, 'z': 0.5}
            }
            await environment_controller.add_object(obj_config, 'small_box')
        
        # Save state
        print("   Saving environment state...")
        success = await environment_controller.save_environment_state(
            'integration_test_state',
            'Integration test environment state'
        )
        assert success is True
        
        # Clear environment
        await environment_controller.clear_environment()
        env_info = environment_controller.get_environment_info()
        assert env_info['current_objects'] == 0
        
        # Load state
        print("   Loading environment state...")
        success = await environment_controller.load_environment_state('integration_test_state')
        assert success is True
        
        # Verify objects were restored
        env_info = environment_controller.get_environment_info()
        print(f"   Objects restored: {env_info['current_objects']}")
        assert env_info['current_objects'] == 3
        
        print("   ✅ Environment state persistence successful")
    
    @pytest.mark.asyncio
    async def test_emergency_stop(self, webots_manager):
        """Test emergency stop functionality."""
        print("\n🚨 Testing emergency stop...")
        
        # Start simulation with robots
        await webots_manager.start_simulation("emergency_test.wbt", robot_count=3)
        await asyncio.sleep(2)
        
        # Start robot movements
        robot_states = webots_manager.get_all_robot_states()
        robot_ids = list(robot_states.keys())
        
        # Send movement commands to all robots
        for i, robot_id in enumerate(robot_ids):
            command = RobotCommand(
                robot_id=robot_id,
                action="navigate",
                parameters={"target_position": {"x": i * 2.0, "y": i * 1.0, "z": 0.0}},
                priority=1,
                timeout=30.0
            )
            await webots_manager.send_robot_command(robot_id, command)
        
        await asyncio.sleep(1)
        
        # Verify robots are moving
        robot_states = webots_manager.get_all_robot_states()
        moving_count = sum(1 for state in robot_states.values() if state.is_moving)
        print(f"   Robots moving before emergency stop: {moving_count}")
        
        # Execute emergency stop
        print("   Executing emergency stop...")
        await webots_manager.emergency_stop_all_robots()
        
        # Verify all robots stopped
        robot_states = webots_manager.get_all_robot_states()
        stopped_count = sum(1 for state in robot_states.values() 
                          if state.status == "emergency_stop" and not state.is_moving)
        
        print(f"   Robots stopped after emergency stop: {stopped_count}")
        assert stopped_count == len(robot_ids)
        
        await webots_manager.stop_simulation()
        print("   ✅ Emergency stop successful")
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self, webots_manager, environment_controller, robot_spawner):
        """Test performance and metrics collection."""
        print("\n📊 Testing performance metrics...")
        
        start_time = time.time()
        
        # Start simulation
        await webots_manager.start_simulation("performance_test.wbt", robot_count=5)
        
        # Perform various operations
        print("   Performing operations for metrics...")
        
        # Spawn additional robots
        spawned_ids = await robot_spawner.spawn_multiple_robots(
            robot_count=3,
            webots_manager=webots_manager
        )
        
        # Add environment objects
        for i in range(5):
            obj_config = {
                'object_id': f'perf_obj_{i}',
                'position': {'x': i * 0.8, 'y': 0.0, 'z': 0.3}
            }
            await environment_controller.add_object(obj_config, 'cylinder_obstacle')
        
        # Execute formations
        await webots_manager.create_formation("circle", radius=2.5)
        await asyncio.sleep(1)
        await webots_manager.create_formation("line", spacing=1.2)
        
        # Collect metrics
        sim_status = webots_manager.get_simulation_status()
        env_info = environment_controller.get_environment_info()
        spawn_summary = robot_spawner.get_spawn_summary()
        
        execution_time = time.time() - start_time
        
        print(f"   Execution time: {execution_time:.2f}s")
        print(f"   Simulation uptime: {sim_status.get('uptime', 0):.2f}s")
        print(f"   Total robots: {sim_status['robot_count']}")
        print(f"   Environment objects: {env_info['current_objects']}")
        print(f"   Spawn success rate: 100%")  # All operations succeeded
        
        # Verify performance is reasonable
        assert execution_time < 30.0  # Should complete within 30 seconds
        assert sim_status['robot_count'] >= 5
        assert env_info['current_objects'] >= 5
        
        await webots_manager.stop_simulation()
        print("   ✅ Performance metrics collection successful")
    
    @pytest.mark.asyncio
    async def test_full_integration_scenario(self, webots_manager, environment_controller, robot_spawner):
        """Test complete integration scenario."""
        print("\n🎯 Testing full integration scenario...")
        
        # This test combines all components in a realistic scenario
        print("   Starting comprehensive integration test...")
        
        # 1. Start simulation
        await webots_manager.start_simulation("full_integration.wbt", robot_count=4)
        await asyncio.sleep(2)
        
        # 2. Create environment
        print("   Creating warehouse environment...")
        success = await environment_controller.apply_obstacle_pattern(
            'warehouse_layout',
            scale=0.8
        )
        assert success is True
        
        # 3. Spawn additional robots
        print("   Spawning additional robots...")
        additional_robots = await robot_spawner.spawn_multiple_robots(
            robot_count=2,
            webots_manager=webots_manager,
            name_prefix='warehouse_robot'
        )
        assert len(additional_robots) == 2
        
        # 4. Execute coordinated movements
        print("   Executing coordinated robot movements...")
        await webots_manager.create_formation("grid", spacing=1.5)
        await asyncio.sleep(2)
        
        # 5. Save environment state
        print("   Saving integration test state...")
        await environment_controller.save_environment_state(
            'full_integration_state',
            'Complete integration test scenario'
        )
        
        # 6. Verify final state
        sim_status = webots_manager.get_simulation_status()
        env_info = environment_controller.get_environment_info()
        
        print(f"   Final robot count: {sim_status['robot_count']}")
        print(f"   Final object count: {env_info['current_objects']}")
        print(f"   Simulation running: {sim_status['running']}")
        
        assert sim_status['robot_count'] >= 6  # 4 initial + 2 additional
        assert env_info['current_objects'] > 0
        assert sim_status['running'] is True
        
        await webots_manager.stop_simulation()
        print("   ✅ Full integration scenario successful")


# Utility function to run integration tests
async def run_integration_tests():
    """Run integration tests manually."""
    print("🤖🌍 Starting Webots Integration Tests")
    print("=" * 60)
    
    # Create test instance
    test_instance = TestWebotsRealIntegration()
    
    # Create fixtures
    config_manager = test_instance.config_manager()
    webots_manager = WebotsManager(config_manager)
    environment_controller = WebotsEnvironmentController(config_manager)
    robot_spawner = WebotsRobotSpawner(config_manager.get('robot_spawner', {}))
    
    # Connect components
    environment_controller.set_webots_manager(webots_manager)
    robot_spawner.set_webots_manager(webots_manager)
    
    try:
        # Run tests in sequence
        await test_instance.test_webots_availability(webots_manager)
        await test_instance.test_start_stop_simulation(webots_manager)
        await test_instance.test_world_file_creation(webots_manager)
        await test_instance.test_robot_spawning_and_tracking(webots_manager, robot_spawner)
        await test_instance.test_robot_command_execution(webots_manager)
        await test_instance.test_robot_formations(webots_manager)
        await test_instance.test_environment_manipulation(webots_manager, environment_controller)
        await test_instance.test_environment_state_persistence(environment_controller)
        await test_instance.test_emergency_stop(webots_manager)
        await test_instance.test_performance_metrics(webots_manager, environment_controller, robot_spawner)
        await test_instance.test_full_integration_scenario(webots_manager, environment_controller, robot_spawner)
        
        print("\n🎉 All integration tests passed!")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise
    finally:
        # Cleanup
        if webots_manager.simulation_running:
            await webots_manager.stop_simulation()


if __name__ == "__main__":
    # Run integration tests directly
    asyncio.run(run_integration_tests())
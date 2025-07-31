#!/usr/bin/env python3
"""
Test script to verify the project setup is working correctly.
"""

import sys
import asyncio
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import ConfigManager
from core import RobotCommand, RobotState, Task, BaseComponent
from datetime import datetime


class TestComponent(BaseComponent):
    """Test component to verify base component functionality."""
    
    async def initialize(self) -> bool:
        self.logger.info("Test component initializing...")
        return True
    
    async def start(self) -> bool:
        self.logger.info("Test component starting...")
        return True
    
    async def stop(self) -> bool:
        self.logger.info("Test component stopping...")
        return True
    
    async def health_check(self):
        return {"status": "healthy", "component": self.component_name}


async def test_setup():
    """Test the project setup."""
    print("Testing ChatGPT for Robots project setup...")
    
    # Test configuration management
    print("\n1. Testing configuration management...")
    config_manager = ConfigManager()
    if config_manager.load_config():
        print("✓ Configuration loaded successfully")
        print(f"  - LLM Model: {config_manager.get_setting('llm.default_model')}")
        print(f"  - Web Port: {config_manager.get_setting('web_interface.port')}")
        print(f"  - Max Robots: {config_manager.get_setting('simulation.max_robots')}")
    else:
        print("✗ Configuration loading failed")
        return False
    
    # Test data models
    print("\n2. Testing data models...")
    try:
        # Test RobotCommand
        command = RobotCommand(
            command_id="test_001",
            robot_id="robot_1",
            action_type="navigate",
            parameters={"target": [1.0, 2.0, 0.0]},
            priority=5,
            timestamp=datetime.now()
        )
        print("✓ RobotCommand created successfully")
        
        # Test RobotState
        state = RobotState(
            robot_id="robot_1",
            position=(0.0, 0.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status="idle",
            battery_level=85.0,
            current_task=None,
            last_update=datetime.now()
        )
        print("✓ RobotState created successfully")
        
        # Test Task
        task = Task(
            task_id="task_001",
            description="Navigate to warehouse section A",
            assigned_robot=None,
            status="pending",
            created_at=datetime.now(),
            estimated_duration=120,
            dependencies=[]
        )
        print("✓ Task created successfully")
        
    except Exception as e:
        print(f"✗ Data model test failed: {e}")
        return False
    
    # Test base component
    print("\n3. Testing base component...")
    try:
        test_component = TestComponent("test_component")
        
        # Test initialization
        if await test_component._safe_initialize():
            print("✓ Component initialization successful")
        else:
            print("✗ Component initialization failed")
            return False
        
        # Test start
        if await test_component._safe_start():
            print("✓ Component start successful")
        else:
            print("✗ Component start failed")
            return False
        
        # Test status
        status = test_component.get_status()
        print(f"✓ Component status: {status['is_running']}")
        
        # Test stop
        if await test_component._safe_stop():
            print("✓ Component stop successful")
        else:
            print("✗ Component stop failed")
            return False
            
    except Exception as e:
        print(f"✗ Base component test failed: {e}")
        return False
    
    print("\n✓ All tests passed! Project setup is working correctly.")
    print("\nNext steps:")
    print("1. Update config/system_config.yaml with your OpenRouter API key")
    print("2. Install ROS2 dependencies for robot control")
    print("3. Install Gazebo for simulation")
    print("4. Begin implementing individual components")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_setup())
    sys.exit(0 if success else 1)
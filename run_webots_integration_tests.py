#!/usr/bin/env python3
"""
Webots Integration Test Runner

This script runs real integration tests that connect to Webots and perform
actual simulation operations. These are not mocked tests - they require
Webots to be installed and available.

Usage:
    python run_webots_integration_tests.py
    
    Or run specific test:
    python run_webots_integration_tests.py --test test_robot_formations
"""

import asyncio
import argparse
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tests.test_webots_integration import TestWebotsRealIntegration, run_integration_tests


async def run_specific_test(test_name: str):
    """Run a specific integration test."""
    print(f"🎯 Running specific test: {test_name}")
    print("=" * 60)
    
    # Create test instance and fixtures
    test_instance = TestWebotsRealIntegration()
    
    try:
        # Get the config manager fixture
        config_manager = test_instance.config_manager()
        
        # Import required components
        from config.config_manager import ConfigManager
        from simulation.webots_manager import WebotsManager
        from simulation.webots_environment_controller import WebotsEnvironmentController
        from simulation.webots_robot_spawner import WebotsRobotSpawner
        
        # Create component instances
        webots_manager = WebotsManager(config_manager)
        environment_controller = WebotsEnvironmentController(config_manager)
        robot_spawner = WebotsRobotSpawner(config_manager.get('robot_spawner', {}))
        
        # Connect components
        environment_controller.set_webots_manager(webots_manager)
        robot_spawner.set_webots_manager(webots_manager)
        
        # Run the specific test
        if hasattr(test_instance, test_name):
            test_method = getattr(test_instance, test_name)
            
            # Determine required parameters based on test method
            if test_name == "test_webots_availability":
                await test_method(webots_manager)
            elif test_name == "test_start_stop_simulation":
                await test_method(webots_manager)
            elif test_name == "test_world_file_creation":
                await test_method(webots_manager)
            elif test_name == "test_robot_spawning_and_tracking":
                await test_method(webots_manager, robot_spawner)
            elif test_name == "test_robot_command_execution":
                await test_method(webots_manager)
            elif test_name == "test_robot_formations":
                await test_method(webots_manager)
            elif test_name == "test_environment_manipulation":
                await test_method(webots_manager, environment_controller)
            elif test_name == "test_environment_state_persistence":
                await test_method(environment_controller)
            elif test_name == "test_emergency_stop":
                await test_method(webots_manager)
            elif test_name == "test_performance_metrics":
                await test_method(webots_manager, environment_controller, robot_spawner)
            elif test_name == "test_full_integration_scenario":
                await test_method(webots_manager, environment_controller, robot_spawner)
            else:
                print(f"❌ Unknown test: {test_name}")
                return False
            
            print(f"\n✅ Test {test_name} completed successfully!")
            return True
            
        else:
            print(f"❌ Test method {test_name} not found")
            return False
            
    except Exception as e:
        print(f"\n❌ Test {test_name} failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        try:
            if 'webots_manager' in locals() and webots_manager.simulation_running:
                await webots_manager.stop_simulation()
        except:
            pass


def list_available_tests():
    """List all available integration tests."""
    test_instance = TestWebotsRealIntegration()
    test_methods = [method for method in dir(test_instance) 
                   if method.startswith('test_') and callable(getattr(test_instance, method))]
    
    print("📋 Available Integration Tests:")
    print("=" * 40)
    for i, test_method in enumerate(test_methods, 1):
        # Get test description from docstring
        method = getattr(test_instance, test_method)
        description = method.__doc__.split('\n')[0].strip() if method.__doc__ else "No description"
        print(f"{i:2d}. {test_method}")
        print(f"    {description}")
    print()


async def interactive_test_runner():
    """Interactive test runner."""
    print("🤖 Webots Integration Test Runner")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Run all integration tests")
        print("2. Run specific test")
        print("3. List available tests")
        print("4. Exit")
        
        try:
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                print("\n🚀 Running all integration tests...")
                await run_integration_tests()
                
            elif choice == "2":
                list_available_tests()
                test_name = input("Enter test name (without 'test_' prefix): ").strip()
                if not test_name.startswith('test_'):
                    test_name = f'test_{test_name}'
                await run_specific_test(test_name)
                
            elif choice == "3":
                list_available_tests()
                
            elif choice == "4":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please enter 1-4.")
                
        except KeyboardInterrupt:
            print("\n👋 Interrupted by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run Webots integration tests")
    parser.add_argument("--test", help="Run specific test")
    parser.add_argument("--list", action="store_true", help="List available tests")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    if args.list:
        list_available_tests()
        return
    
    if args.interactive:
        asyncio.run(interactive_test_runner())
        return
    
    if args.test:
        test_name = args.test
        if not test_name.startswith('test_'):
            test_name = f'test_{test_name}'
        
        success = asyncio.run(run_specific_test(test_name))
        sys.exit(0 if success else 1)
    
    # Default: run all tests
    print("🚀 Running all Webots integration tests...")
    try:
        asyncio.run(run_integration_tests())
        print("\n🎉 All tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
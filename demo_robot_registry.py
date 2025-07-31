#!/usr/bin/env python3
"""
Demonstration script for the Robot Registry functionality.

Shows robot registration, health monitoring, and capability discovery.
"""

import asyncio
import time
from task_orchestrator.robot_registry import RobotRegistry, RobotCapability
from core.data_models import RobotState, RobotStatus


async def demo_robot_registry():
    """Demonstrate robot registry functionality."""
    print("=== Robot Registry Demo ===\n")
    
    # Create registry with short intervals for demo
    config = {
        'heartbeat_timeout': 3.0,
        'health_check_interval': 1.0
    }
    registry = RobotRegistry(config)
    
    # Start the registry
    print("1. Starting robot registry...")
    await registry.start()
    print("   ✓ Registry started with health monitoring\n")
    
    # Register some robots
    print("2. Registering robots...")
    
    robots = [
        {
            'id': 'tiago_001',
            'position': (0.0, 0.0, 0.0),
            'status': RobotStatus.IDLE,
            'battery': 90.0,
            'capabilities': {RobotCapability.NAVIGATION, RobotCapability.MANIPULATION}
        },
        {
            'id': 'tiago_002', 
            'position': (2.0, 1.0, 0.0),
            'status': RobotStatus.IDLE,
            'battery': 85.0,
            'capabilities': {RobotCapability.NAVIGATION, RobotCapability.INSPECTION}
        },
        {
            'id': 'mobile_001',
            'position': (1.0, 3.0, 0.0),
            'status': RobotStatus.MOVING,
            'battery': 70.0,
            'capabilities': {RobotCapability.NAVIGATION, RobotCapability.SENSING}
        }
    ]
    
    for robot in robots:
        state = RobotState(
            robot_id=robot['id'],
            position=robot['position'],
            orientation=(0.0, 0.0, 0.0, 1.0),
            status=robot['status'],
            battery_level=robot['battery']
        )
        
        success = registry.register_robot(robot['id'], state, robot['capabilities'])
        print(f"   ✓ Registered {robot['id']} - Success: {success}")
    
    print()
    
    # Show fleet status
    print("3. Fleet status:")
    status = registry.get_fleet_status()
    print(f"   Total robots: {status['total_robots']}")
    print(f"   Healthy robots: {status['healthy_robots']}")
    print(f"   Available robots: {status['available_robots']}")
    print(f"   Status distribution: {status['status_distribution']}")
    print(f"   Capability distribution: {status['capability_distribution']}")
    print()
    
    # Show available robots
    print("4. Available robots for tasks:")
    available = registry.get_available_robots()
    print(f"   Available: {available}")
    print()
    
    # Show capability queries
    print("5. Robots by capability:")
    for capability in [RobotCapability.NAVIGATION, RobotCapability.MANIPULATION, RobotCapability.INSPECTION]:
        robots_with_cap = registry.get_robots_by_capability(capability)
        print(f"   {capability}: {robots_with_cap}")
    print()
    
    # Simulate heartbeats
    print("6. Simulating heartbeats...")
    for i in range(3):
        print(f"   Heartbeat round {i+1}")
        for robot in robots[:2]:  # Only send heartbeats for first 2 robots
            registry.heartbeat(robot['id'])
            print(f"     ✓ Heartbeat from {robot['id']}")
        await asyncio.sleep(1.0)
    print()
    
    # Wait for health monitoring to detect missing heartbeats
    print("7. Waiting for health monitoring (mobile_001 will go unhealthy)...")
    await asyncio.sleep(4.0)
    
    # Check health status
    print("8. Updated fleet health:")
    healthy = registry.get_healthy_robots()
    status = registry.get_fleet_status()
    print(f"   Healthy robots: {healthy}")
    print(f"   Unhealthy robots: {status['unhealthy_robots']}")
    print()
    
    # Demonstrate capability discovery
    print("9. Capability discovery:")
    test_robots = ['tiago_003', 'mobile_002', 'generic_001']
    for robot_id in test_robots:
        discovered = registry.discover_robot_capabilities(robot_id)
        print(f"   {robot_id}: {discovered}")
    print()
    
    # Show robot details
    print("10. Robot details:")
    for robot in robots:
        info = registry.get_robot_info(robot['id'])
        if info:
            print(f"   {robot['id']}:")
            print(f"     Position: {info.state.position}")
            print(f"     Status: {info.state.status}")
            print(f"     Battery: {info.state.battery_level}%")
            print(f"     Healthy: {info.is_healthy}")
            print(f"     Available: {info.is_available_for_task()}")
            print(f"     Capabilities: {info.capabilities}")
    print()
    
    # Health check
    print("11. Registry health check:")
    health = await registry.health_check()
    print(f"   Component: {health['component']}")
    print(f"   Status: {health['status']}")
    print(f"   Monitoring active: {health['monitoring_active']}")
    print(f"   Total robots: {health['total_robots']}")
    print(f"   Healthy robots: {health['healthy_robots']}")
    print()
    
    # Stop the registry
    print("12. Stopping registry...")
    await registry.stop()
    print("   ✓ Registry stopped")
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(demo_robot_registry())
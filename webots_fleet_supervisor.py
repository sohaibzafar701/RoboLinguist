#!/usr/bin/env python3
"""
Webots Fleet Supervisor Control

This script uses a single Supervisor to control all 10 robots.
This is simpler than multiple external controllers.

SETUP:
1. Open Webots
2. Load webots_fleet_world.wbt
3. Start simulation (play button)
4. Run this script
5. Use simple commands to control the fleet
"""

import os
import sys
import asyncio
import time
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Set robot name FIRST before any imports
os.environ['WEBOTS_ROBOT_NAME'] = 'fleet_supervisor'

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def setup_webots_api():
    """Setup Webots Python API."""
    import os
    import platform
    
    # Common Webots installation paths
    webots_install_paths = []
    
    if platform.system() == "Windows":
        webots_install_paths = [
            r"C:\Program Files\Webots",
            r"C:\Program Files (x86)\Webots",
            r"C:\Users\{}\AppData\Local\Programs\Webots".format(os.getenv('USERNAME', '')),
        ]
    elif platform.system() == "Darwin":
        webots_install_paths = [
            "/Applications/Webots.app",
        ]
    else:
        webots_install_paths = [
            "/usr/local/webots",
            "/opt/webots",
            "/snap/webots/current/usr/share/webots",
        ]
    
    # Check if WEBOTS_HOME is already set
    webots_home = os.getenv('WEBOTS_HOME')
    if webots_home and os.path.exists(webots_home):
        python_path = os.path.join(webots_home, 'lib', 'controller', 'python')
        if os.path.exists(python_path):
            if python_path not in sys.path:
                sys.path.insert(0, python_path)
            print(f"📁 Using WEBOTS_HOME: {webots_home}")
            return True
    
    # Try to find Webots installation
    for install_path in webots_install_paths:
        if os.path.exists(install_path):
            # Set WEBOTS_HOME environment variable
            os.environ['WEBOTS_HOME'] = install_path
            print(f"📁 Found Webots installation: {install_path}")
            print(f"🔧 Set WEBOTS_HOME = {install_path}")
            
            # Add Python API to path
            python_path = os.path.join(install_path, 'lib', 'controller', 'python')
            if os.path.exists(python_path):
                if python_path not in sys.path:
                    sys.path.insert(0, python_path)
                print(f"📁 Added Python API path: {python_path}")
                return True
    
    return False

# Setup Webots API
if not setup_webots_api():
    print("❌ Could not find Webots installation")
    sys.exit(1)

try:
    from controller import Supervisor
    WEBOTS_AVAILABLE = True
    print("✅ Webots Python API available")
except ImportError as e:
    WEBOTS_AVAILABLE = False
    print(f"❌ Webots Python API not available: {e}")
    sys.exit(1)


class RobotState:
    """State of a single robot."""
    
    def __init__(self, robot_id: int, node):
        self.robot_id = robot_id
        self.node = node
        self.target_position = None
        self.status = "idle"
        self.last_position = None
        
    def get_position(self) -> Tuple[float, float, float]:
        """Get current robot position."""
        if self.node:
            return self.node.getPosition()
        return (0, 0, 0)
    
    def set_target(self, x: float, y: float):
        """Set target position."""
        self.target_position = (x, y)
        self.status = "moving"
        print(f"🎯 Robot {self.robot_id} target set to ({x:.2f}, {y:.2f})")
    
    def stop(self):
        """Stop robot."""
        self.target_position = None
        self.status = "stopped"
        print(f"🛑 Robot {self.robot_id} stopped")
    
    def update_position(self, x: float, y: float, z: float = 0):
        """Update robot position using supervisor."""
        if self.node:
            self.node.getField('translation').setSFVec3f([x, y, z])
            self.last_position = (x, y, z)
    
    def move_towards_target(self, speed: float = 0.1):
        """Move robot towards target position."""
        if not self.target_position or not self.node:
            return
        
        current_pos = self.get_position()
        target_x, target_y = self.target_position
        
        # Calculate direction
        dx = target_x - current_pos[0]
        dy = target_y - current_pos[1]
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance < 0.1:  # Reached target
            self.status = "idle"
            self.target_position = None
            print(f"✅ Robot {self.robot_id} reached target")
        else:
            # Move towards target
            move_x = current_pos[0] + (dx / distance) * speed
            move_y = current_pos[1] + (dy / distance) * speed
            self.update_position(move_x, move_y, current_pos[2])


class FleetSupervisorController:
    """Fleet controller using Webots Supervisor."""
    
    def __init__(self):
        self.supervisor = Supervisor()
        self.timestep = int(self.supervisor.getBasicTimeStep())
        self.robots = {}  # robot_id -> RobotState
        self.running = False
        
        print("🚀 Fleet Supervisor Controller initialized")
    
    async def initialize(self):
        """Initialize the fleet controller."""
        print("🔧 Initializing fleet supervisor controller...")
        
        # Find all robots in the simulation
        self.discover_robots()
        
        # Start control loop
        self.running = True
        
        print("✅ Fleet supervisor controller ready for commands!")
    
    def discover_robots(self):
        """Discover all robots in the simulation."""
        print("🔍 Discovering robots...")
        
        for i in range(10):  # We know we have 10 robots
            robot_name = f"robot_{i}"
            robot_node = self.supervisor.getFromDef(robot_name)
            
            if robot_node:
                self.robots[i] = RobotState(i, robot_node)
                pos = robot_node.getPosition()
                print(f"   Found {robot_name} at ({pos[0]:.2f}, {pos[1]:.2f})")
            else:
                print(f"   ❌ Could not find {robot_name}")
        
        print(f"✅ Discovered {len(self.robots)} robots")
    
    def step_simulation(self):
        """Step the simulation and update robots."""
        # Step the supervisor
        if self.supervisor.step(self.timestep) == -1:
            return False
        
        # Update all robots
        for robot in self.robots.values():
            if robot.status == "moving":
                robot.move_towards_target()
        
        return True
    
    async def process_simple_command(self, command: str) -> str:
        """Process a simple command."""
        command = command.lower().strip()
        print(f"\n💬 Processing command: '{command}'")
        
        try:
            if command in ['center', 'middle']:
                await self.move_all_robots(0, 0)
                return "✅ Moving all robots to center"
            
            elif command in ['circle', 'round']:
                await self.create_formation('circle')
                return "✅ Creating circle formation"
            
            elif command in ['line', 'row']:
                await self.create_formation('line')
                return "✅ Creating line formation"
            
            elif command in ['grid', 'square']:
                await self.create_formation('grid')
                return "✅ Creating grid formation"
            
            elif command in ['spread', 'scatter']:
                await self.create_formation('spread')
                return "✅ Spreading robots around"
            
            elif command in ['stop', 'halt']:
                for robot in self.robots.values():
                    robot.stop()
                return "✅ All robots stopped"
            
            elif command.startswith('robot'):
                # Individual robot command like "robot 3 center"
                parts = command.split()
                if len(parts) >= 3:
                    try:
                        robot_id = int(parts[1])
                        action = parts[2]
                        
                        if robot_id in self.robots:
                            if action in ['center', 'middle']:
                                self.robots[robot_id].set_target(0, 0)
                                return f"✅ Moving robot {robot_id} to center"
                            elif action == 'stop':
                                self.robots[robot_id].stop()
                                return f"✅ Robot {robot_id} stopped"
                        else:
                            return f"❌ Robot {robot_id} not found"
                    except ValueError:
                        return "❌ Invalid robot ID"
            
            elif command in ['status', 'info']:
                return self.get_fleet_status_string()
            
            elif command in ['demo', 'show']:
                await self.run_demo_sequence()
                return "✅ Running demo sequence"
            
            else:
                return f"❌ Unknown command: {command}. Try: center, circle, line, grid, spread, stop, status, demo"
                
        except Exception as e:
            return f"❌ Error processing command: {e}"
    
    async def create_formation(self, formation_type: str):
        """Create a robot formation."""
        print(f"🎭 Creating {formation_type} formation...")
        
        if formation_type == 'circle':
            # Arrange robots in a circle
            center_x, center_y = 0, 0
            radius = 4.0
            
            for i, robot in enumerate(self.robots.values()):
                angle = (2 * math.pi * i) / len(self.robots)
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                robot.set_target(x, y)
        
        elif formation_type == 'line':
            # Arrange robots in a line
            for i, robot in enumerate(self.robots.values()):
                x = -4.5 + i * 1.0
                y = 0
                robot.set_target(x, y)
        
        elif formation_type == 'grid':
            # Arrange robots in a 5x2 grid
            for i, robot in enumerate(self.robots.values()):
                x = -2 + (i % 5) * 1.0
                y = -0.5 + (i // 5) * 1.0
                robot.set_target(x, y)
        
        elif formation_type == 'spread':
            # Spread robots randomly around the arena
            import random
            for robot in self.robots.values():
                x = random.uniform(-8, 8)
                y = random.uniform(-8, 8)
                robot.set_target(x, y)
    
    async def move_all_robots(self, target_x: float, target_y: float):
        """Move all robots to a target area."""
        print(f"🎯 Moving all robots to ({target_x:.2f}, {target_y:.2f})")
        
        for i, robot in enumerate(self.robots.values()):
            # Spread robots around the target
            offset_x = (i % 5 - 2) * 0.5
            offset_y = (i // 5 - 1) * 0.5
            robot.set_target(target_x + offset_x, target_y + offset_y)
    
    async def run_demo_sequence(self):
        """Run a demonstration sequence."""
        print("🎬 Running demo sequence...")
        
        formations = ['line', 'circle', 'grid', 'spread']
        
        for formation in formations:
            await self.create_formation(formation)
            print(f"   Showing {formation} formation...")
            
            # Wait for robots to reach positions
            for _ in range(100):  # Wait up to 10 seconds
                if not self.step_simulation():
                    break
                await asyncio.sleep(0.1)
                
                # Check if all robots are idle (reached targets)
                if all(robot.status == "idle" for robot in self.robots.values()):
                    break
            
            await asyncio.sleep(2)  # Pause between formations
    
    def get_fleet_status_string(self) -> str:
        """Get current fleet status as string."""
        total_robots = len(self.robots)
        moving_count = sum(1 for r in self.robots.values() if r.status == "moving")
        stopped_count = sum(1 for r in self.robots.values() if r.status == "stopped")
        idle_count = sum(1 for r in self.robots.values() if r.status == "idle")
        
        status = f"📊 Fleet Status: {total_robots} robots - {moving_count} moving, {stopped_count} stopped, {idle_count} idle\n"
        
        # Add individual robot positions
        for robot_id, robot in self.robots.items():
            pos = robot.get_position()
            status += f"   Robot {robot_id}: ({pos[0]:.1f}, {pos[1]:.1f}) - {robot.status}\n"
        
        return status.strip()
    
    def shutdown(self):
        """Shutdown the fleet controller."""
        print("🛑 Shutting down fleet supervisor controller...")
        self.running = False


async def main():
    """Main demonstration function."""
    print("🤖🌍 WEBOTS FLEET SUPERVISOR DEMONSTRATION")
    print("=" * 60)
    print("This demo uses a Supervisor to control all 10 robots")
    print("=" * 60)
    
    if not WEBOTS_AVAILABLE:
        print("❌ Webots API not available. Please install Webots.")
        return 1
    
    # Initialize fleet controller
    fleet = FleetSupervisorController()
    
    try:
        print("🚀 Initializing fleet supervisor controller...")
        await fleet.initialize()
        
        print("\n🎯 Fleet ready! Try these commands:")
        print("   - 'center' - Move all robots to center")
        print("   - 'circle' - Form circle formation")
        print("   - 'line' - Form line formation")
        print("   - 'grid' - Form grid formation")
        print("   - 'spread' - Spread robots randomly")
        print("   - 'stop' - Stop all robots")
        print("   - 'robot 3 center' - Move robot 3 to center")
        print("   - 'status' - Show fleet status")
        print("   - 'demo' - Run demo sequence")
        print("   - 'quit' to exit")
        
        # Interactive command loop
        while True:
            try:
                command = input("\n💬 Enter command: ").strip()
                
                if command.lower() in ['quit', 'exit', 'q']:
                    break
                
                if command:
                    result = await fleet.process_simple_command(command)
                    print(f"📋 Result: {result}")
                    
                    # Continue stepping simulation
                    for _ in range(10):
                        if not fleet.step_simulation():
                            break
                        await asyncio.sleep(0.01)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n👋 Shutting down...")
        fleet.shutdown()
        return 0
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        fleet.shutdown()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
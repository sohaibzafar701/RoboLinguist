"""
Multi-Robot Fleet Controller for Webots
Integrates with ChatGPT robotics system for natural language robot control.
"""

from controller import Robot, Supervisor
import json
import time
import math
import sys
import os
from typing import Dict, List, Optional, Any


class ChatGPTFleetController:
    """
    Fleet controller that manages multiple robots in Webots simulation.
    Provides interface for ChatGPT command integration.
    """
    
    def __init__(self):
        # Initialize Webots supervisor
        self.supervisor = Supervisor()
        self.timestep = int(self.supervisor.getBasicTimeStep())
        
        # Robot management
        self.robots = {}
        self.robot_states = {}
        self.command_queue = []
        
        # Communication
        self.status_file = "robot_status.json"
        self.command_file = "robot_commands.json"
        
        # Initialize robot fleet
        self.discover_robots()
        
        print(f"✅ Fleet Controller initialized with {len(self.robots)} robots")
    
    def discover_robots(self):
        """Find all robots in the simulation."""
        robot_count = 0
        
        # Look for robots with standard naming pattern
        for i in range(50):  # Check up to 50 robots
            robot_name = f"robot_{i}"
            robot_node = self.supervisor.getFromDef(robot_name)
            
            if robot_node is not None:
                self.robots[robot_name] = {
                    'node': robot_node,
                    'translation_field': robot_node.getField('translation'),
                    'rotation_field': robot_node.getField('rotation')
                }
                
                self.robot_states[robot_name] = {
                    'position': [0, 0, 0],
                    'rotation': [0, 0, 1, 0],
                    'status': 'idle',
                    'target': None,
                    'battery': 100.0,
                    'last_command_time': time.time()
                }
                
                robot_count += 1
                print(f"🤖 Found {robot_name}")
        
        print(f"📊 Total robots discovered: {robot_count}")
    
    def get_robot_position(self, robot_name: str) -> Optional[List[float]]:
        """Get current robot position."""
        if robot_name in self.robots:
            position = self.robots[robot_name]['translation_field'].getSFVec3f()
            return [round(pos, 3) for pos in position]
        return None
    
    def get_robot_rotation(self, robot_name: str) -> Optional[List[float]]:
        """Get current robot rotation."""
        if robot_name in self.robots:
            rotation = self.robots[robot_name]['rotation_field'].getSFRotation()
            return [round(rot, 3) for rot in rotation]
        return None
    
    def move_robot(self, robot_name: str, target_position: List[float]) -> bool:
        """Move robot to target position."""
        if robot_name not in self.robots:
            print(f"❌ Robot {robot_name} not found")
            return False
        
        try:
            # Set robot position using supervisor
            translation_field = self.robots[robot_name]['translation_field']
            translation_field.setSFVec3f(target_position)
            
            # Update robot state
            self.robot_states[robot_name]['target'] = target_position
            self.robot_states[robot_name]['status'] = 'moving'
            self.robot_states[robot_name]['last_command_time'] = time.time()
            
            print(f"🎯 Moving {robot_name} to {target_position}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to move {robot_name}: {e}")
            return False
    
    def rotate_robot(self, robot_name: str, target_rotation: List[float]) -> bool:
        """Rotate robot to target orientation."""
        if robot_name not in self.robots:
            print(f"❌ Robot {robot_name} not found")
            return False
        
        try:
            # Set robot rotation using supervisor
            rotation_field = self.robots[robot_name]['rotation_field']
            rotation_field.setSFRotation(target_rotation)
            
            # Update robot state
            self.robot_states[robot_name]['status'] = 'rotating'
            self.robot_states[robot_name]['last_command_time'] = time.time()
            
            print(f"🔄 Rotating {robot_name} to {target_rotation}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to rotate {robot_name}: {e}")
            return False
    
    def stop_robot(self, robot_name: str) -> bool:
        """Stop robot movement."""
        if robot_name not in self.robots:
            return False
        
        # Update robot state
        self.robot_states[robot_name]['status'] = 'idle'
        self.robot_states[robot_name]['target'] = None
        
        print(f"⏹️ Stopped {robot_name}")
        return True
    
    def get_fleet_status(self) -> Dict[str, Any]:
        """Get status of all robots."""
        status = {
            'timestamp': time.time(),
            'robot_count': len(self.robots),
            'robots': {}
        }
        
        for robot_name in self.robots:
            current_pos = self.get_robot_position(robot_name)
            current_rot = self.get_robot_rotation(robot_name)
            
            # Update position in state
            if current_pos:
                self.robot_states[robot_name]['position'] = current_pos
            if current_rot:
                self.robot_states[robot_name]['rotation'] = current_rot
            
            status['robots'][robot_name] = {
                'position': current_pos,
                'rotation': current_rot,
                'status': self.robot_states[robot_name]['status'],
                'battery': self.robot_states[robot_name]['battery'],
                'target': self.robot_states[robot_name]['target']
            }
        
        return status
    
    def execute_formation(self, formation_type: str, **params) -> bool:
        """Execute formation command for all robots."""
        robot_names = list(self.robots.keys())
        robot_count = len(robot_names)
        
        if robot_count == 0:
            print("❌ No robots available for formation")
            return False
        
        print(f"🎭 Executing {formation_type} formation with {robot_count} robots")
        
        try:
            if formation_type == "line":
                spacing = params.get('spacing', 1.0)
                return self._create_line_formation(robot_names, spacing)
            
            elif formation_type == "circle":
                radius = params.get('radius', 2.0)
                return self._create_circle_formation(robot_names, radius)
            
            elif formation_type == "grid":
                spacing = params.get('spacing', 1.0)
                return self._create_grid_formation(robot_names, spacing)
            
            elif formation_type == "random":
                area_size = params.get('area_size', 5.0)
                return self._create_random_formation(robot_names, area_size)
            
            else:
                print(f"❌ Unknown formation type: {formation_type}")
                return False
                
        except Exception as e:
            print(f"❌ Formation execution failed: {e}")
            return False
    
    def _create_line_formation(self, robot_names: List[str], spacing: float) -> bool:
        """Create line formation."""
        for i, robot_name in enumerate(robot_names):
            x = (i - (len(robot_names) - 1) / 2) * spacing
            y = 0.0
            z = 0.0
            self.move_robot(robot_name, [x, y, z])
        
        print(f"📏 Line formation created with spacing {spacing}")
        return True
    
    def _create_circle_formation(self, robot_names: List[str], radius: float) -> bool:
        """Create circle formation."""
        robot_count = len(robot_names)
        
        for i, robot_name in enumerate(robot_names):
            angle = (2 * math.pi * i) / robot_count
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            z = 0.0
            
            # Also set rotation to face center
            rotation = [0, 0, 1, angle + math.pi]
            
            self.move_robot(robot_name, [x, y, z])
            self.rotate_robot(robot_name, rotation)
        
        print(f"⭕ Circle formation created with radius {radius}")
        return True
    
    def _create_grid_formation(self, robot_names: List[str], spacing: float) -> bool:
        """Create grid formation."""
        robot_count = len(robot_names)
        grid_size = int(math.ceil(math.sqrt(robot_count)))
        
        for i, robot_name in enumerate(robot_names):
            row = i // grid_size
            col = i % grid_size
            
            x = (col - (grid_size - 1) / 2) * spacing
            y = (row - (grid_size - 1) / 2) * spacing
            z = 0.0
            
            self.move_robot(robot_name, [x, y, z])
        
        print(f"🔲 Grid formation created with spacing {spacing}")
        return True
    
    def _create_random_formation(self, robot_names: List[str], area_size: float) -> bool:
        """Create random formation."""
        import random
        
        for robot_name in robot_names:
            x = random.uniform(-area_size/2, area_size/2)
            y = random.uniform(-area_size/2, area_size/2)
            z = 0.0
            
            self.move_robot(robot_name, [x, y, z])
        
        print(f"🎲 Random formation created in {area_size}x{area_size} area")
        return True
    
    def process_commands(self) -> None:
        """Process commands from external system."""
        try:
            # Check for command file
            if os.path.exists(self.command_file):
                with open(self.command_file, 'r') as f:
                    commands = json.load(f)
                
                # Process each command
                for command in commands:
                    self.execute_command(command)
                
                # Clear command file
                os.remove(self.command_file)
                
        except Exception as e:
            print(f"❌ Error processing commands: {e}")
    
    def execute_command(self, command: Dict[str, Any]) -> bool:
        """Execute a single command."""
        try:
            action = command.get('action')
            robot_id = command.get('robot_id')
            params = command.get('parameters', {})
            
            if action == 'move' and robot_id:
                target_pos = params.get('target_position', [0, 0, 0])
                return self.move_robot(robot_id, target_pos)
            
            elif action == 'rotate' and robot_id:
                target_rot = params.get('target_rotation', [0, 0, 1, 0])
                return self.rotate_robot(robot_id, target_rot)
            
            elif action == 'stop' and robot_id:
                return self.stop_robot(robot_id)
            
            elif action == 'formation':
                formation_type = params.get('formation_type', 'line')
                return self.execute_formation(formation_type, **params)
            
            else:
                print(f"❌ Unknown command: {action}")
                return False
                
        except Exception as e:
            print(f"❌ Command execution failed: {e}")
            return False
    
    def save_status(self) -> None:
        """Save robot status to file for external access."""
        try:
            status = self.get_fleet_status()
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            print(f"❌ Failed to save status: {e}")
    
    def demo_sequence(self) -> None:
        """Run a demo sequence to show capabilities."""
        print("🎬 Starting demo sequence...")
        
        # Demo formations
        formations = [
            ('line', {'spacing': 1.5}),
            ('circle', {'radius': 3.0}),
            ('grid', {'spacing': 1.2}),
            ('random', {'area_size': 6.0})
        ]
        
        for formation_type, params in formations:
            print(f"🎭 Demo: {formation_type} formation")
            self.execute_formation(formation_type, **params)
            
            # Wait between formations
            for _ in range(100):  # ~3 seconds at 32ms timestep
                if self.supervisor.step(self.timestep) == -1:
                    return
        
        print("🎬 Demo sequence completed!")
    
    def run(self) -> None:
        """Main control loop."""
        print("🚀 Fleet Controller running...")
        
        step_count = 0
        demo_interval = 1000  # Run demo every ~30 seconds
        status_interval = 100   # Save status every ~3 seconds
        
        while self.supervisor.step(self.timestep) != -1:
            step_count += 1
            
            # Process external commands
            self.process_commands()
            
            # Save status periodically
            if step_count % status_interval == 0:
                self.save_status()
            
            # Run demo periodically (optional)
            if step_count % demo_interval == 0:
                print("🎭 Running periodic demo...")
                self.demo_sequence()
            
            # Update robot states
            for robot_name in self.robots:
                state = self.robot_states[robot_name]
                
                # Simulate battery drain
                if state['status'] != 'idle':
                    state['battery'] = max(0, state['battery'] - 0.001)
                
                # Check if robot reached target
                if state['target'] and state['status'] == 'moving':
                    current_pos = self.get_robot_position(robot_name)
                    if current_pos and self._distance(current_pos, state['target']) < 0.1:
                        state['status'] = 'idle'
                        state['target'] = None
    
    def _distance(self, pos1: List[float], pos2: List[float]) -> float:
        """Calculate distance between two positions."""
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2)))


if __name__ == "__main__":
    # Create and run the fleet controller
    controller = ChatGPTFleetController()
    controller.run()
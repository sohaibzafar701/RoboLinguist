# Webots Setup Guide for ChatGPT for Robots

This guide shows you how to run the complete ChatGPT for Robots system (Tasks 1-6) in Webots simulation using the ROS2 bridge.

## Overview

The system architecture is:
```
Core Components (Tasks 1-6) ←→ ROS2 Topics ←→ ROS2 Bridge ←→ Webots Simulation
```

- **Core Components**: Remain completely unchanged, use standard ROS2
- **ROS2 Bridge**: Translates between ROS2 and Webots API
- **Webots**: Provides realistic robot simulation

## Prerequisites

### 1. Webots Installation

**Windows:**
1. Download Webots from: https://cyberbotics.com/
2. Install to default location (usually `C:\Program Files\Webots`)
3. Add Webots to your PATH or set `WEBOTS_HOME` environment variable

**macOS:**
1. Download Webots from: https://cyberbotics.com/
2. Install to `/Applications/Webots.app`

**Linux:**
1. Download Webots from: https://cyberbotics.com/
2. Install to `/usr/local/webots` or `/opt/webots`

### 2. Python Dependencies

Install required packages:
```bash
pip install asyncio logging dataclasses typing
```

**Optional (for full ROS2 support):**
```bash
# Install ROS2 if you want real ROS2 integration
# Otherwise, the system uses mock ROS2 for testing
pip install rclpy geometry_msgs sensor_msgs nav_msgs std_msgs
```

## Setup Steps

### 1. Prepare Webots World

1. **Open Webots**
2. **Load the fleet world:**
   - File → Open World
   - Navigate to your project directory
   - Open `webots_working_demo/minimal_fleet_world.wbt`

3. **Verify robot setup:**
   - You should see multiple robots in the simulation
   - Each robot should be named `robot_0`, `robot_1`, etc.
   - There should be a `fleet_supervisor` node

### 2. Configure the Bridge

Edit the bridge configuration in your test script:

```python
bridge_config = BridgeConfig(
    use_simulation=True,
    webots_world_file="webots_working_demo/minimal_fleet_world.wbt",
    robot_count=5,  # Match number of robots in your world
    update_rate_hz=10.0,
    enable_safety=True,
    enable_distributed=False
)
```

### 3. Run the System

#### Option A: Complete System Test

Run the comprehensive test that demonstrates all components:

```bash
python test_complete_ros2_bridge.py
```

This will:
- Start the ROS2 simulation bridge
- Initialize all core components (Tasks 1-6)
- Run tests for each system component
- Show robot movement in Webots
- Display comprehensive results

#### Option B: Individual Component Testing

Test specific components:

```python
# Test just the bridge
from simulation_bridge.ros2_simulation_bridge import ROS2SimulationBridge

bridge = ROS2SimulationBridge()
await bridge.initialize()

# Test robot movement
await bridge.send_fleet_command('formation', formation='circle')
```

#### Option C: Core Components with ROS2

Use the core components exactly as you would with real robots:

```python
# These components work unchanged!
from services.command_translator import CommandTranslator
from task_orchestrator.robot_registry import RobotRegistry

# They connect to ROS2 topics provided by the bridge
translator = CommandTranslator()
result = await translator.translate_with_context("Move all robots to center")
```

## Running Instructions

### Step 1: Start Webots
1. Open Webots
2. Load `webots_working_demo/minimal_fleet_world.wbt`
3. Click the "Play" button to start simulation
4. Leave Webots running

### Step 2: Run the Bridge
In your terminal:
```bash
cd /path/to/your/project
python test_complete_ros2_bridge.py
```

### Step 3: Watch the Magic!
You should see:
1. **Console Output**: Detailed logs of system initialization and testing
2. **Webots Simulation**: Robots moving in formations and responding to commands
3. **Test Results**: Comprehensive results showing all components working

## Expected Output

### Console Output:
```
INFO - Setting up simulation bridge...
INFO - Simulation bridge ready!
INFO - Available ROS2 topics for core components:
INFO -   Robot 0: /robot_0/cmd_vel, /robot_0/odom
INFO -   Robot 1: /robot_1/cmd_vel, /robot_1/odom
INFO - Setting up core components...
INFO - Components are using standard ROS2 - no simulation-specific code!

=== Testing Robot Discovery ===
INFO - ✓ Discovered robot 0 at [0.0, 0.0, 0.0]
INFO - ✓ Discovered robot 1 at [1.0, 0.0, 0.0]

=== Testing Context-Aware Translation ===
INFO - Test 1: 'Move all robots to the center'
INFO - Available robots: ['0', '1', '2', '3', '4']
INFO - ✓ Generated 1 commands (confidence: 0.85)

=== Testing Robot Movement via Bridge ===
INFO - Testing movement 1: {'type': 'formation', 'formation': 'circle'}
INFO - ✓ Movement executed successfully
```

### Webots Simulation:
- Robots will move into formations
- You'll see circle, line, and grid formations
- Robots respond to emergency stop
- Real-time movement based on commands

## Troubleshooting

### Issue: "Webots API not available"
**Solution:** 
- Ensure Webots is installed
- Set `WEBOTS_HOME` environment variable
- Check that `WEBOTS_HOME/lib/controller/python` exists

### Issue: "Robot not found"
**Solution:**
- Check robot names in Webots world (should be `robot_0`, `robot_1`, etc.)
- Verify `robot_count` in bridge config matches actual robots
- Ensure robots have DEF names in Webots

### Issue: "ROS2 not available"
**Solution:**
- This is normal! The system uses mock ROS2 for testing
- For full ROS2 integration, install ROS2 packages
- The core functionality works without real ROS2

### Issue: Robots not moving
**Solution:**
- Check that Webots simulation is running (not paused)
- Verify robot nodes have translation fields
- Check console for movement command logs

## Key Features Demonstrated

### ✅ Core Components Unchanged
- CommandTranslator works exactly as with real robots
- RobotRegistry discovers robots via ROS2 topics
- SafetyChecker validates commands normally
- TaskManager orchestrates tasks as usual

### ✅ ROS2 Bridge Translation
- Translates ROS2 `/cmd_vel` to Webots movement
- Publishes robot states to ROS2 `/odom` topics
- Handles fleet commands via ROS2 topics
- Emergency stop via ROS2 messages

### ✅ Real-time Simulation
- 10Hz update rate for smooth movement
- Real-time robot state synchronization
- Formation commands with live feedback
- Context-aware command translation

### ✅ Safety Integration
- Safety validation works in simulation
- Emergency stop affects all simulated robots
- Boundary checking with simulated environment

## Next Steps

### For Real Robot Deployment:
1. **Replace Bridge**: Swap ROS2 bridge with real ROS2 robot drivers
2. **No Code Changes**: Core components work unchanged
3. **Same Topics**: Use identical ROS2 topic structure
4. **Validated Logic**: All logic tested in simulation

### For Advanced Testing:
1. **Add More Robots**: Increase `robot_count` and add robots to Webots world
2. **Complex Scenarios**: Test multi-robot coordination
3. **Custom Commands**: Add new natural language commands
4. **Performance Testing**: Test with larger fleets

## Success Criteria

If everything works correctly, you should see:
- ✅ All tests pass (>90% success rate)
- ✅ Robots move smoothly in Webots
- ✅ Context-aware commands generate appropriate robot actions
- ✅ Safety systems prevent invalid commands
- ✅ Emergency stop works across all robots
- ✅ Core components report "using standard ROS2"

**Congratulations!** Your ChatGPT for Robots system is ready for real-world deployment!

## Support

If you encounter issues:
1. Check the console output for detailed error messages
2. Verify Webots world file has correct robot setup
3. Ensure all Python dependencies are installed
4. Check that Webots simulation is running (not paused)

The system is designed to be robust and provide clear error messages to help with troubleshooting.
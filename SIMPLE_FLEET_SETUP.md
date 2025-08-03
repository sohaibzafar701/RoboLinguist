# Simple Fleet Control Setup

## 🎯 Quick Setup

### Step 1: Load the Simple World
1. **Close the current world** in Webots (if any is open)
2. Go to `File` → `Open World`
3. Navigate to your project directory
4. Select **`simple_fleet_world.wbt`** (NOT the complex one)
5. The world will load with 10 robots and 1 supervisor

### Step 2: Start Simulation
1. Click the **Play button (▶️)** in Webots
2. You should see only ONE message: "Waiting for extern controller" for fleet_supervisor
3. The robots should be visible but not moving yet

### Step 3: Run the Controller
1. In your terminal, make sure virtual environment is active
2. Run: `.\run_fleet_supervisor.bat`
3. The script should connect successfully

## 🎮 Commands to Try

Once connected, try these commands:

- **`center`** - Move all robots to center
- **`circle`** - Form circle formation  
- **`line`** - Form line formation
- **`grid`** - Form grid formation
- **`spread`** - Spread robots randomly
- **`stop`** - Stop all robots
- **`robot 3 center`** - Move robot 3 to center
- **`status`** - Show fleet status
- **`demo`** - Run demo sequence
- **`quit`** - Exit

## 🔧 Key Differences

This simplified approach:
- ✅ Only supervisor has external controller
- ✅ Robots are controlled via supervisor API
- ✅ No complex multi-controller setup
- ✅ Direct position control
- ✅ Immediate visual feedback

## 🎯 Expected Behavior

You should see:
1. Script connects without "robot name" errors
2. All 10 robots discovered and controlled
3. Smooth movement when commands are given
4. Real-time position updates in Webots

Ready to test? Load `simple_fleet_world.wbt` and run the script! 🚀
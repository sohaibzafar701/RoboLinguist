# 🤖 RoboLinguist

**Advanced Context Aware, Natural Language Interface for Autonomous Robot Fleet Management**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![ROS2](https://img.shields.io/badge/ROS2-Humble-green.svg)](https://docs.ros.org/en/humble/)
[![Webots](https://img.shields.io/badge/Webots-2023b-orange.svg)](https://cyberbotics.com/)
[![Success Rate](https://img.shields.io/badge/Test%20Success%20Rate-92.3%25-brightgreen.svg)](#test-results)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

RoboLinguist is an advanced natural language interface for controlling robot fleets. Simply tell your robots what to do in plain English, and watch them execute complex tasks with intelligent coordination, safety validation, and real-time adaptation.

## 🎯 **What Makes RoboLinguist Special**

- **🗣️ Natural Language Control**: "Move all robots to the center" → Coordinated fleet movement
- **🧠 Context-Aware Intelligence**: Understands robot positions, capabilities, and environment
- **🛡️ Advanced Safety Systems**: Multi-layer safety validation with emergency stop capabilities
- **🔄 Real-Time Adaptation**: Dynamic task orchestration with distributed processing
- **🎮 Simulation Ready**: Full Webots integration for testing and development
- **⚡ Production Ready**: 92.3% test success rate with robust error handling

## 🚀 **Quick Start**

### Prerequisites
- Python 3.8+
- ROS2 Humble (optional, mock implementation available)
- Webots 2023b+ (for simulation)
- OpenRouter API key

### Installation

```bash
# Clone the repository
git clone https://github.com/sohaibzafar701/RoboLinguist.git
cd RoboLinguist

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure your API key
cp config/system_config.yaml.template config/system_config.yaml
# Edit config/system_config.yaml and add your OpenRouter API key
```

### 🔑 **API Key Setup**

1. **Get OpenRouter API Key:**
   - Visit [OpenRouter.ai](https://openrouter.ai/)
   - Sign up and get your API key

2. **Configure the system:**
   ```bash
   # Copy template to actual config
   cp config/system_config.yaml.template config/system_config.yaml
   
   # Edit the config file and replace 'your_openrouter_api_key_here' with your actual API key
   # You can use any text editor:
   notepad config/system_config.yaml  # Windows
   nano config/system_config.yaml     # Linux/Mac
   ```

3. **Verify setup:**
   ```bash
   python test_openrouter_live.py
   ```

### Run the Demo

```bash
# Start the complete system demo with Webots simulation
python run_webots_demo.py
```

Watch as RoboLinguist:
1. Discovers 5 simulated robots
2. Translates natural language commands
3. Executes formation maneuvers
4. Validates safety constraints
5. Demonstrates emergency stop capabilities

## 🎮 **Try It Yourself**

```python
from services.command_translator import CommandTranslator
from services.robotics_context_manager import RoboticsContextManager

# Initialize the system
translator = CommandTranslator()
context_manager = RoboticsContextManager()

# Give natural language commands
commands = [
    "Move all robots to the center",
    "Form a circle formation", 
    "Create a line formation with 2 meter spacing",
    "Move robot 0 to position 5, 3"
]

# Execute with context awareness
for command in commands:
    result = await translator.translate_with_context(command)
    print(f"✓ Generated {len(result.commands)} robot commands")
```

## 🏗️ **System Architecture**

RoboLinguist follows a modular, production-ready architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Natural Language Input                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Command Translator (LLM)                       │
│  • Context-aware translation                                │
│  • Formation command handling                               │
│  • Multi-robot coordination                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                Safety Validator                             │
│  • Multi-layer safety rules                                 │
│  • Zone restrictions                                        │
│  • Emergency stop system                                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Task Orchestrator                              │
│  • Distributed task management                              │
│  • Priority-based scheduling                                │
│  • Real-time monitoring                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                ROS2 Bridge                                  │
│  • Standard ROS2 topics                                     │
│  • Real robot compatibility                                 │
│  • Simulation integration                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│            Robot Fleet / Simulation                         │
│  • Real robots via ROS2                                     │
│  • Webots simulation                                        │
│  • Gazebo support (planned)                                 │
└─────────────────────────────────────────────────────────────┘
```

## 🧩 **Core Components**

### 1. **Command Translator** (`services/command_translator.py`)
- **LLM-powered translation** of natural language to robot commands
- **Context-aware processing** using real-time robot states
- **Formation handling** for complex multi-robot maneuvers
- **Confidence scoring** and validation

### 2. **Safety Validator** (`safety_validator/`)
- **Multi-layer safety rules** (velocity, zones, collision avoidance)
- **Emergency stop system** with instant fleet-wide halt
- **Configurable safety policies** for different environments
- **Real-time violation detection**

### 3. **Task Orchestrator** (`task_orchestrator/`)
- **Distributed task management** with Ray integration
- **Priority-based scheduling** for optimal resource utilization
- **Robot registry** with health monitoring
- **Real-time status tracking**

### 4. **Simulation Bridge** (`simulation_bridge/`)
- **ROS2-compatible interface** for seamless real robot integration
- **Webots simulation support** for testing and development
- **Mock implementations** for development without hardware
- **Standard topic interfaces** (`/cmd_vel`, `/odom`, etc.)

### 5. **Context Manager** (`services/robotics_context_manager.py`)
- **Real-time robot state tracking**
- **Environment awareness**
- **Dynamic context updates**
- **Multi-robot coordination**

## 📊 **Test Results**

RoboLinguist achieves **92.3% success rate** across comprehensive system tests:

| Test Category | Success Rate | Details |
|---------------|--------------|---------|
| Robot Discovery | ✅ 100% | All 5 robots discovered and registered |
| Command Translation | ✅ 75% | 3/4 translation tests passing |
| Formation Control | ✅ 100% | Circle and line formations working |
| Safety Validation | ✅ 100% | Safe/unsafe commands handled correctly |
| Task Orchestration | ✅ 100% | Tasks submitted and completed |
| Robot Movement | ✅ 100% | Real robot movement in simulation |
| Emergency Stop | ✅ 100% | Instant fleet-wide emergency halt |

**Overall System Success Rate: 92.3% (12/13 tests passing)**

## 🛡️ **Safety Features**

RoboLinguist prioritizes safety with multiple protection layers:

- **🚫 Forbidden Zones**: Define no-go areas for robots
- **⚡ Velocity Limits**: Configurable speed and acceleration constraints  
- **🔍 Collision Avoidance**: Minimum distance enforcement between robots
- **🔋 Battery Monitoring**: Prevent operations with low battery
- **🚨 Emergency Stop**: Instant fleet-wide halt with 5-second timeout
- **📋 Command Blacklist**: Block dangerous or unauthorized commands

## 🎯 **Supported Commands**

### Navigation Commands
```
"Move all robots to the center"
"Move robot 0 to position 5, 3"
"Navigate to the loading dock"
"Return all robots to home position"
```

### Formation Commands
```
"Form a circle formation"
"Create a line formation with 2 meter spacing"
"Arrange robots in a square pattern"
"Spread out in defensive formation"
```

### Task Commands
```
"Patrol the warehouse perimeter"
"Inspect all workstations"
"Collect items from station A"
"Follow the human operator"
```

## 🔧 **Configuration**

### System Configuration (`config/system_config.yaml`)
```yaml
llm:
  api_key: "your_openrouter_api_key"
  model: "mistralai/mistral-7b-instruct"
  
safety:
  strict_mode: true
  max_velocity: 2.0
  emergency_stop_timeout: 5.0
  
simulation:
  use_webots: true
  world_file: "webots_working_demo/minimal_fleet_world.wbt"
```

### Safety Rules (`config/safety_rules.yaml`)
```yaml
safety_rules:
  - rule_id: max_velocity
    name: Maximum Velocity Limit
    parameters:
      max_linear_velocity: 2.0
      max_angular_velocity: 1.0
    severity: high
    
  - rule_id: forbidden_zones
    name: Forbidden Zone Restriction
    parameters:
      zones:
        - name: human_workspace
          type: rectangle
          bounds: {x_min: -1.0, x_max: 1.0, y_min: -1.0, y_max: 1.0}
    severity: critical
```

## 🚀 **Advanced Usage**

### Custom Safety Rules
```python
from safety_validator.safety_checker import SafetyChecker, SafetyRule

# Create custom safety rule
custom_rule = SafetyRule(
    rule_id="custom_zone",
    name="Custom Restricted Zone",
    rule_type="zone",
    parameters={
        "zones": [{
            "name": "server_room",
            "type": "circle",
            "center": [10.0, 5.0],
            "radius": 3.0
        }]
    },
    severity="critical"
)

# Add to safety checker
safety_checker.add_safety_rule(custom_rule)
```

### Distributed Task Processing
```python
from task_orchestrator.ray_distributed_manager import RayDistributedManager

# Initialize distributed processing
distributed_manager = RayDistributedManager()
await distributed_manager.initialize()

# Submit high-priority task
task = Task(
    task_id="urgent_inspection",
    description="Emergency inspection of area B",
    priority=TaskPriority.HIGH,
    estimated_duration=120
)

result = await distributed_manager.submit_task(task)
```

## 🧪 **Development & Testing**

### Run Tests
```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/test_command_translator.py
python -m pytest tests/test_safety_checker.py

# Run integration tests with Webots
python run_webots_integration_tests.py
```

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run code formatting
black .
isort .

# Run linting
flake8 .
mypy .
```

## 📁 **Project Structure**

```
robolinguist/
├── 🧠 core/                    # Core data models and interfaces
├── 🔧 services/               # Main service components
│   ├── command_translator.py  # Natural language processing
│   ├── openrouter_client.py   # LLM API client
│   └── robotics_context_manager.py # Context awareness
├── 🛡️ safety_validator/       # Safety systems
│   ├── safety_checker.py      # Rule validation
│   └── emergency_stop.py      # Emergency procedures
├── 🎯 task_orchestrator/      # Task management
│   ├── task_manager.py        # Task coordination
│   ├── robot_registry.py      # Robot tracking
│   └── ray_distributed_manager.py # Distributed processing
├── 🌉 simulation_bridge/      # Simulation integration
│   ├── ros2_simulation_bridge.py # ROS2 bridge
│   ├── webots_robot_interface.py # Webots interface
│   └── ros2_bridge_node.py    # ROS2 node management
├── ⚙️ config/                 # Configuration files
├── 🧪 tests/                  # Test suites
├── 🎮 webots_working_demo/    # Webots simulation files
└── 📚 docs/                   # Documentation
```

## 🤝 **Contributing**

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **OpenRouter** for LLM API services
- **ROS2** for robotics middleware
- **Webots** for simulation environment
- **Ray** for distributed computing
- The open-source robotics community

## 📞 **Support**

- 📧 **Email**: chmsohaib701@gmail.com
<!-- - 📖 **Documentation**: [docs.robolinguist.dev](https://docs.robolinguist.dev) -->
- 🐛 **Issues**: [GitHub Issues](https://github.com/sohaibzafar701/RoboLinguist/issues)

---

**Made with ❤️ for the robotics community**

*RoboLinguist - Where natural language meets robotic intelligence*

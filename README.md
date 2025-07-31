# ChatGPT for Robots

A scalable, open-source robotics fleet control system that enables natural language control of multiple robots using Large Language Models (LLMs).

## Features

- **Natural Language Control**: Control robots using plain English commands
- **Multi-Robot Fleet Management**: Coordinate multiple robots simultaneously
- **Safety-First Design**: Built-in safety validation and emergency stop capabilities
- **LLM Integration**: Powered by OpenRouter for flexible model selection
- **ROS2 Compatible**: Full integration with the ROS2 ecosystem
- **Simulation Support**: Test and validate in Gazebo simulation environment
- **Web Interface**: User-friendly web-based control panel
- **Distributed Computing**: Scalable task orchestration using Ray

## Quick Start

### 1. Setup Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Or use our convenience scripts
# For Command Prompt:
activate_venv.bat

# For PowerShell:
.\activate_venv.ps1
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 3. Configure the System

1. Update `config/system_config.yaml` with your OpenRouter API key:
```yaml
llm:
  api_key: your_openrouter_api_key_here
```

2. Adjust other settings as needed (ROS2 domain, web port, etc.)

### 4. Test the Setup

```bash
python test_setup.py
```

## Project Structure

```
chatgpt-for-robots/
├── config/                 # Configuration management
│   ├── config_manager.py   # Configuration loading and validation
│   ├── settings.py         # Typed configuration classes
│   └── system_config.yaml  # Main configuration file
├── core/                   # Core interfaces and data models
│   ├── interfaces.py       # Abstract base classes
│   ├── data_models.py      # Data structures
│   └── base_component.py   # Base component class
├── web_interface/          # Web-based user interface
├── llm_service/           # LLM integration and command translation
├── safety_validator/      # Safety checking and validation
├── task_orchestrator/     # Task management and distribution
├── ros2_bridge/          # ROS2 integration
├── simulation/           # Gazebo simulation support
├── venv/                 # Virtual environment (created after setup)
├── requirements.txt      # Python dependencies
├── setup.py             # Package setup
└── test_setup.py        # Setup verification script
```

## Development Workflow

### Using Virtual Environment

Always activate the virtual environment before working on the project:

```bash
# Windows Command Prompt
venv\Scripts\activate

# Windows PowerShell
venv\Scripts\Activate.ps1

# Or use convenience scripts
activate_venv.bat        # For CMD
.\activate_venv.ps1      # For PowerShell
```

### Running Commands

All Python commands should be run within the virtual environment:

```bash
# Install new dependencies
pip install package_name

# Run tests
python -m pytest

# Run the application
python -m web_interface.app

# Format code
black .

# Type checking
mypy .
```

### Deactivating Virtual Environment

```bash
deactivate
```

## Configuration

The system uses a hierarchical configuration system:

1. **Default values** in `config/settings.py`
2. **YAML configuration** in `config/system_config.yaml`
3. **Environment variables** (highest priority)

### Key Configuration Sections

- **LLM Settings**: API keys, model selection, timeouts
- **ROS2 Settings**: Domain ID, namespaces, QoS profiles
- **Safety Settings**: Velocity limits, safety zones, emergency procedures
- **Web Interface**: Host, port, CORS settings
- **Simulation**: Gazebo world files, robot models

## Dependencies

### Core Dependencies
- Python 3.8+
- PyYAML (configuration)
- Pydantic (data validation)
- Flask (web interface)
- OpenAI/httpx (LLM integration)

### Optional Dependencies
- ROS2 (robot control)
- Gazebo (simulation)
- Ray (distributed computing)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Set up virtual environment and install dependencies
4. Make your changes
5. Run tests and ensure code quality
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support, please open an issue on GitHub.
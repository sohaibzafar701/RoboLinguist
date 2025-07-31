"""
ChatGPT for Robots - Scalable Fleet Control System

A scalable, open-source robotics fleet control system that enables natural language 
control of multiple robots using Large Language Models (LLMs).
"""

__version__ = "0.1.0"
__author__ = "ChatGPT for Robots Team"
__description__ = "Natural language control for robot fleets using LLMs"

# Core imports
from core import (
    ICommandTranslator,
    ISafetyValidator,
    ITaskManager,
    IRobotController,
    ISimulationManager,
    RobotCommand,
    RobotState,
    Task,
    PerformanceMetrics,
    BaseComponent
)

# Configuration imports
from config import (
    ConfigManager,
    SystemSettings,
    LLMSettings,
    ROS2Settings,
    SafetySettings,
    SimulationSettings,
    WebInterfaceSettings
)

__all__ = [
    # Core interfaces and models
    'ICommandTranslator',
    'ISafetyValidator',
    'ITaskManager', 
    'IRobotController',
    'ISimulationManager',
    'RobotCommand',
    'RobotState',
    'Task',
    'PerformanceMetrics',
    'BaseComponent',
    
    # Configuration
    'ConfigManager',
    'SystemSettings',
    'LLMSettings',
    'ROS2Settings',
    'SafetySettings',
    'SimulationSettings',
    'WebInterfaceSettings'
]
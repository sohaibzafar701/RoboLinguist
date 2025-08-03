"""
Simulation Bridge Package

This package provides the bridge between the real ChatGPT for Robots system
and Webots simulation environment.

Architecture:
- ROS2SimulationBridge: Main coordinator
- WebotsRobotInterface: Maps ROS2 robot commands to Webots
- WebotsEnvironmentInterface: Maps environment operations to Webots
- SimulationStateManager: Synchronizes real/simulation states

This allows the real system (Tasks 1-6) to work unchanged while being
demonstrated in Webots simulation.
"""

from .ros2_simulation_bridge import ROS2SimulationBridge
from .webots_robot_interface import WebotsRobotInterface
from .webots_environment_interface import WebotsEnvironmentInterface
from .simulation_state_manager import SimulationStateManager

__all__ = [
    'ROS2SimulationBridge',
    'WebotsRobotInterface', 
    'WebotsEnvironmentInterface',
    'SimulationStateManager'
]
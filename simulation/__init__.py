"""
Simulation module for ChatGPT robotics using Webots.

This module provides simulation capabilities using Webots robot simulator,
offering professional-grade multi-robot simulation with easy Windows setup.
"""

from .webots_manager import WebotsManager, WebotsConfig, RobotInfo
from .webots_environment_controller import WebotsEnvironmentController, EnvironmentObject, EnvironmentState
from .webots_robot_spawner import WebotsRobotSpawner, RobotSpawnConfig, SpawnedRobotInfo

__all__ = [
    'WebotsManager',
    'WebotsConfig',
    'RobotInfo',
    'WebotsEnvironmentController',
    'EnvironmentObject',
    'EnvironmentState',
    'WebotsRobotSpawner',
    'RobotSpawnConfig',
    'SpawnedRobotInfo'
]
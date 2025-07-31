"""
Web Interface Component

Provides user-friendly interface for natural language robot control.
"""

from .app import FlaskApp
from .command_handler import CommandHandler
from .simulation_viewer import SimulationViewer

__all__ = ['FlaskApp', 'CommandHandler', 'SimulationViewer']
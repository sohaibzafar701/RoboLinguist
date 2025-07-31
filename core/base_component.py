"""
Base component class for all system components.

Provides common functionality and lifecycle management for all components.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class BaseComponent(ABC):
    """Base class for all system components."""
    
    def __init__(self, component_name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the base component.
        
        Args:
            component_name: Name of the component for logging
            config: Configuration dictionary for the component
        """
        self.component_name = component_name
        self.config = config or {}
        self.logger = logging.getLogger(f"chatgpt_robots.{component_name}")
        self.is_initialized = False
        self.is_running = False
        self.start_time: Optional[datetime] = None
        
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the component.
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """Start the component.
        
        Returns:
            True if start successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """Stop the component.
        
        Returns:
            True if stop successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the component.
        
        Returns:
            Dictionary containing health status information
        """
        pass
    
    def get_uptime(self) -> float:
        """Get component uptime in seconds.
        
        Returns:
            Uptime in seconds, or 0 if not started
        """
        if self.start_time is None:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current component status.
        
        Returns:
            Dictionary containing component status information
        """
        return {
            'component_name': self.component_name,
            'is_initialized': self.is_initialized,
            'is_running': self.is_running,
            'uptime_seconds': self.get_uptime(),
            'start_time': self.start_time.isoformat() if self.start_time else None
        }
    
    async def _safe_initialize(self) -> bool:
        """Safely initialize the component with error handling."""
        try:
            result = await self.initialize()
            self.is_initialized = result
            if result:
                self.logger.info(f"Component {self.component_name} initialized successfully")
            else:
                self.logger.error(f"Component {self.component_name} initialization failed")
            return result
        except Exception as e:
            self.logger.error(f"Error initializing component {self.component_name}: {e}")
            return False
    
    async def _safe_start(self) -> bool:
        """Safely start the component with error handling."""
        try:
            if not self.is_initialized:
                self.logger.warning(f"Component {self.component_name} not initialized, initializing now")
                if not await self._safe_initialize():
                    return False
            
            result = await self.start()
            if result:
                self.is_running = True
                self.start_time = datetime.now()
                self.logger.info(f"Component {self.component_name} started successfully")
            else:
                self.logger.error(f"Component {self.component_name} start failed")
            return result
        except Exception as e:
            self.logger.error(f"Error starting component {self.component_name}: {e}")
            return False
    
    async def _safe_stop(self) -> bool:
        """Safely stop the component with error handling."""
        try:
            result = await self.stop()
            if result:
                self.is_running = False
                self.logger.info(f"Component {self.component_name} stopped successfully")
            else:
                self.logger.error(f"Component {self.component_name} stop failed")
            return result
        except Exception as e:
            self.logger.error(f"Error stopping component {self.component_name}: {e}")
            return False
"""
Configuration manager for the ChatGPT for Robots system.

Handles loading, validation, and management of system configuration.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import asdict
from .settings import SystemSettings


class ConfigManager:
    """Manages system configuration from multiple sources."""
    
    def __init__(self, config_dir: str = "config"):
        """Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir)
        self.config_data: Dict[str, Any] = {}
        self.system_settings: Optional[SystemSettings] = None
        
    def load_config(self, config_file: str = "system_config.yaml") -> bool:
        """Load configuration from file.
        
        Args:
            config_file: Configuration file name
            
        Returns:
            True if configuration loaded successfully
        """
        config_path = self.config_dir / config_file
        
        try:
            if config_path.suffix.lower() == '.yaml' or config_path.suffix.lower() == '.yml':
                with open(config_path, 'r') as f:
                    self.config_data = yaml.safe_load(f)
            elif config_path.suffix.lower() == '.json':
                with open(config_path, 'r') as f:
                    self.config_data = json.load(f)
            else:
                raise ValueError(f"Unsupported config file format: {config_path.suffix}")
            
            # Load environment variable overrides
            self._load_env_overrides()
            
            # Create system settings object
            self.system_settings = SystemSettings.from_dict(self.config_data)
            
            return True
            
        except FileNotFoundError:
            print(f"Config file not found: {config_path}")
            # Create default configuration
            self._create_default_config(config_path)
            return self.load_config(config_file)
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return False
    
    def _load_env_overrides(self):
        """Load configuration overrides from environment variables."""
        # LLM Service overrides
        if os.getenv('OPENROUTER_API_KEY'):
            self.config_data.setdefault('llm', {})['api_key'] = os.getenv('OPENROUTER_API_KEY')
        
        # ROS2 overrides
        if os.getenv('ROS_DOMAIN_ID'):
            self.config_data.setdefault('ros2', {})['domain_id'] = int(os.getenv('ROS_DOMAIN_ID'))
        
        # Web interface overrides
        if os.getenv('WEB_PORT'):
            self.config_data.setdefault('web_interface', {})['port'] = int(os.getenv('WEB_PORT'))
        
        # Safety overrides
        if os.getenv('SAFETY_MODE'):
            self.config_data.setdefault('safety', {})['strict_mode'] = os.getenv('SAFETY_MODE').lower() == 'strict'
    
    def _create_default_config(self, config_path: Path):
        """Create default configuration file.
        
        Args:
            config_path: Path where to create the config file
        """
        default_config = {
            'llm': {
                'api_key': 'your_openrouter_api_key_here',
                'base_url': 'https://openrouter.ai/api/v1',
                'default_model': 'mistralai/mistral-7b-instruct',
                'fallback_model': 'meta-llama/llama-3-8b-instruct',
                'timeout': 30,
                'max_retries': 3
            },
            'ros2': {
                'domain_id': 0,
                'namespace': '/chatgpt_robots',
                'qos_profile': 'default',
                'discovery_timeout': 10.0
            },
            'safety': {
                'strict_mode': True,
                'max_velocity': 2.0,
                'max_acceleration': 1.0,
                'safety_zones': [],
                'emergency_stop_timeout': 1.0
            },
            'simulation': {
                'use_gazebo': True,
                'world_file': 'warehouse.world',
                'robot_model': 'tiago',
                'max_robots': 10,
                'physics_engine': 'ode'
            },
            'web_interface': {
                'host': '0.0.0.0',
                'port': 8080,
                'debug': False,
                'cors_enabled': True,
                'websocket_enabled': True
            },
            'task_orchestrator': {
                'use_ray': True,
                'ray_address': 'auto',
                'max_concurrent_tasks': 50,
                'task_timeout': 300
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file': 'chatgpt_robots.log',
                'max_file_size': '10MB',
                'backup_count': 5
            }
        }
        
        # Create config directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write default configuration
        if config_path.suffix.lower() in ['.yaml', '.yml']:
            with open(config_path, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)
        else:
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
        
        print(f"Created default configuration file: {config_path}")
        print("Please update the configuration with your API keys and settings.")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting by key.
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'llm.api_key')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config_data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_setting(self, key: str, value: Any):
        """Set a configuration setting.
        
        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        keys = key.split('.')
        config = self.config_data
        
        # Navigate to the parent dictionary
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def save_config(self, config_file: str = "system_config.yaml"):
        """Save current configuration to file.
        
        Args:
            config_file: Configuration file name
        """
        config_path = self.config_dir / config_file
        
        try:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                with open(config_path, 'w') as f:
                    yaml.dump(self.config_data, f, default_flow_style=False, indent=2)
            else:
                with open(config_path, 'w') as f:
                    json.dump(self.config_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration section.
        
        Returns:
            Dictionary containing LLM configuration
        """
        return self.config_data.get('llm', {})
    
    def get_ros2_config(self) -> Dict[str, Any]:
        """Get ROS2 configuration section.
        
        Returns:
            Dictionary containing ROS2 configuration
        """
        return self.config_data.get('ros2', {})
    
    def get_safety_config(self) -> Dict[str, Any]:
        """Get safety configuration section.
        
        Returns:
            Dictionary containing safety configuration
        """
        return self.config_data.get('safety', {})
    
    def get_web_config(self) -> Dict[str, Any]:
        """Get web interface configuration section.
        
        Returns:
            Dictionary containing web interface configuration
        """
        return self.config_data.get('web_interface', {})

    def validate_config(self) -> bool:
        """Validate the current configuration.
        
        Returns:
            True if configuration is valid
        """
        try:
            if self.system_settings is None:
                return False
            
            # Validate required API keys
            if not self.system_settings.llm.api_key or self.system_settings.llm.api_key == 'your_openrouter_api_key_here':
                print("Warning: OpenRouter API key not configured")
                return False
            
            # Validate port ranges
            if not (1024 <= self.system_settings.web_interface.port <= 65535):
                print(f"Error: Invalid web interface port: {self.system_settings.web_interface.port}")
                return False
            
            # Validate safety settings
            if self.system_settings.safety.max_velocity <= 0:
                print(f"Error: Invalid max velocity: {self.system_settings.safety.max_velocity}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Configuration validation error: {e}")
            return False
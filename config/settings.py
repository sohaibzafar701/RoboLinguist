"""
Settings classes for the ChatGPT for Robots system.

Defines typed configuration classes for all system components.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class LLMSettings:
    """Settings for LLM service configuration."""
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "mistralai/mistral-7b-instruct"
    fallback_model: str = "meta-llama/llama-3-8b-instruct"
    timeout: int = 30
    max_retries: int = 3
    temperature: float = 0.7
    max_tokens: int = 1000


@dataclass
class ROS2Settings:
    """Settings for ROS2 configuration."""
    domain_id: int = 0
    namespace: str = "/chatgpt_robots"
    qos_profile: str = "default"
    discovery_timeout: float = 10.0
    node_name_prefix: str = "chatgpt_robots"
    use_sim_time: bool = True


@dataclass
class SafetySettings:
    """Settings for safety validation configuration."""
    strict_mode: bool = True
    max_velocity: float = 2.0
    max_acceleration: float = 1.0
    safety_zones: List[Dict[str, Any]] = None
    emergency_stop_timeout: float = 1.0
    collision_threshold: float = 0.5
    battery_low_threshold: float = 20.0
    
    def __post_init__(self):
        if self.safety_zones is None:
            self.safety_zones = []


@dataclass
class SimulationSettings:
    """Settings for simulation environment configuration."""
    use_gazebo: bool = True
    world_file: str = "warehouse.world"
    robot_model: str = "tiago"
    max_robots: int = 10
    physics_engine: str = "ode"
    real_time_factor: float = 1.0
    gui_enabled: bool = True
    headless: bool = False


@dataclass
class WebInterfaceSettings:
    """Settings for web interface configuration."""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    cors_enabled: bool = True
    websocket_enabled: bool = True
    static_folder: str = "static"
    template_folder: str = "templates"
    secret_key: str = "your-secret-key-here"


@dataclass
class TaskOrchestratorSettings:
    """Settings for task orchestrator configuration."""
    use_ray: bool = True
    ray_address: str = "auto"
    max_concurrent_tasks: int = 50
    task_timeout: int = 300
    retry_attempts: int = 3
    priority_levels: int = 10
    load_balancing_strategy: str = "round_robin"


@dataclass
class LoggingSettings:
    """Settings for logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "chatgpt_robots.log"
    max_file_size: str = "10MB"
    backup_count: int = 5
    console_output: bool = True


@dataclass
class SystemSettings:
    """Complete system settings container."""
    llm: LLMSettings
    ros2: ROS2Settings
    safety: SafetySettings
    simulation: SimulationSettings
    web_interface: WebInterfaceSettings
    task_orchestrator: TaskOrchestratorSettings
    logging: LoggingSettings
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'SystemSettings':
        """Create SystemSettings from configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            SystemSettings instance
        """
        return cls(
            llm=LLMSettings(**config_dict.get('llm', {})),
            ros2=ROS2Settings(**config_dict.get('ros2', {})),
            safety=SafetySettings(**config_dict.get('safety', {})),
            simulation=SimulationSettings(**config_dict.get('simulation', {})),
            web_interface=WebInterfaceSettings(**config_dict.get('web_interface', {})),
            task_orchestrator=TaskOrchestratorSettings(**config_dict.get('task_orchestrator', {})),
            logging=LoggingSettings(**config_dict.get('logging', {}))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert SystemSettings to dictionary.
        
        Returns:
            Configuration dictionary
        """
        from dataclasses import asdict
        return asdict(self)
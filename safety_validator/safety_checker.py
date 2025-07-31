"""
Safety Checker Component

Validates robot commands against safety rules and rejects unsafe operations.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import yaml
from pathlib import Path

from core.base_component import BaseComponent
from core.interfaces import ISafetyValidator
from core.data_models import RobotCommand, RobotState, ActionType
from .emergency_stop import EmergencyStop, EmergencyStopTrigger


@dataclass
class SafetyViolation:
    """Represents a safety rule violation."""
    rule_id: str
    rule_name: str
    violation_type: str
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    timestamp: datetime


@dataclass
class SafetyRule:
    """Represents a configurable safety rule."""
    rule_id: str
    name: str
    rule_type: str  # 'velocity', 'position', 'zone', 'command'
    parameters: Dict[str, Any]
    enabled: bool = True
    severity: str = 'medium'


class SafetyChecker(BaseComponent, ISafetyValidator):
    """
    Safety checker component that validates robot commands against safety rules.
    
    Implements configurable safety rules and provides command filtering
    to ensure safe robot operations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the safety checker.
        
        Args:
            config: Configuration dictionary containing safety settings
        """
        super().__init__("safety_checker", config)
        
        self.safety_rules: Dict[str, SafetyRule] = {}
        self.violation_history: List[SafetyViolation] = []
        self.robot_states: Dict[str, RobotState] = {}
        
        # Initialize emergency stop system
        emergency_config = self.config.get('emergency_stop', {})
        self.emergency_stop_system = EmergencyStop(emergency_config)
        
        # Safety configuration
        self.max_velocity = self.config.get('max_velocity', 2.0)
        self.max_acceleration = self.config.get('max_acceleration', 1.0)
        self.safety_zones = self.config.get('safety_zones', [])
        self.strict_mode = self.config.get('strict_mode', True)
        self.rules_file = self.config.get('rules_file', 'config/safety_rules.yaml')
        
        # Emergency stop state tracking
        self._emergency_active = False
        
    async def initialize(self) -> bool:
        """Initialize the safety checker component."""
        try:
            # Initialize emergency stop system
            if not await self.emergency_stop_system.initialize():
                self.logger.error("Failed to initialize emergency stop system")
                return False
            
            # Load safety rules from configuration file
            await self._load_safety_rules()
            
            self.logger.info(f"Loaded {len(self.safety_rules)} safety rules")
            self.logger.info(f"Safety checker initialized in {'strict' if self.strict_mode else 'permissive'} mode")
            
            self.is_initialized = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize safety checker: {e}")
            self.is_initialized = False
            return False
    
    async def start(self) -> bool:
        """Start the safety checker component."""
        try:
            # Start emergency stop system
            if not await self.emergency_stop_system.start():
                self.logger.error("Failed to start emergency stop system")
                return False
            
            self.is_running = True
            self.start_time = datetime.now()
            self.logger.info("Safety checker started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start safety checker: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the safety checker component."""
        try:
            # Stop emergency stop system
            await self.emergency_stop_system.stop()
            
            self.is_running = False
            self.logger.info("Safety checker stopped")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop safety checker: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the safety checker."""
        emergency_health = await self.emergency_stop_system.health_check()
        
        return {
            'component': self.component_name,
            'status': 'healthy' if self.is_running else 'stopped',
            'rules_loaded': len(self.safety_rules),
            'emergency_stop_active': await self.emergency_stop_system.is_emergency_active(),
            'violations_count': len(self.violation_history),
            'strict_mode': self.strict_mode,
            'emergency_stop_system': emergency_health
        }
    
    async def validate_command(self, command: RobotCommand) -> bool:
        """
        Validate that a command meets safety requirements.
        
        Args:
            command: Robot command to validate
            
        Returns:
            True if command is safe, False otherwise
        """
        if await self.emergency_stop_system.is_emergency_active():
            self.logger.warning(f"Command {command.command_id} rejected - emergency stop active")
            return False
        
        try:
            # Check all applicable safety rules
            violations = await self._check_safety_rules(command)
            
            if violations:
                # Log violations
                for violation in violations:
                    self.violation_history.append(violation)
                    self.logger.warning(f"Safety violation: {violation.description}")
                
                # Check for critical violations that should trigger emergency stop
                critical_violations = [v for v in violations if v.severity == 'critical']
                if critical_violations:
                    # Trigger emergency stop for critical safety violations
                    await self.emergency_stop_system.trigger_emergency_stop(
                        trigger=EmergencyStopTrigger.SAFETY_VIOLATION,
                        description=f"Critical safety violation: {critical_violations[0].description}",
                        robot_id=command.robot_id,
                        severity="critical"
                    )
                    return False
                
                # In strict mode, any violation rejects the command
                if self.strict_mode:
                    return False
                
                # In permissive mode, only critical violations reject the command
                return len(critical_violations) == 0
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating command {command.command_id}: {e}")
            # Fail safe - reject command if validation fails
            return False
    
    async def emergency_stop(self) -> None:
        """Trigger emergency stop for all robots."""
        await self.emergency_stop_system.trigger_emergency_stop(
            trigger=EmergencyStopTrigger.MANUAL,
            description="Emergency stop manually triggered via safety checker",
            severity="critical"
        )
        self._emergency_active = True
        
        # Log emergency stop event in violation history
        violation = SafetyViolation(
            rule_id="emergency_stop",
            rule_name="Emergency Stop",
            violation_type="emergency",
            description="Emergency stop manually triggered",
            severity="critical",
            timestamp=datetime.now()
        )
        self.violation_history.append(violation)
    
    async def reset_emergency_stop(self) -> None:
        """Reset emergency stop state."""
        success = await self.emergency_stop_system.reset_emergency_stop()
        if success:
            self._emergency_active = False
            self.logger.info("Emergency stop reset successfully")
        else:
            self.logger.error("Failed to reset emergency stop")
    
    async def get_safety_violations(self, command: RobotCommand) -> List[str]:
        """
        Get list of safety violations for a command.
        
        Args:
            command: Robot command to check
            
        Returns:
            List of violation descriptions
        """
        violations = await self._check_safety_rules(command)
        return [v.description for v in violations]
    
    async def update_robot_state(self, robot_state: RobotState) -> None:
        """
        Update robot state for safety monitoring.
        
        Args:
            robot_state: Current robot state
        """
        self.robot_states[robot_state.robot_id] = robot_state
    
    async def add_safety_rule(self, rule: SafetyRule) -> None:
        """
        Add a new safety rule.
        
        Args:
            rule: Safety rule to add
        """
        self.safety_rules[rule.rule_id] = rule
        self.logger.info(f"Added safety rule: {rule.name}")
    
    async def remove_safety_rule(self, rule_id: str) -> bool:
        """
        Remove a safety rule.
        
        Args:
            rule_id: ID of rule to remove
            
        Returns:
            True if rule was removed, False if not found
        """
        if rule_id in self.safety_rules:
            rule = self.safety_rules.pop(rule_id)
            self.logger.info(f"Removed safety rule: {rule.name}")
            return True
        return False
    
    async def get_violation_history(self, limit: Optional[int] = None) -> List[SafetyViolation]:
        """
        Get safety violation history.
        
        Args:
            limit: Maximum number of violations to return
            
        Returns:
            List of safety violations
        """
        violations = sorted(self.violation_history, key=lambda v: v.timestamp, reverse=True)
        return violations[:limit] if limit else violations
    
    async def _load_safety_rules(self) -> None:
        """Load safety rules from configuration file."""
        rules_path = Path(self.rules_file)
        
        if not rules_path.exists():
            # Create default safety rules file
            await self._create_default_rules_file(rules_path)
        
        try:
            with open(rules_path, 'r') as f:
                rules_config = yaml.safe_load(f)
            
            # Parse safety rules
            for rule_data in rules_config.get('safety_rules', []):
                rule = SafetyRule(
                    rule_id=rule_data['rule_id'],
                    name=rule_data['name'],
                    rule_type=rule_data['rule_type'],
                    parameters=rule_data['parameters'],
                    enabled=rule_data.get('enabled', True),
                    severity=rule_data.get('severity', 'medium')
                )
                self.safety_rules[rule.rule_id] = rule
                
        except Exception as e:
            self.logger.error(f"Failed to load safety rules from {rules_path}: {e}")
            # Load default rules if file loading fails
            await self._load_default_rules()
    
    async def _create_default_rules_file(self, rules_path: Path) -> None:
        """Create default safety rules configuration file."""
        default_rules = {
            'safety_rules': [
                {
                    'rule_id': 'max_velocity',
                    'name': 'Maximum Velocity Limit',
                    'rule_type': 'velocity',
                    'parameters': {
                        'max_linear_velocity': 2.0,
                        'max_angular_velocity': 1.0
                    },
                    'enabled': True,
                    'severity': 'high'
                },
                {
                    'rule_id': 'forbidden_zones',
                    'name': 'Forbidden Zone Restriction',
                    'rule_type': 'zone',
                    'parameters': {
                        'zones': [
                            {
                                'name': 'human_workspace',
                                'type': 'rectangle',
                                'bounds': {'x_min': -1.0, 'x_max': 1.0, 'y_min': -1.0, 'y_max': 1.0}
                            }
                        ]
                    },
                    'enabled': True,
                    'severity': 'critical'
                },
                {
                    'rule_id': 'battery_level',
                    'name': 'Minimum Battery Level',
                    'rule_type': 'state',
                    'parameters': {
                        'min_battery_level': 20.0
                    },
                    'enabled': True,
                    'severity': 'medium'
                },
                {
                    'rule_id': 'collision_avoidance',
                    'name': 'Collision Avoidance',
                    'rule_type': 'position',
                    'parameters': {
                        'min_distance_to_robots': 0.5,
                        'min_distance_to_obstacles': 0.3
                    },
                    'enabled': True,
                    'severity': 'high'
                },
                {
                    'rule_id': 'command_blacklist',
                    'name': 'Forbidden Commands',
                    'rule_type': 'command',
                    'parameters': {
                        'forbidden_actions': ['shutdown', 'reset', 'calibrate'],
                        'forbidden_keywords': ['dangerous', 'unsafe', 'override']
                    },
                    'enabled': True,
                    'severity': 'critical'
                }
            ]
        }
        
        # Create directory if it doesn't exist
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(rules_path, 'w') as f:
            yaml.dump(default_rules, f, default_flow_style=False, indent=2)
        
        self.logger.info(f"Created default safety rules file: {rules_path}")
    
    async def _load_default_rules(self) -> None:
        """Load default safety rules if configuration file is unavailable."""
        default_rules = [
            SafetyRule(
                rule_id="max_velocity",
                name="Maximum Velocity Limit",
                rule_type="velocity",
                parameters={"max_linear_velocity": 2.0, "max_angular_velocity": 1.0},
                severity="high"
            ),
            SafetyRule(
                rule_id="battery_level",
                name="Minimum Battery Level",
                rule_type="state",
                parameters={"min_battery_level": 20.0},
                severity="medium"
            )
        ]
        
        for rule in default_rules:
            self.safety_rules[rule.rule_id] = rule
        
        self.logger.info("Loaded default safety rules")
    
    async def _check_safety_rules(self, command: RobotCommand) -> List[SafetyViolation]:
        """
        Check command against all applicable safety rules.
        
        Args:
            command: Robot command to check
            
        Returns:
            List of safety violations
        """
        violations = []
        
        for rule in self.safety_rules.values():
            if not rule.enabled:
                continue
            
            violation = await self._check_rule(rule, command)
            if violation:
                violations.append(violation)
        
        return violations
    
    async def _check_rule(self, rule: SafetyRule, command: RobotCommand) -> Optional[SafetyViolation]:
        """
        Check a specific safety rule against a command.
        
        Args:
            rule: Safety rule to check
            command: Robot command to validate
            
        Returns:
            SafetyViolation if rule is violated, None otherwise
        """
        try:
            if rule.rule_type == 'velocity':
                return await self._check_velocity_rule(rule, command)
            elif rule.rule_type == 'zone':
                return await self._check_zone_rule(rule, command)
            elif rule.rule_type == 'state':
                return await self._check_state_rule(rule, command)
            elif rule.rule_type == 'position':
                return await self._check_position_rule(rule, command)
            elif rule.rule_type == 'command':
                return await self._check_command_rule(rule, command)
            else:
                self.logger.warning(f"Unknown rule type: {rule.rule_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error checking rule {rule.rule_id}: {e}")
            return None
    
    async def _check_velocity_rule(self, rule: SafetyRule, command: RobotCommand) -> Optional[SafetyViolation]:
        """Check velocity-based safety rule."""
        if command.action_type != ActionType.NAVIGATE:
            return None
        
        params = command.parameters
        max_linear = rule.parameters.get('max_linear_velocity', 2.0)
        max_angular = rule.parameters.get('max_angular_velocity', 1.0)
        
        # Check linear velocity - support both 'velocity' and 'max_velocity' parameters
        velocity = params.get('velocity') or params.get('max_velocity')
        if velocity:
            if isinstance(velocity, (list, tuple)) and len(velocity) >= 2:
                linear_vel = abs(velocity[0])
                angular_vel = abs(velocity[1]) if len(velocity) > 1 else 0
                
                if linear_vel > max_linear:
                    return SafetyViolation(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        violation_type="velocity_exceeded",
                        description=f"Linear velocity {linear_vel} exceeds maximum {max_linear}",
                        severity=rule.severity,
                        timestamp=datetime.now()
                    )
                
                if angular_vel > max_angular:
                    return SafetyViolation(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        violation_type="velocity_exceeded",
                        description=f"Angular velocity {angular_vel} exceeds maximum {max_angular}",
                        severity=rule.severity,
                        timestamp=datetime.now()
                    )
        
        return None
    
    async def _check_zone_rule(self, rule: SafetyRule, command: RobotCommand) -> Optional[SafetyViolation]:
        """Check zone-based safety rule."""
        if command.action_type != ActionType.NAVIGATE:
            return None
        
        # Support both 'target' and individual 'target_x', 'target_y' parameters
        target = command.parameters.get('target')
        if target and len(target) >= 2:
            x, y = target[0], target[1]
        else:
            x = command.parameters.get('target_x')
            y = command.parameters.get('target_y')
            if x is None or y is None:
                return None
        
        invert_rule = rule.parameters.get('invert', False)
        
        for zone in rule.parameters.get('zones', []):
            point_in_zone = self._point_in_zone(x, y, zone)
            
            # If invert is True, violation occurs when point is NOT in zone
            # If invert is False, violation occurs when point IS in zone
            violation_condition = (not point_in_zone) if invert_rule else point_in_zone
            
            if violation_condition:
                zone_desc = f"outside allowed zone '{zone['name']}'" if invert_rule else f"in forbidden zone '{zone['name']}'"
                return SafetyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    violation_type="forbidden_zone",
                    description=f"Target position ({x}, {y}) is {zone_desc}",
                    severity=rule.severity,
                    timestamp=datetime.now()
                )
        
        return None
    
    async def _check_state_rule(self, rule: SafetyRule, command: RobotCommand) -> Optional[SafetyViolation]:
        """Check robot state-based safety rule."""
        robot_state = self.robot_states.get(command.robot_id)
        if not robot_state:
            return None
        
        min_battery = rule.parameters.get('min_battery_level', 20.0)
        if robot_state.battery_level < min_battery:
            return SafetyViolation(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                violation_type="low_battery",
                description=f"Robot {command.robot_id} battery level {robot_state.battery_level}% below minimum {min_battery}%",
                severity=rule.severity,
                timestamp=datetime.now()
            )
        
        return None
    
    async def _check_position_rule(self, rule: SafetyRule, command: RobotCommand) -> Optional[SafetyViolation]:
        """Check position-based safety rule."""
        if command.action_type != ActionType.NAVIGATE:
            return None
        
        # Support both 'target' and individual 'target_x', 'target_y' parameters
        target = command.parameters.get('target')
        if target and len(target) >= 2:
            x, y = target[0], target[1]
        else:
            x = command.parameters.get('target_x')
            y = command.parameters.get('target_y')
            if x is None or y is None:
                return None
        
        min_distance = rule.parameters.get('min_distance_to_robots', 0.5)
        
        # Check distance to other robots
        for robot_id, robot_state in self.robot_states.items():
            if robot_id == command.robot_id:
                continue
            
            robot_x, robot_y = robot_state.position[0], robot_state.position[1]
            distance = ((x - robot_x) ** 2 + (y - robot_y) ** 2) ** 0.5
            
            if distance < min_distance:
                return SafetyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    violation_type="collision_risk",
                    description=f"Collision risk: Target position too close to robot {robot_id} (distance: {distance:.2f}m)",
                    severity=rule.severity,
                    timestamp=datetime.now()
                )
        
        return None
    
    async def _check_command_rule(self, rule: SafetyRule, command: RobotCommand) -> Optional[SafetyViolation]:
        """Check command-based safety rule."""
        forbidden_actions = rule.parameters.get('forbidden_actions', [])
        forbidden_keywords = rule.parameters.get('forbidden_keywords', [])
        
        # Check action type
        if command.action_type in forbidden_actions:
            return SafetyViolation(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                violation_type="forbidden_action",
                description=f"Action '{command.action_type}' is forbidden",
                severity=rule.severity,
                timestamp=datetime.now()
            )
        
        # Check parameters for forbidden keywords
        params_str = str(command.parameters).lower()
        for keyword in forbidden_keywords:
            if keyword.lower() in params_str:
                return SafetyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    violation_type="forbidden_keyword",
                    description=f"Command contains forbidden keyword: '{keyword}'",
                    severity=rule.severity,
                    timestamp=datetime.now()
                )
        
        return None
    
    def _point_in_zone(self, x: float, y: float, zone: Dict[str, Any]) -> bool:
        """Check if a point is within a defined zone."""
        zone_type = zone.get('type', 'rectangle')
        
        if zone_type == 'rectangle':
            bounds = zone.get('bounds', {})
            x_min = bounds.get('x_min', float('-inf'))
            x_max = bounds.get('x_max', float('inf'))
            y_min = bounds.get('y_min', float('-inf'))
            y_max = bounds.get('y_max', float('inf'))
            
            return x_min <= x <= x_max and y_min <= y <= y_max
        
        elif zone_type == 'circle':
            center = zone.get('center', [0, 0])
            radius = zone.get('radius', 1.0)
            
            distance = ((x - center[0]) ** 2 + (y - center[1]) ** 2) ** 0.5
            return distance <= radius
        
        return False
    
    async def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is currently active."""
        return await self.emergency_stop_system.is_emergency_active()
    
    @property
    def emergency_stop_active(self) -> bool:
        """Synchronous property to check if emergency stop is active (for backward compatibility)."""
        # This is a simplified version that tracks the state locally
        # In practice, you should use the async version is_emergency_stop_active()
        return hasattr(self, '_emergency_active') and self._emergency_active
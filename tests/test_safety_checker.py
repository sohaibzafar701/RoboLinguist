"""
Unit tests for SafetyChecker component.
"""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path
import tempfile
import yaml
from unittest.mock import Mock, patch

from safety_validator.safety_checker import SafetyChecker, SafetyRule, SafetyViolation
from core.data_models import RobotCommand, RobotState, ActionType


class TestSafetyChecker:
    """Test cases for SafetyChecker component."""
    
    @pytest.fixture
    def temp_rules_file(self):
        """Create a temporary safety rules file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            rules_config = {
                'safety_rules': [
                    {
                        'rule_id': 'test_velocity',
                        'name': 'Test Velocity Rule',
                        'rule_type': 'velocity',
                        'parameters': {
                            'max_linear_velocity': 1.0,
                            'max_angular_velocity': 0.5
                        },
                        'enabled': True,
                        'severity': 'high'
                    },
                    {
                        'rule_id': 'test_zone',
                        'name': 'Test Zone Rule',
                        'rule_type': 'zone',
                        'parameters': {
                            'zones': [
                                {
                                    'name': 'test_forbidden_zone',
                                    'type': 'rectangle',
                                    'bounds': {
                                        'x_min': 0.0,
                                        'x_max': 2.0,
                                        'y_min': 0.0,
                                        'y_max': 2.0
                                    }
                                }
                            ]
                        },
                        'enabled': True,
                        'severity': 'critical'
                    }
                ]
            }
            yaml.dump(rules_config, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def safety_checker(self, temp_rules_file):
        """Create a SafetyChecker instance for testing."""
        config = {
            'max_velocity': 2.0,
            'max_acceleration': 1.0,
            'strict_mode': True,
            'rules_file': temp_rules_file
        }
        return SafetyChecker(config)
    
    @pytest.fixture
    def sample_command(self):
        """Create a sample robot command for testing."""
        return RobotCommand(
            command_id="test_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 3.0, "target_y": 4.0, "velocity": [0.5, 0.2]},
            priority=5,
            timestamp=datetime.now()
        )
    
    @pytest.fixture
    def sample_robot_state(self):
        """Create a sample robot state for testing."""
        return RobotState(
            robot_id="robot_1",
            position=(1.0, 2.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status="idle",
            battery_level=85.0,
            current_task=None,
            last_update=datetime.now()
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, safety_checker):
        """Test safety checker initialization."""
        assert await safety_checker.initialize()
        assert safety_checker.is_initialized
        assert len(safety_checker.safety_rules) > 0
        assert not safety_checker.emergency_stop_active
    
    @pytest.mark.asyncio
    async def test_start_stop(self, safety_checker):
        """Test safety checker start and stop."""
        await safety_checker.initialize()
        
        assert await safety_checker.start()
        assert safety_checker.is_running
        
        assert await safety_checker.stop()
        assert not safety_checker.is_running
    
    @pytest.mark.asyncio
    async def test_health_check(self, safety_checker):
        """Test health check functionality."""
        await safety_checker.initialize()
        await safety_checker.start()
        
        health = await safety_checker.health_check()
        
        assert health['component'] == 'safety_checker'
        assert health['status'] == 'healthy'
        assert 'rules_loaded' in health
        assert 'emergency_stop_active' in health
        assert 'violations_count' in health
    
    @pytest.mark.asyncio
    async def test_validate_safe_command(self, safety_checker, sample_command):
        """Test validation of a safe command."""
        await safety_checker.initialize()
        
        # Command with safe parameters
        safe_command = RobotCommand(
            command_id="safe_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 5.0, "target_y": 5.0, "velocity": [0.5, 0.2]},
            priority=5,
            timestamp=datetime.now()
        )
        
        result = await safety_checker.validate_command(safe_command)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_unsafe_velocity(self, safety_checker):
        """Test validation of command with unsafe velocity."""
        await safety_checker.initialize()
        
        # Command with excessive velocity
        unsafe_command = RobotCommand(
            command_id="unsafe_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 5.0, "target_y": 5.0, "velocity": [3.0, 0.2]},  # Exceeds max
            priority=5,
            timestamp=datetime.now()
        )
        
        result = await safety_checker.validate_command(unsafe_command)
        assert result is False
        
        # Check that violation was recorded
        violations = await safety_checker.get_violation_history()
        assert len(violations) > 0
        assert any("velocity" in v.description.lower() for v in violations)
    
    @pytest.mark.asyncio
    async def test_validate_forbidden_zone(self, safety_checker):
        """Test validation of command targeting forbidden zone."""
        await safety_checker.initialize()
        
        # Command targeting forbidden zone
        forbidden_command = RobotCommand(
            command_id="forbidden_001",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.0, "target_y": 1.0},  # Inside forbidden zone
            priority=5,
            timestamp=datetime.now()
        )
        
        result = await safety_checker.validate_command(forbidden_command)
        assert result is False
        
        # Check that violation was recorded
        violations = await safety_checker.get_violation_history()
        assert len(violations) > 0
        assert any("forbidden zone" in v.description.lower() for v in violations)
    
    @pytest.mark.asyncio
    async def test_emergency_stop(self, safety_checker, sample_command):
        """Test emergency stop functionality."""
        await safety_checker.initialize()
        
        # Initially should accept commands
        result = await safety_checker.validate_command(sample_command)
        assert result is True
        
        # Trigger emergency stop
        await safety_checker.emergency_stop()
        assert safety_checker.emergency_stop_active
        
        # Should reject all commands during emergency stop
        result = await safety_checker.validate_command(sample_command)
        assert result is False
        
        # Reset emergency stop
        await safety_checker.reset_emergency_stop()
        assert not safety_checker.emergency_stop_active
        
        # Should accept commands again
        result = await safety_checker.validate_command(sample_command)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_battery_level_check(self, safety_checker, sample_robot_state):
        """Test battery level safety check."""
        await safety_checker.initialize()
        
        # Update robot state with low battery
        low_battery_state = RobotState(
            robot_id="robot_1",
            position=(1.0, 2.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status="idle",
            battery_level=15.0,  # Below minimum
            current_task=None,
            last_update=datetime.now()
        )
        
        await safety_checker.update_robot_state(low_battery_state)
        
        # Add battery level rule
        battery_rule = SafetyRule(
            rule_id="test_battery",
            name="Test Battery Rule",
            rule_type="state",
            parameters={"min_battery_level": 20.0},
            severity="medium"
        )
        await safety_checker.add_safety_rule(battery_rule)
        
        # Command should be rejected due to low battery
        command = RobotCommand(
            command_id="battery_test",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 5.0, "target_y": 5.0},
            priority=5,
            timestamp=datetime.now()
        )
        
        result = await safety_checker.validate_command(command)
        assert result is False
        
        violations = await safety_checker.get_violation_history()
        assert any("battery" in v.description.lower() for v in violations)
    
    @pytest.mark.asyncio
    async def test_collision_avoidance(self, safety_checker):
        """Test collision avoidance safety check."""
        await safety_checker.initialize()
        
        # Add two robot states close to each other
        robot1_state = RobotState(
            robot_id="robot_1",
            position=(1.0, 1.0, 0.0),
            orientation=(0.0, 0.0, 0.0, 1.0),
            status="idle",
            battery_level=85.0,
            current_task=None,
            last_update=datetime.now()
        )
        
        robot2_state = RobotState(
            robot_id="robot_2",
            position=(1.2, 1.2, 0.0),  # Close to robot_1
            orientation=(0.0, 0.0, 0.0, 1.0),
            status="idle",
            battery_level=85.0,
            current_task=None,
            last_update=datetime.now()
        )
        
        await safety_checker.update_robot_state(robot1_state)
        await safety_checker.update_robot_state(robot2_state)
        
        # Add collision avoidance rule
        collision_rule = SafetyRule(
            rule_id="test_collision",
            name="Test Collision Rule",
            rule_type="position",
            parameters={"min_distance_to_robots": 0.5},
            severity="high"
        )
        await safety_checker.add_safety_rule(collision_rule)
        
        # Command to move robot_1 too close to robot_2
        command = RobotCommand(
            command_id="collision_test",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 1.1, "target_y": 1.1},  # Too close to robot_2
            priority=5,
            timestamp=datetime.now()
        )
        
        result = await safety_checker.validate_command(command)
        assert result is False
        
        violations = await safety_checker.get_violation_history()
        assert any("collision" in v.description.lower() for v in violations)
    
    @pytest.mark.asyncio
    async def test_forbidden_commands(self, safety_checker):
        """Test forbidden command detection."""
        await safety_checker.initialize()
        
        # Add command blacklist rule
        blacklist_rule = SafetyRule(
            rule_id="test_blacklist",
            name="Test Blacklist Rule",
            rule_type="command",
            parameters={
                "forbidden_actions": [],
                "forbidden_keywords": ["dangerous", "override", "shutdown", "reset"]
            },
            severity="critical"
        )
        await safety_checker.add_safety_rule(blacklist_rule)
        
        # Test forbidden action (using parameters instead)
        forbidden_action_command = RobotCommand(
            command_id="forbidden_action",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 5.0, "target_y": 5.0, "action": "shutdown"},  # Forbidden action in parameters
            priority=5,
            timestamp=datetime.now()
        )
        
        result = await safety_checker.validate_command(forbidden_action_command)
        assert result is False
        
        # Reset emergency stop to test the second command
        await safety_checker.reset_emergency_stop()
        
        # Test forbidden keyword
        forbidden_keyword_command = RobotCommand(
            command_id="forbidden_keyword",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 5.0, "target_y": 5.0, "instruction": "override safety protocols"},  # Forbidden keyword
            priority=5,
            timestamp=datetime.now()
        )
        
        result = await safety_checker.validate_command(forbidden_keyword_command)
        assert result is False
        
        violations = await safety_checker.get_violation_history()
        assert len(violations) >= 2
    
    @pytest.mark.asyncio
    async def test_strict_vs_permissive_mode(self, safety_checker):
        """Test strict vs permissive mode behavior."""
        await safety_checker.initialize()
        
        # Add a medium severity rule
        medium_rule = SafetyRule(
            rule_id="test_medium",
            name="Test Medium Rule",
            rule_type="command",
            parameters={"forbidden_keywords": ["test"]},
            severity="medium"
        )
        await safety_checker.add_safety_rule(medium_rule)
        
        command = RobotCommand(
            command_id="medium_test",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={"target_x": 10.0, "target_y": 10.0, "instruction": "test command"},
            priority=5,
            timestamp=datetime.now()
        )
        
        # In strict mode, should reject medium severity violations
        safety_checker.strict_mode = True
        result = await safety_checker.validate_command(command)
        assert result is False
        
        # Clear violation history
        safety_checker.violation_history.clear()
        
        # In permissive mode, should allow medium severity violations
        safety_checker.strict_mode = False
        result = await safety_checker.validate_command(command)
        assert result is True  # Should pass in permissive mode
    
    @pytest.mark.asyncio
    async def test_add_remove_safety_rules(self, safety_checker):
        """Test adding and removing safety rules."""
        await safety_checker.initialize()
        
        initial_count = len(safety_checker.safety_rules)
        
        # Add a new rule
        new_rule = SafetyRule(
            rule_id="test_new_rule",
            name="Test New Rule",
            rule_type="command",
            parameters={"forbidden_actions": ["test_action"]},
            severity="low"
        )
        
        await safety_checker.add_safety_rule(new_rule)
        assert len(safety_checker.safety_rules) == initial_count + 1
        assert "test_new_rule" in safety_checker.safety_rules
        
        # Remove the rule
        result = await safety_checker.remove_safety_rule("test_new_rule")
        assert result is True
        assert len(safety_checker.safety_rules) == initial_count
        assert "test_new_rule" not in safety_checker.safety_rules
        
        # Try to remove non-existent rule
        result = await safety_checker.remove_safety_rule("non_existent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_safety_violations(self, safety_checker):
        """Test getting safety violations for a command."""
        await safety_checker.initialize()
        
        # Command with multiple violations
        unsafe_command = RobotCommand(
            command_id="multi_violation",
            robot_id="robot_1",
            action_type=ActionType.NAVIGATE,
            parameters={
                "target_x": 1.0, "target_y": 1.0,  # In forbidden zone
                "velocity": [3.0, 0.2]      # Excessive velocity
            },
            priority=5,
            timestamp=datetime.now()
        )
        
        violations = await safety_checker.get_safety_violations(unsafe_command)
        assert len(violations) > 0
        assert any("zone" in v.lower() for v in violations)
    
    @pytest.mark.asyncio
    async def test_violation_history_limit(self, safety_checker):
        """Test violation history with limit."""
        await safety_checker.initialize()
        
        # Generate multiple violations
        for i in range(5):
            violation = SafetyViolation(
                rule_id=f"test_rule_{i}",
                rule_name=f"Test Rule {i}",
                violation_type="test",
                description=f"Test violation {i}",
                severity="low",
                timestamp=datetime.now()
            )
            safety_checker.violation_history.append(violation)
        
        # Get limited history
        limited_history = await safety_checker.get_violation_history(limit=3)
        assert len(limited_history) == 3
        
        # Get full history
        full_history = await safety_checker.get_violation_history()
        assert len(full_history) == 5
    
    def test_point_in_zone_rectangle(self, safety_checker):
        """Test point in rectangular zone detection."""
        zone = {
            'type': 'rectangle',
            'bounds': {
                'x_min': 0.0,
                'x_max': 2.0,
                'y_min': 0.0,
                'y_max': 2.0
            }
        }
        
        # Point inside zone
        assert safety_checker._point_in_zone(1.0, 1.0, zone) is True
        
        # Point outside zone
        assert safety_checker._point_in_zone(3.0, 3.0, zone) is False
        
        # Point on boundary
        assert safety_checker._point_in_zone(2.0, 2.0, zone) is True
    
    def test_point_in_zone_circle(self, safety_checker):
        """Test point in circular zone detection."""
        zone = {
            'type': 'circle',
            'center': [0.0, 0.0],
            'radius': 2.0
        }
        
        # Point inside zone
        assert safety_checker._point_in_zone(1.0, 1.0, zone) is True
        
        # Point outside zone
        assert safety_checker._point_in_zone(3.0, 3.0, zone) is False
        
        # Point on boundary
        assert safety_checker._point_in_zone(2.0, 0.0, zone) is True
    
    @pytest.mark.asyncio
    async def test_default_rules_creation(self, tmp_path):
        """Test creation of default rules file."""
        rules_file = tmp_path / "test_rules.yaml"
        
        config = {
            'rules_file': str(rules_file),
            'strict_mode': True
        }
        
        checker = SafetyChecker(config)
        await checker.initialize()
        
        # Check that default rules file was created
        assert rules_file.exists()
        
        # Check that rules were loaded
        assert len(checker.safety_rules) > 0
        
        # Verify file content
        with open(rules_file, 'r') as f:
            rules_data = yaml.safe_load(f)
        
        assert 'safety_rules' in rules_data
        assert len(rules_data['safety_rules']) > 0


if __name__ == "__main__":
    pytest.main([__file__])
"""
Unit tests for command translation system.

Tests natural language to robot command translation functionality.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.command_translator import CommandTranslator, TranslationResult, PromptTemplates
from services.openrouter_client import LLMResponse, ChatMessage
from core.data_models import RobotCommand, ActionType
from config.config_manager import ConfigManager


class TestCommandTranslator:
    """Test cases for CommandTranslator."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration manager."""
        config = MagicMock()
        config.load_config.return_value = True
        config.get_llm_config.return_value = {
            'api_key': 'test-key',
            'base_url': 'https://test.api',
            'default_model': 'test-model'
        }
        return config

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client."""
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.fixture
    def translator(self, mock_config):
        """Create command translator with mocked dependencies."""
        with patch('services.command_translator.OpenRouterClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            translator = CommandTranslator(mock_config)
            translator.llm_client = mock_client
            return translator

    def test_translator_initialization(self, mock_config):
        """Test translator initialization."""
        with patch('services.command_translator.OpenRouterClient'):
            translator = CommandTranslator(mock_config)
            
            assert translator.config == mock_config
            assert translator.max_commands_per_request == 10
            assert translator.confidence_threshold == 0.7
            assert translator.max_retries == 2

    def test_classify_instruction_navigation(self, translator):
        """Test instruction classification for navigation."""
        nav_instructions = [
            "Move to position x=2, y=3",
            "Navigate to the kitchen",
            "Go to coordinates 1.5, 2.0",
            "Drive to the warehouse"
        ]
        
        for instruction in nav_instructions:
            result = translator._classify_instruction(instruction)
            assert result == "navigation"

    def test_classify_instruction_manipulation(self, translator):
        """Test instruction classification for manipulation."""
        manip_instructions = [
            "Pick up the red box",
            "Place the object on the shelf",
            "Grab the tool from the table",
            "Push the button"
        ]
        
        for instruction in manip_instructions:
            result = translator._classify_instruction(instruction)
            assert result == "manipulation"

    def test_classify_instruction_inspection(self, translator):
        """Test instruction classification for inspection."""
        inspect_instructions = [
            "Inspect the machinery",
            "Check the temperature sensor",
            "Examine the conveyor belt",
            "Look at the display panel"
        ]
        
        for instruction in inspect_instructions:
            result = translator._classify_instruction(instruction)
            assert result == "inspection"

    def test_classify_instruction_complex(self, translator):
        """Test instruction classification for complex instructions."""
        complex_instructions = [
            "Move to the table and pick up the box",
            "Go to the sensor and inspect it",
            "Navigate to position 2,3 then grab the tool and check its condition"
        ]
        
        for instruction in complex_instructions:
            result = translator._classify_instruction(instruction)
            assert result == "complex"

    def test_get_prompt_template(self, translator):
        """Test prompt template selection."""
        assert PromptTemplates.NAVIGATION_PROMPT in translator._get_prompt_template("navigation")
        assert PromptTemplates.MANIPULATION_PROMPT in translator._get_prompt_template("manipulation")
        assert PromptTemplates.INSPECTION_PROMPT in translator._get_prompt_template("inspection")
        assert PromptTemplates.COMPLEX_PROMPT in translator._get_prompt_template("complex")
        assert PromptTemplates.COMPLEX_PROMPT in translator._get_prompt_template("unknown")

    @pytest.mark.asyncio
    async def test_parse_llm_response_valid_json(self, translator):
        """Test parsing valid LLM response."""
        response = '''[
            {
                "command_id": "cmd_001",
                "robot_id": "robot_1",
                "action_type": "navigate",
                "parameters": {"target_x": 2.0, "target_y": 3.0},
                "priority": 5
            }
        ]'''
        
        commands = await translator._parse_llm_response(response, "robot_1")
        
        assert len(commands) == 1
        assert commands[0].command_id == "cmd_001"
        assert commands[0].action_type == ActionType.NAVIGATE
        assert commands[0].parameters["target_x"] == 2.0
        assert commands[0].parameters["target_y"] == 3.0

    @pytest.mark.asyncio
    async def test_parse_llm_response_wrapped_json(self, translator):
        """Test parsing JSON wrapped in text."""
        response = '''Here are the robot commands:
        [
            {
                "action_type": "manipulate",
                "parameters": {"object_id": "box_1", "action": "pick"},
                "priority": 7
            }
        ]
        These commands will accomplish the task.'''
        
        commands = await translator._parse_llm_response(response, "robot_1")
        
        assert len(commands) == 1
        assert commands[0].action_type == ActionType.MANIPULATE
        assert commands[0].robot_id == "robot_1"  # Should use default
        assert "cmd_" in commands[0].command_id  # Should generate ID

    @pytest.mark.asyncio
    async def test_parse_llm_response_single_object(self, translator):
        """Test parsing single JSON object (not array)."""
        response = '''{
            "action_type": "inspect",
            "parameters": {"target_location": "sensor_1"},
            "priority": 3
        }'''
        
        commands = await translator._parse_llm_response(response, "robot_1")
        
        assert len(commands) == 1
        assert commands[0].action_type == ActionType.INSPECT
        assert commands[0].parameters["target_location"] == "sensor_1"

    @pytest.mark.asyncio
    async def test_parse_llm_response_invalid_json(self, translator):
        """Test parsing invalid JSON."""
        response = "This is not valid JSON at all"
        
        commands = await translator._parse_llm_response(response, "robot_1")
        
        assert len(commands) == 0

    @pytest.mark.asyncio
    async def test_parse_llm_response_missing_action_type(self, translator):
        """Test parsing response with missing action_type."""
        response = '''[
            {
                "command_id": "cmd_001",
                "parameters": {"target_x": 2.0, "target_y": 3.0},
                "priority": 5
            }
        ]'''
        
        commands = await translator._parse_llm_response(response, "robot_1")
        
        assert len(commands) == 0  # Should skip invalid commands

    def test_calculate_confidence(self, translator):
        """Test confidence calculation."""
        instruction = "Move to position 2, 3"
        commands = [
            RobotCommand(
                command_id="cmd_001",
                robot_id="robot_1",
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 2.0, "target_y": 3.0},
                priority=5
            )
        ]
        llm_response = LLMResponse(
            content="test",
            model="test-model",
            usage={},
            response_time=1.5,
            success=True
        )
        
        confidence = translator._calculate_confidence(instruction, commands, llm_response)
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Should be reasonably confident

    def test_calculate_confidence_factors(self, translator):
        """Test confidence calculation with different factors."""
        instruction = "This is a reasonably sized instruction for testing"
        commands = [MagicMock()]  # Single command
        
        # Fast response should increase confidence
        fast_response = LLMResponse("", "model", {}, 1.0, True)
        confidence_fast = translator._calculate_confidence(instruction, commands, fast_response)
        
        # Slow response should decrease confidence
        slow_response = LLMResponse("", "model", {}, 6.0, True)
        confidence_slow = translator._calculate_confidence(instruction, commands, slow_response)
        
        assert confidence_fast > confidence_slow

    @pytest.mark.asyncio
    async def test_translate_command_success(self, translator):
        """Test successful command translation."""
        instruction = "Move to position 2, 3"
        
        # Mock LLM response
        mock_llm_response = LLMResponse(
            content='[{"action_type": "navigate", "parameters": {"target_x": 2.0, "target_y": 3.0}, "priority": 5}]',
            model="test-model",
            usage={},
            response_time=1.5,
            success=True
        )
        
        translator.llm_client.generate_response = AsyncMock(return_value=mock_llm_response)
        
        result = await translator.translate_command(instruction)
        
        assert result.success is True
        assert len(result.commands) == 1
        assert result.commands[0].action_type == ActionType.NAVIGATE
        assert result.original_text == instruction
        assert result.confidence > 0.0
        assert result.processing_time > 0.0

    @pytest.mark.asyncio
    async def test_translate_command_llm_failure(self, translator):
        """Test command translation with LLM failure."""
        instruction = "Move to position 2, 3"
        
        # Mock LLM failure
        mock_llm_response = LLMResponse(
            content="",
            model="test-model",
            usage={},
            response_time=1.0,
            success=False,
            error="API error"
        )
        
        translator.llm_client.generate_response = AsyncMock(return_value=mock_llm_response)
        
        result = await translator.translate_command(instruction)
        
        assert result.success is False
        assert len(result.commands) == 0
        assert "LLM request failed" in result.error

    @pytest.mark.asyncio
    async def test_translate_command_invalid_response(self, translator):
        """Test command translation with invalid LLM response."""
        instruction = "Move to position 2, 3"
        
        # Mock LLM response with invalid JSON
        mock_llm_response = LLMResponse(
            content="This is not valid JSON",
            model="test-model",
            usage={},
            response_time=1.5,
            success=True
        )
        
        translator.llm_client.generate_response = AsyncMock(return_value=mock_llm_response)
        
        result = await translator.translate_command(instruction)
        
        assert result.success is False
        assert len(result.commands) == 0
        assert "Failed to parse valid commands" in result.error

    @pytest.mark.asyncio
    async def test_translate_command_with_context(self, translator):
        """Test command translation with context."""
        instruction = "Now pick up the box"
        context = ["Move to the table", "Inspect the area"]
        
        mock_llm_response = LLMResponse(
            content='[{"action_type": "manipulate", "parameters": {"object_id": "box", "action": "pick"}, "priority": 5}]',
            model="test-model",
            usage={},
            response_time=1.5,
            success=True
        )
        
        translator.llm_client.generate_response = AsyncMock(return_value=mock_llm_response)
        
        result = await translator.translate_command(instruction, context=context)
        
        assert result.success is True
        assert len(result.commands) == 1
        
        # Verify context was included in the request
        call_args = translator.llm_client.generate_response.call_args[0][0]
        user_message = call_args[1].content
        assert "Previous commands context" in user_message

    @pytest.mark.asyncio
    async def test_translate_batch(self, translator):
        """Test batch translation."""
        instructions = [
            "Move to position 1, 2",
            "Pick up the red box",
            "Inspect the sensor"
        ]
        
        # Mock different responses for each instruction
        responses = [
            LLMResponse('[{"action_type": "navigate", "parameters": {"target_x": 1.0, "target_y": 2.0}, "priority": 5}]', "model", {}, 1.0, True),
            LLMResponse('[{"action_type": "manipulate", "parameters": {"object_id": "red_box", "action": "pick"}, "priority": 7}]', "model", {}, 1.0, True),
            LLMResponse('[{"action_type": "inspect", "parameters": {"target_location": "sensor"}, "priority": 3}]', "model", {}, 1.0, True)
        ]
        
        translator.llm_client.generate_response = AsyncMock(side_effect=responses)
        
        results = await translator.translate_batch(instructions)
        
        assert len(results) == 3
        assert all(result.success for result in results)
        assert results[0].commands[0].action_type == ActionType.NAVIGATE
        assert results[1].commands[0].action_type == ActionType.MANIPULATE
        assert results[2].commands[0].action_type == ActionType.INSPECT

    @pytest.mark.asyncio
    async def test_validate_translation(self, translator):
        """Test translation validation."""
        instruction = "Move to position 2, 3"
        commands = [
            RobotCommand(
                command_id="cmd_001",
                robot_id="robot_1",
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 2.0, "target_y": 3.0},
                priority=5
            )
        ]
        
        # Mock validation response
        mock_validation_response = LLMResponse(
            content='[{"command_id": "cmd_001", "robot_id": "robot_1", "action_type": "navigate", "parameters": {"target_x": 2.0, "target_y": 3.0}, "priority": 5}]',
            model="test-model",
            usage={},
            response_time=1.0,
            success=True
        )
        
        translator.llm_client.generate_response = AsyncMock(return_value=mock_validation_response)
        
        result = await translator.validate_translation(instruction, commands)
        
        assert result.success is True
        assert len(result.commands) == 1
        assert result.confidence == 0.9  # High confidence after validation

    @pytest.mark.asyncio
    async def test_context_manager(self, translator):
        """Test async context manager functionality."""
        async with translator as t:
            assert t == translator
            translator.llm_client.__aenter__.assert_called_once()
        
        translator.llm_client.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_command_validation_integration(self, translator):
        """Test integration with command validation."""
        instruction = "Move to position 2, 3"
        
        # Mock LLM response with invalid command (missing required parameter)
        mock_llm_response = LLMResponse(
            content='[{"action_type": "navigate", "parameters": {"target_x": 2.0}, "priority": 5}]',  # Missing target_y
            model="test-model",
            usage={},
            response_time=1.5,
            success=True
        )
        
        translator.llm_client.generate_response = AsyncMock(return_value=mock_llm_response)
        
        result = await translator.translate_command(instruction)
        
        # Should fail validation and return no commands
        assert result.success is False
        assert len(result.commands) == 0
        assert "Failed to parse valid commands" in result.error

    @pytest.mark.asyncio
    async def test_safety_constraint_checking(self, translator):
        """Test safety constraint checking during translation."""
        instruction = "Move very fast to position 2, 3"
        
        # Mock LLM response with unsafe speed
        mock_llm_response = LLMResponse(
            content='[{"action_type": "navigate", "parameters": {"target_x": 2.0, "target_y": 3.0, "max_speed": 5.0}, "priority": 5}]',
            model="test-model",
            usage={},
            response_time=1.5,
            success=True
        )
        
        translator.llm_client.generate_response = AsyncMock(return_value=mock_llm_response)
        
        with patch.object(translator.validator, 'validate_safety_constraints') as mock_safety:
            mock_safety.return_value = ["Speed exceeds safety limit"]
            
            result = await translator.translate_command(instruction)
            
            # Should still succeed but log warnings
            assert result.success is True
            mock_safety.assert_called_once()

    def test_prompt_templates_completeness(self):
        """Test that all prompt templates are properly defined."""
        assert PromptTemplates.SYSTEM_PROMPT
        assert PromptTemplates.NAVIGATION_PROMPT
        assert PromptTemplates.MANIPULATION_PROMPT
        assert PromptTemplates.INSPECTION_PROMPT
        assert PromptTemplates.COMPLEX_PROMPT
        assert PromptTemplates.VALIDATION_PROMPT
        
        # Check that templates contain placeholder
        assert "{instruction}" in PromptTemplates.NAVIGATION_PROMPT
        assert "{instruction}" in PromptTemplates.MANIPULATION_PROMPT
        assert "{instruction}" in PromptTemplates.INSPECTION_PROMPT
        assert "{instruction}" in PromptTemplates.COMPLEX_PROMPT
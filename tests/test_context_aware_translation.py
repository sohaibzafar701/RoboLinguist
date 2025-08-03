"""
Integration tests for context-aware command translation system.

Tests the CommandTranslator with real context data and API calls to ensure
accurate robot command generation with situational awareness.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from services.command_translator import CommandTranslator, TranslationResult
from services.robotics_context_manager import RoboticsContextManager, SystemContext
from services.openrouter_client import OpenRouterClient, LLMResponse
from core.data_models import RobotState, ActionType
from config.config_manager import ConfigManager


class TestContextAwareTranslation:
    """Test suite for context-aware command translation."""

    @pytest.fixture
    async def mock_context_manager(self):
        """Create a mock context manager with sample data."""
        context_manager = Mock(spec=RoboticsContextManager)
        
        # Mock system context
        mock_context = Mock(spec=SystemContext)
        mock_context.get_available_robots.return_value = ['robot_1', 'robot_2', 'robot_3']
        mock_context.to_llm_context_string.return_value = """
AVAILABLE ROBOTS:
- robot_1: Position (2.0, 3.0), Status: idle, Battery: 85%
- robot_2: Position (-1.0, 1.5), Status: moving, Battery: 92%
- robot_3: Position (0.0, -2.0), Status: idle, Battery: 78%

ENVIRONMENT:
- Boundaries: x=[-10, 10], y=[-10, 10]
- Obstacles: [(5.0, 5.0), (-3.0, 2.0)]

WORLD STATE:
- Active tasks: 0
- System status: operational
"""
        
        context_manager.get_system_context.return_value = mock_context
        return context_manager

    @pytest.fixture
    async def mock_llm_client(self):
        """Create a mock LLM client."""
        client = Mock(spec=OpenRouterClient)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.fixture
    async def translator(self, mock_context_manager, mock_llm_client):
        """Create a CommandTranslator with mocked dependencies."""
        config = Mock(spec=ConfigManager)
        config.load_config.return_value = None
        
        with patch('services.command_translator.OpenRouterClient', return_value=mock_llm_client):
            translator = CommandTranslator(config, mock_context_manager)
            translator.llm_client = mock_llm_client
            return translator

    @pytest.mark.asyncio
    async def test_context_aware_navigation_command(self, translator, mock_llm_client):
        """Test context-aware translation of navigation commands."""
        # Mock LLM response for navigation
        mock_response = LLMResponse(
            success=True,
            content='[{"command_id": "nav_001", "robot_id": "robot_1", "action_type": "navigate", "parameters": {"target_x": 5.0, "target_y": 2.0}, "priority": 5}]',
            response_time=1.2,
            model_used="mistral-7b",
            tokens_used=150
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Test translation
        result = await translator.translate_with_context("Move robot_1 to position 5, 2")
        
        # Verify result
        assert result.success is True
        assert len(result.commands) == 1
        
        command = result.commands[0]
        assert command.robot_id == "robot_1"
        assert command.action_type == ActionType.NAVIGATE
        assert command.parameters["target_x"] == 5.0
        assert command.parameters["target_y"] == 2.0
        assert result.confidence > 0.7

    @pytest.mark.asyncio
    async def test_context_aware_multi_robot_formation(self, translator, mock_llm_client):
        """Test context-aware translation for multi-robot formation commands."""
        # Mock LLM response for formation
        mock_response = LLMResponse(
            success=True,
            content='''[
                {"command_id": "form_001", "robot_id": "robot_1", "action_type": "navigate", "parameters": {"target_x": 0.0, "target_y": 2.0}, "priority": 5},
                {"command_id": "form_002", "robot_id": "robot_2", "action_type": "navigate", "parameters": {"target_x": -2.0, "target_y": 0.0}, "priority": 5},
                {"command_id": "form_003", "robot_id": "robot_3", "action_type": "navigate", "parameters": {"target_x": 2.0, "target_y": 0.0}, "priority": 5}
            ]''',
            response_time=1.8,
            model_used="mistral-7b",
            tokens_used=220
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Test translation
        result = await translator.translate_with_context("Form a triangle formation with all robots")
        
        # Verify result
        assert result.success is True
        assert len(result.commands) == 3
        
        # Check that all available robots are commanded
        robot_ids = {cmd.robot_id for cmd in result.commands}
        assert robot_ids == {"robot_1", "robot_2", "robot_3"}
        
        # Check that all commands are navigation
        for cmd in result.commands:
            assert cmd.action_type == ActionType.NAVIGATE
            assert "target_x" in cmd.parameters
            assert "target_y" in cmd.parameters

    @pytest.mark.asyncio
    async def test_context_validation_invalid_robot(self, translator, mock_llm_client):
        """Test that commands for unavailable robots are filtered out."""
        # Mock LLM response with invalid robot ID
        mock_response = LLMResponse(
            success=True,
            content='[{"command_id": "inv_001", "robot_id": "robot_99", "action_type": "navigate", "parameters": {"target_x": 1.0, "target_y": 1.0}, "priority": 5}]',
            response_time=1.0,
            model_used="mistral-7b",
            tokens_used=100
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Test translation
        result = await translator.translate_with_context("Move robot_99 to position 1, 1")
        
        # Verify that invalid robot command is filtered out
        assert result.success is False or len(result.commands) == 0

    @pytest.mark.asyncio
    async def test_context_validation_boundary_check(self, translator, mock_llm_client):
        """Test that commands outside environment boundaries are validated."""
        # Mock LLM response with out-of-bounds coordinates
        mock_response = LLMResponse(
            success=True,
            content='[{"command_id": "oob_001", "robot_id": "robot_1", "action_type": "navigate", "parameters": {"target_x": 15.0, "target_y": 15.0}, "priority": 5}]',
            response_time=1.1,
            model_used="mistral-7b",
            tokens_used=120
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Test translation
        result = await translator.translate_with_context("Move robot_1 to position 15, 15")
        
        # Verify that out-of-bounds command is handled appropriately
        # (Either filtered out or flagged with low confidence)
        if result.success and result.commands:
            assert result.confidence < 0.8  # Lower confidence for boundary issues

    @pytest.mark.asyncio
    async def test_context_aware_prompt_building(self, translator):
        """Test that context-aware prompts are built correctly."""
        instruction = "Move all robots to center"
        mock_context = translator.context_manager.get_system_context()
        
        # Build context-aware prompt
        prompt = translator._build_context_aware_prompt(instruction, mock_context)
        
        # Verify prompt contains context information
        assert "CURRENT SYSTEM CONTEXT:" in prompt
        assert "robot_1" in prompt
        assert "robot_2" in prompt
        assert "robot_3" in prompt
        assert "Position" in prompt
        assert "Boundaries" in prompt
        assert instruction in prompt

    @pytest.mark.asyncio
    async def test_confidence_calculation_with_context(self, translator):
        """Test confidence calculation based on context alignment."""
        from core.data_models import RobotCommand
        
        # Create test commands
        commands = [
            RobotCommand(
                command_id="test_001",
                robot_id="robot_1",  # Valid robot
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 2.0, "target_y": 3.0},  # Within bounds
                priority=5
            ),
            RobotCommand(
                command_id="test_002",
                robot_id="robot_99",  # Invalid robot
                action_type=ActionType.NAVIGATE,
                parameters={"target_x": 1.0, "target_y": 1.0},
                priority=5
            )
        ]
        
        mock_context = translator.context_manager.get_system_context()
        
        # Calculate confidence
        confidence = translator._calculate_context_confidence(commands, mock_context)
        
        # Should have reduced confidence due to invalid robot
        assert 0.0 <= confidence <= 1.0
        assert confidence < 0.8  # Reduced due to invalid robot

    @pytest.mark.asyncio
    async def test_llm_failure_handling(self, translator, mock_llm_client):
        """Test handling of LLM API failures."""
        # Mock LLM failure
        mock_response = LLMResponse(
            success=False,
            content="",
            response_time=0.0,
            model_used="",
            tokens_used=0,
            error="API timeout"
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Test translation
        result = await translator.translate_with_context("Move robot_1 forward")
        
        # Verify failure is handled gracefully
        assert result.success is False
        assert "API timeout" in result.error
        assert len(result.commands) == 0

    @pytest.mark.asyncio
    async def test_malformed_json_handling(self, translator, mock_llm_client):
        """Test handling of malformed JSON responses from LLM."""
        # Mock malformed JSON response
        mock_response = LLMResponse(
            success=True,
            content='{"command_id": "malformed", "robot_id": "robot_1"',  # Incomplete JSON
            response_time=1.0,
            model_used="mistral-7b",
            tokens_used=50
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Test translation
        result = await translator.translate_with_context("Move robot_1 forward")
        
        # Verify malformed JSON is handled gracefully
        assert result.success is False
        assert len(result.commands) == 0
        assert "parse" in result.error.lower() or "json" in result.error.lower()

    @pytest.mark.asyncio
    async def test_context_refresh_functionality(self, translator):
        """Test forced context refresh functionality."""
        # Test with forced refresh
        result1 = await translator.translate_with_context(
            "Move robot_1 to center", 
            force_context_refresh=True
        )
        
        # Verify context manager was called with refresh
        translator.context_manager.get_system_context.assert_called_with(True)
        
        # Test without forced refresh
        result2 = await translator.translate_with_context(
            "Move robot_2 to center", 
            force_context_refresh=False
        )
        
        # Verify context manager was called without refresh
        translator.context_manager.get_system_context.assert_called_with(False)

    @pytest.mark.asyncio
    async def test_fallback_to_basic_translation(self, translator, mock_llm_client):
        """Test fallback to basic translation when context manager is unavailable."""
        # Remove context manager
        translator.context_manager = None
        
        # Mock basic translation response
        mock_response = LLMResponse(
            success=True,
            content='[{"command_id": "basic_001", "robot_id": "default", "action_type": "navigate", "parameters": {"target_x": 1.0, "target_y": 1.0}, "priority": 5}]',
            response_time=1.0,
            model_used="mistral-7b",
            tokens_used=100
        )
        mock_llm_client.generate_response.return_value = mock_response
        
        # Mock the basic translate_command method
        with patch.object(translator, 'translate_command') as mock_translate:
            mock_translate.return_value = TranslationResult(
                success=True,
                commands=[],
                original_text="test",
                confidence=0.8,
                processing_time=1.0
            )
            
            # Test translation
            result = await translator.translate_with_context("Move forward")
            
            # Verify fallback was used
            mock_translate.assert_called_once_with("Move forward")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
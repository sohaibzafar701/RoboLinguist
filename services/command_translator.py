"""
Command translation system for converting natural language to robot commands.

Provides intelligent translation of human language instructions into structured
robot commands using LLM services.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime

from services.openrouter_client import OpenRouterClient, ChatMessage, LLMResponse
from core.data_models import RobotCommand, ActionType
from core.command_validation import CommandValidator
from config.config_manager import ConfigManager


logger = logging.getLogger(__name__)


@dataclass
class TranslationResult:
    """Result of command translation."""
    success: bool
    commands: List[RobotCommand]
    original_text: str
    confidence: float
    processing_time: float
    error: Optional[str] = None
    raw_llm_response: Optional[str] = None


class PromptTemplates:
    """Templates for different types of robot command prompts."""
    
    SYSTEM_PROMPT = """You are an expert robot command translator. Your job is to convert natural language instructions into structured robot commands.

You must respond with valid JSON containing an array of robot commands. Each command must have:
- command_id: unique identifier (generate UUID-like string)
- robot_id: target robot (use "default" if not specified)
- action_type: one of "navigate", "manipulate", "inspect"
- parameters: object with action-specific parameters
- priority: integer 0-10 (higher = more urgent)

Action-specific parameters:
NAVIGATE: target_x, target_y, target_z (optional), max_speed (optional), tolerance (optional)
MANIPULATE: object_id, action (pick/place/push/pull/rotate/grasp/release), force_limit (optional)
INSPECT: target_location, inspection_type (optional), duration (optional), resolution (optional)

Always respond with valid JSON only, no explanations."""

    NAVIGATION_PROMPT = """Convert this navigation instruction to robot commands:
"{instruction}"

Focus on extracting coordinates, destinations, and movement parameters."""

    MANIPULATION_PROMPT = """Convert this manipulation instruction to robot commands:
"{instruction}"

Focus on identifying objects to manipulate and the specific actions to perform."""

    INSPECTION_PROMPT = """Convert this inspection instruction to robot commands:
"{instruction}"

Focus on identifying what needs to be inspected and how."""

    COMPLEX_PROMPT = """Convert this complex instruction to a sequence of robot commands:
"{instruction}"

Break down the instruction into individual robot actions in the correct order."""

    VALIDATION_PROMPT = """Review and validate these robot commands for safety and correctness:
{commands}

Original instruction: "{instruction}"

Respond with the corrected commands in JSON format, ensuring all parameters are valid."""


class CommandTranslator:
    """
    Translates natural language instructions into structured robot commands.
    
    Uses LLM services to intelligently parse human language and generate
    appropriate robot command sequences.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize command translator.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager or ConfigManager()
        self.config.load_config()
        
        self.llm_client = OpenRouterClient(self.config)
        self.validator = CommandValidator()
        
        # Translation settings
        self.max_commands_per_request = 10
        self.confidence_threshold = 0.7
        self.max_retries = 2
        
        logger.info("Command translator initialized")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.llm_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.llm_client.__aexit__(exc_type, exc_val, exc_tb)

    async def translate_command(
        self, 
        instruction: str, 
        robot_id: str = "default",
        context: Optional[List[str]] = None
    ) -> TranslationResult:
        """
        Translate a natural language instruction to robot commands.
        
        Args:
            instruction: Natural language instruction
            robot_id: Target robot ID
            context: Optional context from previous commands
            
        Returns:
            TranslationResult: Translation result with commands or error
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Translating instruction: {instruction}")
            
            # Determine instruction type and select appropriate prompt
            instruction_type = self._classify_instruction(instruction)
            prompt_template = self._get_prompt_template(instruction_type)
            
            # Build context if provided
            context_str = ""
            if context:
                context_str = f"\nPrevious commands context: {'; '.join(context[-3:])}"
            
            # Create messages for LLM
            messages = [
                ChatMessage(role="system", content=PromptTemplates.SYSTEM_PROMPT),
                ChatMessage(role="user", content=prompt_template.format(instruction=instruction) + context_str)
            ]
            
            # Get LLM response
            llm_response = await self.llm_client.generate_response(
                messages,
                temperature=0.3,  # Lower temperature for more consistent output
                max_tokens=800
            )
            
            if not llm_response.success:
                return TranslationResult(
                    success=False,
                    commands=[],
                    original_text=instruction,
                    confidence=0.0,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    error=f"LLM request failed: {llm_response.error}"
                )
            
            # Parse LLM response to extract commands
            commands = await self._parse_llm_response(llm_response.content, robot_id)
            
            if not commands:
                return TranslationResult(
                    success=False,
                    commands=[],
                    original_text=instruction,
                    confidence=0.0,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    error="Failed to parse valid commands from LLM response",
                    raw_llm_response=llm_response.content
                )
            
            # Validate commands
            validated_commands = []
            for cmd in commands:
                try:
                    # Validate command structure
                    self.validator.validate_command_structure(cmd)
                    
                    # Check safety constraints
                    safety_violations = self.validator.validate_safety_constraints(cmd)
                    if safety_violations:
                        logger.warning(f"Safety violations in command {cmd.command_id}: {safety_violations}")
                        # Could either reject or modify the command here
                    
                    validated_commands.append(cmd)
                    
                except Exception as e:
                    logger.warning(f"Command validation failed: {e}")
                    continue
            
            if not validated_commands:
                return TranslationResult(
                    success=False,
                    commands=[],
                    original_text=instruction,
                    confidence=0.0,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    error="No valid commands after validation",
                    raw_llm_response=llm_response.content
                )
            
            # Calculate confidence score
            confidence = self._calculate_confidence(instruction, validated_commands, llm_response)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Successfully translated instruction to {len(validated_commands)} commands")
            
            return TranslationResult(
                success=True,
                commands=validated_commands,
                original_text=instruction,
                confidence=confidence,
                processing_time=processing_time,
                raw_llm_response=llm_response.content
            )
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return TranslationResult(
                success=False,
                commands=[],
                original_text=instruction,
                confidence=0.0,
                processing_time=(datetime.now() - start_time).total_seconds(),
                error=str(e)
            )

    async def translate_batch(
        self, 
        instructions: List[str], 
        robot_id: str = "default"
    ) -> List[TranslationResult]:
        """
        Translate multiple instructions in batch.
        
        Args:
            instructions: List of natural language instructions
            robot_id: Target robot ID
            
        Returns:
            List[TranslationResult]: Results for each instruction
        """
        results = []
        context = []
        
        for instruction in instructions:
            result = await self.translate_command(instruction, robot_id, context)
            results.append(result)
            
            # Add successful commands to context for next instruction
            if result.success:
                context.append(instruction)
        
        return results

    def _classify_instruction(self, instruction: str) -> str:
        """
        Classify the type of instruction.
        
        Args:
            instruction: Natural language instruction
            
        Returns:
            str: Instruction type (navigation, manipulation, inspection, complex)
        """
        instruction_lower = instruction.lower()
        
        # Navigation keywords
        nav_keywords = ['move', 'go', 'navigate', 'drive', 'travel', 'position', 'location', 'coordinate']
        
        # Manipulation keywords
        manip_keywords = ['pick', 'place', 'grab', 'drop', 'push', 'pull', 'lift', 'carry', 'manipulate']
        
        # Inspection keywords
        inspect_keywords = ['inspect', 'check', 'examine', 'look', 'scan', 'monitor', 'observe']
        
        nav_score = sum(1 for keyword in nav_keywords if keyword in instruction_lower)
        manip_score = sum(1 for keyword in manip_keywords if keyword in instruction_lower)
        inspect_score = sum(1 for keyword in inspect_keywords if keyword in instruction_lower)
        
        # Check for complex instructions (multiple action types)
        action_types = sum(1 for score in [nav_score, manip_score, inspect_score] if score > 0)
        
        if action_types > 1:
            return "complex"
        elif nav_score > 0:
            return "navigation"
        elif manip_score > 0:
            return "manipulation"
        elif inspect_score > 0:
            return "inspection"
        else:
            return "complex"  # Default to complex for ambiguous instructions

    def _get_prompt_template(self, instruction_type: str) -> str:
        """
        Get appropriate prompt template for instruction type.
        
        Args:
            instruction_type: Type of instruction
            
        Returns:
            str: Prompt template
        """
        templates = {
            "navigation": PromptTemplates.NAVIGATION_PROMPT,
            "manipulation": PromptTemplates.MANIPULATION_PROMPT,
            "inspection": PromptTemplates.INSPECTION_PROMPT,
            "complex": PromptTemplates.COMPLEX_PROMPT
        }
        
        return templates.get(instruction_type, PromptTemplates.COMPLEX_PROMPT)

    async def _parse_llm_response(self, response: str, robot_id: str) -> List[RobotCommand]:
        """
        Parse LLM response to extract robot commands.
        
        Args:
            response: Raw LLM response
            robot_id: Target robot ID
            
        Returns:
            List[RobotCommand]: Parsed commands
        """
        try:
            # Clean up response - extract JSON if it's wrapped in text
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                # Try to find JSON object
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    # Wrap single object in array
                    json_str = f'[{json_str}]'
                else:
                    logger.error(f"No JSON found in response: {response}")
                    return []
            
            # Parse JSON
            commands_data = json.loads(json_str)
            
            if not isinstance(commands_data, list):
                logger.error("Response is not a list of commands")
                return []
            
            commands = []
            for i, cmd_data in enumerate(commands_data):
                try:
                    # Ensure required fields
                    if 'action_type' not in cmd_data:
                        logger.warning(f"Command {i} missing action_type")
                        continue
                    
                    # Set defaults
                    cmd_data.setdefault('command_id', f"cmd_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}")
                    cmd_data.setdefault('robot_id', robot_id)
                    cmd_data.setdefault('parameters', {})
                    cmd_data.setdefault('priority', 5)
                    
                    # Convert action_type to enum
                    action_type_str = cmd_data['action_type'].lower()
                    if action_type_str == 'navigate':
                        action_type = ActionType.NAVIGATE
                    elif action_type_str == 'manipulate':
                        action_type = ActionType.MANIPULATE
                    elif action_type_str == 'inspect':
                        action_type = ActionType.INSPECT
                    else:
                        logger.warning(f"Unknown action type: {action_type_str}")
                        continue
                    
                    # Create RobotCommand
                    command = RobotCommand(
                        command_id=cmd_data['command_id'],
                        robot_id=cmd_data['robot_id'],
                        action_type=action_type,
                        parameters=cmd_data['parameters'],
                        priority=cmd_data['priority']
                    )
                    
                    commands.append(command)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse command {i}: {e}")
                    continue
            
            return commands
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response was: {response}")
            return []
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return []

    def _calculate_confidence(
        self, 
        instruction: str, 
        commands: List[RobotCommand], 
        llm_response: LLMResponse
    ) -> float:
        """
        Calculate confidence score for the translation.
        
        Args:
            instruction: Original instruction
            commands: Generated commands
            llm_response: LLM response metadata
            
        Returns:
            float: Confidence score (0-1)
        """
        confidence = 0.8  # Base confidence
        
        # Adjust based on response time (faster = more confident)
        if llm_response.response_time < 2.0:
            confidence += 0.1
        elif llm_response.response_time > 5.0:
            confidence -= 0.1
        
        # Adjust based on number of commands (reasonable number = more confident)
        if 1 <= len(commands) <= 3:
            confidence += 0.1
        elif len(commands) > 5:
            confidence -= 0.1
        
        # Adjust based on instruction complexity
        word_count = len(instruction.split())
        if word_count < 5:
            confidence -= 0.1  # Too simple might be ambiguous
        elif 5 <= word_count <= 15:
            confidence += 0.1  # Good complexity
        elif word_count > 20:
            confidence -= 0.1  # Too complex might be error-prone
        
        # Ensure confidence is in valid range
        return max(0.0, min(1.0, confidence))

    async def validate_translation(
        self, 
        instruction: str, 
        commands: List[RobotCommand]
    ) -> TranslationResult:
        """
        Validate a translation by asking the LLM to review it.
        
        Args:
            instruction: Original instruction
            commands: Generated commands
            
        Returns:
            TranslationResult: Validation result
        """
        try:
            # Convert commands to JSON for validation
            commands_json = []
            for cmd in commands:
                commands_json.append({
                    "command_id": cmd.command_id,
                    "robot_id": cmd.robot_id,
                    "action_type": cmd.action_type,
                    "parameters": cmd.parameters,
                    "priority": cmd.priority
                })
            
            validation_prompt = PromptTemplates.VALIDATION_PROMPT.format(
                commands=json.dumps(commands_json, indent=2),
                instruction=instruction
            )
            
            messages = [
                ChatMessage(role="system", content=PromptTemplates.SYSTEM_PROMPT),
                ChatMessage(role="user", content=validation_prompt)
            ]
            
            llm_response = await self.llm_client.generate_response(
                messages,
                temperature=0.2,  # Very low temperature for validation
                max_tokens=800
            )
            
            if not llm_response.success:
                return TranslationResult(
                    success=False,
                    commands=commands,  # Return original commands
                    original_text=instruction,
                    confidence=0.5,  # Medium confidence since validation failed
                    processing_time=llm_response.response_time,
                    error=f"Validation failed: {llm_response.error}"
                )
            
            # Parse validated commands
            validated_commands = await self._parse_llm_response(llm_response.content, commands[0].robot_id)
            
            if validated_commands:
                return TranslationResult(
                    success=True,
                    commands=validated_commands,
                    original_text=instruction,
                    confidence=0.9,  # High confidence after validation
                    processing_time=llm_response.response_time,
                    raw_llm_response=llm_response.content
                )
            else:
                return TranslationResult(
                    success=True,
                    commands=commands,  # Return original if validation parsing failed
                    original_text=instruction,
                    confidence=0.7,
                    processing_time=llm_response.response_time,
                    error="Validation parsing failed, using original commands"
                )
                
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return TranslationResult(
                success=True,
                commands=commands,  # Return original commands on error
                original_text=instruction,
                confidence=0.6,
                processing_time=0.0,
                error=f"Validation error: {e}"
            )
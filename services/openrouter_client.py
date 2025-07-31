"""
OpenRouter API client for LLM integration.

Provides a robust client for interacting with OpenRouter's API with retry logic,
fallback models, and comprehensive error handling.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

import httpx
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log
)

from config.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    """Available model types on OpenRouter."""
    MISTRAL_7B = "mistralai/mistral-7b-instruct"
    LLAMA_3_8B = "meta-llama/llama-3-8b-instruct"
    LLAMA_3_70B = "meta-llama/llama-3-70b-instruct"
    CLAUDE_HAIKU = "anthropic/claude-3-haiku"
    GPT_3_5_TURBO = "openai/gpt-3.5-turbo"


@dataclass
class LLMResponse:
    """Response from LLM API call."""
    content: str
    model: str
    usage: Dict[str, int]
    response_time: float
    success: bool
    error: Optional[str] = None


@dataclass
class ChatMessage:
    """Chat message for conversation context."""
    role: str  # 'system', 'user', 'assistant'
    content: str


class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors."""
    pass


class RateLimitError(OpenRouterError):
    """Raised when API rate limit is exceeded."""
    pass


class ModelUnavailableError(OpenRouterError):
    """Raised when requested model is unavailable."""
    pass


class OpenRouterClient:
    """
    Client for interacting with OpenRouter API.
    
    Provides robust API interaction with retry logic, fallback models,
    and comprehensive error handling.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize OpenRouter client.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager or ConfigManager()
        self.llm_config = self.config.get_llm_config()
        
        self.api_key = self.llm_config.get('api_key')
        self.base_url = self.llm_config.get('base_url', 'https://openrouter.ai/api/v1')
        self.default_model = self.llm_config.get('default_model', ModelType.MISTRAL_7B)
        self.fallback_model = self.llm_config.get('fallback_model', ModelType.LLAMA_3_8B)
        self.timeout = self.llm_config.get('timeout', 30)
        self.max_retries = self.llm_config.get('max_retries', 3)
        
        # Default generation parameters
        self.temperature = self.llm_config.get('temperature', 0.7)
        self.max_tokens = self.llm_config.get('max_tokens', 1000)
        
        if not self.api_key:
            raise ValueError("OpenRouter API key is required")
        
        # HTTP client with proper headers
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/chatgpt-for-robots",
                "X-Title": "ChatGPT for Robots"
            }
        )
        
        logger.info(f"OpenRouter client initialized with model: {self.default_model}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.RequestError, RateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _make_request(
        self, 
        model: str, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make a request to the OpenRouter API with retry logic.
        
        Args:
            model: Model to use for generation
            messages: List of chat messages
            **kwargs: Additional generation parameters
            
        Returns:
            Dict[str, Any]: API response
            
        Raises:
            OpenRouterError: If API request fails
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get('temperature', self.temperature),
            "max_tokens": kwargs.get('max_tokens', self.max_tokens),
            **{k: v for k, v in kwargs.items() if k not in ['temperature', 'max_tokens']}
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            
            if response.status_code == 429:
                raise RateLimitError("API rate limit exceeded")
            elif response.status_code == 503:
                raise ModelUnavailableError(f"Model {model} is currently unavailable")
            elif response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                raise OpenRouterError(error_msg)
            
            return response.json()
            
        except httpx.RequestError as e:
            logger.error(f"HTTP request error: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response: {e}")
            raise OpenRouterError(f"Invalid JSON response: {e}")

    async def generate_response(
        self, 
        messages: Union[List[ChatMessage], List[Dict[str, str]]], 
        model: Optional[str] = None,
        use_fallback: bool = True,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of chat messages or message dictionaries
            model: Model to use (defaults to configured default)
            use_fallback: Whether to use fallback model on failure
            **kwargs: Additional generation parameters
            
        Returns:
            LLMResponse: Generated response with metadata
        """
        start_time = time.time()
        target_model = model or self.default_model
        
        # Convert ChatMessage objects to dictionaries if needed
        if messages and isinstance(messages[0], ChatMessage):
            message_dicts = [{"role": msg.role, "content": msg.content} for msg in messages]
        else:
            message_dicts = messages
        
        try:
            logger.info(f"Generating response with model: {target_model}")
            response_data = await self._make_request(target_model, message_dicts, **kwargs)
            
            content = response_data['choices'][0]['message']['content']
            usage = response_data.get('usage', {})
            response_time = time.time() - start_time
            
            logger.info(f"Response generated successfully in {response_time:.2f}s")
            
            return LLMResponse(
                content=content,
                model=target_model,
                usage=usage,
                response_time=response_time,
                success=True
            )
            
        except (ModelUnavailableError, OpenRouterError) as e:
            logger.warning(f"Primary model {target_model} failed: {e}")
            
            if use_fallback and target_model != self.fallback_model:
                logger.info(f"Attempting fallback to model: {self.fallback_model}")
                try:
                    response_data = await self._make_request(self.fallback_model, message_dicts, **kwargs)
                    
                    content = response_data['choices'][0]['message']['content']
                    usage = response_data.get('usage', {})
                    response_time = time.time() - start_time
                    
                    logger.info(f"Fallback response generated successfully in {response_time:.2f}s")
                    
                    return LLMResponse(
                        content=content,
                        model=self.fallback_model,
                        usage=usage,
                        response_time=response_time,
                        success=True
                    )
                    
                except Exception as fallback_error:
                    logger.error(f"Fallback model also failed: {fallback_error}")
                    response_time = time.time() - start_time
                    
                    return LLMResponse(
                        content="",
                        model=target_model,
                        usage={},
                        response_time=response_time,
                        success=False,
                        error=f"Both primary and fallback models failed: {str(e)}, {str(fallback_error)}"
                    )
            else:
                response_time = time.time() - start_time
                return LLMResponse(
                    content="",
                    model=target_model,
                    usage={},
                    response_time=response_time,
                    success=False,
                    error=str(e)
                )

    async def generate_simple_response(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a simple response from a single prompt.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            model: Model to use
            **kwargs: Additional generation parameters
            
        Returns:
            LLMResponse: Generated response
        """
        messages = []
        
        if system_message:
            messages.append(ChatMessage(role="system", content=system_message))
        
        messages.append(ChatMessage(role="user", content=prompt))
        
        return await self.generate_response(messages, model=model, **kwargs)

    async def test_connection(self) -> bool:
        """
        Test the connection to OpenRouter API.
        
        Returns:
            bool: True if connection is successful
        """
        try:
            response = await self.generate_simple_response(
                "Hello, please respond with 'Connection successful'",
                max_tokens=50
            )
            
            if response.success and "successful" in response.content.lower():
                logger.info("OpenRouter connection test successful")
                return True
            else:
                logger.error(f"Connection test failed: {response.error}")
                return False
                
        except Exception as e:
            logger.error(f"Connection test failed with exception: {e}")
            return False

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """
        List available models from OpenRouter.
        
        Returns:
            List[Dict[str, Any]]: List of available models
        """
        try:
            response = await self.client.get(f"{self.base_url}/models")
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            else:
                logger.error(f"Failed to fetch models: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching available models: {e}")
            return []

    def get_model_info(self, model: str) -> Dict[str, Any]:
        """
        Get information about a specific model.
        
        Args:
            model: Model identifier
            
        Returns:
            Dict[str, Any]: Model information
        """
        model_info = {
            ModelType.MISTRAL_7B: {
                "name": "Mistral 7B Instruct",
                "context_length": 8192,
                "cost_per_token": 0.00001,
                "description": "Fast and efficient 7B parameter model"
            },
            ModelType.LLAMA_3_8B: {
                "name": "Llama 3 8B Instruct", 
                "context_length": 8192,
                "cost_per_token": 0.00001,
                "description": "Meta's Llama 3 8B parameter model"
            },
            ModelType.LLAMA_3_70B: {
                "name": "Llama 3 70B Instruct",
                "context_length": 8192, 
                "cost_per_token": 0.0001,
                "description": "Meta's large 70B parameter model"
            }
        }
        
        return model_info.get(model, {"name": model, "description": "Unknown model"})
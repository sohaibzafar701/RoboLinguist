"""
Unit tests for OpenRouter API client.

Tests API client functionality with mocked responses and error handling.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import httpx
from tenacity import RetryError

from services.openrouter_client import (
    OpenRouterClient, LLMResponse, ChatMessage, ModelType,
    OpenRouterError, RateLimitError, ModelUnavailableError
)
from config.config_manager import ConfigManager


class TestOpenRouterClient:
    """Test cases for OpenRouter client."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration manager."""
        config = MagicMock()
        config.get_llm_config.return_value = {
            'api_key': 'test-api-key',
            'base_url': 'https://openrouter.ai/api/v1',
            'default_model': ModelType.MISTRAL_7B,
            'fallback_model': ModelType.LLAMA_3_8B,
            'timeout': 30,
            'max_retries': 3,
            'temperature': 0.7,
            'max_tokens': 1000
        }
        return config

    @pytest.fixture
    def client(self, mock_config):
        """Create OpenRouter client with mocked config."""
        return OpenRouterClient(mock_config)

    @pytest.fixture
    def mock_success_response(self):
        """Mock successful API response."""
        return {
            "choices": [{
                "message": {
                    "content": "Hello! This is a test response from the robot command system."
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }

    def test_client_initialization(self, mock_config):
        """Test client initialization with config."""
        client = OpenRouterClient(mock_config)
        
        assert client.api_key == 'test-api-key'
        assert client.base_url == 'https://openrouter.ai/api/v1'
        assert client.default_model == ModelType.MISTRAL_7B
        assert client.fallback_model == ModelType.LLAMA_3_8B
        assert client.timeout == 30
        assert client.max_retries == 3

    def test_client_initialization_without_api_key(self, mock_config):
        """Test client initialization fails without API key."""
        mock_config.get_llm_config.return_value = {'api_key': None}
        
        with pytest.raises(ValueError, match="OpenRouter API key is required"):
            OpenRouterClient(mock_config)

    @pytest.mark.asyncio
    async def test_successful_api_request(self, client, mock_success_response):
        """Test successful API request."""
        with patch.object(client.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_success_response
            mock_post.return_value = mock_response

            messages = [{"role": "user", "content": "Hello"}]
            result = await client._make_request(ModelType.MISTRAL_7B, messages)

            assert result == mock_success_response
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, client):
        """Test rate limit error handling."""
        from tenacity import RetryError
        
        with patch.object(client.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_post.return_value = mock_response

            messages = [{"role": "user", "content": "Hello"}]
            
            with pytest.raises(RetryError):
                await client._make_request(ModelType.MISTRAL_7B, messages)

    @pytest.mark.asyncio
    async def test_model_unavailable_error(self, client):
        """Test model unavailable error handling."""
        with patch.object(client.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_post.return_value = mock_response

            messages = [{"role": "user", "content": "Hello"}]
            
            with pytest.raises(ModelUnavailableError):
                await client._make_request(ModelType.MISTRAL_7B, messages)

    @pytest.mark.asyncio
    async def test_http_error_handling(self, client):
        """Test HTTP error handling."""
        with patch.object(client.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_post.return_value = mock_response

            messages = [{"role": "user", "content": "Hello"}]
            
            with pytest.raises(OpenRouterError, match="API request failed with status 500"):
                await client._make_request(ModelType.MISTRAL_7B, messages)

    @pytest.mark.asyncio
    async def test_generate_response_success(self, client, mock_success_response):
        """Test successful response generation."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_success_response

            messages = [ChatMessage(role="user", content="Hello")]
            result = await client.generate_response(messages)

            assert isinstance(result, LLMResponse)
            assert result.success is True
            assert result.content == "Hello! This is a test response from the robot command system."
            assert result.model == ModelType.MISTRAL_7B
            assert result.usage == {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}
            assert result.response_time > 0

    @pytest.mark.asyncio
    async def test_generate_response_with_dict_messages(self, client, mock_success_response):
        """Test response generation with dictionary messages."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_success_response

            messages = [{"role": "user", "content": "Hello"}]
            result = await client.generate_response(messages)

            assert result.success is True
            assert result.content == "Hello! This is a test response from the robot command system."

    @pytest.mark.asyncio
    async def test_generate_response_with_fallback(self, client, mock_success_response):
        """Test response generation with fallback model."""
        with patch.object(client, '_make_request') as mock_request:
            # First call fails, second succeeds
            mock_request.side_effect = [
                ModelUnavailableError("Primary model unavailable"),
                mock_success_response
            ]

            messages = [ChatMessage(role="user", content="Hello")]
            result = await client.generate_response(messages)

            assert result.success is True
            assert result.model == ModelType.LLAMA_3_8B  # Fallback model
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_response_fallback_disabled(self, client):
        """Test response generation with fallback disabled."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = ModelUnavailableError("Model unavailable")

            messages = [ChatMessage(role="user", content="Hello")]
            result = await client.generate_response(messages, use_fallback=False)

            assert result.success is False
            assert result.error == "Model unavailable"
            assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_response_both_models_fail(self, client):
        """Test response generation when both primary and fallback models fail."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.side_effect = [
                ModelUnavailableError("Primary model unavailable"),
                OpenRouterError("Fallback model also failed")
            ]

            messages = [ChatMessage(role="user", content="Hello")]
            result = await client.generate_response(messages)

            assert result.success is False
            assert "Both primary and fallback models failed" in result.error
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_simple_response(self, client, mock_success_response):
        """Test simple response generation."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_success_response

            result = await client.generate_simple_response(
                "Hello", 
                system_message="You are a helpful robot assistant"
            )

            assert result.success is True
            assert result.content == "Hello! This is a test response from the robot command system."
            
            # Verify the request was made with correct messages
            call_args = mock_request.call_args[0]
            messages = call_args[1]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_simple_response_without_system_message(self, client, mock_success_response):
        """Test simple response generation without system message."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_success_response

            result = await client.generate_simple_response("Hello")

            assert result.success is True
            
            # Verify only user message was sent
            call_args = mock_request.call_args[0]
            messages = call_args[1]
            assert len(messages) == 1
            assert messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client):
        """Test successful connection test."""
        mock_response = LLMResponse(
            content="Connection successful",
            model=ModelType.MISTRAL_7B,
            usage={},
            response_time=0.5,
            success=True
        )
        
        with patch.object(client, 'generate_simple_response') as mock_generate:
            mock_generate.return_value = mock_response

            result = await client.test_connection()

            assert result is True
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client):
        """Test failed connection test."""
        mock_response = LLMResponse(
            content="",
            model=ModelType.MISTRAL_7B,
            usage={},
            response_time=0.5,
            success=False,
            error="Connection failed"
        )
        
        with patch.object(client, 'generate_simple_response') as mock_generate:
            mock_generate.return_value = mock_response

            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_list_available_models_success(self, client):
        """Test successful model listing."""
        mock_models = {
            "data": [
                {"id": "mistralai/mistral-7b-instruct", "name": "Mistral 7B"},
                {"id": "meta-llama/llama-3-8b-instruct", "name": "Llama 3 8B"}
            ]
        }
        
        with patch.object(client.client, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_models
            mock_get.return_value = mock_response

            result = await client.list_available_models()

            assert len(result) == 2
            assert result[0]["id"] == "mistralai/mistral-7b-instruct"

    @pytest.mark.asyncio
    async def test_list_available_models_failure(self, client):
        """Test failed model listing."""
        with patch.object(client.client, 'get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = await client.list_available_models()

            assert result == []

    def test_get_model_info(self, client):
        """Test getting model information."""
        info = client.get_model_info(ModelType.MISTRAL_7B)
        
        assert info["name"] == "Mistral 7B Instruct"
        assert info["context_length"] == 8192
        assert "description" in info

        # Test unknown model
        unknown_info = client.get_model_info("unknown/model")
        assert unknown_info["name"] == "unknown/model"
        assert unknown_info["description"] == "Unknown model"

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config):
        """Test async context manager functionality."""
        async with OpenRouterClient(mock_config) as client:
            assert isinstance(client, OpenRouterClient)
            assert client.client is not None

    @pytest.mark.asyncio
    async def test_close_client(self, client):
        """Test client cleanup."""
        with patch.object(client.client, 'aclose') as mock_close:
            await client.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_generation_parameters(self, client, mock_success_response):
        """Test custom generation parameters."""
        with patch.object(client, '_make_request') as mock_request:
            mock_request.return_value = mock_success_response

            messages = [ChatMessage(role="user", content="Hello")]
            await client.generate_response(
                messages, 
                temperature=0.9, 
                max_tokens=500,
                top_p=0.95
            )

            # Verify custom parameters were passed
            call_args = mock_request.call_args
            assert call_args[1]['temperature'] == 0.9
            assert call_args[1]['max_tokens'] == 500
            assert call_args[1]['top_p'] == 0.95

    @pytest.mark.asyncio
    async def test_json_decode_error(self, client):
        """Test JSON decode error handling."""
        with patch.object(client.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_post.return_value = mock_response

            messages = [{"role": "user", "content": "Hello"}]
            
            with pytest.raises(OpenRouterError, match="Invalid JSON response"):
                await client._make_request(ModelType.MISTRAL_7B, messages)

    @pytest.mark.asyncio
    async def test_http_request_error(self, client):
        """Test HTTP request error handling."""
        from tenacity import RetryError
        
        with patch.object(client.client, 'post') as mock_post:
            mock_post.side_effect = httpx.RequestError("Connection failed")

            messages = [{"role": "user", "content": "Hello"}]
            
            with pytest.raises(RetryError):
                await client._make_request(ModelType.MISTRAL_7B, messages)
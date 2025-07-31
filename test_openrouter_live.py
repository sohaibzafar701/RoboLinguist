"""
Live test script for OpenRouter API client.

Tests the actual API connection and model responses.
"""

import asyncio
import logging
from services.openrouter_client import OpenRouterClient, ChatMessage, ModelType
from config.config_manager import ConfigManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_openrouter_connection():
    """Test OpenRouter API connection and basic functionality."""
    
    try:
        # Initialize client
        config = ConfigManager()
        config.load_config()  # Load the configuration
        
        async with OpenRouterClient(config) as client:
            logger.info("Testing OpenRouter API connection...")
            
            # Test 1: Basic connection test
            logger.info("1. Testing basic connection...")
            connection_ok = await client.test_connection()
            if connection_ok:
                logger.info("✅ Connection test passed")
            else:
                logger.error("❌ Connection test failed")
                return False
            
            # Test 2: Simple response generation
            logger.info("2. Testing simple response generation...")
            response = await client.generate_simple_response(
                "Hello! Please respond with a brief greeting.",
                system_message="You are a helpful robot assistant.",
                max_tokens=50
            )
            
            if response.success:
                logger.info(f"✅ Simple response: {response.content}")
                logger.info(f"   Model: {response.model}")
                logger.info(f"   Response time: {response.response_time:.2f}s")
                logger.info(f"   Usage: {response.usage}")
            else:
                logger.error(f"❌ Simple response failed: {response.error}")
                return False
            
            # Test 3: Robot command translation test
            logger.info("3. Testing robot command translation...")
            robot_prompt = """
            Convert this natural language command to a structured robot command:
            "Move the robot to position x=2.5, y=1.0 and then pick up the red box"
            
            Respond with a JSON structure containing the robot commands.
            """
            
            command_response = await client.generate_simple_response(
                robot_prompt,
                system_message="You are a robot command translator. Convert natural language to structured robot commands.",
                max_tokens=200
            )
            
            if command_response.success:
                logger.info(f"✅ Command translation: {command_response.content}")
                logger.info(f"   Model: {command_response.model}")
                logger.info(f"   Response time: {command_response.response_time:.2f}s")
            else:
                logger.error(f"❌ Command translation failed: {command_response.error}")
                return False
            
            # Test 4: Test with conversation context
            logger.info("4. Testing conversation context...")
            messages = [
                ChatMessage(role="system", content="You are a helpful robot assistant."),
                ChatMessage(role="user", content="What can you help me with?"),
                ChatMessage(role="assistant", content="I can help you control robots and translate commands."),
                ChatMessage(role="user", content="Great! Can you move a robot forward?")
            ]
            
            context_response = await client.generate_response(messages, max_tokens=100)
            
            if context_response.success:
                logger.info(f"✅ Context response: {context_response.content}")
                logger.info(f"   Model: {context_response.model}")
            else:
                logger.error(f"❌ Context response failed: {context_response.error}")
                return False
            
            # Test 5: Test fallback mechanism
            logger.info("5. Testing fallback mechanism...")
            try:
                fallback_response = await client.generate_simple_response(
                    "This is a fallback test",
                    model="nonexistent/model"  # This should trigger fallback
                )
                
                if fallback_response.success:
                    logger.info(f"✅ Fallback worked: {fallback_response.model}")
                else:
                    logger.info(f"⚠️  Fallback failed (expected): {fallback_response.error}")
            except Exception as e:
                logger.info(f"⚠️  Fallback test exception (may be expected): {e}")
            
            # Test 6: List available models
            logger.info("6. Testing model listing...")
            models = await client.list_available_models()
            if models:
                logger.info(f"✅ Found {len(models)} available models")
                for model in models[:3]:  # Show first 3 models
                    logger.info(f"   - {model.get('id', 'Unknown')}")
            else:
                logger.info("⚠️  No models returned (may be API limitation)")
            
            # Test 7: Model information
            logger.info("7. Testing model information...")
            model_info = client.get_model_info(ModelType.MISTRAL_7B)
            logger.info(f"✅ Model info: {model_info}")
            
            logger.info("🎉 All tests completed successfully!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        return False


async def test_different_models():
    """Test different available models."""
    
    config = ConfigManager()
    config.load_config()  # Load the configuration
    
    async with OpenRouterClient(config) as client:
        models_to_test = [
            ModelType.MISTRAL_7B,
            ModelType.LLAMA_3_8B,
        ]
        
        prompt = "Hello! Please respond with just 'Hello from [model name]'"
        
        for model in models_to_test:
            logger.info(f"Testing model: {model}")
            
            response = await client.generate_simple_response(
                prompt,
                model=model,
                max_tokens=20
            )
            
            if response.success:
                logger.info(f"✅ {model}: {response.content}")
                logger.info(f"   Response time: {response.response_time:.2f}s")
            else:
                logger.error(f"❌ {model} failed: {response.error}")


if __name__ == "__main__":
    print("🤖 Testing OpenRouter API Client")
    print("=" * 50)
    
    # Run basic tests
    success = asyncio.run(test_openrouter_connection())
    
    if success:
        print("\n🔄 Testing different models...")
        print("=" * 50)
        asyncio.run(test_different_models())
        
        print("\n✅ All tests completed!")
    else:
        print("\n❌ Basic tests failed. Check your API key and configuration.")
"""
Live test script for command translator.

Tests the command translation system with real API calls.
"""

import asyncio
import logging
from services.command_translator import CommandTranslator
from config.config_manager import ConfigManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_command_translation():
    """Test command translation with various instruction types."""
    
    config = ConfigManager()
    config.load_config()
    
    async with CommandTranslator(config) as translator:
        
        # Test cases with different instruction types
        test_instructions = [
            # Navigation instructions
            "Move the robot to position x=2.5, y=1.0",
            "Navigate to the kitchen area",
            "Go to coordinates 3, 4 with maximum speed of 1.5 m/s",
            
            # Manipulation instructions
            "Pick up the red box from the table",
            "Place the object on the shelf carefully",
            "Grab the tool and put it in the toolbox",
            
            # Inspection instructions
            "Inspect the temperature sensor on the wall",
            "Check the conveyor belt for any issues",
            "Examine the machinery and report status",
            
            # Complex instructions
            "Move to the table, pick up the blue box, and bring it to the storage area",
            "Go to the sensor, inspect it, then return to the starting position",
            "Navigate to position 1,2 then grab the wrench and check if it's working properly"
        ]
        
        print("🤖 Testing Command Translation System")
        print("=" * 60)
        
        for i, instruction in enumerate(test_instructions, 1):
            print(f"\n{i}. Testing: '{instruction}'")
            print("-" * 50)
            
            try:
                result = await translator.translate_command(instruction, robot_id="test_robot")
                
                if result.success:
                    print(f"✅ Translation successful!")
                    print(f"   Confidence: {result.confidence:.2f}")
                    print(f"   Processing time: {result.processing_time:.2f}s")
                    print(f"   Generated {len(result.commands)} command(s):")
                    
                    for j, cmd in enumerate(result.commands, 1):
                        print(f"     {j}. {cmd.action_type.upper()}")
                        print(f"        ID: {cmd.command_id}")
                        print(f"        Priority: {cmd.priority}")
                        print(f"        Parameters: {cmd.parameters}")
                        
                        # Validate command
                        try:
                            translator.validator.validate_command_structure(cmd)
                            safety_violations = translator.validator.validate_safety_constraints(cmd)
                            if safety_violations:
                                print(f"        ⚠️  Safety warnings: {safety_violations}")
                            else:
                                print(f"        ✅ Command is safe and valid")
                        except Exception as e:
                            print(f"        ❌ Validation error: {e}")
                    
                    if result.raw_llm_response:
                        print(f"   Raw LLM response: {result.raw_llm_response[:100]}...")
                        
                else:
                    print(f"❌ Translation failed: {result.error}")
                    if result.raw_llm_response:
                        print(f"   Raw response: {result.raw_llm_response}")
                        
            except Exception as e:
                print(f"❌ Exception during translation: {e}")
                
        print("\n" + "=" * 60)
        print("🎉 Command translation tests completed!")


async def test_batch_translation():
    """Test batch translation functionality."""
    
    config = ConfigManager()
    config.load_config()
    
    async with CommandTranslator(config) as translator:
        
        print("\n🔄 Testing Batch Translation")
        print("=" * 40)
        
        batch_instructions = [
            "Move to the starting position",
            "Pick up the first item",
            "Carry it to the destination",
            "Place it down gently",
            "Return to base"
        ]
        
        print("Batch instructions:")
        for i, instruction in enumerate(batch_instructions, 1):
            print(f"  {i}. {instruction}")
        
        print("\nProcessing batch...")
        
        try:
            results = await translator.translate_batch(batch_instructions, robot_id="batch_robot")
            
            print(f"\n✅ Batch processing completed!")
            print(f"   Processed {len(results)} instructions")
            
            successful = sum(1 for r in results if r.success)
            print(f"   Success rate: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
            
            total_commands = sum(len(r.commands) for r in results)
            print(f"   Total commands generated: {total_commands}")
            
            avg_confidence = sum(r.confidence for r in results if r.success) / max(successful, 1)
            print(f"   Average confidence: {avg_confidence:.2f}")
            
            for i, result in enumerate(results, 1):
                if result.success:
                    print(f"   {i}. ✅ {len(result.commands)} commands (confidence: {result.confidence:.2f})")
                else:
                    print(f"   {i}. ❌ Failed: {result.error}")
                    
        except Exception as e:
            print(f"❌ Batch translation failed: {e}")


async def test_validation_system():
    """Test the validation system."""
    
    config = ConfigManager()
    config.load_config()
    
    async with CommandTranslator(config) as translator:
        
        print("\n🔍 Testing Validation System")
        print("=" * 40)
        
        # Test with a complex instruction
        instruction = "Move to position 5,10 then pick up the heavy box and inspect it carefully"
        
        print(f"Testing validation for: '{instruction}'")
        
        try:
            # First, get initial translation
            result = await translator.translate_command(instruction)
            
            if result.success:
                print(f"✅ Initial translation: {len(result.commands)} commands")
                print(f"   Initial confidence: {result.confidence:.2f}")
                
                # Now validate the translation
                print("\nRunning validation...")
                validated_result = await translator.validate_translation(instruction, result.commands)
                
                if validated_result.success:
                    print(f"✅ Validation successful!")
                    print(f"   Validated confidence: {validated_result.confidence:.2f}")
                    print(f"   Commands after validation: {len(validated_result.commands)}")
                    
                    # Compare original vs validated
                    if len(result.commands) != len(validated_result.commands):
                        print(f"   ⚠️  Command count changed: {len(result.commands)} → {len(validated_result.commands)}")
                    
                    confidence_change = validated_result.confidence - result.confidence
                    if confidence_change > 0:
                        print(f"   📈 Confidence improved by {confidence_change:.2f}")
                    elif confidence_change < 0:
                        print(f"   📉 Confidence decreased by {abs(confidence_change):.2f}")
                    else:
                        print(f"   ➡️  Confidence unchanged")
                        
                else:
                    print(f"❌ Validation failed: {validated_result.error}")
                    
            else:
                print(f"❌ Initial translation failed: {result.error}")
                
        except Exception as e:
            print(f"❌ Validation test failed: {e}")


async def test_instruction_classification():
    """Test instruction classification."""
    
    config = ConfigManager()
    config.load_config()
    
    translator = CommandTranslator(config)
    
    print("\n🏷️  Testing Instruction Classification")
    print("=" * 45)
    
    test_cases = [
        ("Move to position 2, 3", "navigation"),
        ("Pick up the red box", "manipulation"),
        ("Inspect the sensor", "inspection"),
        ("Go to the table and grab the tool", "complex"),
        ("Navigate to the kitchen", "navigation"),
        ("Place the object carefully", "manipulation"),
        ("Check the temperature", "inspection"),
        ("Move forward then turn left and pick up the item", "complex")
    ]
    
    correct = 0
    for instruction, expected in test_cases:
        actual = translator._classify_instruction(instruction)
        status = "✅" if actual == expected else "❌"
        print(f"{status} '{instruction}' → {actual} (expected: {expected})")
        if actual == expected:
            correct += 1
    
    accuracy = correct / len(test_cases) * 100
    print(f"\nClassification accuracy: {correct}/{len(test_cases)} ({accuracy:.1f}%)")


if __name__ == "__main__":
    print("🤖 Testing Command Translation System")
    print("=" * 50)
    
    # Run all tests
    asyncio.run(test_command_translation())
    asyncio.run(test_batch_translation())
    asyncio.run(test_validation_system())
    asyncio.run(test_instruction_classification())
    
    print("\n✅ All command translation tests completed!")
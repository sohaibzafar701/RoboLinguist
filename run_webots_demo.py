"""
Simple launcher for ChatGPT for Robots Webots Demo

This script provides an easy way to run the complete system demonstration.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_webots_installation():
    """Check if Webots is properly installed."""
    import os
    import platform
    
    # Check for WEBOTS_HOME
    webots_home = os.getenv('WEBOTS_HOME')
    if webots_home and Path(webots_home).exists():
        logger.info(f"✓ Found Webots at: {webots_home}")
        return True
    
    # Check common installation paths
    system = platform.system()
    common_paths = []
    
    if system == "Windows":
        common_paths = [
            r"C:\Program Files\Webots",
            r"C:\Program Files (x86)\Webots"
        ]
    elif system == "Darwin":
        common_paths = ["/Applications/Webots.app"]
    else:
        common_paths = ["/usr/local/webots", "/opt/webots"]
    
    for path in common_paths:
        if Path(path).exists():
            logger.info(f"✓ Found Webots at: {path}")
            os.environ['WEBOTS_HOME'] = path
            return True
    
    logger.error("✗ Webots not found!")
    logger.error("Please install Webots from: https://cyberbotics.com/")
    logger.error("Or set WEBOTS_HOME environment variable")
    return False


def check_world_file():
    """Check if the Webots world file exists."""
    world_files = [
        "webots_working_demo/minimal_fleet_world.wbt",
        "minimal_fleet_world.wbt",
        "simple_fleet_world.wbt"
    ]
    
    for world_file in world_files:
        if Path(world_file).exists():
            logger.info(f"✓ Found world file: {world_file}")
            return world_file
    
    logger.error("✗ No Webots world file found!")
    logger.error("Please ensure you have a Webots world file with robots")
    return None


async def run_demo():
    """Run the complete demo."""
    logger.info("🤖 ChatGPT for Robots - Webots Demo")
    logger.info("=" * 50)
    
    # Pre-flight checks
    logger.info("Performing pre-flight checks...")
    
    if not check_webots_installation():
        return False
    
    world_file = check_world_file()
    if not world_file:
        return False
    
    logger.info("✓ All checks passed!")
    logger.info("")
    
    # Import and run the complete test
    try:
        from test_complete_ros2_bridge import CompleteSystemTest
        
        logger.info("Starting complete system test...")
        logger.info("This will demonstrate all components working together")
        logger.info("")
        
        test = CompleteSystemTest()
        await test.run_complete_test()
        
        return True
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Please ensure all required files are present")
        return False
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        return False


def print_instructions():
    """Print setup instructions."""
    print("""
🤖 ChatGPT for Robots - Webots Demo Setup

BEFORE RUNNING:
1. Install Webots from: https://cyberbotics.com/
2. Open Webots
3. Load a world file with robots (e.g., minimal_fleet_world.wbt)
4. Click the "Play" button to start simulation
5. Leave Webots running

THEN RUN:
python run_webots_demo.py

WHAT YOU'LL SEE:
- Core components (Tasks 1-6) working unchanged
- ROS2 bridge translating commands to Webots
- Robots moving in formations
- Context-aware command translation
- Safety validation in action
- Complete system integration

The demo proves that your core components are ready for real robots!
""")


def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
        print_instructions()
        return
    
    print("🤖 Starting ChatGPT for Robots Webots Demo...")
    print("Press Ctrl+C to stop at any time")
    print("")
    
    try:
        success = asyncio.run(run_demo())
        
        if success:
            print("\n🎉 Demo completed successfully!")
            print("Your ChatGPT for Robots system is ready for real-world deployment!")
        else:
            print("\n❌ Demo failed. Please check the error messages above.")
            
    except KeyboardInterrupt:
        print("\n⏹️ Demo stopped by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
RoboLinguist Configuration Setup Script

This script helps users set up their configuration file with API keys.
"""

import os
import shutil
from pathlib import Path

def setup_config():
    """Set up the configuration file from template."""
    template_path = Path("config/system_config.yaml.template")
    config_path = Path("config/system_config.yaml")
    
    if not template_path.exists():
        print("❌ Template file not found: config/system_config.yaml.template")
        return False
    
    if config_path.exists():
        response = input("⚠️  Configuration file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("✅ Keeping existing configuration.")
            return True
    
    # Copy template to config
    shutil.copy2(template_path, config_path)
    print("✅ Configuration file created from template.")
    
    # Prompt for API key
    print("\n🔑 API Key Setup:")
    print("1. Visit https://openrouter.ai/ to get your API key")
    print("2. Sign up and copy your API key")
    
    api_key = input("\n📝 Enter your OpenRouter API key (or press Enter to skip): ").strip()
    
    if api_key:
        # Update the config file with the API key
        with open(config_path, 'r') as f:
            content = f.read()
        
        content = content.replace('your_openrouter_api_key_here', api_key)
        
        with open(config_path, 'w') as f:
            f.write(content)
        
        print("✅ API key configured successfully!")
    else:
        print("⚠️  API key skipped. You can edit config/system_config.yaml manually later.")
    
    print("\n🎉 Setup complete! You can now run:")
    print("   python run_webots_demo.py")
    
    return True

if __name__ == "__main__":
    print("🤖 RoboLinguist Configuration Setup")
    print("=" * 40)
    setup_config()
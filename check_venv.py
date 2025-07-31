#!/usr/bin/env python3
"""
Script to verify that we're running in the correct virtual environment.
"""

import sys
import os
from pathlib import Path

def check_virtual_environment():
    """Check if we're running in the project's virtual environment."""
    print("🔍 Checking virtual environment setup...")
    
    # Check if we're in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if not in_venv:
        print("❌ Not running in a virtual environment!")
        print("Please activate the virtual environment first:")
        print("  Windows: venv\\Scripts\\activate")
        print("  Or use: activate_venv.bat")
        return False
    
    # Check if it's our project's virtual environment
    venv_path = Path(sys.prefix)
    project_venv = Path.cwd() / "venv"
    
    try:
        if venv_path.resolve() == project_venv.resolve():
            print("✅ Running in project's virtual environment")
            print(f"   Virtual env path: {venv_path}")
            print(f"   Python executable: {sys.executable}")
            return True
        else:
            print("⚠️  Running in a different virtual environment")
            print(f"   Current venv: {venv_path}")
            print(f"   Expected venv: {project_venv}")
            return False
    except Exception as e:
        print(f"⚠️  Could not verify virtual environment: {e}")
        print(f"   Current Python: {sys.executable}")
        return True  # Assume it's okay if we can't verify
    
def check_dependencies():
    """Check if key dependencies are installed."""
    print("\n📦 Checking key dependencies...")
    
    required_packages = [
        'pydantic',
        'yaml',
        'flask',
        'httpx'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NOT INSTALLED")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Please install dependencies: pip install -r requirements.txt")
        return False
    
    print("✅ All key dependencies are installed")
    return True

def main():
    """Main function to run all checks."""
    print("🤖 ChatGPT for Robots - Environment Check")
    print("=" * 50)
    
    venv_ok = check_virtual_environment()
    deps_ok = check_dependencies()
    
    print("\n" + "=" * 50)
    if venv_ok and deps_ok:
        print("🎉 Environment setup is correct!")
        print("You're ready to work on the project.")
    else:
        print("⚠️  Environment setup needs attention.")
        print("Please fix the issues above before continuing.")
    
    return venv_ok and deps_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
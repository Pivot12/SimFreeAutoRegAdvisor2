import os
import sys
import subprocess
import shutil
from pathlib import Path
import argparse

def check_python_version():
    """Check if Python version is 3.8+"""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✓ Python version {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} detected")

def setup_virtual_env(env_name="venv", upgrade_pip=True):
    """Set up a virtual environment"""
    if os.path.exists(env_name):
        print(f"Virtual environment '{env_name}' already exists")
        return env_name
    
    try:
        subprocess.run([sys.executable, "-m", "venv", env_name], check=True)
        print(f"✓ Created virtual environment: {env_name}")
        
        # Determine path to pip in the virtual environment
        if os.name == "nt":  # Windows
            pip_path = os.path.join(env_name, "Scripts", "pip")
        else:  # Unix/Linux/Mac
            pip_path = os.path.join(env_name, "bin", "pip")
        
        # Upgrade pip if requested
        if upgrade_pip:
            subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)
            print("✓ Upgraded pip")
        
        return env_name
    except subprocess.CalledProcessError as e:
        print(f"Error setting up virtual environment: {e}")
        sys.exit(1)

def install_requirements(venv_name="venv"):
    """Install requirements in the virtual environment"""
    requirements_file = "requirements.txt"
    
    if not os.path.exists(requirements_file):
        print(f"Error: {requirements_file} not found")
        sys.exit(1)
    
    try:
        # Determine path to pip in the virtual environment
        if os.name == "nt":  # Windows
            pip_path = os.path.join(venv_name, "Scripts", "pip")
        else:  # Unix/Linux/Mac
            pip_path = os.path.join(venv_name, "bin", "pip")
        
        subprocess.run([pip_path, "install", "-r", requirements_file], check=True)
        print(f"✓ Installed requirements from {requirements_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error installing requirements: {e}")
        sys.exit(1)

def create_env_file():
    """Create .env file from template if it doesn't exist"""
    env_file = ".env"
    env_template = ".env.template"
    
    if os.path.exists(env_file):
        print(f"{env_file} already exists")
        return
    
    if not os.path.exists(env_template):
        print(f"Warning: {env_template} not found, creating default {env_file}")
        with open(env_file, "w") as f:
            f.write("# API Keys\n")
            f.write("FIRECRAWL_API_KEY=your_firecrawl_api_key_here\n")
            f.write("CEREBRAS_API_KEY=your_cerebras_api_key_here\n")
            f.write("\n# Logging Configuration\n")
            f.write("LOG_LEVEL=INFO\n")
        print(f"✓ Created default {env_file}")
        return
    
    shutil.copy(env_template, env_file)
    print(f"✓ Created {env_file} from template")

def setup_streamlit_secrets():
    """Set up Streamlit secrets directory and file if they don't exist"""
    streamlit_dir = ".streamlit"
    secrets_file = os.path.join(streamlit_dir, "secrets.toml")
    secrets_template = os.path.join(streamlit_dir, "secrets.toml.example")
    
    if not os.path.exists(streamlit_dir):
        os.makedirs(streamlit_dir)
        print(f"✓ Created {streamlit_dir} directory")
    
    if os.path.exists(secrets_file):
        print(f"{secrets_file} already exists")
        return
    
    if os.path.exists(secrets_template):
        shutil.copy(secrets_template, secrets_file)
        print(f"✓ Created {secrets_file} from template")
    else:
        # Create default secrets file
        os.makedirs(os.path.dirname(secrets_file), exist_ok=True)
        with open(secrets_file, "w") as f:
            f.write("# API Keys\n")
            f.write("firecrawl_api_key = \"your_firecrawl_api_key_here\"\n")
            f.write("cerebras_api_key = \"your_cerebras_api_key_here\"\n")
        print(f"✓ Created default {secrets_file}")

def create_data_directory():
    """Create data directory if it doesn't exist"""
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        # Create empty __init__.py
        with open(os.path.join(data_dir, "__init__.py"), "w") as f:
            f.write("# This file is intentionally empty to make the 'data' directory a Python package\n")
        print(f"✓ Created {data_dir} directory")
    else:
        print(f"{data_dir} directory already exists")

def run_tests():
    """Run tests to verify setup"""
    try:
        print("Running tests...")
        # Use unittest discover to find and run all tests
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ All tests passed")
            return True
        else:
            print(f"Some tests failed:\n{result.stdout}\n{result.stderr}")
            return False
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Setup script for SimFreeAutoRegAdvisor2")
    parser.add_argument("--venv", default="venv", help="Name of the virtual environment")
    parser.add_argument("--no-pip-upgrade", action="store_false", dest="upgrade_pip", help="Skip upgrading pip")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    args = parser.parse_args()
    
    print("Setting up SimFreeAutoRegAdvisor2...")
    
    # Step 1: Check Python version
    check_python_version()
    
    # Step 2: Set up virtual environment
    venv_name = setup_virtual_env(args.venv, args.upgrade_pip)
    
    # Step 3: Install requirements
    install_requirements(venv_name)
    
    # Step 4: Create .env file
    create_env_file()
    
    # Step 5: Set up Streamlit secrets
    setup_streamlit_secrets()
    
    # Step 6: Create data directory
    create_data_directory()
    
    # Step 7: Run tests if not skipped
    if not args.skip_tests:
        tests_passed = run_tests()
        if not tests_passed:
            print("Warning: Some tests failed. The application may not work correctly.")
    
    print("\nSetup complete! To run the application:")
    if os.name == "nt":  # Windows
        print(f"1. Activate the virtual environment: {venv_name}\\Scripts\\activate")
    else:  # Unix/Linux/Mac
        print(f"1. Activate the virtual environment: source {venv_name}/bin/activate")
    print("2. Start the application: streamlit run app.py")
    print("\nNote: Make sure to update your API keys in .env or .streamlit/secrets.toml before running the application.")

if __name__ == "__main__":
    main()

"""
File: setup_directories.py
Version: 1.0.0
Created: 2025-03-02
Description: Script to set up the directory structure for the refactored application
"""

import os
import sys

def setup_directories():
    """Create the necessary directory structure for the refactored application."""
    # Get the current directory (should be project root)
    base_dir = os.getcwd()
    
    # Define directories to create
    directories = [
        os.path.join(base_dir, 'app', 'utils'),
        os.path.join(base_dir, 'app', 'services'),
        os.path.join(base_dir, 'app', 'forms'),
        os.path.join(base_dir, 'tests', 'unit'),
        os.path.join(base_dir, 'tests', 'integration'),
    ]
    
    # Create directories if they don't exist
    for directory in directories:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                print(f"Created directory: {directory}")
            except Exception as e:
                print(f"Error creating directory {directory}: {str(e)}")
    
    # Create __init__.py files to make the directories packages
    for directory in directories:
        init_file = os.path.join(directory, '__init__.py')
        if not os.path.exists(init_file):
            try:
                with open(init_file, 'w') as f:
                    f.write('"""Package initialization file."""\n')
                print(f"Created: {init_file}")
            except Exception as e:
                print(f"Error creating {init_file}: {str(e)}")

if __name__ == '__main__':
    setup_directories()
    print("Directory setup complete!")
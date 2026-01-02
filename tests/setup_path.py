"""Common path setup for all tests."""

import sys
import os

def setup_test_paths():
    """Add necessary directories to Python path for imports."""
    # Get directory paths
    setup_file = os.path.abspath(__file__)
    tests_dir = os.path.dirname(setup_file)
    project_dir = os.path.dirname(tests_dir)
    backend_dir = os.path.join(project_dir, 'backend')
    
    # Add to path if not already there
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    
    return tests_dir, project_dir, backend_dir
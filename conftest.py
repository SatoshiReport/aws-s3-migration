"""Pytest configuration to ensure project root is in sys.path for all test workers."""

import sys
from pathlib import Path

# Add project root to sys.path so workers can import local modules
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

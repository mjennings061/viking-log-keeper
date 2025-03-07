"""conftest.py - Configuration for pytest."""

import sys
from pathlib import Path

# Add the src directory to the Python path
src_dir = str(Path(__file__).parent.parent / "src")
sys.path.append(src_dir)

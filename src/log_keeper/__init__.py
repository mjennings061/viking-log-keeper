"""
log_keeper package.
"""

# Standard library imports.
import sys
import logging
from pathlib import Path

# Adjust PYTHONPATH to include the src directory.
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Set up package-wide logging.
log_format = "%(filename)s %(levelname)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

"""
dashboard package.
"""

# Standard library imports.
import os
import sys
import logging

# Ensure the src directory is in the sys.path.
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if src_path not in sys.path:
    sys.path.append(src_path)

# Set up package-wide logging.
log_format = "%(asctime)s %(filename)s %(levelname)s: %(message)s"
date_format = "%y-%m-%d %H:%M:%S"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt=date_format,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("dashboard")
logger.setLevel(logging.DEBUG)

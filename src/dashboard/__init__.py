"""
dashboard package.
"""

# Standard library imports.
import sys
import logging

# Set up package-wide logging.
log_format = "%(filename)s %(levelname)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

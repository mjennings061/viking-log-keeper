"""
dashboard package.
"""

# Standard library imports.
import sys
import logging

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

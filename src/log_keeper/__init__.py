"""
log_keeper package.
"""

import sys
import logging
from pathlib import Path

# Adjust PYTHONPATH to include the src directory.
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Get package-wide modules.
from .get_config import LogSheetConfig  # noqa
from .ingest import collate_log_sheets  # noqa
from .output import launches_to_excel, launches_to_db   # noqa
from .utils import PROJECT_NAME  # noqa

# Set up package-wide logging.
log_format = "%(filename)s %(levelname)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

__all__ = [
    "LogSheetConfig",
    "collate_log_sheets",
    "launches_to_excel",
    "launches_to_db",
    "PROJECT_NAME",
]

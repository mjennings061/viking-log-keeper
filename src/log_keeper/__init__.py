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

from .get_config import LogSheetConfig  # noqa
from .ingest import collate_log_sheets  # noqa
from .output import launches_to_excel, launches_to_db   # noqa
from .utils import PROJECT_NAME  # noqa

# Set up package-wide logging.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

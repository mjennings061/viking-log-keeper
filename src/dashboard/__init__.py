"""
dashboard package.
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
from .utils import is_streamlit_running  # noqa
from .auth import AuthConfig  # noqa
from .plots import (    # noqa
    plot_launches_by_commander,
    plot_all_launches,
    quarterly_summary,
    show_logbook_helper,
)

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
    "is_streamlit_running",
    "AuthConfig",
    "plot_launches_by_commander",
    "plot_all_launches",
    "quarterly_summary",
    "show_logbook_helper",
]

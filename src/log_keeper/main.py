"""main.py
661 VGS - Collate all log sheets (2965D) into one master log DB.
"""

# Get packages.
import sys
import logging
from pathlib import Path

# Get modules.
sys.path.append(str(Path(__file__).resolve().parents[1]))
from log_keeper.get_config import LogSheetConfig    # noqa: E402
from log_keeper.ingest import collate_log_sheets    # noqa: E402
from log_keeper.output import launches_to_excel, launches_to_db   # noqa: E402
from log_keeper.utils import adjust_streamlit_logging  # noqa: E402
from dashboard.auth import authenticate_log_sheet_db  # noqa: E402

# Get the logger instance.
logger = logging.getLogger(__name__)


def update_logs(db_config: LogSheetConfig):
    """Collate log sheets and update the master log."""
    # Output file path.
    log_sheets_dir = Path(db_config.fetch_log_sheet_dir())

    # Create a dataframe of all log sheets.
    launches_df = collate_log_sheets(log_sheets_dir)

    # Master log file path.
    master_log_filepath = Path(
        log_sheets_dir,
        "Master Log.xlsx"
    )

    # Save the launches to excel.
    try:
        launches_to_excel(launches_df, master_log_filepath)
    except Exception:  # pylint: disable=broad-except
        logger.warning("Could not save Master Log excel file.")

    # Save the master log to MongoDB Atlas.
    try:
        launches_to_db(launches_df, db_config)
    except Exception as e:  # pylint: disable=broad-except
        # Filter a ConnectionError.
        if isinstance(e, ConnectionError):
            logger.error(exc_info=True)
        else:
            # Remove the config file and try again.
            logger.error("Could not save to DB. " +
                         "Try changing the config.")


def update_logs_wrapper():
    """
    This function is the entry point of the program.
    It performs the following steps:
    1. Loads DB and directory path config.
    2. Collates all log sheets into a dataframe.
    3. Saves the launches to an Excel file.
    4. Saves the master log to MongoDB Atlas.
    """
    # Initial comment.
    logger.info("Starting...")
    adjust_streamlit_logging()

    # Authenticate with the DB.
    db_config = authenticate_log_sheet_db()
    if db_config is None:
        raise ValueError("Could not authenticate with the DB.")

    # Collate log sheets and update the master log.
    update_logs(db_config)

    # Print success message.
    logger.info("Success!")
    print("Success. You can close the terminal.")


if __name__ == "__main__":
    # Run the log keeper.
    update_logs_wrapper()

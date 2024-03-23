"""main.py
661 VGS - Collate all log sheets (2965D) into one master log DB.
"""

# Get packages.
import logging
from pathlib import Path

# Get modules.
from log_keeper.get_config import Config
from log_keeper.ingest import collate_log_sheets
from log_keeper.output import launches_to_excel, launches_to_db

# Set logging level.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
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

    # Load config.
    db_config = Config()
    if not db_config.validate():
        # Get the credentials from the user.
        db_config.update_credentials()

    # Output file path.
    log_sheets_dir = Path(db_config.log_sheets_dir)

    # Create a dataframe of all log sheets.
    launches_df = collate_log_sheets(log_sheets_dir)

    # Master log file path.
    master_log_filepath = Path(
        log_sheets_dir,
        "Master Log.xlsx"
    )

    # Save the launches to excel.
    launches_to_excel(launches_df, master_log_filepath)

    # Save the master log to MongoDB Atlas.
    try:
        launches_to_db(launches_df, db_config)
    except Exception as e:  # pylint: disable=broad-except
        # Filter a ConnectionError.
        if isinstance(e, ConnectionError):
            logger.error(exc_info=True)
        else:
            # Remove the config file and try again.
            logger.warning("Could not save to DB. " +
                           "Try changing the config.",
                           exc_info=True)
            db_config.update_credentials()
            launches_to_db(launches_df, db_config)

    # Print success message.
    logger.info("Success!")
    print("Success. You can close the terminal.")


if __name__ == "__main__":
    # Run the log keeper.
    main()

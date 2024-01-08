"""main.py
661 VGS - Collate all log sheets (2965D) into one master log DB.
"""

# Get packages.
import logging
from pathlib import Path
from cryptography.fernet import InvalidToken

# Get modules.
from log_keeper.get_config import get_config, update_config
from log_keeper.ingest import collate_log_sheets
from log_keeper.output import launches_to_excel, launches_to_db
from log_keeper.utils import PROJECT_NAME

# Set logging level.
logging.basicConfig(level=logging.INFO)


def get_valid_config():
    """Get a valid config file."""
    # Valid flag.
    is_valid = True

    # Get the config filepath, or use the CLI interface to create one.
    logging.info(f"{PROJECT_NAME}: Loading config...")
    try:
        # Load the config file.
        db_config = get_config()

        # Validate loaded config.
        # Get the log sheets directory path.
        log_sheets_dir = Path()
        if "LOG_SHEETS_DIR" not in db_config:
            # No field in config file.
            logging.warning(f"{PROJECT_NAME}: LOG_SHEETS_DIR not in config.")
            is_valid = False
        else:
            # Get the log sheets directory path from the config.
            log_sheets_dir = Path(db_config["LOG_SHEETS_DIR"])

            # Verify the log sheets directory path.
            if not log_sheets_dir.is_dir():
                logging.warning(f"{PROJECT_NAME}: Log sheets directory not" +
                                f"found at \n{log_sheets_dir}.")
                is_valid = False

    # A Fernet cryptography error is raised if an existing config is invalid.
    except Exception as e:
        logging.warning(f"{PROJECT_NAME}: Invalid config file.")
        is_valid = False
        if isinstance(e, InvalidToken):
            # Create a new config file.
            logging.warning(f"{PROJECT_NAME}: Invalid secret token.")
        else:
            # Raise the error.
            logging.exception(e)

    # Update invalid config.
    if not is_valid:
        db_config = update_config()

    return db_config


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
    logging.info(f"{PROJECT_NAME}: Starting...")

    # Load config.
    db_config = get_valid_config()

    # Output file path.
    log_sheets_dir = Path(db_config["LOG_SHEETS_DIR"])

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
    except Exception as e:
        # Filter a ConnectionError.
        if isinstance(e, ConnectionError):
            logging.warning(e)
        else:
            # Remove the config file and try again.
            logging.warning(f"{PROJECT_NAME}: Could not save to DB." +
                            "Try changing the config.")
            db_config = get_config()
            launches_to_db(launches_df, db_config)

    # Print success message.
    logging.info(f"{PROJECT_NAME}: Success!")


if __name__ == "__main__":
    # Run the log keeper.
    main()

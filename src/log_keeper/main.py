"""main.py
661 VGS - Collate all log sheets (2965D) into one master log DB.
"""

# Get packages.
from pathlib import Path
from cryptography.fernet import InvalidToken

# Get modules.
from log_keeper.get_config import get_config, update_config, remove_key
from log_keeper.ingest import collate_log_sheets
from log_keeper.output import launches_to_excel, launches_to_db
from log_keeper.utils import PROJECT_NAME, get_onedrive_path


def main():
    """
    This function is the entry point of the program.
    It performs the following steps:
    1. Prints a starting message.
    2. Retrieves the file paths.
    3. Creates the log sheets directory path.
    4. Creates the master log file path.
    5. Collates all log sheets into a dataframe.
    6. Saves the launches to an Excel file.
    7. Retrieves the database configuration.
    8. Saves the master log to MongoDB Atlas.
    9. Handles exceptions and retries if necessary.
    10. Prints a success message.
    """
    # Initial comment.
    print(f"{PROJECT_NAME}: Starting...")

    # Get the file paths.
    onedrive_path = get_onedrive_path()

    # Path to the log sheets directory.
    log_sheets_dir = Path(
        onedrive_path,
        "#Statistics",
        "Log Sheets"
    )

    # Output file path.
    master_log_filepath = Path(
        log_sheets_dir,
        "Master Log.xlsx"
    )

    # Create a dataframe of all log sheets.
    launches_df = collate_log_sheets(log_sheets_dir)

    # Save the launches to excel.
    launches_to_excel(launches_df, master_log_filepath)

    # Get the config filepath, or use the CLI interface to create one.
    try:
        db_config = get_config()
    # A Fernet cryptography error is raised if an existing config is invalid.
    except Exception as e:
        print(f"{PROJECT_NAME}: Invalid config file.")
        if isinstance(e, InvalidToken):
            # Create a new config file.
            remove_key()
            db_config = update_config()
        else:
            # Raise the error.
            raise e

    # Save the master log to MongoDB Atlas.
    try:
        launches_to_db(launches_df, db_config)
    except Exception as e:
        # Filter a ConnectionError.
        if isinstance(e, ConnectionError):
            print(e)
        else:
            # Remove the config file and try again.
            print(f"{PROJECT_NAME}: Could not save to DB." +
                  "Try changing the config file.")
            db_config = get_config()
            launches_to_db(launches_df, db_config)

    # Print success message.
    print(f"{PROJECT_NAME}: Success!")


if __name__ == "__main__":
    # Run the log keeper.
    main()

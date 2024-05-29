"""utils.py

This file contains utility functions and constants."""

# Get packages.
import sys
import logging
from pathlib import Path
import inquirer
from inquirer.errors import ValidationError

# Constants.
PROJECT_NAME = "viking-log-keeper"

# Set up logging.
logger = logging.getLogger(__name__)


def validate_directory(answers: dict, path_str: Path) -> bool:
    """
    Verify that the path is a directory.

    Args:
        answers (dict): The answers from the user.
        path (Path): The path to verify.

    Returns:
        bool: True if the path is a directory, otherwise False.
    """
    # Convert the path to a Path object.
    path = Path(path_str)
    if path.is_dir() is False:
        raise ValidationError(
            '',
            reason="Path does not exist or is not a directory."
        )
    return True


def prompt_directory_path() -> Path:
    """
    Prompt the user to enter a directory path.

    Returns:
        Path: The path entered by the user.
    """

    questions = [
        inquirer.Text(
            'path',
            message="Enter the path to the Documents directory " +
                    "e.g. C:\\Users\\YOUR_USERNAME\\OneDrive\\Documents",
            validate=lambda _, x: Path(x).is_dir(
            ) or "Path does not exist or is not a directory.",
        )
    ]
    answers = inquirer.prompt(questions)
    return Path(answers['path'])


def find_directory(start_path, search_string):
    """
    Find a directory.

    Args:
        start_path (Path): The starting path to search from.
        search_string (str): The string to search for in directory names.

    Returns:
        Path or None: The found directory if it exists, otherwise None.
    """
    found_dir = None

    # Search for the directory.
    for directory in start_path.iterdir():
        if directory.is_dir() and search_string in directory.name:
            found_dir = directory
            break

    if found_dir is None:
        # We didn't find the directory.
        logger.warning("Could not find %s.", search_string)

    # Return the directory.
    return found_dir


def get_log_sheets_path():
    """Get the path to OneDrive.

    Returns:
        Path: The path to the OneDrive Documents directory.
    """
    # Name of the onedrive directory to search for.
    onedrive_search_string = "Royal Air Force Air Cadets"
    documents_search_string = "Documents"

    # Search for the onedrive from home.
    root_dir = Path.home()
    log_sheets_dir = Path()

    try:
        onedrive_path = find_directory(root_dir, onedrive_search_string)

        # Now get the path to the documents directory.
        documents_path = find_directory(onedrive_path, documents_search_string)

        # Now attempt to resolve the log sheets directory.
        log_sheets_dir = Path(
            documents_path,
            "#Statistics",
            "Log Sheets"
        )

    except Exception:  # pylint: disable=broad-except
        logger.info("Could not find 'Log Sheets' directory automatically. ",
                    exc_info=True)

    # Prompt the user to enter the path to the documents directory.
    while validate_directory(None, log_sheets_dir) is False:
        log_sheets_dir = prompt_directory_path()

    return log_sheets_dir


def adjust_streamlit_logging():
    """Adjust the logging level of Streamlit to suppress warnings and
    info messages."""
    # Check if Streamlit is in the list of running modules
    if 'streamlit' not in sys.modules:
        # Get the logger for Streamlit
        streamlit_logger = logging.getLogger('streamlit')
        # Set the logging level to ERROR to suppress warnings and info messages
        streamlit_logger.setLevel(logging.ERROR)

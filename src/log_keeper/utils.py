"""utils.py

This file contains utility functions and constants."""

# Get packages.
import logging
from pathlib import Path
import inquirer

# Constants.
PROJECT_NAME = "viking-log-keeper"

# Set up logging.
logger = logging.getLogger(__name__)


def verify_directory_path(path):
    """
    Verify that the path is a directory.

    Args:
        path (Path): The path to verify.

    Returns:
        bool: True if the path is a directory, otherwise False.
    """
    if path.is_dir() is False:
        logger.warning("%s is not a directory.", path)
        return False
    else:
        return True


def prompt_directory_path():
    """
    Prompt the user to enter a directory path.

    Returns:
        Path: The path entered by the user.
    """

    questions = [
        inquirer.Text(
            'path',
            message="Enter the path to the Documents directory " +
                    "e.g. C:\\Users\\YOUR_USERNAME\\OneDrive\\Documents\n",
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
    while verify_directory_path(log_sheets_dir) is False:
        log_sheets_dir = prompt_directory_path()

    return log_sheets_dir

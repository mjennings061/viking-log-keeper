"""utils.py

This file contains utility functions and constants."""

# Get packages.
import inquirer
import logging
from pathlib import Path

# Constants.
PROJECT_NAME = "viking-log-keeper"


def verify_directory_path(path):
    """
    Verify that the path is a directory.

    Args:
        path (Path): The path to verify.

    Returns:
        bool: True if the path is a directory, otherwise False.
    """
    if path.is_dir() is False:
        logging.warning(f"{PROJECT_NAME}: {path} is not a directory.")
        return False
    else:
        return True


def prompt_directory_path(prompt_message):
    """
    Prompt the user to enter a directory path.

    Args:
        prompt_message (str): The prompt message to display to the user.

    Returns:
        Path: The path entered by the user.
    """
    questions = [inquirer.Text('path', message=prompt_message)]
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
    for dir in start_path.iterdir():
        if dir.is_dir() and search_string in dir.name:
            found_dir = dir
            break

    if found_dir is None:
        # We didn't find the directory.
        logging.warning(f"{PROJECT_NAME}: Could not find {search_string}.")

    # Return the directory.
    return found_dir


def get_log_sheets_path():
    """Get the path to OneDrive.

    Returns:
        Path: The path to the OneDrive Documents directory.
    """
    # Name of the onedrive directory to search for.
    ONEDRIVE_SEARCH_STRING = "Royal Air Force Air Cadets"
    DOCUMENTS_SEARCH_STRING = "Documents"

    # Search for the onedrive from home.
    root_dir = Path.home()
    onedrive_path = find_directory(root_dir, ONEDRIVE_SEARCH_STRING)

    # Now get the path to the documents directory.
    documents_path = find_directory(onedrive_path, DOCUMENTS_SEARCH_STRING)

    # Now attempt to resolve the log sheets directory.
    log_sheets_dir = Path(
        documents_path,
        "#Statistics",
        "Log Sheets"
    )

    # Verify that we found the documents directory, otherwise use CLI.
    if verify_directory_path(log_sheets_dir) is False:
        logging.info(f"{PROJECT_NAME}: " +
                     "Could not find 'Log Sheets' directory automatically.")
        # Prompt the user to enter the path to the documents directory.
        while verify_directory_path(log_sheets_dir) is False:
            log_sheets_dir = prompt_directory_path(
                "Enter the path to the Documents directory " +
                "e.g. C:\\Users\\YOUR_USERNAME\\OneDrive\\Documents\n"
            )

    return log_sheets_dir

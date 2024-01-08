"""utils.py

This file contains utility functions and constants."""

# Get packages.
from pathlib import Path

# Constants.
PROJECT_NAME = "viking-log-keeper"


def find_directory(start_path, search_string):
    """Find a directory."""
    # Search for the directory.
    for dir in start_path.iterdir():
        if dir.is_dir() and search_string in dir.name:
            return dir

    # Raise an error if the directory is not found.
    raise FileNotFoundError("Could not find OneDrive directory.")


def get_onedrive_path():
    """Get the path to OneDrive."""
    # Name of the onedrive directory to search for.
    ONEDRIVE_SEARCH_STRING = "Royal Air Force Air Cadets"
    DOCUMENTS_SEARCH_STRING = "Documents"

    # Search for the onedrive from home.
    root_dir = Path.home()
    onedrive_path = find_directory(root_dir, ONEDRIVE_SEARCH_STRING)

    # Now get the path to the documents directory.
    documents_path = find_directory(onedrive_path, DOCUMENTS_SEARCH_STRING)
    return documents_path

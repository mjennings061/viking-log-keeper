"""get_config.py - Get the database configuration from keyring"""

# Get packages.
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import streamlit as st
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import inquirer
import keyring as kr
import logging

# Get packages from the log_keeper package.
from log_keeper.utils import PROJECT_NAME

# Set up logging.
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Data class to store the configuration values."""
    # Define fields with default values of None
    db_hostname: Optional[str] = field(default=None)
    db_username: Optional[str] = field(default=None)
    db_password: Optional[str] = field(default=None)
    db_name: Optional[str] = field(default=None)
    db_collection_name: Optional[str] = field(default=None)
    log_sheets_dir: Optional[str] = field(default=None)

    def __post_init__(self):
        logging.info("Loading config...")
        self.load_config()
        self.validate()

    def load_config(self):
        try:
            logging.info("Using Streamlit secrets.")
            self.db_hostname = st.secrets["db_hostname"]
            self.db_username = st.secrets["db_username"]
            self.db_password = st.secrets["db_password"]
            self.db_name = st.secrets["db_name"]
            self.db_collection_name = st.secrets["db_collection_name"]
            self.log_sheets_dir = st.secrets["log_sheets_dir"]
        except Exception:  # noqa: F841
            logging.info("Using keyring to fetch config.")
            self.load_from_keyring()

    def load_from_keyring(self):
        try:
            self.db_hostname = kr.get_password(PROJECT_NAME, "db_hostname")
            self.db_username = kr.get_password(PROJECT_NAME, "db_username")
            self.db_password = kr.get_password(PROJECT_NAME, "db_password")
            self.db_name = kr.get_password(PROJECT_NAME, "db_name")
            self.db_collection_name = kr.get_password(PROJECT_NAME,
                                                      "db_collection_name")
            self.log_sheets_dir = kr.get_password(PROJECT_NAME,
                                                  "log_sheets_dir")
        except Exception as e:
            logging.error(f"Failed to load from keyring: {e}")
            # Handle failure to load from keyring here

    def validate(self):
        """Validate the configuration values."""
        # Check if any of the values are None.
        if not all([self.db_hostname, self.db_username, self.db_password,
                    self.db_name, self.db_collection_name,
                    self.log_sheets_dir]):
            logger.warning("Configuration values are missing.")
            return False
        # Check if the log_sheets_dir is a directory.
        if not Path(self.log_sheets_dir).is_dir():
            logger.warning("Invalid log sheets directory: %s",
                           self.log_sheets_dir)
            return False
        logger.info("Config valid.")
        return True

    def connect_to_db(self):
        """Connect to the MongoDB database.

        Returns:
            pymongo.MongoClient: The database."""
        # Get variables.
        db_hostname = self.db_hostname
        db_username = self.db_username
        db_password = self.db_password
        db_name = self.db_name

        # Create the DB connection URL.
        db_url = f"mongodb+srv://{db_username}:{db_password}@{db_hostname}" + \
            "/?retryWrites=true&w=majority"

        # Create a new client and connect to the server.
        client = MongoClient(
            db_url,
            server_api=ServerApi('1'),
            tls=True,
            tlsAllowInvalidCertificates=True
        )

        # Print success message if ping is successful.
        if client.admin.command('ping')['ok'] == 1.0:
            logger.info("Connected to DB.")
        else:
            raise ConnectionError("Could not connect to DB.")

        # Get the database.
        db = client[db_name]
        return db

    def save_credentials(self):
        """Save the credentials to the keyring."""
        logger.info("Saving credentials to keyring.")
        kr.set_password(PROJECT_NAME, "db_hostname", self.db_hostname)
        kr.set_password(PROJECT_NAME, "db_username", self.db_username)
        kr.set_password(PROJECT_NAME, "db_password", self.db_password)
        kr.set_password(PROJECT_NAME, "db_name", self.db_name)
        kr.set_password(PROJECT_NAME, "db_collection_name",
                        self.db_collection_name)
        kr.set_password(PROJECT_NAME, "log_sheets_dir",
                        self.log_sheets_dir)
        logger.info("Credentials saved.")

    def get_credentials_cli(self):
        """Get the encrypted credentials using the CLI."""
        questions = [
            inquirer.Text(
                "db_hostname",
                message="Database hostname e.g. 666vgs.pda4bch.mongodb.net"
            ),
            inquirer.Text(
                "db_username",
                message="Database username e.g. 666vgs"
            ),
            inquirer.Text(
                "db_password",
                message="Database password e.g. vigilants_are_better"
            ),
            inquirer.Text(
                "db_name",
                message="Database name e.g. 666vgs"
            ),
            inquirer.Text(
                "db_collection_name",
                message="Database collection name e.g. log_sheets"
            ),
            inquirer.Text(
                "log_sheets_dir",
                message="Enter the path to the Documents directory " +
                        "e.g. C:\\Users\\YOUR_USERNAME\\OneDrive\\Documents\n",
                validate=lambda _, x: Path(x).is_dir(
                ) or "Path does not exist or is not a directory.",
            )
        ]

        # Display the questions.
        answers = inquirer.prompt(questions)
        return answers

    def update_credentials(self):
        """Update the credentials."""
        # Get the credentials using CLI.
        credentials = self.get_credentials_cli()
        self.db_hostname = credentials["db_hostname"]
        self.db_username = credentials["db_username"]
        self.db_password = credentials["db_password"]
        self.db_name = credentials["db_name"]
        self.db_collection_name = credentials["db_collection_name"]
        self.log_sheets_dir = credentials["log_sheets_dir"]
        self.save_credentials()

    def update_log_sheets_dir(self):
        """Update the log sheets directory."""
        # Get the log sheets directory using CLI.
        logging.info("Updating log sheets directory.")
        questions = [
            inquirer.Text(
                "log_sheets_dir",
                message="Enter the path to the Documents directory " +
                        "e.g. C:\\Users\\YOUR_USERNAME\\OneDrive\\Documents\n",
                validate=lambda _, x: Path(x).is_dir(
                ) or "Path does not exist or is not a directory.",
            )
        ]
        answers = inquirer.prompt(questions)
        self.log_sheets_dir = answers["log_sheets_dir"]
        self.save_credentials()


def update_log_sheets_dir_wrapper():
    """Wrapper function to update the log sheets directory."""
    config = Config()
    config.update_log_sheets_dir()


def update_credentials_wrapper():
    """Wrapper function to update the credentials."""
    config = Config()
    config.update_credentials()


if __name__ == "__main__":
    # Get the config file.
    config = Config()
    print(config)

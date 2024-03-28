"""get_config.py - Get the database configuration from keyring"""

# Get packages.
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import keyring as kr
import pandas as pd
import inquirer
import logging

# Set up logging.
logger = logging.getLogger(__name__)


@dataclass
class LogSheetConfig:
    """Data class to store the configuration values.

    Attributes:
        db_hostname (Optional[str]): The hostname of the MongoDB server.
        db_username (Optional[str]): The username of the MongoDB server.
        db_password (Optional[str]): The password of the MongoDB server.
        db_name (Optional[str]): The name of the MongoDB database.
        db_collection_name (Optional[str]): The name of the MongoDB collection.
        log_sheets_dir (Optional[str]): The path to the directory containing
            the log sheets."""
    # Define fields with default values of None.
    db_hostname: Optional[str] = field(default=None)
    db_username: Optional[str] = field(default=None)
    db_password: Optional[str] = field(default=None)
    db_name: Optional[str] = field(default=None)
    db_collection_name: Optional[str] = field(default=None)
    log_sheets_dir: Optional[str] = field(default=None)

    def validate(self):
        """Validate the configuration values.

        Returns:
            bool: True if all values are present and valid, otherwise False."""
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

        # Create the DB connection URL.
        db_url = (f"mongodb+srv://{db_username}:{db_password}@{db_hostname}"
                  "/?retryWrites=true&w=majority")

        # Create a new client and connect to the server.
        client = MongoClient(
            db_url,
            server_api=ServerApi('1'),
            tls=True,
            tlsAllowInvalidCertificates=True,
        )

        # Print success message if ping is successful.
        if client.admin.command('ping')['ok'] == 1.0:
            logger.info("Connected to DB.")
        else:
            raise ConnectionError("Could not connect to DB.")

        # Return the client.
        return client

    def fetch_log_sheet_dir(self):
        """Fetch the log sheet directory from keyring.

        Returns:
            str: The log sheet directory."""
        try:
            self.log_sheets_dir = kr.get_password("log_keeper",
                                                  "log_sheets_dir")
        except Exception:
            logger.warning("Could not fetch log_sheets_dir from keyring.",
                           exc_info=True)

        if not self.log_sheets_dir:
            self.update_log_sheets_dir()
        return self.log_sheets_dir

    def update_log_sheets_dir(self):
        """Update the log sheets directory."""
        # Get the log sheets directory using CLI.
        logging.info("Updating log sheets directory.")
        questions = [
            inquirer.Text(
                "log_sheets_dir",
                message="Log sheets directory " +
                        "e.g. C:\\Users\\YOUR_USERNAME\\OneDrive\\Documents\n",
                validate=lambda _, x: Path(x).is_dir(
                ) or "Path does not exist or is not a directory.",
            )
        ]
        answers = inquirer.prompt(questions)
        self.log_sheets_dir = answers["log_sheets_dir"]

        # Save to keyring.
        try:
            kr.set_password("log_keeper", "log_sheets_dir",
                            self.log_sheets_dir)
        except Exception:
            logger.error("Could not save log_sheets_dir to keyring.",
                         exc_info=True)

    def fetch_data_from_mongodb(self):
        """Fetch data from MongoDB.

        Returns:
            pandas.DataFrame: The data fetched from MongoDB."""
        try:
            client = self.connect_to_db()
            db = client[self.db_name]
            collection = db[self.db_collection_name]

            # Convert list of dictionaries to DataFrame
            df = pd.DataFrame(collection.find())

        except Exception:  # pylint: disable=broad-except
            logging.error("Could not fetch data from MongoDB.", exc_info=True)
            df = pd.DataFrame()
        return df


def update_log_sheets_dir_wrapper():
    """Wrapper function to update the log sheets directory."""
    config = LogSheetConfig()
    config.update_log_sheets_dir()


if __name__ == "__main__":
    # Get the config file.
    config = LogSheetConfig()
    print(config)

"""get_config.py - Get the database configuration from keyring"""

# Get packages.
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import OperationFailure
import keyring as kr
import pandas as pd
import inquirer
import logging

# Set up logging.
logger = logging.getLogger(__name__)


@dataclass
class DbUser():
    """Store the database user configuration values.

    Attributes:
        username (str): The username of the database user.
        password (str): The password of the database user.
        uri (str): The URI of the database."""
    username: str
    password: str
    uri: str

    def get_connection_string(self):
        """Get the connection string to the database.

        Returns:
            str: The connection string."""
        return f"mongodb+srv://{self.username}:{self.password}@{self.uri}"


class Client(MongoClient):
    def __init__(self, db_user: DbUser):
        """Initialize the Client object to inherit from MongoClient."""
        # Validate db_user.
        super().__init__(
            db_user.get_connection_string(),
            server_api=ServerApi('1'),
            tls=True,
            tlsAllowInvalidCertificates=True,
        )
        self.db_user = db_user

    def log_in(self):
        """Log in to the database.

        Returns:
            bool: True if the user is logged in, otherwise False."""
        try:
            self.admin.command('ping')
            logging.info("Logged in to DB.")
            return True
        except OperationFailure:
            logging.error("Could not log in to DB.")
            return False


class Database:
    """MongoDB database class to connect to a database."""
    def __init__(self, client: Client, database_name: str):
        # Set launches collection.
        self.launches_collection = "log_sheets"
        # Validate client.
        if not client.log_in():
            raise ConnectionError("Could not log in to the database.")
        self.client = client

        # Validate database name.
        if not database_name:
            raise ValueError("Database name is required.")
        if database_name not in client.list_database_names():
            raise ValueError("Database does not exist.")
        self.database_name = database_name

        # Connect to the database.
        # Throw an error if the user does not have access.
        try:
            self.db = client[self.database_name]
        except Exception:
            logging.error("Could not connect to the database.")
            raise ConnectionError("Could not connect to the database.")

    def get_collection(self, collection_name: str):
        """Get a collection from the database.

        Args:
            collection_name (str): The name of the collection.

        Returns:
            pymongo.collection.Collection: The collection."""
        # Validate collection name.
        if not collection_name:
            raise ValueError("Collection name is required.")

        # Check if the collection exists.
        if collection_name not in self.db.list_collection_names():
            logging.error("Collection does not exist.")
            raise ValueError("Collection does not exist.")

        # Get the collection.
        collection = self.db[collection_name]

        # Check if the collection has data.
        if collection.count_documents({}) == 0:
            logging.warning("Collection is empty.")
        return collection

    def get_launches_collection(self):
        """Get the launches collection from the database.

        Returns:
            pymongo.collection.Collection: The launches collection."""
        return self.get_collection("log_sheets")


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

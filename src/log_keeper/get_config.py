"""get_config.py - Get the database configuration from keyring"""

# Get packages.
import inquirer
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import OperationFailure
from pymongo.collection import Collection
import keyring as kr
import pandas as pd


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

    def __post_init__(self):
        """Post-initialization method to validate the attributes."""
        # Validate the username.
        if not self.username:
            raise ValueError("Username is required.")
        # Validate the password.
        if not self.password:
            raise ValueError("Password is required.")
        # Validate the URI.
        if not self.uri:
            raise ValueError("URI is required.")

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
        self._authenticated = False
        self._available_databases = []
        self._default_database = None

    def log_in(self):
        """Log in to the database.

        Returns:
            bool: True if the user is logged in, otherwise False."""
        try:
            # Try to ping the database.
            self.admin.command('ping')
            self._authenticated = True
            logging.info("Logged in to DB.")
            # Retrieve the list of databases.
            self._available_databases = self._get_readable_databases()
            # Set the default database.
            self._set_default_database()
            return True
        except OperationFailure:
            self._authenticated = False
            logging.error("Could not log in to DB.")
            return False

    def authenticated(self):
        """Check if the user is authenticated.

        Returns:
            bool: True if the user is authenticated, otherwise False."""
        return self._authenticated

    def _get_readable_databases(self):
        """Get the readable databases for the user.

        Returns:
            list: The list of readable databases."""
        try:
            # Get the list of databases.
            databases = self.list_database_names()
            # Filter "admin" and "local" databases.
            databases = [
                db for db in databases if db not in ["admin", "local"]
            ]
            logging.info("User can access: %s", databases)
            return databases
        except OperationFailure:
            logging.error("Could not get readable databases.")
            return []

    def _set_default_database(self):
        """Set the default database for the user."""
        DEFAULT_DB = "test"
        # Check if the user is authenticated.
        if not self.authenticated():
            logging.error("User is not authenticated.")
            self._default_database = DEFAULT_DB
            return

        # Set the default database to the user's username.
        username_db = self.db_user.username
        if username_db in self._available_databases:
            self._default_database = username_db
        else:
            self._default_database = DEFAULT_DB

    @property
    def available_databases(self):
        """Get the available databases for the user.

        Returns:
            list: The available databases."""
        if not self.authenticated():
            logging.error("User is not authenticated.")
            return []
        return self._available_databases

    @property
    def default_database(self):
        """Get the default database for the user.

        Returns:
            str: The default database."""
        if not self.authenticated():
            logging.error("User is not authenticated.")
            return "test"
        return self._default_database


class Database:
    """MongoDB database class to connect to a database."""
    def __init__(self, client: Client, database_name: str):
        # Set launches collection.
        self.launches_collection = "log_sheets"
        self.aircraft_info_collection = "aircraft"
        # Validate client.
        if not client.authenticated():
            raise ConnectionError("Could not log in to the database.")
        self.client = client

        # Validate database name.
        if not database_name:
            raise ValueError("Database name is required.")
        if database_name not in client.available_databases:
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
        logging.info("Collection %s fetched.", collection_name)
        return collection

    def get_launches_collection(self) -> Collection:
        """Get the launches collection from the database.

        Returns:
            pymongo.collection.Collection: The launches collection."""
        return self.get_collection(self.launches_collection)

    def get_launches_dataframe(self):
        """Get log sheets collection as a DataFrame.

        Returns:
            pandas.DataFrame: The log sheets collection as a DataFrame."""
        try:
            # Get the collection and convert it to a DataFrame.
            collection = self.get_launches_collection()
            df = pd.DataFrame(collection.find())
            df = df.sort_values(by="Date", ascending=False)
        except Exception:  # pylint: disable=broad-except
            # Log error and return an empty DataFrame.
            logging.error("Could not fetch data from the collection.")
            df = pd.DataFrame()
        return df

    def get_aircraft_info_collection(self) -> Collection:
        """Get the aircraft information collection from the database.

        Returns:
            pymongo.collection.Collection: The aircraft information
            collection."""
        return self.get_collection(self.aircraft_info_collection)

    def get_aircraft_info(self) -> pd.DataFrame:
        """Get the aircraft information as a dictionary.

        Returns:
            pd.DataFrame: The aircraft information as a dataframe."""
        try:
            # Get the collection and convert it to a DataFrame.
            collection = self.get_aircraft_info_collection()
            df = pd.DataFrame(collection.find())
            df = df.sort_values(by="Date", ascending=False)
        except Exception:  # pylint: disable=broad-except
            # Log error and return an empty DataFrame.
            logging.error("Could not fetch data from aircraft collection.")
            df = pd.DataFrame()
        return df

    @staticmethod
    def dummy_launches_dataframe():
        """Create a dummy DataFrame with varied data."""
        n_days = 10
        n_rep = 30
        base_date = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        dates = [base_date - timedelta(days=i*7) for i in range(n_days)]

        all_data = []

        aircraft_list = ["ZE123", "ZE456", "ZE321", "ZE654", "ZE118"]
        commanders = ["Jennings", "White, C", "Abbott", "MacGregor", "Philips"]
        second_pilots = ["Jones", "Clarke", "Taylor", "White", "Green"]
        duties = ["SCT U/T", "GIF", "SCT QGI", "AGT", "G/S"]

        for day in sorted(dates):
            take_off_times = [
                day + timedelta(hours=random.randint(6, 12))
                for _ in range(n_rep)
            ]
            flight_time = [random.randint(5, 10) for _ in range(n_rep)]
            landing_times = [
                take_off_times[i] + timedelta(minutes=flight_time[i])
                for i in range(n_rep)
            ]

            daily_data = {
                "Date": [day for _ in range(n_rep)],
                "Aircraft": [
                    random.choice(aircraft_list) for _ in range(n_rep)
                ],
                "AircraftCommander": [
                    random.choice(commanders) for _ in range(n_rep)
                ],
                "SecondPilot": [
                    random.choice(second_pilots) for _ in range(n_rep)
                ],
                "Duty": [random.choice(duties) for _ in range(n_rep)],
                "FlightTime": flight_time,
                "TakeOffTime": take_off_times,
                "LandingTime": landing_times,
                "SPC": [random.randint(0, 5) for _ in range(n_rep)],
                "P1": [random.choice([True, False]) for _ in range(n_rep)],
                "P2": [random.choice([True, False]) for _ in range(n_rep)],
                "PLF": [random.choice([True, False]) for _ in range(n_rep)],
            }

            all_data.append(pd.DataFrame(daily_data))

        df = pd.concat(all_data, ignore_index=True)
        return df

    @staticmethod
    def dummy_aircraft_info_dataframe() -> pd.DataFrame:
        """Create a dummy DataFrame with varied data.

        Returns:
            pd.DataFrame: The dummy DataFrame."""
        # Constants.
        keys = ["_id", "Aircraft", "Date", "Hours After", "Launches After"]
        aircraft_choices = ["ZE123", "ZE456", "ZE321", "ZE654", "ZE118"]
        n_reps = 10

        id = [i for i in range(n_reps)]
        aircraft = [random.choice(aircraft_choices) for i in range(n_reps)]
        date = [datetime.now() - timedelta(weeks=1) for i in range(n_reps)]
        launches_after = [random.randint(10000, 30000) for i in range(n_reps)]
        hours_after = [
            random.randint(10000, 30000)
            for i in range(n_reps)
        ]

        # Create the DataFrame.
        df = pd.DataFrame(
            data=[id, aircraft, date, hours_after, launches_after],
            index=keys,
        ).T
        return df


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

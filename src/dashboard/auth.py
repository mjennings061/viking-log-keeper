"""auth.py - Data class to store the authentication configuration values.
"""

# Import modules.
from dataclasses import dataclass, field
from typing import Optional
import re
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import keyring as kr
import inquirer
import logging

# User defined modules.
from dashboard.utils import is_streamlit_running
from log_keeper.utils import PROJECT_NAME
from log_keeper.get_config import LogSheetConfig

# Set up logging.
logger = logging.getLogger(__name__)
logging.getLogger('pymongo').setLevel(logging.WARNING)


@dataclass
class AuthConfig:
    """Data class to store the authentication configuration values."""
    # Constants.
    db_name: str = field(default="auth")
    db_collection_name: str = field(default="auth")
    db_credentials_name: str = field(default="databases")
    # Configurable fields.
    auth_url: str = field(default=(
        "mongodb+srv://vgs_user:<password>@auth.hr6kjov.mongodb.net"
        "/?retryWrites=true&w=majority"
    ))
    vgs: str = field(default=None)
    password: Optional[str] = field(default=None)
    authenticated: bool = field(default=False)
    client: Optional[MongoClient] = field(default=None)
    connected: bool = field(default=False)
    allowed_vgs: list = field(default_factory=list)
    log_sheet_config: LogSheetConfig = field(default_factory=LogSheetConfig)

    def __post_init__(self):
        """Load db_url from secrets or keyring."""
        self.load_secrets()

    def load_secrets(self):
        """Load secrets from keyring or streamlit."""
        # Load auth password from secrets or keyring.
        if is_streamlit_running():
            import streamlit as st
            auth_password = st.secrets["auth_password"]
        else:
            # Get vgs and password from keyring.
            self.vgs = kr.get_password(PROJECT_NAME, "vgs")
            self.password = kr.get_password(PROJECT_NAME, "password")
            auth_password = kr.get_password(PROJECT_NAME, "auth_password")

        # Replace the password in the auth_url. Note, this is different from
        # the password used to authenticate with each individual user.
        if auth_password is not None:
            self.auth_url = self.auth_url.replace(
                "<password>",
                auth_password,
            )

    def validate(self) -> bool:
        """Validate the configuration values.

        Returns:
            bool: True if all values are present and valid, otherwise False."""
        # Check if any of the values are None.
        if not all([self.vgs, self.password]):
            logging.warning("Configuration values are missing.")
            return False

        # Validate if the auth_url is set.
        if "<password>" in self.auth_url:
            logging.warning("Auth URL is not set.")
            return False
        return True

    def _connect(self) -> bool:
        """Connect to the DB.

        Returns:
            bool: True if connected to the DB.
        """
        # Connect to MongoDB.
        self.client = MongoClient(
            self.auth_url,
            server_api=ServerApi('1'),
            tls=True,
            tlsAllowInvalidCertificates=True
        )

        # Ping the server.
        try:
            if self.client.admin.command('ping')['ok'] == 1.0:
                logging.info("Connected to Auth DB.")
                self.connected = True
            else:
                logging.error("Failed to connect to Auth DB.")
        except Exception:  # pylint: disable=broad-except
            logging.error("Connection error", exc_info=True)
        return self.connected

    def _login(self, vgs, password: str) -> bool:
        """Login to the DB.

        Args:
            password (str): The password to check.

        Returns:
            bool: True if the password is correct.
        """
        # Set the DB credentials.
        self.vgs = vgs
        self.password = password

        # Connect to the DB.
        self._connect()

        # Get the auth credentials from the DB.
        if self.connected:
            db = self.client[self.db_name]
            collection = db[self.db_collection_name]

            # Try to fetch the VGS document.
            document = collection.find_one({"vgs": self.vgs})

            # Check the password.
            if document and self.password == document.get("password"):
                self.authenticated = True
                self.allowed_vgs = document.get("allowed_vgs", [])
            else:
                logging.error("Invalid username or password.")
        return self.authenticated

    def fetch_log_sheets_credentials(self, vgs: str = None,
                                     password: str = None) -> dict:
        """Fetch the log_sheets DB credentials from MongoDB.

        Args:
            vgs (str): The VGS to fetch the credentials for.
            password (str): The password to authenticate with.

        Returns:
            dict: The log_sheets DB credentials."""
        # Connect to the DB.
        if not vgs or not password:
            # Entered via the CLI.
            logging.info("Using stored auth DB credentials.")
            vgs = self.vgs
            password = self.password

        # Entered via streamlit form.
        self._login(vgs, password)

        # Get the log_sheets credentials.
        credentials = {}
        if self.authenticated:
            db = self.client[self.db_name]
            collection = db[self.db_credentials_name]

            # Fetch the log_sheets credentials.
            credentials = collection.find_one({"vgs": vgs.lower()})
            logging.info("Fetched log_sheets credentials.")

            # Pop the _id and vgs fields.
            credentials.pop("_id", None)
            credentials.pop("vgs", None)
        else:
            logging.error("Failed to fetch log_sheets credentials.")

        # Close the connection.
        self.close_connection()
        return credentials

    def update_credentials(self):
        """Use inquirer to update the credentials. Save to keyring."""
        # Prompt the user to enter the credentials.
        questions = [
            inquirer.Text(
                "vgs",
                message="VGS",
                default="661VGS"
            ),
            inquirer.Password(
                "password",
                message="Password"
            ),
            inquirer.Password(
                "auth_password",
                message="Auth database password (different from above)"
            )
        ]

        # Update the credentials.
        answers = inquirer.prompt(questions)
        self.vgs = answers["vgs"]
        self.password = answers["password"]

        # Replace the password in the auth_url.
        self.auth_url = re.sub(r"vgs_user:.*@",
                               f"vgs_user:{answers['auth_password']}@",
                               self.auth_url)

        # Save credentials to keyring.
        try:
            kr.set_password(PROJECT_NAME, "vgs", answers["vgs"])
            kr.set_password(PROJECT_NAME, "auth_password",
                            answers["auth_password"])
            kr.set_password(PROJECT_NAME, "password", answers["password"])
        except Exception:
            logging.error("Failed to save credentials to keyring.",
                          exc_info=True)

    def close_connection(self):
        """Close the connection to the DB."""
        if self.client:
            self.client.close()
            logging.info("Closed connection to Auth DB.")


def update_credentials_wrapper():
    """Wrapper function to update the credentials."""
    config = AuthConfig()
    config.update_credentials()


if __name__ == "__main__":
    update_credentials_wrapper()
    config = AuthConfig()
    print(config.fetch_log_sheets_credentials())
    config.close_connection()

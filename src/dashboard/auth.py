"""auth.py - User authentication for Streamlit."""

# Import modules.
import logging
import re
from uuid import uuid4
from dataclasses import dataclass, field, fields
from typing import Optional
from datetime import datetime, timedelta
import streamlit as st
from extra_streamlit_components import CookieManager
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import inquirer
import keyring as kr

# User defined modules.
from log_keeper.utils import PROJECT_NAME
from log_keeper.get_config import LogSheetConfig

# Set up logging.
logger = logging.getLogger(__name__)


@dataclass
class AuthConfig():
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
    client: Optional[MongoClient] = field(default=None, repr=False)
    connected: bool = field(default=False)
    allowed_vgs: list = field(default_factory=list)
    log_sheet_config: LogSheetConfig = field(default=None)
    session_id: str = field(default=None)

    def __post_init__(self):
        """Load db_url from secrets or keyring."""
        self.load_secrets()

    def to_dict(self):
        """Remove unserialisable elements from the dictionary.

        Returns:
            dict: The serialised dictionary."""
        dictionary = {}
        for this_field in fields(self):
            # Skip the client field, its not serialisable.
            if this_field.name == "client":
                continue
            # Log sheet config has its own serialisation method.
            elif this_field.name == "log_sheet_config":
                # Ensure non-empty.
                log_sheet_config = getattr(self, this_field.name)
                if log_sheet_config:
                    dictionary[this_field.name] = getattr(
                        self,
                        this_field.name
                    ).__dict__
            else:
                # Other fields are serialisable.
                dictionary[this_field.name] = getattr(self, this_field.name)
        return dictionary

    def load_secrets(self):
        """Load secrets from keyring or streamlit."""
        # Load auth password from secrets or keyring.
        try:
            auth_password = st.secrets["auth_password"]
            self.auth_url = self.auth_url.replace("<password>", auth_password)
            return
        except Exception:  # noqa: F841
            # Load the config from keyring.
            auth_password = kr.get_password(PROJECT_NAME, "auth_password")

            # Replace the password in the auth_url if it exists.
            if auth_password is not None:
                self.auth_url = self.auth_url.replace("<password>",
                                                      auth_password)

        # Get vgs and password from keyring.
        self.vgs = kr.get_password(PROJECT_NAME, "vgs")
        self.password = kr.get_password(PROJECT_NAME, "password")

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

                # Update session ID if necessary.
                if self.session_id is None:
                    self.session_id = str(uuid4())
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

            # Save credentials as LogSheetConfig.
            self.log_sheet_config = LogSheetConfig(**credentials)
        else:
            logging.error("Failed to fetch log_sheets credentials.")

        # Close the connection.
        self._close_connection()
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

    def _close_connection(self):
        """Close the connection to the DB."""
        if self.client:
            self.client.close()
            self.connected = False
            logging.info("Closed connection to Auth DB.")


class Session():
    """Store session information after authentication."""
    session_collection = "sessions"
    _cookie_lifetime = 30   # Days

    def __init__(self, auth_db_config: AuthConfig = None):
        """Initialize the session.

        Args:
            auth_db_config (AuthConfig): Authentication DB configuration."""
        self.auth_db_config = auth_db_config
        self.session_id = str(uuid4())
        self.date_created = datetime.now()

    def __str__(self):
        return f"Session ID: {self.session_id}"

    def save_session(self):
        """Save session to MongodDB"""
        # Connect to the DB.
        self.auth_db_config._connect()

        # Get the auth credentials from the DB.
        if self.auth_db_config.connected:
            db = self.auth_db_config.client[self.auth_db_config.db_name]
            collection = db[self.session_collection]

            # Format document.
            document = {
                "session_id": self.session_id,
                "auth_config": self.auth_db_config.to_dict(),
                "date_created": self.date_created,
            }

            # Insert into the DB.
            logger.info("Saving session to DB.")
            collection.insert_one(document=document)
            logger.info("Saved session to DB.")
            self.auth_db_config._close_connection()

    def delete_session(self):
        """Delete this session."""
        # Connect to the DB.
        self.auth_db_config._connect()

        # Get the auth credentials from the DB.
        if self.auth_db_config.connected:
            db = self.auth_db_config.client[self.auth_db_config.db_name]
            collection = db[self.session_collection]

            # Delete the session.
            logger.info("Deleting session from DB.")
            collection.delete_one({"session_id": self.session_id})
            logger.info("Deleted session from DB.")
            self.auth_db_config._close_connection()

            # Delete cookie.
            self.delete_cookie()

    def retrieve_session_data(self, session_id: str):
        """Retrieve the session data from the DB.

        Args:
            session_id (str): The session ID to retrieve.

        Returns:
            dict: The session data."""
        # Update the session ID if required.
        if session_id != self.session_id:
            self.session_id = session_id

        # Connect to the DB.
        if self.auth_db_config is None:
            self.auth_db_config = AuthConfig()
            self.auth_db_config.fetch_log_sheets_credentials()

        # Get the auth credentials from the DB.
        self.auth_db_config._connect()
        if self.auth_db_config.connected:
            db = self.auth_db_config.client[self.auth_db_config.db_name]
            collection = db[self.session_collection]

            # Fetch the session.
            session_data = collection.find_one({"session_id": session_id})
            logging.info("Fetched session data.")

            # Close the connection.
            self.auth_db_config.client.close()
            return session_data
        return None

    def save_cookie(self, cookie_manager: CookieManager):
        """Save the session to a cookie.

        Args:
            cookie_manager (CookieManager): The cookie manager."""
        cookie_manager.set(
            "vgs_auth",
            self.session_id,
            expires_at=datetime.now() + timedelta(days=self._cookie_lifetime),
            path="/",
        )
        logging.info("Saved session to cookie.")

    def delete_cookie(self, cookie_manager: CookieManager):
        """Delete the session cookie.

        Args:
            cookie_manager (CookieManager): The cookie manager."""
        try:
            cookie_manager.delete("vgs_auth")
        except Exception:
            logging.error("Failed to delete session from cookie.",
                          exc_info=True)
        logging.info("Deleted session from cookie.")

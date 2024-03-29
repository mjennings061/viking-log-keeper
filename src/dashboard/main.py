"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

# Import modules.
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta    # noqa: F401
from typing import Optional
import re
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import streamlit as st
from extra_streamlit_components import CookieManager
import pandas as pd
import keyring as kr
import logging
import inquirer

# User defined modules.
from log_keeper.get_config import LogSheetConfig
from log_keeper.utils import PROJECT_NAME
from dashboard.plots import plot_launches_by_commander
from dashboard.plots import plot_all_launches, quarterly_summary
from dashboard.plots import show_logbook_helper

# Set up logging.
logger = logging.getLogger(__name__)


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


def date_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter the data by date.

    Args:
        df (pd.DataFrame): The data to be filtered.

    Returns:
        pd.DataFrame: The filtered data.
    """
    # Add a date filter to the sidebar.
    st.sidebar.markdown("<hr>", unsafe_allow_html=True)
    st.sidebar.markdown("## Date Filter")

    # Get the date range from the user.
    min_date = df["Date"].min()
    max_date = df["Date"].max()

    # Add a date filter to the sidebar.
    start_date = st.sidebar.date_input(
        "Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        help="Select the start date",
    )
    end_date = st.sidebar.date_input(
        "End Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        help="Select the end date",
    )

    # Convert the date to a pandas datetime object.
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    # Validate the date range.
    if start_date <= end_date:
        # Filter the data by the date range.
        filtered_df = df[
            (df["Date"] >= start_date) & (df["Date"] <= end_date)
        ]
    else:
        st.error("Error: End date must fall after start date.")
        filtered_df = df
    return filtered_df


def show_data_dashboard(db_credentials: LogSheetConfig):
    """Display the dashboard.

    Args:
        db_credentials (dict): The database credentials."""
    # Set the page title.
    vgs = db_credentials.db_name.upper()
    st.markdown(f"# {vgs} Dashboard")

    # Sidebar for page navigation
    pages = ["📈 Statistics", "🌍 All Data"]
    page = st.sidebar.selectbox("Select a Page:", pages)
    st.sidebar.markdown("<hr>", unsafe_allow_html=True)

    # Fetch data from MongoDB
    if "df" not in st.session_state:
        st.session_state['df'] = db_credentials.fetch_data_from_mongodb()

    # Refresh data button.
    if st.button("🔃 Refresh Data"):
        st.session_state.df = db_credentials.fetch_data_from_mongodb()
        st.success("Data Refreshed!", icon="✅")

    # Get the data from the session state.
    df = st.session_state['df']

    # Setup sidebar filters.
    st.sidebar.markdown("# Dashboard Filters")

    # Filter by AircraftCommander.
    commander = st.sidebar.selectbox(
        "Filter by AircraftCommander",
        sorted(df["AircraftCommander"].unique()),
        index=None,
        help="Select the AircraftCommander to filter by.",
        placeholder="All",
    )

    # Create a list of quarters from the data.
    quarters = df["Date"].dt.to_period("Q").unique()

    # Filter by quarter.
    st.sidebar.markdown("## Quarterly Summary")
    quarter = st.sidebar.selectbox(
        "Select Quarter",
        quarters,
        index=None,
        help="Select the quarter to display."
    )

    # Add a date filter to the sidebar.
    filtered_df = date_filter(df)

    match page:
        case "📈 Statistics":

            # Plot the number of launches by unique AircraftCommander.
            plot_launches_by_commander(filtered_df)

            # Logbook helper by AircraftCommander.
            show_logbook_helper(filtered_df, commander)

            # Filter the data by the selected quarter.
            if quarter and commander:
                quarterly_summary(filtered_df, commander, quarter)

        case "🌍 All Data":
            plot_all_launches(filtered_df)


def authenticate():
    """Prompt and authenticate."""
    # Set up the cookie manager.
    cookie_manager = CookieManager()

    # Add auth to session state.
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return

    # Attempt to read the authenticated cookie.
    authenticated_cookie = cookie_manager.get(cookie="vgs_auth")
    if authenticated_cookie:
        # Cookie read successfully.
        st.session_state["authenticated"] = True
        st.toast("Login successful", icon="🍪")
        return

    # No cookie present, authenticate.
    st.subheader("VGS Dashboard")
    st.session_state["auth"] = AuthConfig()

    # Login form.
    with st.form(key="login_form"):
        st.text_input("Username", help="VGS e.g. '661VGS'", key="vgs")
        st.text_input("Password", type="password", key="password")
        submitted = st.form_submit_button("Enter")

        # Validate the password.
        if submitted:
            # Login to the DB.
            db_credentials = st.session_state["auth"].\
                fetch_log_sheets_credentials(
                    st.session_state["vgs"],
                    st.session_state["password"]
                )

            if db_credentials:
                # User is authenticated remove the form.
                st.session_state["authenticated"] = True
                st.session_state["log_sheet_db"] = LogSheetConfig(
                    **db_credentials
                )
                st.toast("Login successful")

                # TODO: Store cookie as a TTLCache e.g. [session_id: 661VGS]
                # User is authenticated, set the authenticated cookie.
                # expires_at = datetime.now() + timedelta(days=90)
                # cookie_manager.set(
                #     "vgs_auth",
                #     "true",
                #     expires_at=expires_at
                # )  # Expires in 90 days
                st.rerun()

            else:
                st.error("Invalid Password")


def main():
    """Main Streamlit App Code."""
    # Authenticate the user.
    authenticate()

    # User is authenticated display the dashboard.
    if st.session_state["authenticated"]:
        try:
            show_data_dashboard(st.session_state["log_sheet_db"])
        except Exception:  # pylint: disable=broad-except
            logging.error("Failed to display dashboard.", exc_info=True)
            st.error("Failed to display dashboard.")

            # Clear the session state.
            st.session_state.clear()
            try:
                cookie_manager = CookieManager()
                cookie_manager.delete("vgs_auth")
            except Exception:  # pylint
                logging.error("Failed to delete cookie.", exc_info=True)


def display_dashboard():
    """Run the Streamlit app."""
    subprocess.run(["streamlit", "run", "src/dashboard/dashboard.py"],
                   check=True)


def update_credentials_wrapper():
    """Wrapper function to update the credentials."""
    config = AuthConfig()
    config.update_credentials()


if __name__ == '__main__':
    main()

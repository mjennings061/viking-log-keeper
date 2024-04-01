"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

# Import modules.
import subprocess
from datetime import datetime, timedelta
import streamlit as st
from extra_streamlit_components import CookieManager
import pandas as pd
import logging

# User defined modules.
from log_keeper.get_config import LogSheetConfig
from dashboard.plots import plot_launches_by_commander
from dashboard.plots import plot_all_launches, quarterly_summary
from dashboard.plots import show_logbook_helper
from dashboard.auth import AuthConfig, Session

# Set up logging.
logger = logging.getLogger(__name__)

# Create a cookie manager.
cookie_manager = CookieManager()

# TODO:
# Delete session ID after logout.


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


@st.cache_data(ttl=None)
def fetch_log_sheets_mongodb(db_credentials: LogSheetConfig) \
        -> pd.DataFrame:
    """Fetch log sheet data from MongoDB.

    Args:
        db_credentials (LogSheetConfig): The database credentials.

    Returns:
        pd.DataFrame: The log sheet data."""
    return db_credentials.fetch_data_from_mongodb()


def logout():
    """Log out."""
    # Get session info.
    # TODO: Use the session ID in auth_db_config to find and delete the 
    # session DB entry.
    st.session_state["authenticated"] = False
    session = Session()
    session.delete_cookie(cookie_manager=cookie_manager)
    st.toast("Logged out.")
    logging.info("Logged out.")
    st.rerun()


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
        st.session_state['df'] = fetch_log_sheets_mongodb(db_credentials)

    # Refresh data button.
    if st.button("🔃 Refresh Data"):
        # Clear the cache.
        fetch_log_sheets_mongodb.clear()
        st.session_state['df'] = fetch_log_sheets_mongodb(db_credentials)
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

    # Logout button.
    st.sidebar.markdown("<hr>", unsafe_allow_html=True)
    st.sidebar.button("🚪 Logout", on_click=logout)

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


def get_log_sheet_creds():
    """Use AuthConfig to get log sheet DB credentials.

    Returns:
        LogSheetConfig: The log sheet DB credentials."""
    # Login to the DB.
    if st.session_state["auth"].log_sheet_config is not None:
        log_sheet_db = st.session_state["auth"].log_sheet_config
    else:
        # Get the VGS and password from the session state.
        if "vgs" not in st.session_state:
            vgs = password = None
        else:
            vgs = st.session_state["vgs"]
            password = st.session_state["password"]
        # Fetch the log sheet DB credentials.
        log_sheet_db = st.session_state["auth"].\
            fetch_log_sheets_credentials(vgs, password)
    return log_sheet_db


def authenticate():
    """Prompt and authenticate."""
    # Add auth to session state.
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # Attempt to read the authenticated cookie.
    authenticated_cookie = cookie_manager.get(cookie="vgs_auth")
    if authenticated_cookie:
        # Create a new authenticated session.
        user_session = Session()
        user_session.retrieve_session_data(authenticated_cookie)

        # Load auth db credentials.
        st.session_state["auth"] = user_session.auth_db_config

        # Cookie read successfully.
        st.session_state["authenticated"] = True
        st.toast("Login successful", icon="🍪")

    if st.session_state["authenticated"]:
        # Ensure the log sheet DB details are loaded.
        if "log_sheet_db" not in st.session_state:
            st.session_state["log_sheet_db"] = get_log_sheet_creds()
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
            db_credentials = get_log_sheet_creds()

            if db_credentials:
                # Create a new authenticated session.
                user_session = Session(st.session_state["auth"])
                user_session.save_session()
                # Save a cookie and rerun.
                user_session.save_cookie(cookie_manager)
                st.session_state["authenticated"] = True
                st.toast("Login successful")
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

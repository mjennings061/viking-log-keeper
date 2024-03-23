"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

# Import modules.
import subprocess
from datetime import datetime, timedelta
import pymongo
import streamlit as st
from extra_streamlit_components import CookieManager
import pandas as pd

# User defined modules.
from log_keeper.get_config import Config
from dashboard.plots import plot_launches_by_commander
from dashboard.plots import plot_all_launches, quarterly_summary
from dashboard.plots import show_logbook_helper


def fetch_data_from_mongodb() -> pd.DataFrame:
    """Fetch data from MongoDB and return as a DataFrame.
    Returns:
        pd.DataFrame: The data from MongoDB."""

    try:
        # Construct the MongoDB connection URI
        db_config = Config()
        if not db_config.validate():
            db_config.update_credentials()

        # Create the DB connection URL
        db_url = (
            f"mongodb+srv://{db_config.db_username}:"
            f"{db_config.db_password}@{db_config.db_hostname}"
            "/?retryWrites=true&w=majority"
        )

        # Connect to MongoDB
        client = pymongo.MongoClient(db_url)
        db = client[db_config.db_name]
        collection = db[db_config.db_collection_name]

        # Convert list of dictionaries to DataFrame
        df = pd.DataFrame(collection.find())

    except Exception as e:  # pylint: disable=broad-except
        st.error(f"Error: {e}")
        df = pd.DataFrame()
    return df


def date_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter the data by date.

    Args:
        df (pd.DataFrame): The data to be filtered.

    Returns:
        pd.DataFrame: The filtered data.
    """
    # Add a date filter to the sidebar.
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


def show_data_dashboard():
    """Display the dashboard."""
    # Set the page title.
    st.markdown("# 661 VGS Dashboard")
    st.sidebar.markdown("# Dashboard Filters")

    # Fetch data from MongoDB
    if "df" not in st.session_state:
        st.session_state.df = fetch_data_from_mongodb()

    # Refresh data button.
    if st.button("🔃 Refresh Data"):
        st.session_state.df = fetch_data_from_mongodb()
        st.success("Data Refreshed!", icon="✅")

    # Get the data from the session state.
    df = st.session_state.df

    # Filter by AircraftCommander.
    commander = st.sidebar.selectbox(
        "Filter by AircraftCommander",
        sorted(df["AircraftCommander"].unique()),
        index=None,
        help="Select the AircraftCommander to filter by.",
        placeholder="All",
    )

    # Add a date filter to the sidebar.
    filtered_df = date_filter(df)

    tabs = ["Statistics", "All Data"]
    stats_tab, all_data_tab = st.tabs(tabs)

    with stats_tab:

        # Plot the number of launches by unique AircraftCommander.
        plot_launches_by_commander(filtered_df)

        # Logbook helper by AircraftCommander.
        show_logbook_helper(filtered_df, commander)

        # Show a quarterly summary of the number of launches
        # for each AircraftCommander.
        st.sidebar.markdown("## Quarterly Summary")

        # Create a list of quarters from the data.
        quarters = filtered_df["Date"].dt.to_period("Q").unique()

        quarter = st.sidebar.selectbox(
            "Select Quarter",
            quarters,
            index=None,
            help="Select the quarter to display."
        )

        # Filter the data by the selected quarter.
        if quarter and commander:
            quarterly_summary(filtered_df, commander, quarter)

    with all_data_tab:
        plot_all_launches(filtered_df)


def check_password(password: str) -> bool:
    """Returns true if the password is correct.

    Args:
        password (str): The password to check.

    Returns:
        bool: True if the password is correct.
    """
    correct_password = st.secrets["dashboard_password"]

    # Check if the password is correct.
    if password == correct_password:
        authenticated = True
    else:
        authenticated = False
    return authenticated


def authenticate():
    """Prompt and authenticate."""
    # Create a cookie manager.
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
    password = st.text_input("Password", type="password")

    # Validate the password.
    if st.button("Enter"):
        valid_login = check_password(password)
        if valid_login:
            # User is authenticated remove the form.
            st.session_state["authenticated"] = True
            st.toast("Login successful")

            # User is authenticated, set the authenticated cookie.
            expires_at = datetime.now() + timedelta(days=90)
            cookie_manager.set(
                "vgs_auth",
                "true",
                expires_at=expires_at
            )  # Expires in 90 days

        else:
            st.error("Invalid Password")


def main():
    """Main Streamlit App Code."""
    # Authenticate the user.
    authenticate()

    # User is authenticated display the dashboard.
    if st.session_state.get("authenticated"):
        show_data_dashboard()


def display_dashboard():
    """Run the Streamlit app."""
    subprocess.run(["streamlit", "run", "src/dashboard/dashboard.py"],
                   check=True)


if __name__ == '__main__':
    main()

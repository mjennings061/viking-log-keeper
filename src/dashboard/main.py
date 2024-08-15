"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

# Import modules.
import sys
import os
import subprocess
import logging
from datetime import datetime, timedelta    # noqa: F401
import streamlit as st
import pandas as pd
from pathlib import Path

# User defined modules.
# Ensure the src directory is in the sys.path.
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if src_path not in sys.path:
    sys.path.append(src_path)

from log_keeper.get_config import DbUser, Client, Database  # noqa: E402
from dashboard.plots import plot_duty_pie_chart  # noqa: E402
from dashboard.plots import plot_launches_by_commander  # noqa: E402
from dashboard.plots import plot_longest_flight_times  # noqa: E402
from dashboard.plots import plot_monthly_launches  # noqa: E402
from dashboard.plots import plot_all_launches, quarterly_summary  # noqa: E402
from dashboard.plots import show_logbook_helper  # noqa: E402
from dashboard.plots import plot_firstlast_launch_table  # noqa: E402
from dashboard.plots import launches_by_type_table  # noqa: E402
from dashboard.plots import generate_aircraft_weekly_summary  # noqa: E402
from dashboard.plots import generate_aircraft_daily_summary  # noqa: E402
from dashboard.plots import show_launch_delta_metric, show_logo  # noqa: E402
from dashboard.plots import aircraft_flown_per_day  # noqa: E402
from dashboard.plots import launches_daily_summary  # noqa: E402
from dashboard.plots import table_gifs_per_date  # noqa: E402
from dashboard.plots import plot_gif_bar_chart  # noqa: E402
from dashboard.utils import LOGO_PATH, upload_log_sheets  # noqa: E402

# Set up logging.
logger = logging.getLogger(__name__)


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
    end_date = pd.to_datetime(end_date + timedelta(days=1))

    # Validate the date range.
    if start_date < end_date:
        # Filter the data by the date range.
        filtered_df = df[
            (df["Date"] >= start_date) & (df["Date"] <= end_date)
        ]
    else:
        st.error("Error: End date must fall after start date.")
        filtered_df = df
    return filtered_df


def get_launches_for_dashboard(db: Database) -> pd.DataFrame:
    """Get the launches from the database. Store in session state.

    Args:
        db (Database): The VGS database class.

    Returns:
        pd.DataFrame: The launches DataFrame."""
    # Fetch data from MongoDB
    if "df" not in st.session_state:
        st.session_state['df'] = db.get_launches_dataframe()

    # Ensure the data is not empty by preallocating the DataFrame.
    if st.session_state['df'].empty:
        # Make a dictionary of one row to display the columns.
        st.session_state['df'] = db.dummy_launches_dataframe()
        logging.error("No data found in the database, using dummy data.")
        st.error("No data found in the database, using dummy data.")
    return st.session_state['df']


def refresh_data():
    """Refresh the data in the session state."""
    logger.info("Refreshing data.")
    db = st.session_state["log_sheet_db"]
    get_launches_for_dashboard(db)
    st.toast("Data Refreshed!", icon="✅")


def show_data_dashboard(db: Database):
    """Display the dashboard.

    Args:
        db (Database): Database class for the VGS."""
    # Set the page title.
    vgs = db.client.db_user.username.upper()
    st.title(f"{vgs} Dashboard")

    # Sidebar for page navigation
    pages = ["📈 Statistics", "📁 Upload Log Sheets",
             "🧮 Stats & GUR Helper", "🌍 All Data"]
    page = st.selectbox("Select a Page:", pages, key="select_page")

    # Get dataframe of launches.
    df = get_launches_for_dashboard(db)

    # Setup sidebar filters.
    st.sidebar.markdown("# Dashboard Filters")

    # Filter by AircraftCommander.
    commander = st.sidebar.selectbox(
        "Filter by AircraftCommander",
        sorted(df["AircraftCommander"].unique()),
        index=None,
        help="Select the AircraftCommander to filter by.",
        placeholder="All",
        key="filter_commander"
    )

    # Create a list of quarters from the data.
    quarters = df["Date"].dt.to_period("Q").unique()

    # Filter by quarter.
    st.sidebar.markdown("## Quarterly Summary")
    quarter = st.sidebar.selectbox(
        "Select Quarter",
        quarters,
        index=None,
        help="Select the quarter to display.",
        key="filter_quarter"
    )

    # Add a date filter to the sidebar.
    filtered_df = date_filter(df)

    match page:
        case "📈 Statistics":
            # Refresh data button.
            if st.button("🔃 Refresh Data", key="refresh"):
                refresh_data()

            # Display metrics for financial year.
            show_launch_delta_metric(filtered_df)

            left, right = st.columns(2, gap="medium")
            with left:
                # Plot the number of launches by unique AircraftCommander.
                plot_launches_by_commander(filtered_df)
            with right:
                # Plot the ten unique longest flight times
                plot_longest_flight_times(filtered_df)
                # Plot the pie chart to show launches per duty
                plot_duty_pie_chart(filtered_df)

            # Plot the number of launches per month
            plot_monthly_launches(filtered_df)

            # Plot number of GIFs flown.
            plot_gif_bar_chart(filtered_df)

            # Logbook helper by AircraftCommander.
            show_logbook_helper(filtered_df, commander)

            # Filter the data by the selected quarter.
            if quarter and commander:
                quarterly_summary(filtered_df, commander, quarter)

        case "🌍 All Data":
            # Plot all launches in a table.
            plot_all_launches(filtered_df)

        case "🧮 Stats & GUR Helper":
            # Show statistics and glider utilisation return helpers.
            # Stats helpers.
            st.header("Stats Helpers")
            left, right = st.columns(2, gap="medium")
            with left:
                # Show the first and last launch time table.
                plot_firstlast_launch_table(filtered_df)
                # Show number of GIFs flown by day.
                table_gifs_per_date(filtered_df)
            with right:
                # Show launches by sortie type.
                launches_by_type_table(filtered_df)

            # GUR helpers.
            st.header("GUR Helpers")
            left, right = st.columns(2, gap="medium")
            with left:
                generate_aircraft_weekly_summary(filtered_df)
                aircraft_flown_per_day(filtered_df)
            with right:
                generate_aircraft_daily_summary(filtered_df)
                launches_daily_summary(filtered_df)

        case "📁 Upload Log Sheets":
            # Text to display the upload log sheets page.

            # Display the upload log sheets page.
            files = st.file_uploader(
                "Upload log sheets below. Existing files will be updated.",
                type=["xlsx"],
                accept_multiple_files=True,
                key="upload_log_sheets",
                on_change=None,
                help="Upload the log sheets to update the dashboard.",
            )

            if files:
                # Upload the log sheets and refresh data.
                upload_log_sheets(files)
                refresh_data()


def login(username: str, password: str):
    """Login to the dashboard."""
    try:
        # Create the DB user.
        db_user = DbUser(
            username=username,
            password=password,
            uri=st.secrets["MONGO_URI"],
        )
    except ValueError as e:
        # Handle where username or password is empty.
        st.error(str(e))
        return

    # Validate the password.
    client = Client(db_user)
    if client.log_in():
        # User is authenticated remove the form.
        st.session_state["authenticated"] = True
        st.session_state["log_sheet_db"] = Database(
            client=client,
            database_name=username
        )
        st.toast("Login successful")
        st.rerun()
    else:
        st.error("Invalid Password")


def authenticate():
    """Prompt and authenticate."""
    # Add auth to session state.
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return

    # Login form.
    with st.form(key="login_form"):
        st.text_input("Username", help="VGS e.g. '661vgs'", key="username")
        st.text_input("Password", type="password", key="password")
        submitted = st.form_submit_button("Enter")

        if submitted:
            login(
                username=st.session_state["username"],
                password=st.session_state["password"],
            )


def configure_app(LOGO_PATH: Path):
    """Configure the Streamlit app.

    Args:
        LOGO_PATH (Path): The path to the logo."""
    # Set the page title.
    st.set_page_config(
        page_title="VGS Dashboard",
        page_icon=str(LOGO_PATH),
        layout="centered",
        initial_sidebar_state="expanded",
    )


def main():
    """Main Streamlit App Code."""
    # Confiure the Streamlit app.
    configure_app(LOGO_PATH)
    show_logo(LOGO_PATH)

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


def display_dashboard():
    """Run the Streamlit app."""
    subprocess.run(["streamlit", "run", "src/dashboard/main.py"],
                   check=True)


if __name__ == '__main__':
    main()

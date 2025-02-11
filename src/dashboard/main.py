"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

# Import modules.
import sys
import os
import subprocess
import logging
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
from dashboard.plots import table_all_launches, quarterly_summary  # noqa: E402
from dashboard.plots import show_logbook_helper  # noqa: E402
from dashboard.plots import plot_firstlast_launch_table  # noqa: E402
from dashboard.plots import launches_by_type_table  # noqa: E402
from dashboard.plots import table_aircraft_weekly_summary  # noqa: E402
from dashboard.plots import generate_aircraft_daily_summary  # noqa: E402
from dashboard.plots import show_launch_delta_metric, show_logo  # noqa: E402
from dashboard.plots import aircraft_flown_per_day  # noqa: E402
from dashboard.plots import launches_daily_summary  # noqa: E402
from dashboard.plots import table_gifs_per_date  # noqa: E402
from dashboard.plots import plot_gif_bar_chart  # noqa: E402
from dashboard.plots import table_aircraft_totals  # noqa: E402
from dashboard.plots import table_gur_summary  # noqa: E402
from dashboard.utils import LOGO_PATH, upload_log_sheets  # noqa: E402
from dashboard.utils import date_filter  # noqa: E402

# Set up logging.
logger = logging.getLogger(__name__)


def get_launches_for_dashboard(db: Database) -> pd.DataFrame:
    """Get the launches from the database. Store in session state.

    Args:
        db (Database): The VGS database class.

    Returns:
        pd.DataFrame: The launches DataFrame."""
    # Fetch data from MongoDB
    st.session_state['df'] = db.get_launches_dataframe()

    # Ensure the data is not empty by preallocating the DataFrame.
    if st.session_state['df'].empty:
        # Make a dictionary of one row to display the columns.
        st.session_state['df'] = db.dummy_launches_dataframe()
        logging.error("No data found in the database, using dummy data.")
        st.error("No data found in the database, using dummy data.")
    return st.session_state['df']


def get_aircraft_for_dashboard(db: Database) -> pd.DataFrame:
    """Fetch the aircraft data from the database.

    Args:
        db (Database): The VGS database class.

    Returns:
        pd.DataFrame: The aircraft DataFrame."""
    # Fetch data from MongoDB.
    st.session_state['aircraft_df'] = db.get_aircraft_info()

    # Ensure the data is not empty by preallocating the DataFrame.
    if st.session_state['aircraft_df'].empty:
        # Make a dictionary of one row to display the columns.
        st.session_state['aircraft_df'] = db.dummy_aircraft_info_dataframe()
        logging.error("No AC data found in the database, using dummy data.")
        st.error("No aircraft data found in the database, using dummy data.")
    return st.session_state['aircraft_df']


def refresh_data():
    """Refresh the data in the session state."""
    logger.info("Refreshing data.")
    db = st.session_state["log_sheet_db"]
    st.session_state['df'] = get_launches_for_dashboard(db)
    st.session_state['aircraft_df'] = get_aircraft_for_dashboard(db)
    st.toast("Data Refreshed!", icon="✅")


def show_data_dashboard(db: Database):
    """Display the dashboard.

    Args:
        db (Database): Database class for the VGS."""
    # Set the page title.
    vgs = db.database_name.upper()
    st.title(f"{vgs} Dashboard")

    # Sidebar for page navigation
    pages = ["📈 Statistics", "📁 Upload Log Sheets",
             "🧮 Stats & GUR Helper", "🌍 All Data"]
    page = st.selectbox("Select a Page:", pages, key="select_page")

    # Get dataframe of launches and aircraft info.
    if "df" not in st.session_state:
        st.session_state['df'] = get_launches_for_dashboard(db)

    if "aircraft_df" not in st.session_state:
        st.session_state['aircraft_df'] = get_aircraft_for_dashboard(db)

    # Get the data from the session state.
    df = st.session_state['df']
    aircraft_df = st.session_state['aircraft_df']

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
                quarterly_summary(df, commander, quarter)

        case "🌍 All Data":
            # Plot all launches. Filter by AircraftCommander and date if
            # selected.
            if commander:
                commander_df = filtered_df[
                    filtered_df['AircraftCommander'] == commander
                ]
            else:
                commander_df = filtered_df
            table_all_launches(commander_df)

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
            st.divider()
            st.header("GUR Helpers")
            table_gur_summary(aircraft_df, df)
            left, right = st.columns(2, gap="medium")
            with left:
                table_aircraft_totals(aircraft_df)
                table_aircraft_weekly_summary(filtered_df)
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
        st.session_state["client"] = client
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


def set_db():
    """Set the database to use. Called when the user selects a database."""
    # Get the previous database name.
    if "log_sheet_db" in st.session_state:
        previous_db_name = st.session_state['log_sheet_db'].database_name
    else:
        previous_db_name = st.session_state['db_name']

    # Set the database to use.
    st.session_state["log_sheet_db"] = Database(
        client=st.session_state["client"],
        database_name=st.session_state["db_name"]
    )

    # Check if the selected DB name is different from the current one.
    if st.session_state['db_name'] != previous_db_name:
        # Refresh the data.
        refresh_data()


def choose_db(client: Client) -> Database:
    """Choose the database to use.

    Args:
        client (Client): The client object."""
    # If more than one database is available, display a select box.
    if all(db == client.db_user.username for db in client.available_databases):
        # Use the default database.
        st.session_state["db_name"] = client.default_database
        set_db()
    else:
        # Display a select box to choose the database.
        st.selectbox(
            "Select the database to use:",
            client.available_databases,
            index=None,
            help="Select the database to use.",
            key="db_name",
            on_change=set_db
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
            # Choose the database to use.
            choose_db(client=st.session_state["client"])

            if "log_sheet_db" in st.session_state:
                # Display dashboard.
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

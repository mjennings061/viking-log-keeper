"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

# Import modules.
import sys
import subprocess
from datetime import datetime, timedelta    # noqa: F401
from pathlib import Path
import streamlit as st
from extra_streamlit_components import CookieManager
import pandas as pd
import logging

# User defined modules. We need to add the parent directory to the path
# to allow running the script from the command line (i.e what streamlit does).
sys.path.append(str(Path(__file__).resolve().parents[1]))
from log_keeper.get_config import LogSheetConfig    # noqa: E402
from dashboard.plots import plot_duty_pie_chart  # noqa: E402
from dashboard.plots import plot_launches_by_commander  # noqa: E402
from dashboard.plots import plot_longest_flight_times  # noqa: E402
from dashboard.plots import plot_monthly_launches  # noqa: E402
from dashboard.plots import plot_all_launches, quarterly_summary  # noqa: E402
from dashboard.plots import show_logbook_helper   # noqa: E402
from dashboard.plots import plot_firstlast_launch_table  # noqa: E402
from dashboard.plots import launches_by_type_table  # noqa: E402
from dashboard.plots import generate_aircraft_weekly_summary  # noqa: E402
from dashboard.plots import generate_aircraft_daily_summary  # noqa: E402
from dashboard.auth import AuthConfig   # noqa: E402
from dashboard.plots import show_launch_delta_metric  # noqa: E402
from dashboard.plots import show_logo  # noqa: E402
from dashboard.utils import LOGO_PATH  # noqa: E402

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
    st.title(f"{vgs} Dashboard")

    # Sidebar for page navigation
    pages = ["📈 Statistics", "🧮 Stats & GUR Helper", "🌍 All Data"]
    page = st.selectbox("Select a Page:", pages)

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
            with right:
                # Show launches by sortie type.
                launches_by_type_table(filtered_df)

            # GUR helpers.
            st.header("GUR Helpers")
            left, right = st.columns(2, gap="medium")
            with left:
                generate_aircraft_weekly_summary(filtered_df)
            with right:
                generate_aircraft_daily_summary(filtered_df)


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
    st.subheader("Volunteer Gliding Squadron Dashboard")
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
            try:
                cookie_manager = CookieManager()
                cookie_manager.delete("vgs_auth")
            except Exception:  # pylint
                logging.error("Failed to delete cookie.", exc_info=True)


def display_dashboard():
    """Run the Streamlit app."""
    subprocess.run(["streamlit", "run", "src/dashboard/main.py"],
                   check=True)


if __name__ == '__main__':
    main()

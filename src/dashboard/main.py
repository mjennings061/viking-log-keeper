"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

# Import modules.
import sys
import os
import subprocess
import streamlit as st
import pandas as pd
from pathlib import Path

# Ensure the src directory is in the sys.path.
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if src_path not in sys.path:
    sys.path.append(src_path)

# User defined modules.
from log_keeper.get_config import DbUser, Client, Database  # noqa: E402
from dashboard import logger    # noqa: E402
from dashboard.plots import (   # noqa: E402
    plot_duty_pie_chart,
    plot_launches_by_commander,
    plot_longest_flight_times,
    plot_monthly_launches,
    table_all_launches,
    quarterly_summary,
    show_logbook_helper,
    plot_firstlast_launch_table,
    launches_by_type_table,
    table_aircraft_weekly_summary,
    generate_aircraft_daily_summary,
    show_single_metrics,
    show_logo,
    aircraft_flown_per_day,
    launches_daily_summary,
    table_gifs_per_date,
    plot_gif_bar_chart,
    table_aircraft_totals,
    table_gur_summary,
    table_solo_dual_summary,
    ops_form_helper,
)
from dashboard.weather import weather_page  # noqa: E402
from dashboard.utils import (   # noqa: E402
    LOGO_PATH,
    upload_log_sheets,
    date_filter,
    get_prefilled_log_sheet,
    update_template_from_upload,
)
from dashboard.session import (   # noqa: E402
    COOKIE_NAME,
    clear_auth_cookie,
    cookie_expiry,
    decrypt_credentials,
    encrypt_credentials,
    get_cookie_manager,
    persistence_available,
)


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
        logger.error("No data found in the database, using dummy data.")
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
        logger.error("No AC data found in the database, using dummy data.")
        st.error("No aircraft data found in the database, using dummy data.")
    return st.session_state['aircraft_df']


def get_personal_df(filtered_df: pd.DataFrame, client: Client) -> pd.DataFrame:
    """Combine launches from CGS if any VGS Aircraft Commanders appear
    in CGS data."""

    if filtered_df.empty:
        return filtered_df

    # Extract all unique AircraftCommanders from VGS data
    df = st.session_state['df']
    ac_names = (
        df["AircraftCommander"]
        .unique()
    )

    # ✅ Initialize if not already set
    if "cgs_match_count" not in st.session_state:
        st.session_state["cgs_match_count"] = {}

    # Reset CGS match count
    st.session_state["cgs_match_count"].clear()

    if "cgs" in client.available_databases:
        try:
            cgs_db = Database(client, "cgs")
            cgs_df = cgs_db.get_launches_dataframe()

            # Filter CGS where either role matches any AircraftCommander
            cgs_user_df = cgs_df[
                cgs_df["AircraftCommander"].isin(ac_names) |
                cgs_df["SecondPilot"].isin(ac_names)
            ]

            # Count matches per name
            for name in ac_names:
                count = cgs_user_df[
                    (cgs_user_df["AircraftCommander"] == name) |
                    (cgs_user_df["SecondPilot"] == name)
                ].shape[0]
                st.session_state["cgs_match_count"][name] = count

            if not cgs_user_df.empty:
                return pd.concat([filtered_df, cgs_user_df], ignore_index=True)
        except Exception:
            st.error("Failed to pull or filter CGS launches.")

    return filtered_df


def refresh_data():
    """Refresh the data in the session state."""
    logger.info("Refreshing data.")
    db = st.session_state["log_sheet_db"]
    st.session_state['df'] = get_launches_for_dashboard(db)
    st.session_state['aircraft_df'] = get_aircraft_for_dashboard(db)
    st.toast("Data Refreshed!", icon="✅")


def show_log_sheets_page(db: Database, aircraft_df: pd.DataFrame):
    """Render Log Sheets page: pre-filled download, template update and sheet upload.

    Args:
        db (Database): The VGS database class.
        aircraft_df (pd.DataFrame): Aircraft info for the brought-forward
            lookup and the aircraft drop-down."""
    # Download a pre-filled 2965D for a chosen aircraft.
    st.subheader("⬇️ Download pre-filled log sheet")
    if not aircraft_df.empty:
        # Only offer the most recently flown aircraft.
        recent = (
            aircraft_df.dropna(subset=["Date", "Aircraft"])
            .sort_values("Date", ascending=False)
            .drop_duplicates("Aircraft")
        )
        known_aircraft = sorted(recent["Aircraft"].head(6))
    else:
        known_aircraft = []
    chosen = st.selectbox(
        "Aircraft",
        known_aircraft,
        index=None,
        accept_new_options=True,
        placeholder="Select or type an aircraft, e.g. ZE683",
        key="prefill_aircraft",
        help="Pick a known aircraft or type a new tail number.",
    )
    if chosen:
        result = get_prefilled_log_sheet(
            db, chosen.strip().upper(), aircraft_df)
        if result:
            data, filename = result
            st.download_button(
                "Download pre-filled log sheet",
                data=data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet",
                key="download_prefilled",
            )

    # Replace the stored template (holds squadron-specific INPUT_DATA).
    with st.expander("⚙️ Update log sheet template"):
        template_file = st.file_uploader(
            "Upload a new 2965D template (.xltx/.xlsx) with the "
            "INPUT_DATA sheet filled in.",
            type=["xltx", "xlsx"],
            key="template_upload",
        )
        if template_file and st.button("Store template", key="store_template"):
            update_template_from_upload(db, template_file)

    st.divider()

    # Upload completed log sheets.
    st.subheader("⬆️ Upload completed log sheets")
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
        success = upload_log_sheets(files)
        refresh_data()
        # Only redirect on a successful upload.
        if success:
            # Flag a redirect to the stats page.
            st.session_state["redirect_to_stats"] = True
            st.rerun()


def show_data_dashboard(db: Database):
    """Display the dashboard.

    Args:
        db (Database): Database class for the VGS."""
    # Set the page title.
    logger.info("Displaying %s dashboard.", db.database_name)
    vgs = db.database_name.upper()
    st.title(f"{vgs} Dashboard")

    # Sidebar for page navigation
    pages = ["📈 Statistics", "📁 Log Sheets",
             "🧮 Stats & GUR Helper", "⛅ Weather", "🌍 All Data"]
    # Honour a redirect after a log sheet upload before the widget is instantiated.
    if st.session_state.pop("redirect_to_stats", False):
        st.session_state["select_page"] = "🧮 Stats & GUR Helper"
    page = st.selectbox("Select a Page:", pages, key="select_page")

    # Get dataframe of launches and aircraft info.
    if "df" not in st.session_state:
        logger.debug("Fetching launches for dashboard.")
        st.session_state['df'] = get_launches_for_dashboard(db)

    if "aircraft_df" not in st.session_state:
        logger.debug("Fetching aircraft info for dashboard.")
        st.session_state['aircraft_df'] = get_aircraft_for_dashboard(db)

    # Get the data from the session state.
    df = st.session_state['df']
    aircraft_df = st.session_state['aircraft_df']

    # Setup sidebar filters.
    st.sidebar.markdown("# Dashboard Filters")

    # Filter by AircraftCommander.
    commander = st.sidebar.selectbox(
        "Filter by Pilot",
        sorted(df["AircraftCommander"].unique()),
        index=None,
        help="Select the pilot to filter by.",
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

    # Add a date filter to the sidebar (this will apply to both DataFrames)
    filtered_df = date_filter(df, key="main_filter")

    # Combine CGS launches if the user flew there, then apply the same filter
    personal_df = get_personal_df(filtered_df, st.session_state["client"])

    match page:
        case "📈 Statistics":
            # Refresh data button.
            if st.button("🔃 Refresh Data", key="refresh"):
                refresh_data()

            # Display metrics for financial year.
            show_single_metrics(filtered_df)

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
            show_logbook_helper(personal_df, commander)
            # Show CGS match info if applicable
            if (
                commander
                and "cgs_match_count" in st.session_state
                and commander in st.session_state["cgs_match_count"]
            ):
                match_count = st.session_state["cgs_match_count"][commander]
                if match_count > 0:
                    st.info(f"CGS launches for {commander}: {match_count}")

            # Show solo/dual launch summary for selected pilot
            table_solo_dual_summary(personal_df, commander)

            # Filter the data by the selected quarter.
            if quarter and commander:
                personal_df = get_personal_df(
                    filtered_df=df,
                    client=st.session_state["client"]
                )
                quarterly_summary(personal_df, commander, quarter)

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

            # Stats return - summarise the last flying day by default.
            ops_form_helper(df)

            # Hide the detailed tables behind a toggle.
            if st.toggle("Show more stats", key="more_stats_shown"):
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

        case "⛅ Weather":
            weather_page(db, filtered_df)

        case "📁 Log Sheets":
            show_log_sheets_page(db, aircraft_df)


def login(username: str, password: str):
    """Login to the dashboard.

    Args:
        username (str): The VGS username.
        password (str): The VGS password."""
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
        # Stash the encrypted credentials. main() writes the cookie on the next
        # (completing) run - setting it here then immediately calling st.rerun()
        # drops it, because the set-component never gets to render.
        st.session_state["_auth_token"] = encrypt_credentials(username, password)
        # A fresh login cancels any pending logout from earlier this session.
        st.session_state.pop("_logging_out", None)
        st.toast("Login successful")
        st.rerun()
    else:
        st.error("Invalid Password")


def restore_session(cookie_manager):
    """Restore a login from the auth cookie after a page refresh.

    Args:
        cookie_manager: The cookie manager component."""
    # Nothing to do if already authenticated this session.
    if st.session_state.get("authenticated"):
        return

    # A logout is pending or done this session: never restore from the cookie.
    # _process_logout() owns deleting it; we must not race that by re-reading.
    if st.session_state.get("_logging_out"):
        return

    # The cookie iframe reports nothing on the first Cloud run; give it one
    # rerun to deliver cookies before falling through to the login form.
    cookies = cookie_manager.get_all()
    if not cookies and not st.session_state.get("_cookies_settled"):
        st.session_state["_cookies_settled"] = True
        st.rerun()

    token = cookie_manager.get(COOKIE_NAME)
    credentials = decrypt_credentials(token) if token else None
    if not credentials:
        return

    username, password = credentials
    try:
        client = Client(DbUser(
            username=username,
            password=password,
            uri=st.secrets["MONGO_URI"],
        ))
    except ValueError:
        client = None

    if client and client.log_in():
        st.session_state["authenticated"] = True
        st.session_state["client"] = client
        st.session_state["_auth_token"] = token
        logger.info("Restored session for %s from cookie.", username)
    else:
        # Stale or invalid cookie - drop the connection and clear the cookie.
        if client:
            client.close()
        clear_auth_cookie(cookie_manager, key="del_stale")


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
        password_value = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter")

        if submitted:
            # Pass the password value directly from the variable
            login(
                username=st.session_state["username"],
                password=password_value,
            )


def _persist_cookie(cookie_manager):
    """Write the auth cookie once the login has settled.

    Args:
        cookie_manager: The cookie manager component."""
    token = st.session_state.get("_auth_token")
    if not token:
        return
    # Already stored - nothing to do.
    if cookie_manager.get(COOKIE_NAME) == token:
        return
    cookie_manager.set(
        COOKIE_NAME,
        token,
        key="set_auth",
        expires_at=cookie_expiry(),
        same_site="lax",  # Strict withholds the cookie on link/bookmark entry.
        secure=True,  # Bearer credential - never send over plain HTTP.
    )


def _process_logout(cookie_manager):
    """Delete the auth cookie on a completing run while a logout is pending."""
    if not st.session_state.get("_logging_out"):
        return
    # Overwrite the cookie expired on this completing run.
    clear_auth_cookie(cookie_manager, key="del_logout")
    # Keep _logging_out set so restore stays suppressed until login or reload.
    for key in ("authenticated", "client", "_auth_token"):
        st.session_state.pop(key, None)


def _logout_button():
    """Render a logout button pinned to the bottom of the sidebar."""
    st.sidebar.divider()
    if st.sidebar.button("🚪 Log out", use_container_width=True, key="logout"):
        # _process_logout() does the work next run, on a completing run.
        st.session_state["_logging_out"] = True
        st.rerun()


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
    elif set(client.available_databases) == {client.db_user.username, "cgs"}:
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
        initial_sidebar_state="auto",
        menu_items={
            "Report a Bug": (
                "https://github.com/mjennings061/viking-log-keeper/"
                "issues/new?template=BLANK_ISSUE"
            ),
            "About": (
                "https://github.com/mjennings061/viking-log-keeper"
            )
        }
    )


def main():
    """Main Streamlit App Code."""
    # Confiure the Streamlit app.
    configure_app(LOGO_PATH)
    show_logo(LOGO_PATH)

    # Cookie manager used to persist the login across page refreshes.
    cookie_manager = get_cookie_manager()

    # Warn once if persistence is unconfigured - the usual cause of logins not
    # surviving a refresh on Streamlit Cloud (COOKIE_SECRET missing from secrets).
    if not persistence_available() and not st.session_state.get("_warned_no_persist"):
        logger.warning(
            "COOKIE_SECRET is not set - login persistence is disabled. "
            "Add it under Settings -> Secrets to keep users logged in."
        )
        st.session_state["_warned_no_persist"] = True

    # Finish any pending logout before reading the cookie for restore.
    _process_logout(cookie_manager)

    # Restore a previous login from the encrypted auth cookie if present
    restore_session(cookie_manager)

    # Authenticate the user.
    authenticate()

    # User is authenticated display the dashboard.
    if st.session_state["authenticated"]:
        # Persist the login cookie now that we are on a run that completes.
        _persist_cookie(cookie_manager)
        try:
            # Choose the database to use.
            choose_db(client=st.session_state["client"])

            if "log_sheet_db" in st.session_state:
                # Display dashboard.
                show_data_dashboard(st.session_state["log_sheet_db"])
        except Exception:  # pylint: disable=broad-except
            logger.error("Failed to display dashboard.", exc_info=True)
            st.error("Failed to display dashboard.")

            # Clear the session state.
            st.session_state.clear()

        # Logout control, pinned to the bottom of the sidebar. Only shown if we
        # did not just clear the session due to an error above.
        if st.session_state.get("authenticated"):
            _logout_button()


def display_dashboard():
    """Run the Streamlit app."""
    logger.info("Running Streamlit app.")
    subprocess.run(["streamlit", "run", "src/dashboard/main.py"],
                   check=True)


if __name__ == '__main__':
    main()

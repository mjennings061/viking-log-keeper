"""utils.py - Utility functions for the Streamlit app."""

import logging
import pandas as pd
from pathlib import Path
import streamlit as st
from typing import List
from io import BytesIO
from datetime import datetime, timedelta

# User defined modules.
from log_keeper.ingest import ingest_log_sheet_from_upload, sanitise_log_sheets
from log_keeper.output import update_launches_collection, update_aircraft_info

# Get the logger instance.
logger = logging.getLogger(__name__)

# Set global variables.
LOGO_PATH = Path(__file__).resolve().parent / "media/2fts-logo.png"


def is_streamlit_running() -> bool:
    """Check if Streamlit is running.

    Returns:
        bool: True if Streamlit is running, False otherwise.
    """
    try:
        import streamlit as st
        # Check if Streamlit is running by accessing a Streamlit attribute
        if hasattr(st, 'runtime') and st.runtime.exists():
            return True
        else:
            return False
    except ImportError:
        return False


def main():
    """Run utils as a Streamlit app e.g.
    python -m streamlit run src/dashboard/utils.py"""
    # Create a Streamlit app.
    import streamlit as st
    st.title("Streamlit App")

    # Check if Streamlit is running.
    if is_streamlit_running():
        logger.info("Streamlit is running.")
        st.write("Streamlit is running.")
    else:
        logger.info("Streamlit is not running.")
        st.write("Streamlit is not running.")


def get_financial_year(df) -> int:
    """Get the financial year from the last df entry.

    Args:
        df (pd.DataFrame): The DataFrame to get the financial year from.

    Returns:
        int: The financial year"""
    # Check if the DataFrame is empty.
    if df.empty:
        return datetime.now().year

    # Get the last date in the DataFrame
    last_date = df['Date'].iloc[0]
    # Get the year from the last date
    if last_date.month >= 4:
        return last_date.year
    else:
        return last_date.year - 1


def filter_by_financial_year(df, year):
    """Filter DataFrame by financial year.

    Args:
        df (pd.DataFrame): The DataFrame to filter.
        year (int): The year to filter by.

    Returns:
        pd.DataFrame: The filtered DataFrame"""
    start_date = pd.Timestamp(year, 4, 1)  # Assuming FY starts from April 1st
    end_date = pd.Timestamp(year + 1, 3, 31)  # Assuming FY ends on March 31st
    filtered_df = df[
        (df['Date'] >= start_date) & (df['Date'] <= end_date)
    ].reset_index(drop=True)
    return filtered_df


def total_launches_for_financial_year(df, year) -> int:
    """Calculate total launches for a given financial year.

    Args:
        df (pd.DataFrame): The DataFrame to filter.
        year (int): The year to filter by.

    Returns:
        int: The total number of launches for the financial year"""
    filtered_df = filter_by_financial_year(df, year)
    return filtered_df.shape[0]  # Count number of rows (launches)


def delta_launches_previous_day(df) -> int:
    """Calculate the number of launches in the last day.

    Args:
        df (pd.DataFrame): The DataFrame to filter.

    Returns:
        int: The difference in launches between the last day"""
    # Check if the DataFrame is empty.
    if df.empty:
        return 0

    # Check if there are at least two dates in the DataFrame.
    if df['Date'].nunique() < 1:
        return 0

    # Sort the DataFrame by date and find numel of the last date.
    dates = df['Date'].sort_values(ascending=False).reset_index(drop=True)
    last_date = dates[0]
    last_date_df = dates[dates == last_date]
    delta = last_date_df.size
    return delta


def validate_log_sheet(file: BytesIO) -> bool:
    """Validate the log sheet file.

    Args:
        file (BytesIO): The log sheet file to validate.

    Returns:
        bool: True if the log sheet is valid, False otherwise."""
    # Contants.
    TEMPLATE_LOG_SHEET = "2965D_YYMMDD_ZEXXX.xlsx"
    MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB

    # Validate the file is an Excel file.
    if not file.name.endswith(".xlsx"):
        error_msg = f"Invalid file: {file.name}"
        st.warning(error_msg)
        logger.warning(error_msg)
        return False

    # Check for the template log sheet.
    if file.name == TEMPLATE_LOG_SHEET:
        error_msg = "Template log sheet detected."
        st.warning(error_msg)
        logger.warning(error_msg)
        return False

    # Check file size.
    if file.size > MAX_FILE_SIZE:
        error_msg = f"File size too large: {file.size} bytes."
        st.warning(error_msg)
        logger.warning(error_msg)
        return False

    # Checks pass.
    return True


def upload_log_sheets(files: List[BytesIO]):
    """Upload multiple log sheets to the database.

    Args:
        files (List[BytesIO]): The log sheet files to upload."""
    # Output preallocated list.
    log_sheet_list = []
    aircraft_info_list = []

    # Progress bar.
    n_files = len(files)
    logger.info("Processing %d log sheets...", int(n_files))
    st.toast(f"Processing {n_files} Log Sheets...", icon="⏳")
    progress_bar = st.progress(0, f"Uploading 0/{n_files}")

    for index, file in enumerate(files):
        # Update the progress bar.
        progress_bar.progress((index + 1) / n_files,
                              text=f"Uploading {index + 1}/{n_files}")

        # Validate the file is an Excel file.
        if not validate_log_sheet(file):
            continue

        try:
            # Read the log sheet to a DataFrame.
            sheet_df, aircraft_info = ingest_log_sheet_from_upload(file)

            # Append log sheets to a list of dataframes.
            log_sheet_list.append(sheet_df)
            aircraft_info_list.append(aircraft_info)
        except Exception:  # pylint
            warning_msg = f"Log sheet invalid: {file.name}"
            st.warning(warning_msg)
            logger.warning(warning_msg)

    # Update GUI elements.
    progress_bar.empty()

    # Process the uploaded log sheets.
    with st.status("Uploading to Database...", expanded=True) as status_text:

        # Concatenate the log sheets.
        st.write("Concatenating log sheets...")
        log_sheet_df = pd.concat(log_sheet_list, ignore_index=True)
        aircraft_info_df = pd.concat(aircraft_info_list, ignore_index=True)

        # Sanitise the log sheets.
        st.write("Santising log sheets...")
        collated_df = sanitise_log_sheets(log_sheet_df)

        try:
            # Upload the log sheets to the database.
            st.write("Uploading to DB...")
            update_launches_collection(
                launches_df=collated_df,
                db=st.session_state["log_sheet_db"]
            )
            update_aircraft_info(
                aircraft_info=aircraft_info_df,
                db=st.session_state["log_sheet_db"]
            )
            status_text.update(label="Log Sheets Uploaded!",
                               state="complete", expanded=False)

            # Display a success message.
            logger.info("Done uploading log sheets.")
            st.toast("Log Sheets Uploaded!", icon="✅")
        except Exception:  # pylint: disable=broad-except
            # Log the error.
            logger.error("Failed to upload log sheets.", exc_info=True)
            st.error("Failed to upload log sheets.")
            status_text.update(label="Failed to upload log sheets.",
                               state="error", expanded=True)


def gifs_flown_per_day(df: pd.DataFrame) -> pd.DataFrame:
    """Show a table of how many unique GIFs were flown each day

    Args:
        df (pd.DataFrame): The data to be displayed."""
    # Filter the data to only include GIFs.
    gif_df = df[df["Duty"] == "GIF"]

    # Get the total number of GIFs flown each day.
    grouped = gif_df.groupby([
        'Date',
        'Aircraft',
        'AircraftCommander',
        'SecondPilot'
    ], as_index=False).size()

    # Group by 'Date'. Count the number elements in the group.
    grouped = grouped.groupby('Date').agg(
        GIFsFlown=('size', 'count')
    ).reset_index()

    # Change the column name.
    grouped.columns = ['Date', 'GIFs Flown']

    # Sort by 'Date' in descending order.
    grouped = grouped.sort_values(by='Date', ascending=False)
    return grouped


def format_minutes_to_HHHH_mm(minutes):
    """Format minutes to HHHH:mm.

    Args:
        minutes (int): The number of minutes to format.

    Returns:
        str: The formatted time."""
    hours = int(minutes) // 60
    mins = int(minutes) % 60
    formatted = f"{hours:04}:{mins:02}"
    return formatted


def date_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter the data by date or financial year.

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

    # Get financial year from data.
    financial_year = get_financial_year(df)
    default_min_date = pd.Timestamp(year=financial_year, month=4, day=1)
    default_max_date = min(
        pd.Timestamp(year=financial_year + 1, month=3, day=31),
        max_date
    )

    # Option to filter by date or financial year.
    filter_option = st.sidebar.radio(
        "Filter by:",
        options=["Financial Year", "Date Range", "All Data"],
        index=0,
        help="Select the filter option"
    )

    if filter_option == "Date Range":
        # Use Streamlit's date_input with a range selection.
        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(default_min_date, default_max_date),
            min_value=min_date,
            max_value=max_date,
            help="Select the date range",
        )

        # Convert the date to a pandas datetime object.
        if len(date_range) > 1:
            start_date = pd.to_datetime(date_range[0])
            end_date = pd.to_datetime(date_range[1] + timedelta(days=1))
        else:
            start_date = min_date
            end_date = max_date

    elif filter_option == "All Data":
        # No filtering.
        start_date = min_date
        end_date = max_date

    else:
        # List all financial years in the data as a user selectable box.
        financial_years = sorted(df["Date"].apply(
            lambda x: x.year if x.month >= 4 else x.year - 1
        ).unique(), reverse=True)
        selected_year = st.sidebar.selectbox(
            "Select Financial Year",
            financial_years,
            index=financial_years.index(financial_year),
            help="Select the financial year to filter by."
        )

        # Filter by the selected financial year.
        start_date = pd.Timestamp(year=selected_year, month=4, day=1)
        end_date = pd.Timestamp(year=selected_year + 1, month=3, day=31)

    # Validate the date range.
    if start_date < end_date:
        # Filter the data by the date range.
        filtered_df = df[
            (df["Date"] >= start_date) & (df["Date"] <= end_date)
        ]
    else:
        st.error("Error: End date must fall after start date.")
        filtered_df = df

    # Sort by takeoff time.
    filtered_df = filtered_df.sort_values(by='TakeOffTime', ascending=False)
    return filtered_df


if __name__ == "__main__":
    main()

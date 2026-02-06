"""attendance.py - Attendance data extraction and processing.

This module handles reading attendance data from Excel roster files
and provides the attendance dashboard page.
"""

import calendar
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard import logger


def get_roster_file_paths(directory_path: str | Path) -> list[str]:
    """Get all Excel file paths from the specified directory.

    Args:
        directory_path: Path to the directory containing roster files.

    Returns:
        Sorted list of Excel file paths as strings.
    """
    base_dir = Path(directory_path)
    file_paths = sorted(base_dir.glob('*.xlsx'))
    return [str(path) for path in file_paths]


def get_all_years_attendance(directory_path: str | Path) -> pd.Series:
    """Extract and combine attendance data from all roster files.

    Args:
        directory_path: Path to directory containing yearly roster files.

    Returns:
        Combined Series with dates as index and attendance counts as values.
    """
    file_paths = get_roster_file_paths(directory_path)
    all_series = [xls_to_dataframe(path) for path in file_paths]
    combined_series = pd.concat(all_series).sort_index()
    return combined_series


def xls_to_dataframe(file_path: str) -> pd.DataFrame:
    """Extract attendance data from an Excel roster file.

    Args:
        file_path: Path to the Excel roster file.

    Returns:
        DataFrame with attendance data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not an .xlsx file.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix != ".xlsx":
        raise ValueError("Invalid file extension. Expected .xlsx")

    # Extract year from filename (e.g., "2023.xlsx" -> 2023)
    year = int(path.stem)

    with pd.ExcelFile(file_path) as xls:
        series_list = extract_attendance(xls, year=year)
        combined = pd.concat(series_list).sort_index()

    return combined


def extract_attendance(xls: pd.ExcelFile, year: int) -> list[pd.Series]:
    """Extract attendance data from all monthly sheets in a roster file.

    Args:
        xls: Excel file object containing monthly sheets.
        year: The year of the roster.

    Returns:
        List of Series, one per month with attendance data.
    """
    raw_all_months = pd.read_excel(xls, sheet_name=None, header=1)
    all_months = []

    # Map month numbers to names: {1: 'January', 2: 'February', ...}
    months_dict = {i: name for i, name in enumerate(calendar.month_name) if name}

    for month_num, month_name in months_dict.items():
        if month_name in raw_all_months:
            raw_series = sheet_df_to_series(raw_all_months[month_name])
            series = clean_data(raw_series, month_num, year)
            all_months.append(series)

    return all_months


def sheet_df_to_series(raw_df: pd.DataFrame) -> pd.Series:
    """Extract the attendance summary row from a monthly sheet.

    The function searches for the first row containing numeric summary
    values (attendance counts) after the Y/N attendance markers.

    Args:
        raw_df: Raw DataFrame from Excel sheet.

    Returns:
        Series with day numbers as index and attendance counts as values.

    Raises:
        ValueError: If no numeric summary row is found.
    """
    # Skip the first column (usually contains row labels)
    df = raw_df.iloc[:, 1:]

    # Find the summary row with numeric attendance counts
    staffing_idx = None
    for idx, row in df.iterrows():
        non_null = row.dropna()
        if len(non_null) > 0:
            numeric_count = sum(
                1 for val in non_null if isinstance(val, (int, float))
            )
            # At least 3 numeric values indicate a summary row
            if numeric_count >= 3:
                staffing_idx = idx
                break

    if staffing_idx is None:
        raise ValueError("No numeric summary row found in the dataframe")

    return df.iloc[staffing_idx].dropna()


def clean_data(sr: pd.Series, month: int, year: int) -> pd.Series:
    """Convert day numbers to date objects and filter invalid entries.

    Args:
        sr: Attendance series with day numbers as index.
        month: Month number (1-12).
        year: Year.

    Returns:
        Series with datetime index, excluding low attendance days.
    """
    # Convert index to numeric, filtering out non-numeric labels
    numeric_index = pd.to_numeric(sr.index, errors='coerce')
    sr = sr[numeric_index.notna()].copy()

    # Remove days with attendance <= 6 (likely invalid)
    sr = sr[sr > 6]

    # Get clean day numbers
    clean_days = pd.to_numeric(sr.index).astype(int)

    # Handle month boundary: if first entry is late in month, it's from previous month
    new_months = []
    for i, day in enumerate(clean_days):
        if i == 0 and day > 20:
            new_months.append(month - 1)
        else:
            new_months.append(month)

    # Convert to datetime index
    sr.index = pd.to_datetime({
        'year': year,
        'month': new_months,
        'day': clean_days
    })
    return sr


def attendance_page(launches_df: pd.DataFrame) -> None:
    """Display the attendance dashboard page.

    Args:
        launches_df: DataFrame containing launch data for correlation analysis.
    """
    # Import here to avoid circular import
    from dashboard.attendance_plots import (
        plot_attendance_vs_flight_time,
        attendance_table,
    )

    st.header("Attendance Summary")

    attendance_df = None

    with st.status("Fetching attendance data...", expanded=True) as status:
        try:
            attendance_dir = (
                Path(__file__).parent.parent.parent / 'rsc' / 'attendance_xls'
            )
            attendance_df = get_all_years_attendance(attendance_dir)
            st.session_state["attendance"] = True
            st.session_state["refresh_attendance"] = False

            status.update(
                label="Attendance data fetched successfully.",
                state="complete",
                expanded=False
            )
            logger.info("Attendance data fetched successfully.")
        except Exception as e:
            status.update(
                label="Error fetching attendance data.",
                expanded=True,
                state="error",
            )
            st.error(f"Error fetching attendance data: {e}")
            logger.error("Attendance data fetch failed: %s", e, exc_info=True)
            return

    if attendance_df is not None:
        st.subheader("Attendance Impact on Flying")
        plot_attendance_vs_flight_time(attendance_df, launches_df)
        attendance_table(attendance_df)


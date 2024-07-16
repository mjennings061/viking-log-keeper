"""utils.py - Utility functions for the Streamlit app."""

import sys
import logging
import pandas as pd
from pathlib import Path

# Set up logging.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a console handler and set the level to INFO.
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

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
        return 0

    # Get the last date in the DataFrame
    last_date = df['Date'].iloc[-1]
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
    return df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]


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


if __name__ == "__main__":
    main()

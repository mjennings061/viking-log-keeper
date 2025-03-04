"""weather.py - Plot weather data."""

# Module imports.
import pandas as pd
import streamlit as st

# User imports.
from dashboard.utils import get_weekends
from log_keeper.weather import WeatherFetcher
from log_keeper.get_config import Database


def weather_page(db: Database, df: pd.DataFrame):
    """Display the weather page.

    Args:
        db (Database): Database instance.
        df (pd.DataFrame): DataFrame containing the data."""
    st.header("Weather Summary")
    st.write("Weather summary will be displayed here.")

    # Get the date range from the DataFrame.
    start_date = df.index.min().date()
    end_date = df.index.max().date()

    if "weather_df" not in st.session_state:
        st.session_state.weather_df = get_weather_data(
            db=db,
            dates=get_weekends(start_date, end_date)
        )


def get_weather_data(db: Database, dates: pd.DateTimeIndex):
    """Fetch weather data for the given date range.

    Args:
        db (Database): Database instance.
        start_date (datetime): Start date.
        end_date (datetime): End date.

    Returns:
        pd.DataFrame: DataFrame containing the weather data."""
    # TODO: Implement the function to fetch weather data using WeatherFetcher.

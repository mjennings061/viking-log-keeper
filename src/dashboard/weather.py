"""weather.py - Plot weather data."""

# Module imports.
import time
import pandas as pd
import streamlit as st
from datetime import datetime
from typing import List

# User imports.
from dashboard import logger
from log_keeper.weather import WeatherFetcher
from log_keeper.get_config import Database
from log_keeper.output import weather_to_db


def weather_page(db: Database, df: pd.DataFrame):
    """Display the weather page.

    Args:
        db (Database): Database instance.
        df (pd.DataFrame): DataFrame containing the data."""
    st.header("Weather Summary")
    st.write("Weather summary will be displayed here.")

    if "weather_df" not in st.session_state:
        # Fetch weather data.
        weather_df = get_weather_data(db, df)

        # Update the session state with the weather data.
        st.session_state.weather_df = weather_df

    # Display the weather data.
    if st.session_state.weather_df is not None:
        # Display the weather data in a table.
        st.subheader("Weather Data")
        st.dataframe(
            st.session_state.weather_df,
            use_container_width=True,
            column_config={
                "datetime": st.column_config.DateColumn(
                    "Date", format="DD MMM YY HH:mm (ddd)"
                ),
                "temperature_2m": st.column_config.NumberColumn(
                    "Temperature (°C)", format="%.1f"
                ),
                "relative_humidity_2m": st.column_config.NumberColumn(
                    "Relative Humidity (%)", format="%.1f"
                ),
                "dew_point_2m": st.column_config.NumberColumn(
                    "Dew Point (°C)", format="%.1f"
                ),
                "precipitation": st.column_config.NumberColumn(
                    "Precipitation (mm)", format="%.1f"
                ),
                "surface_pressure": st.column_config.NumberColumn(
                    "Surface Pressure (hPa)", format="%.0f"
                ),
                "cloud_cover_low": st.column_config.NumberColumn(
                    "Cloud Cover Low (%)", format="%.0f"
                ),
                "wind_speed_10m": st.column_config.NumberColumn(
                    "Wind Speed (kn)", format="%.1f"
                ),
                "wind_direction_10m": st.column_config.NumberColumn(
                    "Wind Direction (°)", format="%.0f"
                ),
                "wind_gusts_10m": st.column_config.NumberColumn(
                    "Wind Gusts (kn)", format="%.1f"
                )
            }
        )

        # TODO: Add a plot of the weather data.

        # TODO: Compare the weather data with the flight data.

        # TODO: Calculate and show cloud base and wind speed vs launches.


def get_weather_data(db: Database, df: pd.DataFrame) -> pd.DataFrame:
    """Get weather data from the database or API.
    Args:
        db (Database): Database instance.
        df (pd.DataFrame): DataFrame containing the data.
    Returns:
        pd.DataFrame: DataFrame containing the weather data.
    """
    # Get the all dates from the DataFrame.
    dates = df["Date"].dt.date.unique().tolist()

    # Get weather data from the database.
    logger.info("Fetching weather data from the database.")
    weather_df = db.get_weather_dataframe()

    # Check if all dates are present in the weather data.
    if weather_df.empty:
        missing_dates = dates
    else:
        # TODO: Ensure this is working and not updating every time.
        missing_dates = [
                date for date in dates
                if date not in
                weather_df["Date"].dt.date.unique()
            ]

    # Check all 24 hours of weather are present for each date.
    if not weather_df.empty:
        dates_missing_hours = [
            date for date in weather_df["Date"].dt.date.unique()
            if len(weather_df[weather_df["Date"].dt.date == date]) != 24
        ]
        if dates_missing_hours:
            logger.info(
                "Missing hours for the following dates: \n"
                f"{dates_missing_hours.__str__()}")
            # Get the missing dates from the API.
            missing_dates.extend(dates_missing_hours)

    # If there are missing dates, fetch the weather data from the API.
    if missing_dates:
        # Get the missing dates from the API.
        logger.info(
            "Fetching missing weather data for dates: \n"
            f"{missing_dates.__str__()}")
        missing_weather_df = get_api_weather_data(
            db=db,
            dates=missing_dates
        )
        # Append the new data to the existing weather data.
        weather_df = pd.concat([weather_df, missing_weather_df])

        # Save the new data to the database.
        weather_to_db(
            weather_df=weather_df,
            db=db,
        )
    return weather_df


def get_api_weather_data(db: Database, dates: List[datetime.date]):
    """Fetch weather data for the given date range.

    Args:
        db (Database): Database instance.
        dates (List[datetime.date]): List of dates to fetch weather data.

    Returns:
        pd.DataFrame: DataFrame containing the weather data."""
    # Get the VGS location from the database.
    vgs_info = db.get_info()
    # Handle empty vgs_info.
    if vgs_info is None:
        st.warning("No VGS information available.")
        return

    # Get the latitude and longitude from the database.
    latitude = vgs_info["latitude"].iloc[0]
    longitude = vgs_info["longitude"].iloc[0]

    # Get weather data for the given dates.
    weather_data = []
    for date in dates:
        weather_fetcher = WeatherFetcher(
            latitude=latitude,
            longitude=longitude,
            start_date=date,
            end_date=date
        )
        # Add a delay to avoid hitting the API too quickly.
        # This is important to avoid being blocked by the API.
        time.sleep(0.2)
        weather_fetcher.hourly_df.dropna(inplace=True)
        if weather_fetcher.hourly_df.empty:
            st.warning(f"No weather data available for {date}.")
            continue
        weather_data.append(weather_fetcher.hourly_df)

    # Concatenate all DataFrames into a single DataFrame.
    if not weather_data:
        st.warning("No weather data available for the selected dates.")
        return pd.DataFrame()
    weather_data = pd.concat(weather_data)
    weather_data = weather_data.sort_index(ascending=False)
    return weather_data

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

        # Use the timezone from the data itself for display formatting
        display_df = st.session_state.weather_df.copy()
        display_df['datetime'] = display_df['datetime'].dt.tz_localize(None)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_order=[
                "datetime",
                "wind_direction_10m",
                "wind_speed_10m",
                "wind_gusts_10m",
                "cloud_cover_low"
                "precipitation",
                "temperature_2m",
                "dew_point_2m",
                "relative_humidity_2m",
                "surface_pressure",
            ],
            column_config={
                "datetime": st.column_config.DateColumn(
                    "Date", format="DD MMM YY HH:mm (ddd)", pinned=True
                ),
                "temperature_2m": st.column_config.NumberColumn(
                    "Temperature", format="%.1f °C"
                ),
                "relative_humidity_2m": st.column_config.NumberColumn(
                    "Relative Humidity", format="%.1f %%"
                ),
                "dew_point_2m": st.column_config.NumberColumn(
                    "Dew Point", format="%.1f °C"
                ),
                "precipitation": st.column_config.NumberColumn(
                    "Precipitation", format="%.1f mm"
                ),
                "surface_pressure": st.column_config.NumberColumn(
                    "Surface Pressure", format="%.0f hPa"
                ),
                "cloud_cover_low": st.column_config.NumberColumn(
                    "Low Cloud", format="%.0f %%"
                ),
                "wind_speed_10m": st.column_config.NumberColumn(
                    "Wind Speed", format="%.1f kts"
                ),
                "wind_direction_10m": st.column_config.NumberColumn(
                    "Wind Direction", format="%.0f °"
                ),
                "wind_gusts_10m": st.column_config.NumberColumn(
                    "Wind Gusts", format="%.1f kts"
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
                weather_df["datetime"].dt.date.unique()
            ]

    # Check all 24 hours of weather are present for each date.
    if not weather_df.empty:
        dates_missing_hours = [
            date for date in dates
            if len(weather_df[weather_df["datetime"].dt.date == date]) != 24
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

        # Merge the new data with the existing weather data
        if weather_df.empty:
            weather_df = missing_weather_df
        else:
            # Concatenate and keep only the latest data for duplicates
            weather_df = pd.concat([weather_df, missing_weather_df])
            weather_df = weather_df.drop_duplicates(
                subset=["datetime"],
                keep="last"
            )

        # Sort by datetime in descending order
        weather_df = weather_df.sort_values(
            by="datetime",
        ).reset_index(drop=True)

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
        if weather_fetcher.hourly_df.empty:
            st.warning(f"No weather data available for {date}.")
            continue
        weather_data.append(weather_fetcher.hourly_df)

    # Concatenate all DataFrames into a single DataFrame.
    if not weather_data:
        st.warning("No weather data available for the selected dates.")
        return pd.DataFrame()

    # Concatenate all DataFrames into a single DataFrame.
    weather_df = pd.concat(weather_data)
    weather_df = weather_df.sort_values(
        by="datetime",
    ).reset_index(drop=True)

    if weather_df.empty:
        st.warning("No weather data available for the selected dates.")
        return pd.DataFrame()
    return weather_df

"""weather.py - Plot weather data."""

import time
from datetime import date
from typing import Optional, List, Any

import pandas as pd
import streamlit as st

from dashboard import logger
from dashboard.utils import get_weekends
from dashboard.weather_plots import (
    plot_launch_vs_nonlaunch_weather,
    plot_weather_vs_flight_time,
    plot_wind_polar,
    weather_table,
)
from dashboard.weather_utils import calculate_cloud_base, weather_metadata
from log_keeper.get_config import Database
from log_keeper.output import weather_to_db
from log_keeper.weather import WeatherFetcher


# --- Cached API batch fetch ---
@st.cache_data(ttl="12h", show_spinner=True)
def fetch_weather_for_dates_cached(
    latitude: float, longitude: float, dates: tuple
) -> pd.DataFrame:
    """Fetch weather data for a batch of dates using the API, with caching.
    Args:
        latitude (float): Latitude of the site.
        longitude (float): Longitude of the site.
        dates (tuple): Tuple of datetime.date objects.
    Returns:
        pd.DataFrame: Concatenated weather data for all dates.
    """
    # Create a WeatherFetcher instance for each date and collect the data.
    logger.info("Fetching weather data for %d dates.", len(dates))
    all_data = []
    for day in dates:
        weather_fetcher = WeatherFetcher(
            latitude=latitude, longitude=longitude, weather_date=day
        )
        if not weather_fetcher.hourly_df.empty:
            all_data.append(weather_fetcher.hourly_df.copy())
        time.sleep(0.1)  # Throttle API requests to 600/minute

    # Concatenate all dataframes and sort by datetime.
    if all_data:
        return pd.concat(all_data).sort_values(by="datetime").reset_index(drop=True)
    return pd.DataFrame()


def weather_page(db: Database, launches_df: pd.DataFrame):
    """Display the weather page.

    Args:
        db (Database): Database instance.
        launches_df (pd.DataFrame): DataFrame containing the data."""
    st.header("Weather Summary")

    # Add a button to clear the cache in the sidebar
    with st.sidebar:
        st.divider()
        if st.button("Reset Weather Cache"):
            st.session_state["refresh_weather"] = True
            st.toast(
                "Weather data cache reset! New data will be fetched.",
                icon="✅",
            )
            st.cache_data.clear()
        st.info("Reset the cache to fetch the latest weather data from the API.")

    # Use session state to check if the weather data needs to be refreshed.
    # Get the weather data from the database or API.
    with st.status("Fetching weather data...", expanded=True) as status:
        try:
            # Always fetch new data from the database
            # (API caching will be handled separately)
            weather_df = get_weather_data(db=db, df=launches_df)
            st.session_state["weather"] = True
            st.session_state["refresh_weather"] = False

            # Calculate cloud base from weather data.
            weather_df = calculate_cloud_base(weather_df)
            status.update(
                label="Weather data fetched successfully.",
                expanded=False,
                state="complete",
            )
            logger.info("Weather data fetched successfully.")
        except Exception as e:
            status.update(
                label="Error fetching weather data.",
                expanded=True,
                state="error",
            )
            st.error(f"Error fetching weather data: {e}")
            return

    # Display the weather data.
    if weather_df is not None:
        # Plot weather vs launches
        st.subheader("Weather Impact on Flying")
        selected_metric = select_metric_to_plot()
        plot_weather_vs_flight_time(weather_df, launches_df, selected_metric)
        st.subheader("Weather on Launch vs Non-Launch Days")
        plot_launch_vs_nonlaunch_weather(weather_df, launches_df, selected_metric)
        # Display the weather data in a table.
        weather_table(weather_df)

        # Plot wind direction as a polar plot.
        st.subheader("Wind Direction")
        plot_wind_polar(weather_df)


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

    # Get all weekends and add any missing weekends to the dates.
    all_weekends = get_weekends(start_date=df["Date"].min(), end_date=df["Date"].max())
    dates.extend(all_weekends)
    dates = sorted(set(dates))

    # Calculate date range for optimised query
    start_date = min(dates)
    end_date = max(dates)

    # Get weather data from the database filtered by date range.
    logger.info("Fetching weather data from the database.")
    st.write(f"Fetching weather from the database for {start_date} to {end_date}...")
    weather_df = db.get_weather_dataframe_by_dates(start_date, end_date)

    # Check if all dates are present in the weather data.
    if weather_df.empty:
        missing_dates = dates
    else:
        # Check if all dates are present in the weather data.
        # Since we filtered at DB level, we only need to check the specific dates we
        # need
        existing_dates = set(weather_df["datetime"].dt.date.unique())
        missing_dates = list(set(dates) - existing_dates)

    # Check all 24 hours of weather are present for each date.
    if not weather_df.empty:
        # Create a set of dates with incomplete hourly data
        # Only check dates we actually need, since we already filtered at DB level
        date_hour_counts = weather_df.groupby(weather_df["datetime"].dt.date).size()
        dates_missing_hours = [
            date
            for date, count in date_hour_counts.items()
            if count < 22 and date in dates and date not in missing_dates
        ]
        if dates_missing_hours:
            # Get the missing dates from the API.
            logger.debug(
                "Missing hours for the following dates: \n"
                f"{dates_missing_hours.__str__()}"
            )
            missing_dates.extend(dates_missing_hours)

    # If there are missing dates, fetch the weather data from the API.
    if missing_dates:
        # Get the missing dates from the API.
        logger.debug(
            "Fetching missing weather data for dates: \n" f"{missing_dates.__str__()}"
        )
        logger.info("Fetching weather data for %d dates.", len(missing_dates))
        st.write(f"Fetching missing dates: {missing_dates} from the API...")
        missing_weather_df = get_api_weather_data(
            db=db, dates=missing_dates
        )

        # Merge the new data with the existing weather data
        if weather_df.empty:
            weather_df = missing_weather_df
        else:
            # Concatenate and keep only the latest data for duplicates
            weather_df = pd.concat([weather_df, missing_weather_df])
            weather_df = weather_df.drop_duplicates(subset=["datetime"], keep="last")

        # Sort by datetime in descending order
        weather_df = weather_df.sort_values(by="datetime", ascending=False).reset_index(
            drop=True
        )

        # Save the new data to the database.
        st.write("Saving new weather data to the database...")
        weather_to_db(weather_df=weather_df, db=db)
        st.toast("Weather data saved to the database.", icon="✅")

    # No need to filter again - we already got filtered data from DB
    # and any new data was merged appropriately
    return weather_df


def get_api_weather_data(db: Database, dates: List[date]) -> pd.DataFrame:
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
        return pd.DataFrame()

    # Get the latitude and longitude from the database.
    latitude = vgs_info["latitude"].iloc[0]
    longitude = vgs_info["longitude"].iloc[0]

    # Convert to tuple for cache key
    date_tuple = tuple(sorted(dates))
    weather_df = fetch_weather_for_dates_cached(latitude, longitude, date_tuple)

    if weather_df.empty:
        st.warning("No weather data available for the selected dates.")
        return pd.DataFrame()
    return weather_df


def select_metric_to_plot():
    """Select the metric to plot.
    Returns:
        str: Selected metric.
        str: Display name of the selected metric.
        str: Unit of the selected metric.
    """
    metric_options = list(weather_metadata.keys())
    metric_display_names = [
        weather_metadata[metric]["display_name"]
        for metric in metric_options
        if metric != "datetime"
    ]
    metric_options.remove("datetime")
    metric_display_name = st.selectbox(
        "Select weather metric to compare:",
        metric_display_names,
        index=0,
        key="compare_weather_metric",
    )

    # Lookup the selected metric in the metadata
    selected_metric = metric_options[metric_display_names.index(metric_display_name)]
    return selected_metric

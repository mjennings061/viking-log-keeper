"""weather.py - Plot weather data."""

# Module imports.
import time
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st

# User imports.
from log_keeper.get_config import Database
from log_keeper.output import weather_to_db
from log_keeper.weather import WeatherFetcher
from dashboard import logger
from dashboard.utils import get_weekends
from dashboard.weather_plots import (
    plot_launch_vs_nonlaunch_weather,
    plot_weather_vs_flight_time,
    plot_wind_polar,
    weather_table
)
from dashboard.weather_utils import (
    calculate_cloud_base,
    weather_metadata,
)


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
        st.info(
            "Reset the cache to fetch the latest weather data from the API."
        )

    # Use session state to check if the weather data needs to be refreshed.
    refresh = st.session_state.get("refresh_weather", False)
    weather = st.session_state.get("weather", False)

    # Get the weather data from the database or API.
    with st.status("Fetching weather data...", expanded=True) as status:
        try:
            # Decide whether to fetch new data or use cached data
            if refresh or not weather:
                # Fetch new data and store it in session state
                weather_df = get_weather_data(
                    db=db, df=launches_df, show_progress=True
                )
                st.session_state["weather"] = True
                st.session_state["refresh_weather"] = False
            else:
                # Use the cached function with launches dataframe attributes
                # This will trigger cache update when dates change.
                # Generate a hash of the unique dates in launches_df to
                # use as cache key
                launches_dates = tuple(
                    sorted(launches_df["Date"].dt.date.unique().tolist())
                )
                weather_df = get_cached_weather_data(
                    _db=db,
                    launches_df_hash=launches_dates,
                )

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
        plot_launch_vs_nonlaunch_weather(
            weather_df, launches_df, selected_metric
        )

        # Display the weather data in a table.
        weather_table(weather_df)

        # Plot wind direction as a polar plot.
        st.subheader("Wind Direction")
        plot_wind_polar(weather_df)


@st.cache_data(ttl="1h", show_spinner=False)
def get_cached_weather_data(
    _db: Database,  # Not hashed.
    launches_df_hash: str,
) -> pd.DataFrame:
    """Cached wrapper for get_weather_data that updates only
    when launches_df changes.

    Args:
        _db (Database): Database instance
        launches_df_hash: Hash value representing the launches dataframe

    Returns:
        Weather dataframe
    """
    # Create a dummy dataframe with the date range
    dummy_df = pd.DataFrame({"Date": list(pd.to_datetime(launches_df_hash))})
    logger.debug("Fetching weather from cache.")

    # Get weather data. Setting show_progress to False
    # to avoid showing the progress bar in the cache.
    # This fixes the streamlit cache error.
    return get_weather_data(_db, dummy_df, show_progress=False)


def get_weather_data(
    db: Database, df: pd.DataFrame, show_progress: bool = True
) -> pd.DataFrame:
    """Get weather data from the database or API.
    Args:
        db (Database): Database instance.
        df (pd.DataFrame): DataFrame containing the data.
        show_progress (bool): Whether to show progress bar.
    Returns:
        pd.DataFrame: DataFrame containing the weather data.
    """
    # Get the all dates from the DataFrame.
    dates = df["Date"].dt.date.unique().tolist()

    # Get all weekends and add any missing weekends to the dates.
    all_weekends = get_weekends(
        start_date=df["Date"].min(), end_date=df["Date"].max()
    )
    dates.extend(all_weekends)
    dates = sorted(set(dates))

    # Get weather data from the database.
    logger.info("Fetching weather data from the database.")
    if show_progress:
        st.write("Fetching weather data from the database...")
    weather_df = db.get_weather_dataframe()

    # Check if all dates are present in the weather data.
    if weather_df.empty:
        missing_dates = dates
    else:
        # Check if all dates are present in the weather data.
        missing_dates = list(
            set(dates) - set(weather_df["datetime"].dt.date.unique())
        )

    # Check all 24 hours of weather are present for each date.
    if not weather_df.empty:
        # Create a set of dates with incomplete hourly data
        date_hour_counts = weather_df.groupby(
            weather_df["datetime"].dt.date
        ).size()
        dates_missing_hours = set(
            date
            for date, count in date_hour_counts.items()
            if count < 22 and date in dates
        )
        # Remove dates that are already in missing_dates to avoid duplicates
        dates_missing_hours = dates_missing_hours - set(missing_dates)
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
            "Fetching missing weather data for dates: \n"
            f"{missing_dates.__str__()}"
        )
        logger.info(f"Fetching weather data for {len(missing_dates)} dates.")
        missing_weather_df = get_api_weather_data(
            db=db, dates=missing_dates, show_progress=show_progress
        )

        # Merge the new data with the existing weather data
        if weather_df.empty:
            weather_df = missing_weather_df
        else:
            # Concatenate and keep only the latest data for duplicates
            weather_df = pd.concat([weather_df, missing_weather_df])
            weather_df = weather_df.drop_duplicates(
                subset=["datetime"], keep="last"
            )

        # Sort by datetime in descending order
        weather_df = weather_df.sort_values(
            by="datetime", ascending=False
        ).reset_index(drop=True)

        # Save the new data to the database.
        weather_to_db(
            weather_df=weather_df,
            db=db,
        )
        if show_progress:
            st.toast(
                "Weather data saved to the database.",
                icon="✅",
            )

    # Filter the weather data to only include the dates for launches.
    weather_df = weather_df[weather_df["datetime"].dt.date.isin(dates)]
    return weather_df


def get_api_weather_data(
    db: Database, dates: List[datetime.date], show_progress: bool = True
) -> pd.DataFrame:
    """Fetch weather data for the given date range.

    Args:
        db (Database): Database instance.
        dates (List[datetime.date]): List of dates to fetch weather data.
        show_progress (bool): Whether to show progress bar.
    Returns:
        pd.DataFrame: DataFrame containing the weather data."""
    # Get the VGS location from the database.
    vgs_info = db.get_info()
    # Handle empty vgs_info.
    if vgs_info is None:
        if show_progress:
            st.warning("No VGS information available.")
        return pd.DataFrame()

    # Get the latitude and longitude from the database.
    latitude = vgs_info["latitude"].iloc[0]
    longitude = vgs_info["longitude"].iloc[0]

    # Get weather data for the given dates.
    weather_data = []

    # Create a progress bar
    if show_progress:
        progress_bar = st.progress(0)
        status_text = st.empty()

    for i_date, date in enumerate(dates):
        # Update progress bar and status text
        if show_progress:
            progress = i_date / len(dates)
            progress_bar.progress(progress)
            status_text.text(
                f"Fetching weather data for {date} ({i_date + 1}/{len(dates)})"
            )

        # Fetch weather data for the given date range.
        weather_fetcher = WeatherFetcher(
            latitude=latitude, longitude=longitude, weather_date=date
        )
        # Add a delay to avoid hitting the API too quickly.
        # This is important to avoid being blocked by the API.
        time.sleep(0.2)
        if weather_fetcher.hourly_df.empty:
            if show_progress:
                st.warning(f"No weather data available for {date}.")
            continue
        weather_data.append(weather_fetcher.hourly_df)

    # Complete the progress bar
    if show_progress:
        progress_bar.progress(1.0)
        status_text.text("Weather data fetching complete!")
        time.sleep(0.5)
        status_text.empty()
        progress_bar.empty()

    # Concatenate all DataFrames into a single DataFrame.
    if not weather_data:
        if show_progress:
            st.warning("No weather data available for the selected dates.")
        return pd.DataFrame()

    # Concatenate all DataFrames into a single DataFrame.
    weather_df = pd.concat(weather_data)
    weather_df = weather_df.sort_values(
        by="datetime",
    ).reset_index(drop=True)

    if weather_df.empty:
        if show_progress:
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
    selected_metric = metric_options[
        metric_display_names.index(metric_display_name)
    ]
    return selected_metric

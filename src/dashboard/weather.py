"""weather.py - Plot weather data."""

# Module imports.
import time
import pandas as pd
import streamlit as st
import altair as alt
from datetime import datetime
from typing import List

# User imports.
from dashboard import logger
from dashboard.utils import get_weekends
from log_keeper.weather import WeatherFetcher
from log_keeper.get_config import Database
from log_keeper.output import weather_to_db


weather_metadata = {
    "wind_speed_10m": {
        "description": "Wind speed at 10 meters above ground level.",
        "unit": "kts",
        "display_name": "Wind Speed",
    },
    "wind_direction_10m": {
        "description": "Wind direction at 10 meters above ground level.",
        "unit": "degrees",
        "display_name": "Wind Direction",
    },
    "wind_gusts_10m": {
        "description": "Wind gusts at 10 meters above ground level.",
        "unit": "kts",
        "display_name": "Wind Gusts",
    },
    "cloud_base_ft": {
        "description": "Cloud base height in feet.",
        "unit": "ft",
        "display_name": "Cloud Base",
    },
    "cloud_cover_low": {
        "description": "Low cloud cover percentage.",
        "unit": "%",
        "display_name": "Low Cloud Cover",
    },
    "precipitation": {
        "description": "Precipitation amount.",
        "unit": "mm",
        "display_name": "Precipitation",
    },
    "temperature_2m": {
        "description": "Temperature at 2 meters above ground level.",
        "unit": "°C",
        "display_name": "Temperature",
    },
    "dew_point_2m": {
        "description": "Dew point temperature at 2 meters above ground level.",
        "unit": "°C",
        "display_name": "Dew Point",
    },
    "relative_humidity_2m": {
        "description": "Relative humidity at 2 meters above ground level.",
        "unit": "%",
        "display_name": "Relative Humidity",
    },
    "surface_pressure": {
        "description": "Surface pressure.",
        "unit": "hPa",
        "display_name": "Surface Pressure",
    },
    "datetime": {
        "description": "Date and time of the weather observation (Local).",
        "unit": "",
        "display_name": "Date",
    },
}


def weather_page(db: Database, launches_df: pd.DataFrame):
    """Display the weather page.

    Args:
        db (Database): Database instance.
        launches_df (pd.DataFrame): DataFrame containing the data."""
    st.header("Weather Summary")

    # Get the weather data from the database or API.
    with st.status("Fetching weather data...", expanded=True) as status:
        try:
            # Generate a hash of the unique dates in launches_df to
            # use as cache key
            launches_dates = tuple(
                sorted(launches_df["Date"].dt.date.unique().tolist())
            )

            # Use the cached function with launches dataframe attributes
            # This will trigger cache update when dates change.
            weather_df = get_cached_weather_data(
                _db=db,
                launches_df_hash=launches_dates,
            )

            # Calculate cloud base from weather data.
            weather_df = calculate_cloud_base(weather_df)
            status.update(
                label="Weather data fetched successfully.",
                expanded=False,
                state="complete"
            )
            logger.info("Weather data fetched successfully.")
        except Exception as e:
            status.update(
                label="Error fetching weather data.",
                expanded=True,
                state="error"
            )
            st.error(f"Error fetching weather data: {e}")
            return

    # Display the weather data.
    if weather_df is not None:
        # Display the weather data in a table.
        st.subheader("Weather Data")

        # Use the timezone from the data itself for display formatting
        display_df = weather_df.copy()
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
                "cloud_base_ft",
                "cloud_cover_low",
                "precipitation",
                "temperature_2m",
                "dew_point_2m",
                "relative_humidity_2m",
                "surface_pressure",
            ],
            column_config={
                "datetime": st.column_config.DatetimeColumn(
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
                "cloud_base_ft": st.column_config.NumberColumn(
                    "Cloud Base", format="%.0f ft"
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

        # Plot weather vs launches
        st.subheader("Wind Impact on Flying")
        plot_wind_vs_launches(weather_df, launches_df)

        st.subheader("Weather Impact on Flight Time")
        selected_metric = select_metric_to_plot()
        plot_weather_vs_flight_time(
            weather_df,
            launches_df,
            selected_metric
        )
        st.subheader("Weather on Launch vs Non-Launch Days")
        plot_launch_vs_nonlaunch_weather(
            weather_df,
            launches_df,
            selected_metric
        )

    # Add a button to clear the cache
    st.divider()
    col_clear, col_info = st.columns([1, 3])

    with col_clear:
        if st.button("Clear Weather Cache"):
            st.cache_data.clear()
            st.toast(
                "Weather data cache cleared! New data will be fetched.",
                icon="✅"
            )

    with col_info:
        st.info(
            "Clear the cache to fetch the latest weather data from the API."
        )


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
    dummy_df = pd.DataFrame({
        "Date": list(pd.to_datetime(launches_df_hash))
    })

    # Get weather data
    return get_weather_data(_db, dummy_df)


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
    all_weekends = get_weekends(
        start_date=df["Date"].min(),
        end_date=df["Date"].max()
    )
    dates.extend(all_weekends)
    dates = sorted(set(dates))

    # Get weather data from the database.
    logger.info("Fetching weather data from the database.")
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
            date for date, count in date_hour_counts.items()
            if count < 22 and date in dates
        )
        # Remove dates that are already in missing_dates to avoid duplicates
        dates_missing_hours = dates_missing_hours - set(missing_dates)
        if dates_missing_hours:
            # Get the missing dates from the API.
            logger.debug(
                "Missing hours for the following dates: \n"
                f"{dates_missing_hours.__str__()}")
            missing_dates.extend(dates_missing_hours)

    # If there are missing dates, fetch the weather data from the API.
    if missing_dates:
        # Get the missing dates from the API.
        logger.debug(
            "Fetching missing weather data for dates: \n"
            f"{missing_dates.__str__()}")
        logger.info(f"Fetching weather data for {len(missing_dates)} dates.")
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
        st.toast(
            "Weather data saved to the database.",
            icon="✅",
        )

    # Filter the weather data to only include the dates for launches.
    weather_df = weather_df[
        weather_df["datetime"].dt.date.isin(dates)
    ]
    return weather_df


def calculate_cloud_base(weather_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate cloud base from weather data.

    Args:
        weather_df (pd.DataFrame): DataFrame containing the weather data.

    Returns:
        pd.DataFrame: DataFrame with cloud base calculated."""
    # Check if the required columns are present
    cols_present = all(
        col in weather_df.columns
        for col in ["temperature_2m", "dew_point_2m"]
    )
    if not cols_present:
        st.warning("Missing required columns for cloud base calculation.")
        return weather_df

    # Calculate cloud base using spread between temperature and dew point
    # The formula is: spread * 400 feet per degree C
    # (temperature - dew_point) * 400 gives cloud base in feet
    spread = weather_df["temperature_2m"] - weather_df["dew_point_2m"]

    # Round down to nearest 100 feet.
    cloud_base = (spread * 400).apply(lambda x: int(x // 100) * 100)
    weather_df["cloud_base_ft"] = cloud_base
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

    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i_date, date in enumerate(dates):
        # Update progress bar and status text
        progress = (i_date / len(dates))
        progress_bar.progress(progress)
        status_text.text(
            f"Fetching weather data for {date} ({i_date+1}/{len(dates)})"
        )

        # Fetch weather data for the given date range.
        weather_fetcher = WeatherFetcher(
            latitude=latitude,
            longitude=longitude,
            weather_date=date
        )
        # Add a delay to avoid hitting the API too quickly.
        # This is important to avoid being blocked by the API.
        time.sleep(0.2)
        if weather_fetcher.hourly_df.empty:
            st.warning(f"No weather data available for {date}.")
            continue
        weather_data.append(weather_fetcher.hourly_df)

    # Complete the progress bar
    progress_bar.progress(1.0)
    status_text.text("Weather data fetching complete!")
    time.sleep(0.5)
    status_text.empty()
    progress_bar.empty()

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


def plot_wind_vs_launches(weather_df, launches_df):
    """Create a scatter plot showing correlation between wind speed
    and number of launches.

    Args:
        weather_df (pd.DataFrame): Weather data
        launches_df (pd.DataFrame): Launches data
    """
    # Filter by operating hours for each day.
    START_HOUR = 9
    END_HOUR = 17
    weather_df = weather_df[
        (weather_df['datetime'].dt.hour >= START_HOUR) &
        (weather_df['datetime'].dt.hour < END_HOUR)
    ]

    # Aggregate launches by day
    daily_launches = launches_df.groupby(
        launches_df['Date'].dt.date
    ).size().reset_index(name='Launches')

    # Get average daily wind speed
    daily_wind = weather_df.groupby(weather_df['datetime'].dt.date).agg({
        'wind_speed_10m': 'mean',
        'wind_gusts_10m': 'mean'
    }).reset_index()

    # Merge the data
    merged_df = daily_launches.merge(
        daily_wind,
        left_on='Date',
        right_on='datetime',
        how='inner'
    )

    # Create a scatter plot with Altair
    scatter = alt.Chart(merged_df).mark_circle(size=60).encode(
        x=alt.X('wind_speed_10m:Q', title='Average Wind Speed (kts)'),
        y=alt.Y('Launches:Q', title='Number of Launches'),
        color=alt.Color('wind_gusts_10m:Q', title='Wind Gusts (kts)'),
        tooltip=['datetime', 'Launches', 'wind_speed_10m', 'wind_gusts_10m']
    ).properties(
        title='Wind Speed vs Number of Launches',
        width=600,
        height=400
    )

    # Add a trend line
    trend = scatter.transform_regression(
        'wind_speed_10m', 'Launches'
    ).mark_line(color='red')

    # Display the chart
    st.altair_chart(scatter + trend, use_container_width=True)


def plot_weather_vs_flight_time(weather_df, launches_df,
                                selected_metric):
    """Create a scatter plot showing how weather affects flight duration.

    Args:
        weather_df (pd.DataFrame): Weather data
        launches_df (pd.DataFrame): Launches data
        selected_metric (str): The weather metric to plot
    """
    # Filter by operating hours for each day.
    START_HOUR = 9
    END_HOUR = 17
    weather_df = weather_df[
        (weather_df['datetime'].dt.hour >= START_HOUR) &
        (weather_df['datetime'].dt.hour < END_HOUR)
    ]

    # Get median flight and number of launches per day
    daily_launches = launches_df.groupby(
        launches_df['Date'].dt.date
    ).agg({
        'TakeOffTime': 'count',
        'FlightTime': 'median',
    }).reset_index().rename(
        columns={'TakeOffTime': 'Launches', 'FlightTime': 'MedianFlightTime'},
    )

    # Get median daily weather conditions
    daily_weather = weather_df.groupby(weather_df['datetime'].dt.date).agg({
        'wind_speed_10m': 'median',
        'wind_gusts_10m': 'median',
        'wind_direction_10m': 'median',
        'cloud_base_ft': 'median',
        'cloud_cover_low': 'median',
        'precipitation': 'sum',
        'temperature_2m': 'median',
        'relative_humidity_2m': 'median',
        'surface_pressure': 'median',
        'dew_point_2m': 'median',
    }).reset_index()

    # Merge the data
    merged_df = daily_launches.merge(
        daily_weather,
        left_on='Date',
        right_on='datetime',
        how='inner'
    )

    # Lookup the selected metric in the metadata.
    metric_display_name = weather_metadata[selected_metric]['display_name']

    # Append unit to the display name.
    unit = weather_metadata[selected_metric]['unit']
    metric_display_name += f' ({unit})'

    # Create a scatter plot with Altair
    tooltips = [col for col in merged_df.columns if col != 'datetime']

    # Set specific domain for surface pressure if that's the selected metric
    x_encoding = alt.X(
        f'{selected_metric}:Q',
        title=metric_display_name
    )

    # Set domain range specifically for surface pressure
    if selected_metric == 'surface_pressure':
        x_encoding = alt.X(
            f'{selected_metric}:Q',
            title=metric_display_name,
            scale=alt.Scale(domain=[950, 1050])
        )

    scatter = alt.Chart(merged_df).mark_circle().encode(
        x=x_encoding,
        y=alt.Y('Launches:Q', title='Number of Launches'),
        size=alt.Size(
            'MedianFlightTime:Q',
            scale=alt.Scale(range=[20, 100]),
            legend=alt.Legend(title="Flight Time (mins)")
        ),
        color=alt.Color('MedianFlightTime:Q'),
        tooltip=tooltips
    ).properties(
        title=f'{metric_display_name} vs Number of Launches',
        width=600,
        height=400
    )

    # Add a trend line for number of launches
    trend = scatter.transform_regression(
        f'{selected_metric}', 'Launches'
    ).mark_line(color='red')

    # Display the chart
    st.altair_chart(scatter + trend, use_container_width=True)


def plot_launch_vs_nonlaunch_weather(weather_df, launches_df,
                                     selected_metric):
    """Compare weather conditions on days with launches vs
    days without launches.

    Args:
        weather_df (pd.DataFrame): Weather data
        launches_df (pd.DataFrame): Launches data
        selected_metric (str): Selected weather metric to compare.
    """
    # Number of launches per day cutoff.
    MIN_LAUNCHES = 10

    # Filter by operating hours for each day.
    START_HOUR = 9
    END_HOUR = 17
    weather_df = weather_df[
        (weather_df['datetime'].dt.hour >= START_HOUR) &
        (weather_df['datetime'].dt.hour < END_HOUR)
    ]

    # Get all weekends.
    all_weekends = get_weekends(
        start_date=launches_df['Date'].min(),
        end_date=launches_df['Date'].max()
    )

    # Group launches by date.
    daily_launches = launches_df.groupby(
        launches_df['Date'].dt.date
    ).agg({
        'TakeOffTime': 'count',
        'FlightTime': 'median',
    }).reset_index().rename(
        columns={'TakeOffTime': 'Launches', 'FlightTime': 'MedianFlightTime'},
    )

    # Place 0 for weekends with no launches while retaining midweek launches
    weekend_dates_set = set(all_weekends)
    launch_dates_set = set(daily_launches['Date'])
    missing_weekends = list(weekend_dates_set - launch_dates_set)

    if missing_weekends:
        missing_df = pd.DataFrame({
            'Date': missing_weekends,
            'Launches': [0] * len(missing_weekends),
            'MedianFlightTime': [0] * len(missing_weekends)
        })
        daily_launches = pd.concat(
            [daily_launches, missing_df],
            ignore_index=True
        )

    # Sort the data by date.
    daily_launches = daily_launches.sort_values(by='Date').reset_index(
        drop=True
    )

    # Get median daily weather conditions
    daily_weather = weather_df.groupby(weather_df['datetime'].dt.date).agg({
        'wind_speed_10m': 'median',
        'wind_gusts_10m': 'median',
        'wind_direction_10m': 'median',
        'cloud_base_ft': 'median',
        'cloud_cover_low': 'median',
        'precipitation': 'sum',
        'temperature_2m': 'median',
        'relative_humidity_2m': 'median',
        'surface_pressure': 'median',
        'dew_point_2m': 'median',
    }).reset_index()

    # Merge the data
    merged_df = daily_launches.merge(
        daily_weather,
        left_on='Date',
        right_on='datetime',
        how='inner'
    )

    # Split into days with and without launches
    days_with_launches = merged_df[merged_df['Launches'] >= MIN_LAUNCHES]
    days_low_launches = merged_df[merged_df['Launches'] < MIN_LAUNCHES]

    # Show how many days with launches vs low launches
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            label="Flying days",
            value=len(days_with_launches)
        )
    with col2:
        st.metric(
            label=f"Poor flying days: (<{MIN_LAUNCHES} launches): ",
            value=len(days_low_launches)
        )

    # Get the display name for the selected metric
    metric_display_name = weather_metadata[selected_metric]['display_name']
    metric_unit = weather_metadata[selected_metric]['unit']

    # Create a DataFrame for plotting
    plot_data = pd.DataFrame({
        'Weather Condition': [metric_display_name] * len(merged_df),
        'Value': merged_df[selected_metric],
        'Flying Day': merged_df['Launches'].apply(
            lambda x: 'Launch Day' if x >= MIN_LAUNCHES else 'Low Launches'
        )
    })

    # Set specific domain for surface pressure if that's the selected metric
    x_encoding = alt.X(
        'Value:Q',
        title=metric_display_name,
    )

    # Set domain range specifically for surface pressure
    if selected_metric == 'surface_pressure':
        x_encoding = alt.X(
            'Value:Q',
            title=f"{metric_display_name} ({metric_unit})",
            scale=alt.Scale(domain=[950, 1050])
        )

    # Create a box plot comparing the metric between days with and
    # low launches
    chart = alt.Chart(plot_data).mark_boxplot(
        extent='min-max',
        ticks=True,
        median={'color': 'black'},
        rule={'color': 'gray'},
        box={'color': 'gray'},
        outliers={'color': 'red'},
    ).encode(
        y=alt.Y('Flying Day:N', title=None),
        x=x_encoding,
        color=alt.Color('Flying Day:N', legend=None)
    ).properties(
        title=f"Comparison of {metric_display_name} on Launch vs "
              "Low-Launch Days",
        width=600,
        height=400
    )

    # Display the chart
    st.altair_chart(chart, use_container_width=True)

    # Show statistical summary
    st.subheader("Statistical Summary")

    if len(days_with_launches) > 0 and len(days_low_launches) > 0:
        launch_median = days_with_launches[selected_metric].median()
        low_launch_median = days_low_launches[selected_metric].median()

        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                f"Median {metric_display_name} on Launch Days",
                f"{launch_median:.0f} {metric_unit}"
            )
        with col2:
            st.metric(
                f"Median {metric_display_name} on Low-Launch Days",
                f"{low_launch_median:.0f} {metric_unit}",
                f"{low_launch_median - launch_median:.0f} {metric_unit}"
            )


def select_metric_to_plot():
    """Select the metric to plot.
    Returns:
        str: Selected metric.
        str: Display name of the selected metric.
        str: Unit of the selected metric.
    """
    metric_options = list(weather_metadata.keys())
    metric_display_names = [
        weather_metadata[metric]['display_name']
        for metric in metric_options
        if metric != 'datetime'
    ]
    metric_options.remove('datetime')
    metric_display_name = st.selectbox(
        'Select weather metric to compare:',
        metric_display_names,
        index=0,
        key='compare_weather_metric'
    )

    # Lookup the selected metric in the metadata
    selected_metric = metric_options[
        metric_display_names.index(metric_display_name)
    ]
    return selected_metric

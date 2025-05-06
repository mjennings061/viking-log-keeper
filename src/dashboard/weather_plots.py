"""weather_plots.py

Plots for weather data."""

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.utils import get_weekends
from dashboard.weather_utils import weather_metadata


def plot_launch_vs_nonlaunch_weather(weather_df, launches_df, selected_metric):
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
        (weather_df["datetime"].dt.hour >= START_HOUR)
        & (weather_df["datetime"].dt.hour < END_HOUR)
    ]

    # Get all weekends.
    all_weekends = get_weekends(
        start_date=launches_df["Date"].min(),
        end_date=launches_df["Date"].max(),
    )

    # Group launches by date.
    daily_launches = (
        launches_df.groupby(launches_df["Date"].dt.date)
        .agg(
            {
                "TakeOffTime": "count",
                "FlightTime": "median",
            }
        )
        .reset_index()
        .rename(
            columns={
                "TakeOffTime": "Launches",
                "FlightTime": "MedianFlightTime",
            },
        )
    )

    # Place 0 for weekends with no launches while retaining midweek launches
    weekend_dates_set = set(all_weekends)
    launch_dates_set = set(daily_launches["Date"])
    missing_weekends = list(weekend_dates_set - launch_dates_set)

    if missing_weekends:
        missing_df = pd.DataFrame(
            {
                "Date": missing_weekends,
                "Launches": [0] * len(missing_weekends),
                "MedianFlightTime": [0] * len(missing_weekends),
            }
        )
        daily_launches = pd.concat(
            [daily_launches, missing_df], ignore_index=True
        )

    # Sort the data by date.
    daily_launches = daily_launches.sort_values(by="Date").reset_index(
        drop=True
    )

    # Get median daily weather conditions
    daily_weather = (
        weather_df.groupby(weather_df["datetime"].dt.date)
        .agg(
            {
                "wind_speed_10m": "median",
                "wind_gusts_10m": "median",
                "wind_direction_10m": "median",
                "cloud_base_ft": "median",
                "cloud_cover_low": "median",
                "precipitation": "sum",
                "temperature_2m": "median",
                "relative_humidity_2m": "median",
                "surface_pressure": "median",
                "dew_point_2m": "median",
            }
        )
        .reset_index()
    )

    # Merge the data
    merged_df = daily_launches.merge(
        daily_weather, left_on="Date", right_on="datetime", how="inner"
    )

    # Split into days with and without launches
    days_with_launches = merged_df[merged_df["Launches"] >= MIN_LAUNCHES]
    days_low_launches = merged_df[merged_df["Launches"] < MIN_LAUNCHES]

    # Show how many days with launches vs low launches
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Flying days", value=len(days_with_launches))
    with col2:
        st.metric(
            label=f"Poor flying days: (<{MIN_LAUNCHES} launches): ",
            value=len(days_low_launches),
        )

    # Get the display name for the selected metric
    metric_display_name = weather_metadata[selected_metric]["display_name"]
    metric_unit = weather_metadata[selected_metric]["unit"]

    # Create a DataFrame for plotting
    plot_data = pd.DataFrame(
        {
            "Weather Condition": [metric_display_name] * len(merged_df),
            "Value": merged_df[selected_metric],
            "Flying Day": merged_df["Launches"].apply(
                lambda x: "Launch Day" if x >= MIN_LAUNCHES else "Low Launches"
            ),
        }
    )

    # Set specific domain for surface pressure if that's the selected metric
    x_encoding = alt.X(
        "Value:Q",
        title=metric_display_name,
    )

    # Set domain range specifically for surface pressure
    if selected_metric == "surface_pressure":
        x_encoding = alt.X(
            "Value:Q",
            title=f"{metric_display_name} ({metric_unit})",
            scale=alt.Scale(domain=[950, 1050]),
        )

    # Create a box plot comparing the metric between days with and
    # low launches
    chart = (
        alt.Chart(plot_data)
        .mark_boxplot(
            extent="min-max",
            ticks=True,
            median={"color": "black"},
            rule={"color": "gray"},
            box={"color": "gray"},
            outliers={"color": "red"},
        )
        .encode(
            y=alt.Y("Flying Day:N", title=None),
            x=x_encoding,
            color=alt.Color("Flying Day:N", legend=None),
        )
        .properties(
            title=f"Comparison of {metric_display_name} on Launch vs "
            "Low-Launch Days",
            width=600,
            height=400,
        )
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
                f"{launch_median:.0f} {metric_unit}",
            )
        with col2:
            st.metric(
                f"Median {metric_display_name} on Low-Launch Days",
                f"{low_launch_median:.0f} {metric_unit}",
                f"{low_launch_median - launch_median:.0f} {metric_unit}",
            )


def plot_weather_vs_flight_time(weather_df, launches_df, selected_metric):
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
        (weather_df["datetime"].dt.hour >= START_HOUR)
        & (weather_df["datetime"].dt.hour < END_HOUR)
    ]

    # Get median flight and number of launches per day
    daily_launches = (
        launches_df.groupby(launches_df["Date"].dt.date)
        .agg(
            {
                "TakeOffTime": "count",
                "FlightTime": "median",
            }
        )
        .reset_index()
        .rename(
            columns={
                "TakeOffTime": "Launches",
                "FlightTime": "MedianFlightTime",
            },
        )
    )

    # Get median daily weather conditions
    daily_weather = (
        weather_df.groupby(weather_df["datetime"].dt.date)
        .agg(
            {
                "wind_speed_10m": "median",
                "wind_gusts_10m": "median",
                "wind_direction_10m": "median",
                "cloud_base_ft": "median",
                "cloud_cover_low": "median",
                "precipitation": "sum",
                "temperature_2m": "median",
                "relative_humidity_2m": "median",
                "surface_pressure": "median",
                "dew_point_2m": "median",
            }
        )
        .reset_index()
    )

    # Merge the data
    merged_df = daily_launches.merge(
        daily_weather, left_on="Date", right_on="datetime", how="inner"
    )

    # Lookup the selected metric in the metadata.
    metric_display_name = weather_metadata[selected_metric]["display_name"]

    # Append unit to the display name.
    unit = weather_metadata[selected_metric]["unit"]
    metric_display_name += f" ({unit})"

    # Create a scatter plot with Altair
    # TODO: Make this a violin plot.
    tooltips = [col for col in merged_df.columns if col != "datetime"]

    # Set specific domain for surface pressure if that's the selected metric
    x_encoding = alt.X(f"{selected_metric}:Q", title=metric_display_name)

    # Set domain range specifically for surface pressure
    if selected_metric == "surface_pressure":
        x_encoding = alt.X(
            f"{selected_metric}:Q",
            title=metric_display_name,
            scale=alt.Scale(domain=[950, 1050]),
        )

    scatter = (
        alt.Chart(merged_df)
        .mark_circle()
        .encode(
            x=x_encoding,
            y=alt.Y("Launches:Q", title="Number of Launches"),
            size=alt.Size(
                "MedianFlightTime:Q",
                scale=alt.Scale(range=[20, 100]),
                legend=alt.Legend(title="Flight Time (mins)"),
            ),
            color=alt.Color("MedianFlightTime:Q"),
            tooltip=tooltips,
        )
        .properties(
            title=f"{metric_display_name} vs Number of Launches",
            width=600,
            height=400,
        )
    )

    # Add a trend line for number of launches
    trend = scatter.transform_regression(
        f"{selected_metric}", "Launches"
    ).mark_line(color="red")

    # Display the chart
    st.altair_chart(scatter + trend, use_container_width=True)


# TODO: Finish this function
def plot_wind_polar(weather_df):
    """Create a polar plot showing wind direction frequency."""
    START_HOUR = 9
    END_HOUR = 17
    weather_df = weather_df[
        (weather_df["datetime"].dt.hour >= START_HOUR)
        & (weather_df["datetime"].dt.hour < END_HOUR)
    ]

    # Bin wind direction (e.g., every 10 degrees)
    BIN_SIZE = 10
    weather_df["wind_dir_bin"] = (
        (weather_df["wind_direction_10m"] // BIN_SIZE) * BIN_SIZE
    ).astype(int)

    # https://altair-viz.github.io/gallery/polar_bar_chart.html


def weather_table(weather_df: pd.DataFrame):
    """Display the weather data in a table.

    Args:
        weather_df (pd.DataFrame): DataFrame containing the weather data.
    """
    st.subheader("Weather Data")
    # Use the timezone from the data itself for display formatting
    display_df = weather_df.copy()
    display_df["datetime"] = display_df["datetime"].dt.tz_localize(None)
    # Sort by descending datetime
    display_df = display_df.sort_values(
        by="datetime", ascending=False
    ).reset_index(drop=True)

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
            ),
        },
    )

"""weather_plots.py

Plots for weather data."""

import altair as alt
import matplotlib.pyplot as plt
import numpy as np
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

    # Plot violin of the selected metric
    plot_flying_non_flying_violin(weather_df, selected_metric)

    # Show statistical summary
    st.subheader("Statistical Summary")

    if len(days_with_launches) > 0 and len(days_low_launches) > 0:
        launch_median = days_with_launches[selected_metric].median()
        low_launch_median = days_low_launches[selected_metric].median()

        col1, col2 = st.columns(2)
        weather_name = weather_metadata[selected_metric]["display_name"]
        weather_unit = weather_metadata[selected_metric]["unit"]
        with col1:
            st.metric(
                f"Median {weather_name} on Launch Days",
                f"{launch_median:.0f} {weather_unit}",
            )
        with col2:
            st.metric(
                f"Median {weather_name} on Low-Launch Days",
                f"{low_launch_median:.0f} {weather_unit}",
                f"{low_launch_median - launch_median:.0f} {weather_unit}",
            )


def plot_flying_non_flying_violin(weather_df, selected_metric):
    """Create a violin plot for the selected weather metric.

    Args:
        weather_df (pd.DataFrame): Weather data
        selected_metric (str): The weather metric to plot
    """
    # Filter by operating hours for each day.
    START_HOUR = 9
    END_HOUR = 17
    weather_df = weather_df[
        (weather_df["datetime"].dt.hour >= START_HOUR)
        & (weather_df["datetime"].dt.hour < END_HOUR)
    ]

    # Get all weekends.
    all_weekends = get_weekends(
        start_date=weather_df["datetime"].min(),
        end_date=weather_df["datetime"].max(),
    )

    # Create a DataFrame for plotting
    plot_data = pd.DataFrame(
        {
            "Weather Condition": [selected_metric] * len(weather_df),
            "Value": weather_df[selected_metric],
            "Flying Day": weather_df["datetime"].dt.date.apply(
                lambda x: (
                    "Flying Day" if x not in all_weekends else "Non-Flying Day"
                )
            ),
        }
    )

    # Create a violin plot using mirrored density curves for each group
    density = alt.Chart(plot_data).transform_density(
        "Value",
        as_=["Value", "density"],
        groupby=["Flying Day"],
        extent=[
            float(plot_data["Value"].min()),
            float(plot_data["Value"].max()),
        ],
    )

    violin = (
        density.mark_area(opacity=0.7)
        .encode(
            x=alt.X(
                "Value:Q",
                title=(
                    f"{weather_metadata[selected_metric]['display_name']} "
                    f"({weather_metadata[selected_metric]['unit']})"
                ),
            ),
            y=alt.Y("density:Q", stack=None, title=None, axis=None),
            color=alt.Color("Flying Day:N", legend=None),
            row=alt.Row(
                "Flying Day:N", title=None, header=alt.Header(labelAngle=0)
            ),
        )
        .properties(width=600, height=100)
    )

    # Display the chart
    st.altair_chart(violin, use_container_width=True)


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


def plot_wind_polar(weather_df):
    """Create a polar plot showing wind direction frequency."""
    START_HOUR = 9
    END_HOUR = 17
    df = weather_df.copy()
    df = df[
        (df["datetime"].dt.hour >= START_HOUR)
        & (df["datetime"].dt.hour < END_HOUR)
    ]

    # Bin wind direction (e.g., every 10 degrees)
    BIN_SIZE = 10
    df["wind_dir_bin"] = (
        (df["wind_direction_10m"] / BIN_SIZE).round() * BIN_SIZE
    ).astype(int) % 360

    # Count frequencies for each bin
    all_bins = np.arange(0, 360, BIN_SIZE)
    bin_counts = (
        df["wind_dir_bin"]
        .value_counts()
        .reindex(all_bins, fill_value=0)
        .sort_index()
    )

    # Convert bin centers to radians for polar plot
    bin_centers = np.deg2rad(all_bins + BIN_SIZE / 2)
    frequencies = bin_counts.values

    theme_base = st.get_option("theme.base")
    if theme_base == "dark":
        text_color = "#222222"
        edge_color = "#222222"
    else:
        text_color = "#BBBBBB"
        edge_color = "#BBBBBB"

    fig, ax = plt.subplots(subplot_kw={"projection": "polar"}, figsize=(7, 6))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")

    # Normalize frequencies for inverse color mapping (high freq = lighter)
    norm = plt.Normalize(frequencies.min(), frequencies.max())
    colors = plt.cm.Blues_r(norm(frequencies))  # Use reversed colormap

    # Create the bars for the polar plot
    bars = ax.bar(  # noqa: F841
        bin_centers,
        frequencies,
        width=np.deg2rad(BIN_SIZE),
        bottom=0.0,
        color=colors,
        edgecolor=edge_color,
        alpha=0.8,
    )

    # Set theta direction and zero location to North
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    # Set the radial ticks and labels
    ax.set_xticks(np.deg2rad(np.arange(0, 360, 45)))
    ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])

    # Set circular grid labels and add values as text
    max_freq = max(frequencies)
    ax.set_yticks(np.arange(0, max_freq + 1, round(max_freq / 5)))
    for i in ax.get_yticks():
        ax.text(0, i, str(int(i)), color=text_color, ha="right", va="center")

    # Title
    ax.set_title("Wind Direction Frequency", va="bottom")

    # Set all lines and text to the theme color
    ax.spines["polar"].set_color(edge_color)
    ax.tick_params(colors=text_color)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(text_color)
    ax.title.set_color(text_color)
    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)
    for line in ax.get_lines():
        line.set_color(edge_color)
    ax.set_yticklabels([])

    # Show plot.
    st.pyplot(fig)


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

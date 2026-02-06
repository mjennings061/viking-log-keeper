"""attendance_plots.py - Visualisation functions for attendance data.

This module provides plotting functions to display attendance trends,
tables, and correlations with flight operations.
"""

import pandas as pd
import streamlit as st
import altair as alt


def attendance_table(s: pd.Series) -> None:
    """Display a table of the most recent daily attendance levels.

    Args:
        s: Attendance data with dates as index and counts as values.
    """
    # Convert Series to DataFrame for display
    df = s.to_frame(name='Attendance')
    df.index.name = 'Date'
    df.reset_index(inplace=True)

    # Format date as YY Mon DD for readability
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%y %b %d')

    # Show only the most recent entries
    n_rows_to_display = 16
    st.table(df.head(n_rows_to_display))


def plot_attendance_vs_flight_time(
    attendance_df: pd.Series,
    launches_df: pd.DataFrame
) -> None:
    """Create a scatter plot showing how attendance affects flight operations.

    Displays the relationship between daily attendance and number of launches,
    with bubble colour indicating median flight time. Includes a regression
    trend line.

    Args:
        attendance_df: Attendance data with dates as index.
        launches_df: Launch records containing Date, TakeOffTime, and FlightTime.
    """
    # Prepare attendance data
    attendance_data = attendance_df.to_frame(name='attendance')
    attendance_data.index = pd.to_datetime(attendance_data.index)
    attendance_data['attendance'] = pd.to_numeric(
        attendance_data['attendance'], errors='coerce'
    )

    # Aggregate attendance by day
    daily_attendance = (
        attendance_data
        .groupby(attendance_data.index.normalize())['attendance']
        .sum()
        .reset_index()
        .rename(columns={'index': 'Date', 'attendance': 'Attendance'})
    )

    # Aggregate launches by day
    launches_df = launches_df.copy()
    launches_df['Date'] = pd.to_datetime(launches_df['Date']).dt.normalize()

    daily_launches = (
        launches_df.groupby('Date')
        .agg({
            "TakeOffTime": "count",
            "FlightTime": "median",
        })
        .reset_index()
        .rename(columns={
            "TakeOffTime": "Launches",
            "FlightTime": "MedianFlightTime",
        })
    )

    # Merge attendance and launch data
    merged_df = daily_launches.merge(daily_attendance, on="Date", how="inner")

    # Configure chart encoding
    x_encoding = alt.X(
        "Attendance:Q",
        title="Attendance",
        scale=alt.Scale(domain=[5, merged_df["Attendance"].max()])
    )

    tooltips = [col for col in merged_df.columns if col != "datetime"]

    # Create scatter plot with size encoding for flight time
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
            title="Attendance vs Number of Launches",
            width=600,
            height=400,
        )
    )

    # Add regression trend line
    trend = (
        alt.Chart(merged_df)
        .mark_line(color='red', strokeDash=[5, 5])
        .encode(x=x_encoding, y=alt.Y("Launches:Q"))
        .transform_regression('Attendance', 'Launches')
    )

    st.altair_chart(scatter + trend, use_container_width=True)


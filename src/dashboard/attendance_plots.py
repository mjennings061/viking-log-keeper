import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from attendance import xls_to_dataframe
from dashboard.attendance import get_all_years_attendance

s = get_all_years_attendance()


def plot_attendance_by_day(s, window=4):
    """
    Takes a Pandas Series of attendance data, cleans it,
    and plots a scatter plot with a rolling average trend line.

    Parameters:
    s (pd.Series): Index = dates, Values = attendance counts
    window (int): The number of periods for the rolling average (default 4 for ~1 month)
    """

    # 1. Convert Series to DataFrame to allow for multiple columns
    # We name the value column 'attendance' so we can reference it easily
    df = s.to_frame(name='attendance')

    # 2. DATA CLEANING
    # Fix Index: Convert string dates to actual datetime objects
    df.index = pd.to_datetime(df.index)

    # Fix Values: Convert object/strings to integers (coercing errors to NaN)
    df['attendance'] = pd.to_numeric(df['attendance'], errors='coerce')

    # Sort by date (crucial for rolling average to work correctly)
    df = df.sort_index()

    # 3. ANALYSIS
    # Calculate rolling average (smooths out the noise)
    df['rolling_avg'] = df['attendance'].rolling(window=window).mean()

    # 4. PLOTTING
    plt.figure(figsize=(12, 6))

    # Scatter plot for raw data (The "Cloud")
    plt.scatter(df.index, df['attendance'],
                alpha=0.4, color='steelblue', label='Actual Attendance')

    # Line plot for rolling average (The "Trend")
    plt.plot(df.index, df['rolling_avg'],
             color='firebrick', linewidth=2.5, label=f'{window}-Session Rolling Avg')

    # Formatting
    plt.title('661 Attendance Log (2022-2026)')
    plt.xlabel('Date')
    plt.ylabel('Attendees')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)

    # Rotate date labels to prevent overlap
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.show()




plot_attendance_by_day(s)
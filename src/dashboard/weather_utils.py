"""weather_utils.py

Weather data retrieval and processing utilities"""

import pandas as pd
import streamlit as st


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


def calculate_cloud_base(weather_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate cloud base from weather data.

    Args:
        weather_df (pd.DataFrame): DataFrame containing the weather data.

    Returns:
        pd.DataFrame: DataFrame with cloud base calculated."""
    # Check if the required columns are present
    cols_present = all(
        col in weather_df.columns for col in ["temperature_2m", "dew_point_2m"]
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

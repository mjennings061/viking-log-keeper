"""weather.py: Weather data retrieval and processing."""

# Import modules.
import openmeteo_requests
import requests_cache
import pandas as pd
import numpy as np
from retry_requests import retry
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class WeatherFetcher():
    """Fetch and process weather data."""
    weather_date: pd.Timestamp
    latitude: float = 55.875599555800726  # Kirknewton.
    longitude: float = -3.401593692255116
    hourly: List[str] = field(default_factory=lambda: [
        "temperature_2m", "relative_humidity_2m", "dew_point_2m",
        "precipitation", "surface_pressure", "cloud_cover_low",
        "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"
    ])
    daily: List[str] = field(default_factory=lambda: [
        "weather_code", "precipitation_sum", "sunrise", "sunset",
        "precipitation_hours", "wind_direction_10m_dominant"
    ])
    wind_speed_unit: str = "kn"
    timezone: str = "Europe/London"
    hourly_df: Optional[pd.DataFrame] = field(default=None, init=False)
    daily_df: Optional[pd.DataFrame] = field(default=None, init=False)

    # Constants.
    _API_URL: str = "https://archive-api.open-meteo.com/v1/archive"

    def __post_init__(self):
        self._fetch_weather_data()

    def _fetch_weather_data(self):
        """Get weather data from Open Meteo API."""
        cache_session = requests_cache.CachedSession('.cache', expire_after=-1)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        # Set parameters.
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_date": self.weather_date.strftime("%Y-%m-%d"),
            "end_date": self.weather_date.strftime("%Y-%m-%d"),
            "hourly": self.hourly,
            "daily": self.daily,
            "timezone": self.timezone,
            "wind_speed_unit": self.wind_speed_unit
        }

        # Fetch data.
        responses = openmeteo.weather_api(self._API_URL, params=params)
        response = responses[0]

        # Create hourly dataframe.
        self.hourly_df = self._parse_data(response, "Hourly")

        # Create daily dataframe.
        self.daily_df = self._parse_data(response, "Daily")

    def _parse_data(self, response, data_type: str):
        """Parse weather data from the response.

        Args:
            response: API response object
            data_type: Either 'Hourly' or 'Daily'

        Returns:
            DataFrame with parsed weather data
        """
        # Get data object based on type
        data_obj = getattr(response, data_type)()

        # Get variables list based on type (lowercase)
        variables = getattr(self, data_type.lower())

        # The API will return data for the entire date range, starting at
        # 00:00 local time on the start date and ending 23:00 local time on the
        # end date. The data is returned as local time.
        time_start = pd.to_datetime(
            self.weather_date
        ).tz_localize(self.timezone)
        time_end = (
            pd.to_datetime(self.weather_date) +
            pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        ).tz_localize(self.timezone)
        interval = pd.Timedelta(seconds=data_obj.Interval())

        # Create a date range.
        timestamps = pd.date_range(
            start=time_start,
            end=time_end,
            freq=interval,
            inclusive="left"
        )

        # Create a dictionary to hold the data.
        data = {"date": timestamps}

        # Extract data variables
        for i, var in enumerate(variables):
            data[var] = data_obj.Variables(i).ValuesAsNumpy()

            # Ensure data[var] is an array
            if not isinstance(data[var], np.ndarray) and data_type == "Daily":
                data[var] = np.array([data[var]])
                continue

            # Handle cases where a time is missing e.g. BST change.
            if len(timestamps) < len(data[var]):
                # Spring forward, an hour should be removed from second hour.
                data[var] = np.delete(data[var], 1)
            elif len(timestamps) > len(data[var]):
                # Fall back, an hour should be added to second hour.
                data[var] = np.insert(data[var], 1, np.nan)

        # Convert to DataFrame
        weather_df = pd.DataFrame(data).rename(
            columns={"date": "datetime"}
        ).sort_values(
            by="datetime"
        ).dropna().reset_index(drop=True)
        return weather_df


if __name__ == "__main__":
    # Test the WeatherFetcher class.
    start_date = pd.Timestamp(2025, 2, 22)
    weather_fetcher = WeatherFetcher(
        weather_date=start_date
    )
    # Print the first few rows of the hourly and daily dataframes.
    print(weather_fetcher.hourly_df.head())
    print(weather_fetcher.daily_df.head())

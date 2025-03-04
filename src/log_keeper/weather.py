"""weather.py: Weather data retrieval and processing."""

# Import modules.
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class WeatherFetcher():
    """Fetch and process weather data."""
    start_date: datetime
    end_date: datetime
    latitude: float = 55.875599555800726  # Kirknewton.
    longitude: float = -3.401593692255116
    hourly: List[str] = field(default_factory=lambda: [
        "temperature_2m", "relative_humidity_2m", "dew_point_2m",
        "precipitation", "surface_pressure", "cloud_cover_low",
        "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"
    ])
    daily: List[str] = field(default_factory=lambda: [
        "weather_code", "sunrise", "sunset", "precipitation_sum",
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
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "end_date": self.end_date.strftime("%Y-%m-%d"),
            "hourly": self.hourly,
            "daily": self.daily,
            "timezone": self.timezone,
            "wind_speed_unit": self.wind_speed_unit
        }

        # Fetch data.
        responses = openmeteo.weather_api(self._API_URL, params=params)
        response = responses[0]

        # Create hourly dataframe.
        hourly = response.Hourly()
        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            )
        }

        # Extract hourly data.
        for i, var in enumerate(self.hourly):
            hourly_data[var] = hourly.Variables(i).ValuesAsNumpy()

        # Convert to DataFrame.
        self.hourly_df = pd.DataFrame(
            data=hourly_data
        ).rename(columns={"date": "datetime"}).set_index("datetime")

        # Create daily dataframe.
        daily = response.Daily()
        daily_data = {
            "date": pd.date_range(
                start=pd.to_datetime(daily.Time(), unit="s", utc=True),
                end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=daily.Interval()),
                inclusive="left"
            )
        }

        # Extract daily data.
        for i, var in enumerate(self.daily):
            daily_data[var] = daily.Variables(i).ValuesAsNumpy()

        # Convert to DataFrame.
        self.daily_df = pd.DataFrame(
            data=daily_data
        ).rename(columns={"date": "datetime"}).set_index("datetime")


if __name__ == "__main__":
    # Test the WeatherFetcher class.
    start_date = datetime(2025, 2, 22)
    end_date = datetime(2025, 2, 23)
    weather_fetcher = WeatherFetcher(
        start_date=start_date,
        end_date=end_date
    )
    print(weather_fetcher.hourly_df.head())

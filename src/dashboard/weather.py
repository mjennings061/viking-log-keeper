"""weather.py - Obtain the weather data from the Open Meteo API."""

# Import modules.
from dataclasses import dataclass, field
from typing import Optional
import requests
from requests.exceptions import RequestException
from datetime import datetime

# User defined modules.
from dashboard import logger
from dashboard.utils import is_streamlit_running
from dashboard.auth import AuthConfig

# Constants.
API_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class WeatherData:
    """Weather data class."""
    # Constants.
    api_url: str = field(default=API_URL)
    # Configurable fields.
    latitude: float = field(default=51.5074)
    longitude: float = field(default=-0.1278)
    timezone: str = field(default="Europe/London")
    current_weather: Optional[dict] = field(default=None)
    last_updated: Optional[datetime] = field(default=None)
    last_updated_str: Optional[str] = field(default=None)
    temperature: Optional[float] = field(default=None)
    windspeed: Optional[float] = field(default=None)
    winddirection: Optional[float] = field(default=None)
    weathercode: Optional[int] = field(default=None)
    is_day: Optional[int] = field(default=None)

    def __post_init__(self):
        """Load db_url from secrets or keyring."""
        self.load_secrets()

    def load_secrets(self):
        """Load secrets from keyring or streamlit."""
        # Load auth password from secrets or keyring.
        if is_streamlit_running():
            import streamlit as st
            self.latitude = st.secrets["latitude"]
            self.longitude = st.secrets["longitude"]
            self.timezone = st.secrets["timezone"]
        else:
            # Get vgs and password from keyring.
            self.latitude = AuthConfig().latitude
            self.longitude = AuthConfig().longitude
            self.timezone = AuthConfig().timezone

    def get_weather_data(self) -> bool:
        """Get the weather data from the Open Meteo API."""
        try:
            response = requests.get(
                self.api_url,
                params={
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "current_weather": True,
                    "timezone": self.timezone
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            if "current_weather" in data:
                self.current_weather = data["current_weather"]
                return True
            else:
                logger.error("No current weather data found in response.")
                return False
        except RequestException as e:
            logger.error(f"Error fetching weather data: {e}")
            return False
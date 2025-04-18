"""Tests for the weather module."""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

# Import the WeatherFetcher class from the log_keeper module.
from log_keeper.weather import WeatherFetcher


class MockResponse:
    """Mock class for OpenMeteo API responses."""
    def __init__(self, hourly_data, daily_data,
                 hourly_interval=3600, daily_interval=86400):
        self.hourly_data = hourly_data
        self.daily_data = daily_data
        self.hourly_interval = hourly_interval
        self.daily_interval = daily_interval

    def Hourly(self):
        return MockHourlyData(self.hourly_data, self.hourly_interval)

    def Daily(self):
        return MockDailyData(self.daily_data, self.daily_interval)


class MockHourlyData:
    """Mock class for hourly data."""
    def __init__(self, data, interval):
        self.data = data
        self.interval_value = interval

    def Interval(self):
        return self.interval_value

    def Variables(self, index):
        return MockVariable(self.data[index])


class MockDailyData:
    """Mock class for daily data."""
    def __init__(self, data, interval):
        self.data = data
        self.interval_value = interval

    def Interval(self):
        return self.interval_value

    def Variables(self, index):
        return MockVariable(self.data[index])


class MockVariable:
    """Mock class for variables."""
    def __init__(self, values):
        self.values = np.array(values)

    def ValuesAsNumpy(self):
        return self.values


@pytest.fixture
def mock_openmeteo_client():
    """Mock the OpenMeteo client."""
    with patch('openmeteo_requests.Client') as mock_client:
        # Setup default mock response data - 24 hours of data for a 1-day range
        hourly_data = [
            [20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0,
             29.0, 30.0, 31.0, 32.0, 33.0, 34.0, 35.0, 36.0, 37.0,
             38.0, 39.0, 40.0, 41.0, 42.0, 43.0],  # temperature_2m
            [50.0, 52.0, 54.0, 56.0, 58.0, 60.0, 62.0, 64.0, 66.0,
             68.0, 70.0, 72.0, 74.0, 76.0, 78.0, 80.0, 82.0, 84.0,
             86.0, 88.0, 90.0, 92.0, 94.0, 96.0],  # relative_humidity_2m
            [15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0,
             24.0, 25.0, 26.0, 27.0, 28.0, 29.0, 30.0, 31.0, 32.0,
             33.0, 34.0, 35.0, 36.0, 37.0, 38.0],  # dew_point_2m
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.2, 0.3, 0.2, 0.1, 0.0,
             0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.2, 0.3, 0.2, 0.1,
             0.0, 0.0],    # precipitation
            [1013.0, 1014.0, 1014.0, 1015.0, 1015.0, 1016.0, 1016.0,
             1017.0, 1017.0, 1018.0, 1018.0, 1019.0, 1019.0, 1020.0,
             1020.0, 1019.0, 1019.0, 1018.0, 1018.0, 1017.0, 1017.0,
             1016.0, 1016.0, 1015.0],  # surface_pressure
            [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0,
             60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 85.0, 80.0, 75.0,
             70.0, 65.0, 60.0, 55.0],  # cloud_cover_low
            [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0,
             14.0, 13.0, 12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 6.0,
             7.0, 8.0],  # wind_speed_10m
            [270.0, 275.0, 280.0, 285.0, 290.0, 295.0, 300.0, 305.0, 310.0,
             315.0, 320.0, 325.0, 330.0, 335.0, 340.0, 345.0, 350.0, 355.0,
             0.0, 5.0, 10.0, 15.0, 20.0, 25.0],  # wind_direction_10m
            [8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0,
             18.0, 17.0, 16.0, 15.0, 14.0, 13.0, 12.0, 11.0, 10.0, 9.0,
             8.0, 9.0, 10.0, 11.0]  # wind_gusts_10m
        ]

        daily_data = [
            [1],     # weather_code
            [1.5],   # precipitation_sum
            [pd.Timestamp('2023-06-01 05:00:00').timestamp()],  # sunrise
            [pd.Timestamp('2023-06-01 21:30:00').timestamp()],  # sunset
            [4],     # precipitation_hours
            [300]    # wind_direction_10m_dominant
        ]

        mock_response = MockResponse(hourly_data, daily_data)
        mock_client_instance = MagicMock()
        mock_client_instance.weather_api.return_value = [mock_response]
        mock_client.return_value = mock_client_instance
        yield mock_client


def test_weather_fetcher_initialization():
    """Test initialization of WeatherFetcher."""
    weather_date = pd.Timestamp('2023-06-01')

    with patch.object(WeatherFetcher, '_fetch_weather_data') as mock_fetch:
        fetcher = WeatherFetcher(
            weather_date=weather_date
        )

        # Check default parameters
        assert fetcher.weather_date == weather_date
        assert fetcher.latitude == 55.875599555800726  # Kirknewton default
        assert fetcher.longitude == -3.401593692255116
        assert fetcher.wind_speed_unit == "kn"
        assert fetcher.timezone == "Europe/London"

        # Check that _fetch_weather_data was called during initialization
        mock_fetch.assert_called_once()


def test_weather_fetcher_custom_parameters():
    """Test initialization with custom parameters."""
    weather_date = pd.Timestamp('2023-06-01')
    custom_lat = 51.5074
    custom_lon = -0.1278
    custom_timezone = "UTC"
    custom_wind_unit = "ms"

    with patch.object(WeatherFetcher, '_fetch_weather_data'):
        fetcher = WeatherFetcher(
            weather_date=weather_date,
            latitude=custom_lat,
            longitude=custom_lon,
            timezone=custom_timezone,
            wind_speed_unit=custom_wind_unit
        )

        # Check custom parameters
        assert fetcher.latitude == custom_lat
        assert fetcher.longitude == custom_lon
        assert fetcher.timezone == custom_timezone
        assert fetcher.wind_speed_unit == custom_wind_unit


def test_fetch_weather_data(mock_openmeteo_client):
    """Test the weather data fetching process."""
    weather_date = pd.Timestamp('2024-06-01')

    fetcher = WeatherFetcher(
        weather_date=weather_date
    )

    # Check that API was called with correct parameters
    client_instance = mock_openmeteo_client.return_value
    client_instance.weather_api.assert_called_once()

    # Verify the API URL used
    call_args = client_instance.weather_api.call_args[0]
    assert call_args[0] == "https://archive-api.open-meteo.com/v1/archive"

    # Verify the parameters passed to the API
    call_kwargs = client_instance.weather_api.call_args[1]
    params = call_kwargs['params']
    assert params["latitude"] == fetcher.latitude
    assert params["longitude"] == fetcher.longitude
    assert params["start_date"] == weather_date.strftime("%Y-%m-%d")
    assert params["hourly"] == fetcher.hourly
    assert params["daily"] == fetcher.daily
    assert params["timezone"] == fetcher.timezone
    assert params["wind_speed_unit"] == fetcher.wind_speed_unit


def test_weather_fetcher_dataframes(mock_openmeteo_client):
    """Test that the dataframes are correctly created."""
    weather_date = pd.Timestamp('2023-06-01')

    fetcher = WeatherFetcher(
        weather_date=weather_date
    )

    # Check that dataframes are created
    assert fetcher.hourly_df is not None
    assert fetcher.daily_df is not None

    # Check the structure and content of the hourly dataframe
    assert "datetime" in fetcher.hourly_df.columns
    assert "temperature_2m" in fetcher.hourly_df.columns
    assert "relative_humidity_2m" in fetcher.hourly_df.columns
    assert "dew_point_2m" in fetcher.hourly_df.columns
    assert "precipitation" in fetcher.hourly_df.columns
    assert "surface_pressure" in fetcher.hourly_df.columns
    assert "cloud_cover_low" in fetcher.hourly_df.columns
    assert "wind_speed_10m" in fetcher.hourly_df.columns
    assert "wind_direction_10m" in fetcher.hourly_df.columns
    assert "wind_gusts_10m" in fetcher.hourly_df.columns

    # Verify we got 24 hours of data
    assert len(fetcher.hourly_df) == 24

    # Check the structure and content of the daily dataframe
    assert "datetime" in fetcher.daily_df.columns
    assert "weather_code" in fetcher.daily_df.columns
    assert "precipitation_sum" in fetcher.daily_df.columns
    assert "sunrise" in fetcher.daily_df.columns
    assert "sunset" in fetcher.daily_df.columns
    assert "precipitation_hours" in fetcher.daily_df.columns
    assert "wind_direction_10m_dominant" in fetcher.daily_df.columns

    # Verify we got 1 day of data
    assert len(fetcher.daily_df) == 1


def test_dst_change_handling(mock_openmeteo_client):
    """Test handling of DST changes (skipped hour during spring forward)."""
    # Use a real DST change date in UK (clocks go forward)
    weather_date = pd.Timestamp('2025-03-30')

    # Launch the fetcher.
    fetcher = WeatherFetcher(weather_date=weather_date)

    # Verify data was properly handled
    assert fetcher.hourly_df is not None
    assert len(fetcher.hourly_df) == 23  # We should have 23 hours

    # Check that the hour that's skipped (typically 1am→3am) isn't in the data
    hourly_times = fetcher.hourly_df['datetime'].dt.hour.tolist()

    # If BST starts at 1am, we should see hour 0 and hour 2, but not hour 1
    if 0 in hourly_times and 2 in hourly_times:
        assert 1 not in hourly_times


def test_fall_dst_change(mock_openmeteo_client):
    """Test handling of fall DST changes (more timestamps than data points)."""
    # Use a real DST change date in UK (clocks go back)
    weather_date = pd.Timestamp('2023-10-29')

    # Launch the fetcher.
    fetcher = WeatherFetcher(weather_date=weather_date)

    # Verify data was properly handled
    assert fetcher.hourly_df is not None
    assert len(fetcher.hourly_df) == 24  # We should have 24 hours

    # Check the hours are local time.
    first_hour = fetcher.hourly_df['datetime'].dt.hour
    assert first_hour[0] == 0  # First hour should be 0
    assert first_hour[1] == 1  # Second hour should be 1


# Verify data was properly handled
def test_parse_data_with_scalar_values():
    """Test _parse_data method when ValuesAsNumpy returns scalar values."""
    weather_date = pd.Timestamp('2023-06-01')

    # Create a fetcher with mocked _fetch_weather_data
    with patch.object(WeatherFetcher, '_fetch_weather_data'):
        fetcher = WeatherFetcher(
            weather_date=weather_date,
            daily=["weather_code"]
        )

    # Create mock objects
    mock_response = MagicMock()
    mock_daily = MagicMock()
    mock_variable = MagicMock()

    # Setup ValuesAsNumpy to return a scalar
    mock_variable.ValuesAsNumpy.return_value = 20.0

    # Chain the mocks
    mock_daily.Variables.return_value = mock_variable
    mock_daily.Interval.return_value = 3600 * 24
    mock_response.Daily.return_value = mock_daily

    # Override daily list to have just one variable for simplicity
    fetcher.daily = ["weather_code"]

    # Call _parse_data
    result = fetcher._parse_data(mock_response, "Daily")

    # Check results
    assert result is not None
    assert len(result) == 1
    assert result['weather_code'].iloc[0] == 20.0

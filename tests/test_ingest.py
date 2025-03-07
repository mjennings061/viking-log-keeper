"""test_ingest.py - Test cases for the ingest module."""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from datetime import timedelta

from log_keeper.ingest import (
    ingest_log_sheet,
    ingest_log_sheet_from_upload,
    extract_launches,
    extract_aircraft_info,
    validate_aircraft_info,
    validate_log_sheet,
    parse_hours_after,
    collate_log_sheets,
    sanitise_log_sheets
)


@pytest.fixture
def sample_log_data():
    """Create a sample log sheet DataFrame."""
    return pd.DataFrame({
        'AircraftCommander': ['John Doe', 'Jane Smith'],
        '2ndPilot': ['Bob Wilson', 'Alice Brown'],
        'Duty': ['SCT U/T', 'G/S'],
        'TakeOffTime': [pd.Timestamp('2025-01-23 10:00:00'), pd.Timestamp('2025-01-23 11:00:00')],
        'LandingTime': [pd.Timestamp('2025-01-23 10:30:00'), pd.Timestamp('2025-01-23 11:45:00')],
        'FlightTime': [30, 45],
        'SPC': [1, 6],
        'PLF': [True, False],
        'Aircraft': ['ZE123', 'ZE456'],
        'Date': [pd.Timestamp('2025-01-23'), pd.Timestamp('2025-01-23')],
        'P1': [True, False],
        'P2': [False, False]
    })


@pytest.fixture
def sample_aircraft_info():
    """Create a sample aircraft info DataFrame."""
    return pd.DataFrame({
        'Date': [pd.Timestamp('2025-01-23')],
        'Aircraft': ['ZE123'],
        'Launches After': [100],
        'Hours After': [120]
    })


@pytest.fixture
def mock_excel_file(sample_log_data, sample_aircraft_info):
    """Create a mock ExcelFile object."""
    mock_xls = MagicMock(spec=pd.ExcelFile)

    def mock_read_excel(*args, **kwargs):
        sheet_name = kwargs.get('sheet_name')
        if sheet_name == 'FORMATTED':
            return sample_log_data
        elif sheet_name == '_AIRCRAFT':
            return sample_aircraft_info
        return pd.DataFrame()

    with patch('pandas.read_excel', side_effect=mock_read_excel):
        yield mock_xls


def test_ingest_log_sheet(tmp_path, sample_log_data):
    """Test ingesting a log sheet from file."""
    # Create a temporary Excel file
    file_path = tmp_path / "test.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        sample_log_data.to_excel(writer, sheet_name='FORMATTED', index=False)

    # Test successful ingestion
    df = ingest_log_sheet(str(file_path))
    assert not df.empty
    assert list(df.columns) == list(sample_log_data.columns)

    # Test file not found
    with pytest.raises(FileNotFoundError):
        ingest_log_sheet("nonexistent.xlsx")

    # Test invalid extension
    invalid_path = tmp_path / "test.txt"
    invalid_path.touch()
    with pytest.raises(ValueError):
        ingest_log_sheet(str(invalid_path))


def test_ingest_log_sheet_from_upload(mock_excel_file):
    """Test ingesting a log sheet from upload."""
    mock_file = MagicMock()
    mock_file.name = "test.xlsx"

    # Create a BytesIO object to simulate file content
    mock_file.read = MagicMock(return_value=b"fake excel content")
    mock_file.seek = MagicMock()

    with patch('pandas.ExcelFile', return_value=mock_excel_file):
        raw_df, aircraft_info = ingest_log_sheet_from_upload(mock_file)
        assert not raw_df.empty
        assert not aircraft_info.empty

    # Test invalid extension
    mock_file.name = "test.txt"
    with pytest.raises(ValueError):
        ingest_log_sheet_from_upload(mock_file)


def test_extract_launches(mock_excel_file, sample_log_data):
    """Test extracting launches from Excel file."""
    df = extract_launches(mock_excel_file)
    assert not df.empty
    assert list(df.columns) == list(sample_log_data.columns)


def test_parse_hours_after():
    """Test parsing hours after string."""
    # Test valid timedelta
    td = timedelta(hours=2, minutes=30)
    result = parse_hours_after(td)
    assert result == 150  # 2.5 hours in minutes

    # Test None/NaT
    assert pd.isna(parse_hours_after(None))
    assert pd.isna(parse_hours_after(pd.NaT))

    # Test invalid input
    assert pd.isna(parse_hours_after("invalid"))


def test_extract_aircraft_info(mock_excel_file, sample_aircraft_info):
    """Test extracting aircraft info."""
    df = extract_aircraft_info(mock_excel_file)
    assert not df.empty
    assert list(df.columns) == list(sample_aircraft_info.columns)

    # Test exception handling
    with patch('pandas.read_excel', side_effect=Exception("Test error")):
        df = extract_aircraft_info(mock_excel_file)
        assert df.empty


def test_validate_aircraft_info(sample_aircraft_info):
    """Test aircraft info validation."""
    # Test valid data
    validate_aircraft_info(sample_aircraft_info)

    # Test empty DataFrame
    with pytest.raises(ValueError, match="Aircraft information is empty"):
        validate_aircraft_info(pd.DataFrame())

    # Test empty values
    df = sample_aircraft_info.copy()
    df.loc[0, 'Aircraft'] = None
    with pytest.raises(ValueError, match="contains empty values"):
        validate_aircraft_info(df)

    # Test invalid aircraft name
    df = sample_aircraft_info.copy()
    df.loc[0, 'Aircraft'] = 'XX123'
    with pytest.raises(ValueError, match="does not contain 'ZE'"):
        validate_aircraft_info(df)

    # Test invalid launches
    df = sample_aircraft_info.copy()
    df.loc[0, 'Launches After'] = -1
    with pytest.raises(ValueError, match="Difference in AC launches is too large"):
        validate_aircraft_info(df)

    # Test invalid hours
    df = sample_aircraft_info.copy()
    df.loc[0, 'Hours After'] = -1
    with pytest.raises(ValueError, match="Difference in AC hours is too large"):
        validate_aircraft_info(df)


def test_validate_log_sheet(sample_log_data):
    """Test log sheet validation."""
    # Test valid data
    validate_log_sheet(sample_log_data)

    # Test empty DataFrame
    with pytest.raises(ValueError, match="Log sheet is empty"):
        validate_log_sheet(pd.DataFrame())

    # Test NaT values in date/time columns
    df = sample_log_data.copy()
    df.loc[0, 'TakeOffTime'] = pd.NaT
    with pytest.raises(ValueError, match="Date or time columns contain NaT values"):
        validate_log_sheet(df)

    # Test landing before takeoff
    df = sample_log_data.copy()
    df.loc[0, 'LandingTime'] = df.loc[0, 'TakeOffTime'] - pd.Timedelta(minutes=30)
    with pytest.raises(ValueError, match="LandingTime is before TakeOffTime"):
        validate_log_sheet(df)

    # Test invalid flight time
    df = sample_log_data.copy()
    df.loc[0, 'FlightTime'] = 1000
    with pytest.raises(ValueError, match="FlightTime column contains huge value"):
        validate_log_sheet(df)

    # Test missing aircraft
    df = sample_log_data.copy()
    df.loc[0, 'Aircraft'] = '0'
    with pytest.raises(ValueError, match="Aircraft column has no aircraft"):
        validate_log_sheet(df)


def test_sanitise_log_sheets(sample_log_data):
    """Test log sheet sanitization."""
    sanitised_df = sanitise_log_sheets(sample_log_data)
    assert not sanitised_df.empty
    assert 'AircraftCommander' in sanitised_df.columns
    assert all(isinstance(x, str) for x in sanitised_df['AircraftCommander'])


def test_collate_log_sheets(tmp_path, sample_log_data):
    """Test collating multiple log sheets."""
    # Create test log sheets
    for i in range(3):
        file_path = tmp_path / f"2965D_{i}.xlsx"  # Changed to match expected pattern
        with pd.ExcelWriter(file_path) as writer:
            sample_log_data.to_excel(writer, sheet_name='FORMATTED', index=False)

    # Test successful collation
    df = collate_log_sheets(tmp_path)
    assert not df.empty
    assert len(df) == len(sample_log_data) * 3

    # Test empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        collate_log_sheets(empty_dir)

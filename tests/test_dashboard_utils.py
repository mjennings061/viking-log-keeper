"""test_dashboard_utils.py - Test cases for dashboard utility helpers."""

import pandas as pd

from dashboard.utils import last_flying_day_summary


def _launches_df() -> pd.DataFrame:
    """Two flying days; the latest day repeats one GIF crew across two sorties."""
    return pd.DataFrame({
        'Date': [
            pd.Timestamp('2025-01-22'),
            pd.Timestamp('2025-01-23'),
            pd.Timestamp('2025-01-23'),
            pd.Timestamp('2025-01-23'),
            pd.Timestamp('2025-01-23'),
        ],
        # Rows 4 and 5 share aircraft, crew and GIF duty -> one cadet.
        'Aircraft': ['ZE123', 'ZE456', 'ZE123', 'ZE123', 'ZE123'],
        'AircraftCommander': [
            'John Doe', 'Jane Smith', 'John Doe', 'Sam Vimes', 'Sam Vimes',
        ],
        'SecondPilot': ['Bob Wilson', 'Alice Brown', 'Cadet A', 'Cadet B', 'Cadet B'],
        'Duty': ['GIF', 'SCT U/T', 'GIF', 'GIF', 'GIF'],
        'TakeOffTime': [
            pd.Timestamp('2025-01-22 09:00:00'),
            pd.Timestamp('2025-01-23 10:15:00'),
            pd.Timestamp('2025-01-23 09:30:00'),
            pd.Timestamp('2025-01-23 11:00:00'),
            pd.Timestamp('2025-01-23 16:45:00'),
        ],
        'LandingTime': [
            pd.Timestamp('2025-01-22 09:30:00'),
            pd.Timestamp('2025-01-23 10:45:00'),
            pd.Timestamp('2025-01-23 10:00:00'),
            pd.Timestamp('2025-01-23 11:30:00'),
            pd.Timestamp('2025-01-23 17:15:00'),
        ],
        'FlightTime': [30, 30, 30, 30, 30],
        'SPC': [1, 1, 1, 1, 1],
        'PLF': [False, False, False, False, False],
        'P1': [True, True, True, True, True],
        'P2': [False, False, False, False, False],
    })


def test_last_flying_day_summary_basic():
    """Summary covers only the latest day with correct figures."""
    summary = last_flying_day_summary(_launches_df())

    # Latest day only (2025-01-23, four launches).
    assert summary["date"] == pd.Timestamp('2025-01-23')
    assert summary["first_launch"] == "09:30"
    assert summary["last_launch"] == "16:45"

    # Aircraft used that day, sorted and unique.
    assert summary["aircraft"] == ["ZE123", "ZE456"]

    # GIF cadets: two distinct crews; Sam Vimes/Cadet B's repeat collapses.
    assert summary["gif_cadets"] == 2

    # Launches by duty for the latest day: 3x GIF, 1x SCT U/T.
    by_duty = summary["launches_by_duty"].set_index("Duty")["Launches"].to_dict()
    assert by_duty == {"GIF": 3, "SCT U/T": 1}


def test_last_flying_day_summary_empty():
    """An empty DataFrame yields an empty summary."""
    assert last_flying_day_summary(pd.DataFrame()) == {}


def test_last_flying_day_summary_zero_gifs():
    """A day with no GIF duties reports zero GIF cadets."""
    df = _launches_df()
    df["Duty"] = "SCT U/T"
    summary = last_flying_day_summary(df)
    assert summary["gif_cadets"] == 0

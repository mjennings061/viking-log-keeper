"""test_dashboard_utils.py - Test cases for dashboard utility helpers."""

import pandas as pd

from dashboard.utils import (
    last_flying_day_summary,
    solo_gs_cadet_count,
    gs_cadet_count,
    gif_cadet_count,
    delta_gifs_previous_day,
)


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


def test_solo_gs_cadet_count():
    """Count unique solo G/S commanders; dedupe, exclude dual and non-G/S."""
    df = pd.DataFrame({
        "Duty": ["G/S", "G/S", "G/S", "G/S", "G/S", "SCT U/T"],
        "AircraftCommander": ["A", "A", "B", "C", "D", "E"],
        "SecondPilot": [0, "", "0", "-", "Real Guy", "0"],
    })
    # A (twice, dedup), B, C => 3 unique solo G/S commanders.
    # D excluded (has a SecondPilot); E excluded (not G/S).
    assert solo_gs_cadet_count(df) == 3


def test_gs_cadet_count():
    """Count unique dual G/S SecondPilots; dedupe, exclude solo and non-G/S."""
    df = pd.DataFrame({
        "Duty": ["G/S", "G/S", "G/S", "G/S", "SCT U/T"],
        "AircraftCommander": ["Inst1", "Inst1", "Inst2", "Cadet A", "Inst1"],
        "SecondPilot": ["Cadet A", "Cadet A", "Cadet B", 0, "Cadet C"],
    })
    # Cadet A (twice, dedup) + Cadet B => 2 unique dual G/S cadets.
    # Solo row (SecondPilot 0) excluded; SCT U/T row excluded.
    assert gs_cadet_count(df) == 2


def test_gif_cadet_count():
    """Total GIF cadets = unique (date, aircraft, commander, 2nd pilot) GIF rows."""
    df = pd.DataFrame({
        "Date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02"]),
        "Aircraft": ["ZE123", "ZE123", "ZE123"],
        "AircraftCommander": ["Inst1", "Inst1", "Inst1"],
        "SecondPilot": ["Cadet A", "Cadet B", "Cadet C"],
        "Duty": ["GIF", "GIF", "SCT U/T"],
    })
    # Two distinct GIF crews on day 1; day-2 row excluded (not GIF) => 2.
    assert gif_cadet_count(df) == 2


def test_delta_gifs_previous_day():
    """Delta counts only GIFs on the most recent flying day; 0 when empty."""
    df = pd.DataFrame({
        "Date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-02"]),
        "Aircraft": ["ZE123", "ZE123", "ZE123"],
        "AircraftCommander": ["Inst1", "Inst1", "Inst1"],
        "SecondPilot": ["Cadet A", "Cadet B", "Cadet C"],
        "Duty": ["GIF", "GIF", "GIF"],
    })
    # Latest day (02 Jan) had two distinct GIF crews; 01 Jan ignored.
    assert delta_gifs_previous_day(df) == 2
    assert delta_gifs_previous_day(pd.DataFrame()) == 0

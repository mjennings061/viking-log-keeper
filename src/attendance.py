from typing import Any

import pandas as pd
from pathlib import Path
import calendar


def ingest_roster(file_path: str) -> pd.Series:
    """
    Extract data from an excel roster.
    Output a pandas dataframe.

    Parameters:
    - file_path (str): The path to the excel roster file.

    Returns:
    - raw_df (pandas.DataFrame): The extracted data as a pandas dataframe.
    """
    # Validate the file path.
    if not Path(file_path).is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    # Validate the file extension.
    if Path(file_path).suffix != ".xlsx":
        raise ValueError("Invalid file extension. Expected .xlsx")

    # Read the excel file.
    with pd.ExcelFile(file_path) as xls:
        # Extract the attendace.
        sr = extract_attendance(xls)
        big_series = pd.concat(sr)
        big_series = big_series.sort_index()

    return big_series

def extract_attendance(xls: pd.ExcelFile) -> list[Any]:
    """Extract the attendance levels from the excel file.

    Args:
        xls (pd.ExcelFile): The excel file object.

    Returns:
        pd.DataFrame: The extracted attendance dataframe with dates as columns."""
    raw_all_months = pd.read_excel(xls, sheet_name=None, header=1)
    all_months = []
    year = 2025 # HARD CODED


    # {1: 'January', 2: 'February', ...}
    months_dict = {i: name for i, name in enumerate(calendar.month_name) if name}

    for month_num, month_name in months_dict.items():
        if month_name in raw_all_months:
            raw_series = sheet_df_to_series(raw_all_months[month_name])
            series = convert_day_to_date(raw_series, month_num, year)
            all_months.append(series)

    return all_months

def sheet_df_to_series(raw_df: pd.DataFrame) -> pd.Series:
    """Parse the raw dataframe to extract the attendance levels.

    Args:
        df (pd.DataFrame): The raw dataframe extracted from the excel file.

    Returns:
        pd.Series: The parsed attendance series with dates as indices."""
    # raw_df.columns = raw_df.iloc[0]
    # raw_df = raw_df[1:].reset_index(drop=True)
    # Find the summary row that contains numeric values after Y/N data
    df = raw_df.iloc[:, 1:]

    staffing_idx = None
    """Find the first row that contains numeric summaries after Y/N data"""
    for idx, row in df.iterrows():
        # Check if row has numeric values (not Y/N strings)
        # Skip rows that are all NaN or contain Y/N
        non_null = row.dropna()
        if len(non_null) > 0:
            # Check if values contain predominantly numeric data (not 'Y' or 'N')
            # Allow for some string/datetime values in extra columns
            numeric_count = sum(1 for val in non_null if isinstance(val, (int, float)))
            # If we have multiple numeric values, this is likely the summary row
            if numeric_count >= 3:  # At least 3 numeric values indicate a summary row
                staffing_idx = idx
                break

    if staffing_idx is None:
        raise ValueError("No numeric summary row found in the dataframe")

    series = df.iloc[staffing_idx]

    series = series.dropna()

    return series

def convert_day_to_date(sr: pd.Series, month: int, year: int) -> pd.Series:
    """Convert the day numbers in the series to actual date objects.

    Args:
        series (pd.Series): The attendance series with day numbers as indices.

    Returns:
        pd.Series: The attendance series with date objects as indices."""
    # 1. Convert index to numeric, turning 'Unnamed: X' into NaN
    numeric_index = pd.to_numeric(sr.index, errors='coerce')

    # 2. Filter the series to keep only the valid numeric days
    sr = sr[numeric_index.notna()].copy()

    # Update our numeric index after filtering
    clean_days = pd.to_numeric(sr.index).astype(int)

    # 3. Determine the months (handling your first-element logic)
    new_months = []
    for i, day in enumerate(clean_days):
        if i == 0 and day > 20:
            new_months.append(month - 1)
        else:
            new_months.append(month)

    # 4. Final Conversion
    sr.index = pd.to_datetime({
        'year': year,
        'month': new_months,
        'day': clean_days
    })
    return sr



def main():
     print(ingest_roster("../rsc/Roster 2025.xlsx"))




main()
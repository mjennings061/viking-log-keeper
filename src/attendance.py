import pandas as pd
from pathlib import Path
import calendar


def ingest_roster(file_path: str) -> pd.DataFrame:
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
        raw_df = extract_attendance(xls)
    return raw_df



def extract_attendance(xls: pd.ExcelFile) -> pd.DataFrame:
    """Extract the attendance levels from the excel file.

    Args:
        xls (pd.ExcelFile): The excel file object.

    Returns:
        pd.DataFrame: The extracted attendance dataframe with dates as columns."""
    raw_all_months = pd.read_excel(xls, sheet_name=None, header=1)
    all_months = []

    # {1: 'January', 2: 'February', ...}
    months_dict = {i: name for i, name in enumerate(calendar.month_name) if name}

    for month_num, month_name in months_dict.items():
        if month_name in raw_all_months:
            all_months.append(sheet_df_to_series(raw_all_months[month_name]))



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


print(extract_attendance(("../rsc/Roster 2025.xlsx")))

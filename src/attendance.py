import pandas as pd
from pathlib import Path


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
    # Constants.
    SHEET_NAME = "January"

    # Read from the log sheet with no header first
    raw_df = pd.read_excel(
        xls,
        sheet_name=SHEET_NAME,
        header=1
    )


    return raw_df

def parse_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Parse the raw dataframe to extract the attendance levels.

    Args:
        df (pd.DataFrame): The raw dataframe extracted from the excel file.

    Returns:
        pd.DataFrame: The parsed attendance dataframe with dates as columns."""
    # Find the summary row that contains numeric values after Y/N data
    df = raw_df.iloc[:, 1:]


    """Find the first row that contains numeric summaries after Y/N data"""
    for idx, row in df.iterrows():
        # Check if row has numeric values (not Y/N strings)
        # Skip rows that are all NaN or contain Y/N
        non_null = row.dropna()
        if len(non_null) > 0:
            # Check if values are numeric (not 'Y' or 'N')
            if all(isinstance(val, (int, float)) for val in non_null if pd.notna(val)):
                staffing_idx = idx

    series = df.iloc[staffing_idx]

    series = series.dropna()

    return series


print(parse_df(ingest_roster("../rsc/Roster 2025.xlsx")))

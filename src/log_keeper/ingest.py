"""ingest.py

This file handles log sheet extraction and sanitisation.
"""

# Get packages.
import logging
from pathlib import Path
from typing import Tuple, Union
import pandas as pd
from tqdm import tqdm

# Get the logger instance.
logger = logging.getLogger(__name__)


def ingest_log_sheet(file_path: str) -> pd.DataFrame:
    """
    Extract data from an excel log sheet.
    Output a pandas dataframe.

    Parameters:
    - file_path (str): The path to the excel log sheet file.

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
        # Extract the launches.
        raw_df = extract_launches(xls)
    return raw_df


def ingest_log_sheet_from_upload(file) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Extract data from an uploaded excel log sheet.

    Parameters:
        file (UploadedFile/BytesIO): The uploaded excel log sheet file.

    Returns:
        raw_df (pandas.DataFrame): The extracted data as a pandas dataframe.
        aircraft_info (pandas.DataFrame): The extracted aircraft information
            e.g. launches/hours.
    """
    # Validate the file extension.
    if Path(file.name).suffix != ".xlsx":
        raise ValueError("Invalid file extension. Expected .xlsx")

    # Read the excel file.
    with pd.ExcelFile(file) as xls:
        # Extract the launches.
        raw_df = extract_launches(xls)

        # Extract the aircraft information.
        aircraft_info = extract_aircraft_info(xls)
    return raw_df, aircraft_info


def extract_launches(xls: pd.ExcelFile) -> pd.DataFrame:
    """Extract the launches from the excel file.

    Args:
        xls (pd.ExcelFile): The excel file object.

    Returns:
        pd.DataFrame: The extracted launches dataframe."""
    # Constants.
    SHEET_NAME = "FORMATTED"

    # Read from the log sheet.
    raw_df = pd.read_excel(
        xls,
        sheet_name=SHEET_NAME,
        dtype={
            'AircraftCommander': 'string',
            '2ndPilot': 'string',
            'Duty': 'string',
            'TakeOffTime': 'datetime64[ns]',
            'LandingTime': 'datetime64[ns]',
            'FlightTime': 'UInt16',
            'SPC': 'UInt8',
            'PLF': 'bool',
            'Aircraft': 'string',
            'Date': 'datetime64[ns]',
            'P1': 'bool',
            'P2': 'bool'
        }
    )

    # Validate the log sheet. Raise an error if invalid.
    validate_log_sheet(raw_df)
    return raw_df


def parse_hours_after(s):
    """Parse the hours after string into number of minutes.

    Args:
        s (str): The hours after string.

    Returns:
        int: The total minutes."""
    if pd.isna(s):
        logging.warning("Hours after is NaT.")
        return pd.NA
    try:
        total_minutes = s.days * 24 * 60 + s.seconds // 60
        return total_minutes
    except (ValueError, AttributeError):
        # Handle cases where the format is incorrect or the value
        # is not a string.
        logging.warning("Invalid hours after format: %s", s)
        return pd.NA


def extract_aircraft_info(xls: pd.ExcelFile) -> dict:
    """Extract aircraft information from the excel file.

    Args:
        xls (pd.ExcelFile): The excel file object.

    Returns:
        dict: The extracted aircraft information."""
    # Constants.
    SHEET_NAME = "_AIRCRAFT"

    # Read from the log sheet.
    try:
        raw_df = pd.read_excel(
            xls,
            sheet_name=SHEET_NAME,
            dtype={
                'Date': 'datetime64[ns]',
                'Aircraft': 'string',
                'Launches After': 'UInt32'
            },
            converters={
                'Hours After': parse_hours_after
            }
        )
        # Validate the log sheet. Raise an error if invalid.
        validate_aircraft_info(raw_df)
    except Exception:
        logging.error("Could not read aircraft info.", exc_info=True)
        raw_df = pd.DataFrame()
    return raw_df


def validate_aircraft_info(aircraft_info_df: pd.DataFrame):
    """Validate the aircraft information dataframe.

    Args:
        aircraft_info_df (pd.DataFrame): The aircraft information dataframe."""
    # Check if the dataframe is empty.
    if aircraft_info_df.empty:
        raise ValueError("Aircraft information is empty.")

    # Check for an empty cell.
    if aircraft_info_df.isna().any().any():
        raise ValueError("Aircraft information contains empty values.")

    # Check aircraft name does not contain "ZEXXX".
    if not any("ZE" in aircraft for aircraft in aircraft_info_df['Aircraft']):
        raise ValueError("Aircraft name does not contain 'ZE'.")

    # Check for NaT (not a time).
    columns_to_check = ['Date']
    if aircraft_info_df[columns_to_check].isna().any().any():
        raise ValueError("Date column contains NaT values.")

    # Check for wild values in the Launches After column.
    launches_after = aircraft_info_df['Launches After']
    if any(launches_after < 0) or any(launches_after > 100e6):
        raise ValueError("Difference in AC launches is too large.")

    # Check for wild values in the Hours After column.
    hours_after = aircraft_info_df['Hours After']
    max_minutes = 100e3 * 60
    if any(hours_after <= 0) or any(hours_after > max_minutes):
        raise ValueError("Difference in AC hours is too large.")


def validate_log_sheet(log_sheet_df: pd.DataFrame):
    """
    Validate the log sheet dataframe.

    Parameters:
    - log_sheet_df (pandas.DataFrame): The log sheet dataframe to be validated.
    """
    # Constants.
    MAX_FLIGHT_TIME = 240   # [Minutes].

    # Check if the dataframe is empty.
    if log_sheet_df.empty:
        raise ValueError("Log sheet is empty.")

    # Check for NaT (not a time).
    columns_to_check = ['Date', 'TakeOffTime', 'LandingTime']
    if log_sheet_df[columns_to_check].isna().any().any():
        raise ValueError("Date or time columns contain NaT values.")

    # Check if the LandingTime is before the TakeOffTime.
    if (log_sheet_df['LandingTime'] < log_sheet_df['TakeOffTime']).any():
        raise ValueError("LandingTime is before TakeOffTime.")

    # Check for wild values in the FlightTime column.
    if log_sheet_df['FlightTime'].max() > MAX_FLIGHT_TIME:
        raise ValueError("FlightTime column contains huge value.")

    # Check there is an aircraft. Excel defaults to 0 if empty.
    if (log_sheet_df['Aircraft'] == '0').any():
        raise ValueError("Aircraft column has no aircraft.")


def sanitise_log_sheets(log_sheet_df):
    """
    Filter and replace data in the master log dataframe.

    Parameters:
    log_sheet_df (pandas.DataFrame): The master log dataframe to
        be filtered and modified.

    Returns:
    pandas.DataFrame: The filtered and modified master log dataframe.
    """
    # Filter the log sheets to remove AircraftCommander "0"
    log_sheet_df = log_sheet_df[log_sheet_df.AircraftCommander != "0"]

    # Filter "launches" with a takeoff time equal to 00:00:00.
    log_sheet_df = log_sheet_df[
        log_sheet_df['TakeOffTime'].dt.time != pd.Timestamp('00:00:00').time()
    ]

    # Change Duty column to upper case.
    log_sheet_df.loc[:, 'Duty'] = log_sheet_df['Duty'].str.upper()

    # Change GIC to GIF.
    log_sheet_df.loc[log_sheet_df['Duty'] == 'GIC', 'Duty'] = 'GIF'

    # Change SGS to G/S.
    log_sheet_df.loc[log_sheet_df['Duty'] == 'SGS', 'Duty'] = 'G/S'

    # Change GWGT to AGT.
    log_sheet_df.loc[log_sheet_df['Duty'] == 'GWGT', 'Duty'] = 'AGT'

    # Add SCT into QGI and U/T duties e.g. "QGI" -> "SCT QGI"
    log_sheet_df.loc[log_sheet_df['Duty'] == 'U/T', 'Duty'] = 'SCT U/T'
    log_sheet_df.loc[log_sheet_df['Duty'] == 'QGI', 'Duty'] = 'SCT QGI'

    # Change aircraft commander and second pilot to Upper Case.
    log_sheet_df.loc[:, 'AircraftCommander'] = \
        log_sheet_df['AircraftCommander'].str.title()
    log_sheet_df.loc[:, '2ndPilot'] = log_sheet_df['2ndPilot'].str.title()

    # Remove trailing whitespace in AircraftCommander and 2ndPilot.
    log_sheet_df.loc[:, 'AircraftCommander'] = \
        log_sheet_df['AircraftCommander'].str.strip()
    log_sheet_df.loc[:, '2ndPilot'] = log_sheet_df['2ndPilot'].str.strip()

    # Sort by takeofftime.
    log_sheet_df = log_sheet_df.sort_values(
        by="TakeOffTime",
        ascending=True,
        na_position="first"
    )

    # Rename 2ndPilot to SecondPilot.
    log_sheet_df.rename(columns={"2ndPilot": "SecondPilot"}, inplace=True)

    return log_sheet_df


def collate_log_sheets(dir_path: Union[str, Path]) -> pd.DataFrame:
    """
    Collate all log sheets into a single dataframe
    using the path to the log sheet directory.

    Args:
        dir_path (str): The path to the log sheet directory.

    Returns:
        pandas.DataFrame: The collated dataframe containing data
            from all log sheets.

    Raises:
        FileNotFoundError: If no log sheets are found in the
            specified directory.
    """
    # Convert to Path object.
    dir_path = Path(dir_path)

    # Get the directory contents.
    FILE_NAME = "2965D_*.xlsx"
    dir_contents = dir_path.glob(f"{FILE_NAME}")
    log_sheet_files = [x for x in dir_contents if x.is_file()]

    # Check if list is empty.
    if not log_sheet_files:
        raise FileNotFoundError(f"No log sheets found in \n{dir_path}")

    # Log the number of log sheets found.
    logger.info("Found %d log sheets.", len(log_sheet_files))

    # Extract data from each log sheet.
    log_sheet_list = []
    for file_path in tqdm(log_sheet_files,
                          desc="Processing log sheets",
                          unit="file"):
        # Get the log sheet data.
        try:
            this_sheet_df = ingest_log_sheet(file_path)
            log_sheet_list.append(this_sheet_df)
        except Exception:   # pylint: disable=broad-except
            if file_path.name != "2965D_YYMMDD_ZEXXX.xlsx":
                warning_msg = f"Log sheet invalid: {file_path.name}"
                tqdm.write(warning_msg)

    # Concatenate the log sheets.
    log_sheet_df = pd.concat(log_sheet_list, ignore_index=True)
    logger.info("Done importing log sheets.")

    # Sanitise the log sheets.
    collated_df = sanitise_log_sheets(log_sheet_df)
    return collated_df


if __name__ == "__main__":
    # Test the collate function.
    test_dir_path = "/home/michaeljennings/Downloads"
    test_collated_df = collate_log_sheets(test_dir_path)
    logger.info(test_collated_df.head())

    # Test the ingest function from an upload.
    upload_collated_df = ingest_log_sheet_from_upload(test_dir_path)
    logger.info(upload_collated_df.head())

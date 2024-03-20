"""ingest.py

This file handles log sheet extraction and sanitisation.
"""

import warnings
import pandas as pd


def ingest_log_sheet(file_path):
    """
    Extract data from an excel log sheet.
    Output a pandas dataframe.

    Parameters:
    - file_path (str): The path to the excel log sheet file.

    Returns:
    - raw_df (pandas.DataFrame): The extracted data as a pandas dataframe.
    """
    # Constants.
    SHEET_NAME = "FORMATTED"

    # Read from the log sheet.
    raw_df = pd.read_excel(
        file_path,
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

    return raw_df


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

    # Sort by takeofftime.
    log_sheet_df = log_sheet_df.sort_values(
        by="TakeOffTime",
        ascending=True,
        na_position="first"
    )

    # Rename 2ndPilot to SecondPilot.
    log_sheet_df.rename(columns={"2ndPilot": "SecondPilot"}, inplace=True)

    return log_sheet_df


def collate_log_sheets(dir_path):
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
    # Get the directory contents.
    FILE_NAME = "2965D_*.xlsx"
    dir_contents = dir_path.glob(f"{FILE_NAME}")
    log_sheet_files = [x for x in dir_contents if x.is_file()]

    # Check if list is empty.
    if not log_sheet_files:
        raise FileNotFoundError(f"No log sheets found in \n{dir_path}")

    # Extract data from each log sheet.
    log_sheet_df = pd.DataFrame()
    for i_file, file_path in enumerate(log_sheet_files):
        # Get the log sheet data.
        try:
            this_sheet_df = ingest_log_sheet(file_path)
            # TODO: Write a function to also ingest the launches
            # and hours CF for F724 if given.
            if i_file == 0:
                # Create a new dataframe based on the first file ingest.
                log_sheet_df = this_sheet_df
            else:
                # Append to the master dataframe.
                log_sheet_df = pd.concat(
                    [log_sheet_df, this_sheet_df],
                    ignore_index=True
                )
        except Exception as e:
            if file_path.name != "2965D_YYMMDD_ZEXXX.xlsx":
                warnings.warn(
                    f"Log sheet invalid: {file_path.name}",
                    RuntimeWarning
                )
                print(e)

    collated_df = sanitise_log_sheets(log_sheet_df)
    return collated_df

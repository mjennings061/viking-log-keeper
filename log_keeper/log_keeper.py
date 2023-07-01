"""log_keeper.py
661 VGS - Collate all log sheets (2965D) into one master log."""

# Get packages.
from pathlib import Path
import pandas as pd
import warnings


def ingest_log_sheet(file_path):
    """
    Extract data from an excel log sheet.
    Output a pandas dataframe.
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
        'Date': 'string'
        }
    )
    
    return raw_df


def sanitise_log_sheets(log_sheet_df):
    """Filter and replace data in the master log dataframe."""

    # Filter the log sheets to remove AircraftCommander "0"
    log_sheet_df = log_sheet_df[log_sheet_df.AircraftCommander != "0"]

    # Change GIC to GIF.
    log_sheet_df.loc[log_sheet_df['Duty'] == 'GIC', 'Duty'] = 'GIF'

    # Add SCT into QGI and U/T duties e.g. "QGI" -> "SCT QGI"
    log_sheet_df.loc[log_sheet_df['Duty'] == 'U/T', 'Duty'] = 'SCT U/T'
    log_sheet_df.loc[log_sheet_df['Duty'] == 'QGI', 'Duty'] = 'SCT QGI'
    
    # Change aircraft commander and second pilot to Upper Case.
    log_sheet_df.loc[:, 'AircraftCommander'] = log_sheet_df['AircraftCommander'].str.title()
    log_sheet_df.loc[:, '2ndPilot'] = log_sheet_df['2ndPilot'].str.title()

    # Change date to DD/MM/YYYY format.
    log_sheet_df.loc[:, 'Date'] = log_sheet_df['Date'].str[:10]

    # Sort by takeofftime.
    log_sheet_df = log_sheet_df.sort_values(by="TakeOffTime", ascending=True, na_position="first")

    # Rename 2ndPilot to SecondPilot.
    log_sheet_df.rename(columns={"2ndPilot": "SecondPilot"}, inplace=True)

    return log_sheet_df


def collate_log_sheets(dir_path):
    """Collate all log sheets into a single dataframe using the path to the log sheet directory."""
    # Get the directory contents.
    FILE_NAME = "2965D_*.xlsx"
    dir_contents = dir_path.glob(f"{FILE_NAME}")
    log_sheet_files = [x for x in dir_contents if x.is_file()]

    # Extract data from each log sheet.
    # Constants.
    N_COLS = 10

    for i_file, file_path in enumerate(log_sheet_files):
        # Get the log sheet data.
        try:
            this_sheet_df = ingest_log_sheet(file_path)
            if i_file == 0:
                # Create a new dataframe based on the first file ingest.
                log_sheet_df = this_sheet_df
            else:
                # Append to the master dataframe.
                log_sheet_df = pd.concat([log_sheet_df, this_sheet_df], ignore_index=True)
        except:
            warnings.warn(f"Log sheet invalid: {file_path.name}", RuntimeWarning, stacklevel=2)

    collated_df = sanitise_log_sheets(log_sheet_df)

    return collated_df


def master_log_to_excel(master_log, output_file_path):
    """Save the master log dataframe to an excel table."""

    # Sheet the table should be inserted into.
    SHEET_NAME = "MASTER LOG"

    # Create the excel file and table.
    writer = pd.ExcelWriter(output_file_path, engine='xlsxwriter')
    master_log.to_excel(
        writer,
        sheet_name=SHEET_NAME,
        index=False,
        header=False,
        startrow=1
    )

    # Get the xlsxwriter workbook and worksheet objects.
    workbook = writer.book
    worksheet = writer.sheets[SHEET_NAME]

    # Get the dimensions of the dataframe.
    (max_row, max_col) = master_log.shape

    # Create a list of column headers, to use in add_table().
    column_settings = [{"header": column} for column in master_log.columns]

    # Add the Excel table structure. Pandas will add the data.
    worksheet.add_table(
        0, 0, max_row, max_col - 1, 
        {"columns": column_settings, 'style': 'Table Style Medium 1'}
    )

    # Make the columns wider for clarity.
    worksheet.set_column(0, max_col - 1, 17)

    # Change the format of the 'Date' column to 'dd/mm/yyyy'.
    date_column = master_log.columns.get_loc("Date")
    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'}) # type: ignore
    worksheet.set_column(date_column, date_column, 10, date_format)

    # Close the Pandas Excel writer and output the Excel file.
    writer.close()


def main():
    # Initial comment.
    print("viking-log-keeper: Starting...")

    # Get the file path.
    root_dir = Path.home()

    # Path to the sharepoint directory.
    SHAREPOINT_DIR = Path(
        root_dir, 
        "Royal Air Force Air Cadets",
        "661 VGS - RAF Kirknewton - 661 Documents",
    )
    # Path to the log sheets directory.
    LOG_SHEETS_DIR = Path(
        SHAREPOINT_DIR, 
        "Log Sheets"
    )

    # Output file path.
    OUTPUT_FILE = Path(
        SHAREPOINT_DIR,
        "Stats",
        "MASTER-LOG.xlsx"
    )

    # Create a dataframe of all log sheets.
    master_log = collate_log_sheets(LOG_SHEETS_DIR)

    # Save the master log to excel.
    master_log_to_excel(master_log, OUTPUT_FILE)

    # Print success message.
    print("viking-log-keeper: Success!")


if __name__ == "__main__":
    main()
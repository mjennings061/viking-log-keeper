"""main.py
661 VGS - Collate all log sheets (2965D) into one master log DB.
"""

# Get packages.
from pathlib import Path
import pandas as pd
import warnings
from datetime import datetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Get modules.
from log_keeper.get_config import get_config, remove_config

# Project constants.
PROJECT_NAME = "viking-log-keeper"


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
        'Date': 'datetime64[ns]',
        'P1': 'bool',
        'P2': 'bool'
        }
    )
    
    return raw_df


def sanitise_log_sheets(log_sheet_df):
    """Filter and replace data in the master log dataframe."""

    # Filter the log sheets to remove AircraftCommander "0"
    log_sheet_df = log_sheet_df[log_sheet_df.AircraftCommander != "0"]

    # Filter "launches" with a takeoff time equal to 00:00:00.
    log_sheet_df = log_sheet_df[log_sheet_df['TakeOffTime'].dt.time != pd.Timestamp('00:00:00').time()]

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
    log_sheet_df.loc[:, 'AircraftCommander'] = log_sheet_df['AircraftCommander'].str.title()
    log_sheet_df.loc[:, '2ndPilot'] = log_sheet_df['2ndPilot'].str.title()

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
    log_sheet_df = pd.DataFrame()
    for i_file, file_path in enumerate(log_sheet_files):
        # Get the log sheet data.
        try:
            this_sheet_df = ingest_log_sheet(file_path)
            # TODO: Write a function to also ingest the launches and hours CF for F724 if given.
            if i_file == 0:
                # Create a new dataframe based on the first file ingest.
                log_sheet_df = this_sheet_df
            else:
                # Append to the master dataframe.
                log_sheet_df = pd.concat([log_sheet_df, this_sheet_df], ignore_index=True)
        except Exception as e:
            if file_path.name != "2965D_YYMMDD_ZEXXX.xlsx":
                warnings.warn(f"Log sheet invalid: {file_path.name}", RuntimeWarning)
                print(e)


    collated_df = sanitise_log_sheets(log_sheet_df)
    return collated_df


def launches_to_excel(launches_df, output_file_path):
    """Save the master log dataframe to an excel table."""

    # Sheet the table should be inserted into.
    SHEET_NAME = "MASTER LOG"

    # Create the excel file and table.
    try:
        writer = pd.ExcelWriter(output_file_path, engine='xlsxwriter')
    except Exception as e:
        # Writing to MASTER_LOG didn't work. We will need to create a temp file to copy and paste.
        print(e)
        # Get new path using todays date.
        date = datetime.today().strftime('%y%m%d')
        output_file_path = output_file_path.with_suffix('')
        output_file_path = Path(str(output_file_path) + '-' + date + '.xlsx')
        print(f"{PROJECT_NAME}: Writing to ")
        writer = pd.ExcelWriter(output_file_path, engine='xlsxwriter')
        
    launches_df.to_excel(
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
    (max_row, max_col) = launches_df.shape

    # Create a list of column headers, to use in add_table().
    column_settings = [{"header": column} for column in launches_df.columns]

    # Add the Excel table structure. Pandas will add the data.
    worksheet.add_table(
        0, 0, max_row, max_col - 1, 
        {"columns": column_settings, 'style': 'Table Style Medium 1'}
    )

    # Make the columns wider for clarity.
    worksheet.set_column(0, max_col - 1, 17)

    # Change the format of the 'Date' column to 'dd/mm/yyyy'.
    date_column = launches_df.columns.get_loc("Date")
    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'}) # type: ignore
    worksheet.set_column(date_column, date_column, 10, date_format)

    # Close the Pandas Excel writer and output the Excel file.
    writer.close()

    # Print success message.
    print(f"{PROJECT_NAME}: Saved to {output_file_path.name}")


def launches_to_db(launches_df, db_config):
    """Save the master log dataframe to a MongoDB."""
    # Get environment variables.
    DB_HOSTNAME = db_config["DB_HOSTNAME"]
    DB_USERNAME = db_config["DB_USERNAME"]
    DB_PASSWORD = db_config["DB_PASSWORD"]
    DB_COLLECTION_NAME = db_config["DB_COLLECTION_NAME"]
    DB_NAME = db_config["DB_NAME"]

    # Format dataframe to be saved.
    master_dict = launches_df.to_dict('records')

    # Create the DB connection URL
    db_url = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOSTNAME}/?retryWrites=true&w=majority"

    # Create a new client and connect to the server
    client = MongoClient(db_url, server_api=ServerApi('1'))

    # Print success message if ping is successful.
    if client.admin.command('ping')['ok'] == 1.0:
        print(f"{PROJECT_NAME}: Connected to DB.")
    else:
        raise ConnectionError(f"{PROJECT_NAME}: Could not connect to DB.")

    # Get the database.
    db = client[DB_NAME]

    # Get all collections in the DB.
    collections = db.list_collection_names()

    # Backup the old collection with today's date as the suffix.
    # Get today's date as YYMMDD.
    today = datetime.today().strftime('%y%m%d')

    # Create collection search string.
    collection_search_string = f"{DB_COLLECTION_NAME}_{today}"

    # Check if the backup exists and replace it.
    if collection_search_string in collections:
        db.drop_collection(collection_search_string)

    # Rename the old collection.
    if DB_COLLECTION_NAME in collections:
        old_collection = db[DB_COLLECTION_NAME]
        old_collection.rename(collection_search_string)

    # Save to the DB.
    collection = db.create_collection(DB_COLLECTION_NAME)
    collection.insert_many(master_dict)
    print(f"{PROJECT_NAME}: Saved to DB.")
    
    # Close DB session.
    client.close()


def find_directory(start_path, search_string):
    """Find a directory."""
    # Search for the directory.
    for dir in start_path.iterdir():
        if dir.is_dir() and search_string in dir.name:
            return dir
        
    # Raise an error if the directory is not found.
    raise FileNotFoundError("Could not find OneDrive directory.")


def get_onedrive_path():
    """Get the path to OneDrive."""
    # Name of the onedrive directory to search for.
    ONEDRIVE_SEARCH_STRING = "Royal Air Force Air Cadets"
    DOCUMENTS_SEARCH_STRING = "Documents"
    
    # Search for the onedrive from home.
    root_dir = Path.home()
    onedrive_path = find_directory(root_dir, ONEDRIVE_SEARCH_STRING)

    # Now get the path to the documents directory.
    documents_path = find_directory(onedrive_path, DOCUMENTS_SEARCH_STRING)
    return documents_path


def main():
    # Initial comment.
    print(f"{PROJECT_NAME}: Starting...")

    # Get the file paths.
    onedrive_path = get_onedrive_path()

    # Path to the log sheets directory.
    log_sheets_dir = Path(
        onedrive_path, 
        "Log Sheets"
    )

    # Output file path.
    master_log_filepath = Path(
        log_sheets_dir,
        "Master Log.xlsx"
    )

    # Create a dataframe of all log sheets.
    launches_df = collate_log_sheets(log_sheets_dir)

    # Save the launches to excel.
    launches_to_excel(launches_df, master_log_filepath)

    # Get the config filepath, or use the CLI interface to create one.
    db_config = get_config()

    # Save the master log to MongoDB Atlas.
    try:
        launches_to_db(launches_df, db_config)
    except Exception as e:
        # Filter a ConnectionError.
        if isinstance(e, ConnectionError):
            print(e)
        else:
            # Remove the config file and try again.
            print(f"{PROJECT_NAME}: Could not save to DB. Try changing the config file.")
            remove_config()
            db_config = get_config()
            launches_to_db(launches_df, db_config)

    # Print success message.
    print(f"{PROJECT_NAME}: Success!")

    # Pause for user input.
    input("Press any key to finish...")


if __name__ == "__main__":
    # Run the log keeper.
    main()

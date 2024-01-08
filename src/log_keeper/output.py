"""output.py

This file handles outputting the master log to excel and MongoDB Atlas.
"""

import logging
from pathlib import Path
import pandas as pd
from datetime import datetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from log_keeper.utils import PROJECT_NAME


def launches_to_excel(launches_df, output_file_path):
    """Save the master log dataframe to an excel table."""

    # Sheet the table should be inserted into.
    SHEET_NAME = "MASTER LOG"

    # Create the excel file and table.
    try:
        writer = pd.ExcelWriter(output_file_path, engine='xlsxwriter')
    except Exception as e:
        # Writing to MASTER_LOG didn't work. We will need to create a temp
        # file to copy and paste.
        logging.exception(e)
        # Get new path using todays date.
        date = datetime.today().strftime('%y%m%d')
        output_file_path = output_file_path.with_suffix('')
        output_file_path = Path(str(output_file_path) + '-' + date + '.xlsx')
        logging.info(f"{PROJECT_NAME}: Writing to {output_file_path.name}")
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
    date_format = workbook.add_format(
        {'num_format': 'dd/mm/yyyy'}
    )  # type: ignore
    worksheet.set_column(date_column, date_column, 10, date_format)

    # Close the Pandas Excel writer and output the Excel file.
    writer.close()

    # Print success message.
    logging.info(f"{PROJECT_NAME}: Saved to {output_file_path.name}")


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
    db_url = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOSTNAME}" + \
        "/?retryWrites=true&w=majority"

    # Create a new client and connect to the server
    client = MongoClient(db_url, server_api=ServerApi('1'))

    # Print success message if ping is successful.
    if client.admin.command('ping')['ok'] == 1.0:
        logging.info(f"{PROJECT_NAME}: Connected to DB.")
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
    logging.info(f"{PROJECT_NAME}: Saved to DB.")

    # Close DB session.
    client.close()

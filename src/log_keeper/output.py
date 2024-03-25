"""output.py

This file handles outputting the master log to excel and MongoDB Atlas.
"""

import logging
from pathlib import Path
import pandas as pd
from datetime import datetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

logger = logging.getLogger(__name__)


def launches_to_excel(launches_df, output_file_path):
    """Save the master log dataframe to an excel table."""

    # Sheet the table should be inserted into.
    SHEET_NAME = "MASTER LOG"

    # Create the excel file and table.
    try:
        writer = pd.ExcelWriter(output_file_path, engine='xlsxwriter')
    except Exception:
        # Writing to MASTER_LOG didn't work. We will need to create a temp
        # file to copy and paste.
        logger.error("Could not write to MASTER_LOG.xlsx. ", exc_info=True)
        # Get new path using todays date.
        date = datetime.today().strftime('%y%m%d')
        output_file_path = output_file_path.with_suffix('')
        output_file_path = Path(str(output_file_path) + '-' + date + '.xlsx')
        logger.info("Writing to %s", output_file_path.name)
        writer = pd.ExcelWriter(output_file_path, engine='xlsxwriter')

    # Write the dataframe to the Excel file.
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
    logger.info("Saved to %s", output_file_path.name)


def launches_to_db(launches_df, db_config):
    """Save the master log dataframe to a MongoDB."""
    # Get environment variables.
    db_hostname = db_config.db_hostname
    db_username = db_config.db_username
    db_password = db_config.db_password
    db_collection_name = db_config.db_collection_name
    db_name = db_config.db_name

    # Format dataframe to be saved.
    master_dict = launches_df.to_dict('records')

    # Create the DB connection URL
    db_url = f"mongodb+srv://{db_username}:{db_password}@{db_hostname}" + \
        "/?retryWrites=true&w=majority"

    # Create a new client and connect to the server
    client = MongoClient(
        db_url,
        server_api=ServerApi('1'),
        tls=True,
        tlsAllowInvalidCertificates=True
    )

    # Print success message if ping is successful.
    if client.admin.command('ping')['ok'] == 1.0:
        logger.info("Connected to DB.")
    else:
        raise ConnectionError("Could not connect to DB.")

    # Get the database.
    db = client[db_name]

    # Get all collections in the DB.
    collections = db.list_collection_names()

    # Backup the old collection with today's date as the suffix.
    # Get today's date as YYMMDD.
    today = datetime.today().strftime('%y%m%d')

    # Create collection search string.
    collection_search_string = f"{db_collection_name}_{today}"

    # Check if the backup exists and replace it.
    if collection_search_string in collections:
        db.drop_collection(collection_search_string)

    # Rename the old collection.
    if db_collection_name in collections:
        old_collection = db[db_collection_name]
        old_collection.rename(collection_search_string)

    # Save to the DB.
    logger.info("Saving to DB.")
    collection = db.create_collection(db_collection_name)
    collection.insert_many(master_dict)
    logger.info("Saved to DB.")

    # Close DB session.
    client.close()

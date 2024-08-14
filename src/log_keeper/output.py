"""output.py

This file handles outputting the master log to excel and MongoDB Atlas.
"""

# Standard library imports.
import logging
from pathlib import Path
import pandas as pd
from datetime import datetime
from pymongo import DeleteMany

# User defined modules.
from log_keeper.get_config import Database

# Get the logger instance.
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
        logger.warning(
            "Could not write to MASTER_LOG.xlsx. Saving to temp file."
        )
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


def backup_launches_collection(db: Database):
    """Backup the launches collection in MongoDB.

    Args:
        ddb (Database): The log sheet DB configuration.
    """
    # Get all collections in the DB.
    collections = db.db.list_collection_names()

    # Backup the old collection with today's date as the suffix.
    # Get today's date as YYMMDD.
    today = datetime.today().strftime('%y%m%d')

    # Create collection search string.
    collection_search_string = f"{db.launches_collection}_{today}"

    # Check if the backup exists and replace it.
    if collection_search_string in collections:
        db.db.drop_collection(collection_search_string)

    # Use aggregation with $out to backup the collection.
    db.get_launches_collection().aggregate([
        {"$match": {}},
        {"$out": collection_search_string},
    ])

    # Close the connection.
    db.client.close()


def launches_to_db(launches_df, db: Database):
    """Save the master log dataframe to a MongoDB.

    Args:
        launches_df (pd.DataFrame): The master log dataframe.
        db (Database): The log sheet DB configuration.
    """
    # Backup the current collection.
    backup_launches_collection(db=db)

    # Format dataframe to be saved.
    master_dict = launches_df.to_dict('records')

    # Save to the DB.
    logger.info("Saving to DB.")
    db.get_launches_collection().insert_many(master_dict)
    logger.info("Saved to DB.")

    # Close DB session.
    db.client.close()


def update_launches_collection(launches_df, db: Database):
    """Update the master log collection in MongoDB by checking the date
    and aircraft. Append new records and update existing records.

    Args:
        launches_df (pd.DataFrame): The master log dataframe.
        db (Database): VGS database.
    """
    # Backup the current collection.
    backup_launches_collection(db)

    # Connect to the DB.
    collection = db.get_launches_collection()

    # Group by date and aircraft.
    grouped = launches_df.groupby(['Date', 'Aircraft'])

    # Prepare bulk delete and inset operations.
    delete_ops = []

    # Step 1: Prepare bulk delete operations.
    for (date, aircraft) in grouped:
        # We want to delete all launches with the same date and aircraft
        # as the records we are about to insert.
        delete_query = {
            "Date": date,
            "Aircraft": aircraft,
        }
        delete_ops.append(DeleteMany(delete_query))

    if delete_ops:
        logging.info("Deleting %.0f sheets.", len(delete_ops))
        collection.bulk_write(delete_ops)

    # Step 2: Insert all the records.
    records = launches_df.to_dict('records')
    logging.info("Inserting %.0f launches.", len(records))
    collection.insert_many(records)

    # Close DB session.
    db.client.close()

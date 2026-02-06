# Standard library imports.
import pandas as pd
from pymongo import DeleteMany, UpdateOne

# User defined modules.
from datetime import datetime
from log_keeper import logger
from log_keeper.get_config import Database


def backup_attendance_collection(db: Database):
    """Backup the attendance collection in MongoDB.

    Args:
        db (Database): The log sheet DB configuration.
    """
    # Get all collections in the DB.
    collections = db.db.list_collection_names()

    # Backup the old collection with today's date as the suffix.
    # Get today's date as YYMMDD.
    today = datetime.today().strftime('%y%m%d')

    # Create collection search string.
    collection_search_string = f"{db.attendance_collection}_{today}"

    # Check if the backup exists and replace it.
    if collection_search_string in collections:
        db.db.drop_collection(collection_search_string)

    # Use aggregation with $out to backup the collection.
    db.get_attendance_collection().aggregate([
        {"$match": {}},
        {"$out": collection_search_string},
    ])

def attendance_to_db(attendance_df, db: Database):
    """Save the master log dataframe to a MongoDB.

    Args:
        attendance_df (pd.DataFrame): The master log dataframe.
        db (Database): The log sheet DB configuration.
    """
    # Backup the current collection.
    backup_attendance_collection(db=db)

    # Format dataframe to be saved.
    master_dict = attendance_df.to_dict('records')

    # Save to the DB.
    logger.info("Saving to DB.")
    db.get_attendance_collection().insert_many(master_dict)
    logger.info("Saved to DB.")

def update_attendance_collection(attendance_df, db: Database):
    """Update the master attendance collection in MongoDB by checking the year.
    Append new records and update existing records.

    Args:
        attendance_df (pd.DataFrame): The master log dataframe.
        db (Database): VGS database.
    """
    # Validate the dataframe is not empty.
    if attendance_df.empty:
        logger.warning("Empty dataframe. Nothing to update.")
        return

    # Backup the current collection.
    backup_attendance_collection(db=db)

    # Connect to the DB.
    collection = db.get_attendance_collection()

    # Prepare bulk delete and inset operations.
    delete_ops = []
    deleted_attendance = 0

    # Step 1: Prepare bulk delete operations.
    for date in attendance_df.index:
        delete_query = {"Date": date}
        deleted_attendance += collection.count_documents(delete_query)
        delete_ops.append(DeleteMany(delete_query))

    # Delete the records if they exist.
    if delete_ops:
        logger.info("Deleting %.0f attendance from %.0f days.",
                    deleted_attendance, len(delete_ops))
        collection.bulk_write(delete_ops)

    # Step 2: Insert all the records.
    documents = attendance_df.to_dict('records')
    logger.info("Inserting %.0f launches from %.0f days/aircraft.",
                len(documents), len(attendance_df))
    collection.insert_many(documents)

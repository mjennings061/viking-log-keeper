"""output.py

This file handles outputting the master log to excel and MongoDB Atlas.
"""

# Standard library imports.
import re
import zipfile
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from pymongo import DeleteMany, UpdateOne

# User defined modules.
from log_keeper import logger
from log_keeper.get_config import Database

# 2965D template pre-fill constants.
EXCEL_EPOCH = date(1899, 12, 30)
MINUTES_PER_DAY = 1440
TEMPLATE_SHEET_NAME = "2965D"
# Header cells filled on the 2965D sheet.
CELL_AIRCRAFT = "F2"
CELL_DATE = "O2"
CELL_HOURS_BF = "C4"
CELL_LAUNCHES_BF = "C5"
# Content type of a .xltx workbook part vs a normal .xlsx workbook part.
TEMPLATE_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument." "spreadsheetml.template.main+xml"
)
WORKBOOK_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument." "spreadsheetml.sheet.main+xml"
)


def _set_cell(sheet_xml: str, ref: str, inner: str, extra_attr: str = "") -> str:
    """Inject a value into a worksheet cell, preserving its existing style.

    Args:
        sheet_xml (str): The worksheet XML.
        ref (str): The cell reference, e.g. "C4".
        inner (str): XML to place inside the cell, e.g. "<v>1234</v>".
        extra_attr (str): Extra opening-tag attributes, e.g. ' t="inlineStr"'.

    Returns:
        str: The worksheet XML with the cell populated."""
    pattern = re.compile(
        r'<c r="%s"((?: [a-zA-Z:]+="[^"]*")*)\s*(?:/>|>.*?</c>)' % re.escape(ref),
        re.DOTALL,
    )

    def repl(match: re.Match) -> str:
        # Drop any existing type (e.g. shared-string) attribute, then add ours.
        attrs = re.sub(r' t="[^"]*"', "", match.group(1))
        return f'<c r="{ref}"{attrs}{extra_attr}>{inner}</c>'

    new_xml, count = pattern.subn(repl, sheet_xml, count=1)
    if count != 1:
        raise ValueError(
            f"Cell {ref} not found in the template's " f"{TEMPLATE_SHEET_NAME} sheet."
        )
    return new_xml


def fill_log_sheet(
    template_bytes: bytes,
    aircraft: str,
    launches_bf,
    hours_bf_minutes,
    sheet_date: date,
) -> bytes:
    """Pre-fill a 2965D template's header cells, preserving everything else.

    Args:
        template_bytes (bytes): The stored template (.xltx/.xlsx) file.
        aircraft (str): Aircraft number, e.g. "ZE683" (cell F2).
        launches_bf (int | None): Launches brought forward (C5); blank if None.
        hours_bf_minutes (int | None): Hours brought forward in minutes (C4),
            written as an Excel duration; blank if None.
        sheet_date (date): Date of the log sheet (O2).

    Returns:
        bytes: The filled .xlsx file."""
    # An xlsx is a zip of XML; patch 4 cells, copy the rest byte-for-byte.
    # (openpyxl would drop the form controls, image and drop-downs on save.)
    with zipfile.ZipFile(BytesIO(template_bytes)) as zin:
        # Locate the 2965D sheet's file: name -> rId (workbook) -> filename.
        workbook = zin.read("xl/workbook.xml").decode("utf-8")
        rid = re.search(
            r'<sheet[^>]*name="%s"[^>]*r:id="([^"]+)"' % TEMPLATE_SHEET_NAME,
            workbook,
        )
        if not rid:
            raise ValueError(
                f'"{TEMPLATE_SHEET_NAME}" sheet not found in the template.'
            )
        rels = zin.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        target = re.search(
            r'<Relationship[^>]*Id="%s"[^>]*Target="([^"]+)"' % rid.group(1),
            rels,
        )
        if not target:
            # Clear error instead of an AttributeError on a malformed template.
            raise ValueError(
                f"Relationship {rid.group(1)} for the "
                f"{TEMPLATE_SHEET_NAME} sheet is missing from the template."
            )
        sheet_path = "xl/" + target.group(1).lstrip("/")

        # Fill F2=aircraft, O2=date serial, C4=hours (mins/1440), C5=launches.
        # Each keeps its cell style; C4/C5 skipped when unknown (left blank).
        sheet_xml = zin.read(sheet_path).decode("utf-8")
        sheet_xml = _set_cell(
            sheet_xml,
            CELL_AIRCRAFT,
            f"<is><t>{escape(aircraft)}</t></is>",
            ' t="inlineStr"',
        )
        sheet_xml = _set_cell(
            sheet_xml, CELL_DATE, f"<v>{(sheet_date - EXCEL_EPOCH).days}</v>"
        )
        if hours_bf_minutes is not None:
            sheet_xml = _set_cell(
                sheet_xml, CELL_HOURS_BF, f"<v>{hours_bf_minutes / MINUTES_PER_DAY}</v>"
            )
        if launches_bf is not None:
            sheet_xml = _set_cell(
                sheet_xml, CELL_LAUNCHES_BF, f"<v>{int(launches_bf)}</v>"
            )

        # Mark as a workbook so Excel opens it editable, not as a copy.
        content_types = (
            zin.read("[Content_Types].xml")
            .decode("utf-8")
            .replace(TEMPLATE_CONTENT_TYPE, WORKBOOK_CONTENT_TYPE)
        )

        # Copy all parts; swap in only the 2 edited ones.
        edited = {
            sheet_path: sheet_xml.encode("utf-8"),
            "[Content_Types].xml": content_types.encode("utf-8"),
        }
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, edited.get(item.filename, zin.read(item.filename)))
    return buffer.getvalue()


def launches_to_excel(launches_df, output_file_path):
    """Save the master log dataframe to an excel table."""

    # Sheet the table should be inserted into.
    SHEET_NAME = "MASTER LOG"

    # Create the excel file and table.
    try:
        writer = pd.ExcelWriter(output_file_path, engine="xlsxwriter")
    except Exception:
        # Writing to MASTER_LOG didn't work. We will need to create a temp
        # file to copy and paste.
        logger.warning("Could not write to MASTER_LOG.xlsx. Saving to temp file.")
        # Get new path using todays date.
        date = datetime.today().strftime("%y%m%d")
        output_file_path = output_file_path.with_suffix("")
        output_file_path = Path(str(output_file_path) + "-" + date + ".xlsx")
        logger.info("Writing to %s", output_file_path.name)
        writer = pd.ExcelWriter(output_file_path, engine="xlsxwriter")

    # Write the dataframe to the Excel file.
    launches_df.to_excel(
        writer, sheet_name=SHEET_NAME, index=False, header=False, startrow=1
    )

    # Get the xlsxwriter workbook and worksheet objects.
    workbook = writer.book
    worksheet = writer.sheets[SHEET_NAME]

    # Get the dimensions of the dataframe.
    max_row, max_col = launches_df.shape

    # Create a list of column headers, to use in add_table().
    column_settings = [{"header": column} for column in launches_df.columns]

    # Add the Excel table structure. Pandas will add the data.
    worksheet.add_table(
        0,
        0,
        max_row,
        max_col - 1,
        {"columns": column_settings, "style": "Table Style Medium 1"},
    )

    # Make the columns wider for clarity.
    worksheet.set_column(0, max_col - 1, 17)

    # Change the format of the 'Date' column to 'dd/mm/yyyy'.
    date_column = launches_df.columns.get_loc("Date")
    date_format = workbook.add_format({"num_format": "dd/mm/yyyy"})  # type: ignore
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
    today = datetime.today().strftime("%y%m%d")

    # Create collection search string.
    collection_search_string = f"{db.launches_collection}_{today}"

    # Check if the backup exists and replace it.
    if collection_search_string in collections:
        db.db.drop_collection(collection_search_string)

    # Use aggregation with $out to backup the collection.
    db.get_launches_collection().aggregate(
        [
            {"$match": {}},
            {"$out": collection_search_string},
        ]
    )


def launches_to_db(launches_df, db: Database):
    """Save the master log dataframe to a MongoDB.

    Args:
        launches_df (pd.DataFrame): The master log dataframe.
        db (Database): The log sheet DB configuration.
    """
    # Backup the current collection.
    backup_launches_collection(db=db)

    # Format dataframe to be saved.
    master_dict = launches_df.to_dict("records")

    # Save to the DB.
    logger.info("Saving to DB.")
    db.get_launches_collection().insert_many(master_dict)
    logger.info("Saved to DB.")


def update_launches_collection(launches_df, db: Database):
    """Update the master log collection in MongoDB by checking the date
    and aircraft. Append new records and update existing records.

    Args:
        launches_df (pd.DataFrame): The master log dataframe.
        db (Database): VGS database.
    """
    # Validate the dataframe is not empty.
    if launches_df.empty:
        logger.warning("Empty dataframe. Nothing to update.")
        return

    # Backup the current collection.
    backup_launches_collection(db=db)

    # Connect to the DB.
    collection = db.get_launches_collection()

    # Group by date and aircraft.
    grouped = launches_df.groupby(["Date", "Aircraft"])

    # Prepare bulk delete and inset operations.
    delete_ops = []
    deleted_launches = 0

    # Step 1: Prepare bulk delete operations.
    for group_keys, _ in grouped:
        # We want to delete all launches with the same date and aircraft
        # as the records we are about to insert.
        date, aircraft = group_keys
        delete_query = {
            "Date": date,
            "Aircraft": aircraft,
        }

        # Count the number of records to delete.
        deleted_launches += collection.count_documents(delete_query)

        # Append the recursive delete operation.
        delete_ops.append(DeleteMany(delete_query))

    # Delete the records if they exist.
    if delete_ops:
        logger.info(
            "Deleting %.0f launches from %.0f days/aircraft.",
            deleted_launches,
            len(delete_ops),
        )
        collection.bulk_write(delete_ops)

    # Step 2: Insert all the records.
    documents = launches_df.to_dict("records")
    logger.info(
        "Inserting %.0f launches from %.0f days/aircraft.", len(documents), len(grouped)
    )
    collection.insert_many(documents)


def backup_aircraft_info_collection(db: Database):
    """Backup the aircraft information collection in MongoDB.

    Args:
        db (Database): The log sheet DB configuration.
    """
    # Get all collections in the DB.
    collections = db.db.list_collection_names()

    # Backup the old collection with today's date as the suffix.
    # Get today's date as YYMMDD.
    today = datetime.today().strftime("%y%m%d")

    # Create collection search string.
    collection_search_string = f"{db.aircraft_info_collection}_{today}"

    if collection_search_string in collections:

        # Check if the backup exists and replace it.
        db.db.drop_collection(collection_search_string)

        # Use aggregation with $out to backup the collection.
        db.get_aircraft_info_collection().aggregate(
            [
                {"$match": {}},
                {"$out": collection_search_string},
            ]
        )


def update_aircraft_info(aircraft_info: pd.DataFrame, db: Database):
    """Update the aircraft information collection in MongoDB.

    Args:
        aircraft_info (pd.DataFrame): The aircraft information.
        db (Database): The log sheet DB configuration.
    """
    # Validate the dataframe is not empty.
    if aircraft_info.empty:
        logger.warning("Empty dataframe. Nothing to update.")
        return

    # Backup the current collection.
    backup_aircraft_info_collection(db=db)

    # Connect to the DB.
    collection = db.get_aircraft_info_collection()

    # Group by aircraft.
    grouped = aircraft_info.groupby(["Aircraft", "Date"])

    # Prepare bulk delete and insert operations.
    delete_ops = []
    deleted_aircraft = 0

    # Step 1: Prepare bulk delete operations.
    for group_keys, _ in grouped:
        # Delete all records with the same aircraft and date.
        aircraft, date = group_keys
        delete_query = {
            "Aircraft": aircraft,
            "Date": date,
        }

        # Count the number of records to delete.
        deleted_aircraft += collection.count_documents(delete_query)

        # Append the recursive delete operation.
        delete_ops.append(DeleteMany(delete_query))

    # Delete the records if they exist.
    if delete_ops:
        logger.info("Deleting %.0f aircraft info records.", deleted_aircraft)
        collection.bulk_write(delete_ops)

    # Step 2: Insert all the records.
    documents = aircraft_info.to_dict("records")
    logger.info("Inserting %.0f aircraft info records.", len(documents))
    collection.insert_many(documents)


def weather_to_db(weather_df: pd.DataFrame, db: Database):
    """Update or insert weather data in MongoDB.

    Args:
        weather_df (pd.DataFrame): The weather dataframe.
        db (Database): The log sheet DB configuration.
    """
    # Validate the dataframe is not empty.
    if weather_df.empty:
        logger.warning("Empty dataframe. Nothing to update.")
        return

    # Connect to the DB.
    collection = db.get_weather_collection()

    # Prepare bulk upsert operations
    bulk_operations = []

    for _, row in weather_df.iterrows():
        # Convert row to dictionary
        doc = row.to_dict()

        # Create query to find existing record
        # Use datetime for unique identification
        query = {
            "datetime": doc["datetime"],
        }

        # Create update operation
        bulk_operations.append(UpdateOne(query, {"$set": doc}, upsert=True))

    # Execute bulk operations
    if bulk_operations:
        result = collection.bulk_write(bulk_operations)
        logger.info(
            "Weather data updated: %d records modified, %d records upserted.",
            result.modified_count,
            result.upserted_count,
        )
    else:
        logger.info("No weather data to update.")

"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

import pymongo
import streamlit as st
import pandas as pd
import altair as alt
from log_keeper.get_config import get_config


def format_data_for_table(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Format the data for display in Streamlit.
    Args:
        data_df (pd.DataFrame): The data to be formatted.

    Returns:
        pd.DataFrame: The formatted data.
    """
    # Group the data by the specified columns
    grouped = raw_df.groupby(
        ["Date", "Aircraft", "AircraftCommander", "SecondPilot", "Duty"]
    )

    # Aggregate to sum the FlightTime for each group
    flight_time_sum = grouped.agg(
        FlightTime=("FlightTime", "sum")
    ).reset_index()

    # Calculate the size of each group (number of launches)
    group_sizes = grouped.size().reset_index(name='Launches')

    # Merge the sum of FlightTime and the count of Launches for each group
    data_df = pd.merge(
        flight_time_sum,
        group_sizes,
        on=["Date", "Aircraft", "AircraftCommander", "SecondPilot", "Duty"]
    )

    # Sort by date in descending order.
    data_df = data_df.sort_values(by="Date", ascending=False)

    # Format the date.
    data_df["Date"] = data_df["Date"].dt.strftime("%Y-%m-%d")

    # Convert the FlightTime (minutes) to a string in HH:MM format.
    data_df["FlightTime"] = data_df["FlightTime"].apply(
        lambda x: f"{x//60}:{x%60:02d}"
    )

    # Reorder the columns
    desired_order = ["Date", "Aircraft", "AircraftCommander",
                     "SecondPilot", "Duty", "Launches", "FlightTime"]
    # Ensure all desired columns are in the DataFrame before
    # reordering to avoid KeyError. This also implicitly filters
    # out any columns not listed in `desired_order`
    data_df = data_df[desired_order]
    return data_df


def fetch_data_from_mongodb() -> pd.DataFrame:
    """Fetch data from MongoDB and return as a DataFrame.
    Returns:
        pd.DataFrame: The data from MongoDB."""

    try:
        # Construct the MongoDB connection URI
        db_config = get_config()
        db_hostname = db_config["DB_HOSTNAME"]
        db_username = db_config["DB_USERNAME"]
        db_password = db_config["DB_PASSWORD"]
        db_collection_name = db_config["DB_COLLECTION_NAME"]
        db_name = db_config["DB_NAME"]

        # Create the DB connection URL
        db_url = f"mongodb+srv://{db_username}:{db_password}@{db_hostname}" + \
            "/?retryWrites=true&w=majority"

        # Connect to MongoDB
        client = pymongo.MongoClient(db_url)
        db = client[db_name]
        collection = db[db_collection_name]

        # Convert list of dictionaries to DataFrame
        df = pd.DataFrame(collection.find())

    except Exception as e:  # pylint: disable=broad-except
        st.error(f"Error: {e}")
        df = pd.DataFrame()
    return df


def plot_launches_by_commander(df: pd.DataFrame):
    """ Plot the number of launches by AircraftCommander.

    Args:
        df (pd.DataFrame): The data to be plotted.
    """
    # Group by AircraftCommander and count launches
    launches_by_commander = df.groupby("AircraftCommander").size()
    launches_by_commander = launches_by_commander.reset_index(
        name='Number of Launches'
    )

    # Sort launches by commander in descending order explicitly in the chart
    chart = alt.Chart(launches_by_commander).mark_bar().encode(
        # Quantitative scale for Number of Launches
        x=alt.X('Number of Launches:Q', sort=None),
        # Sort by Number of Launches in descending order
        y=alt.Y('AircraftCommander:N', sort='-x'),
        color=alt.value('blue'),  # Set bar color
        tooltip=['AircraftCommander', 'Number of Launches']  # Tooltip on hover
    ).properties(
        title='Launches by Aircraft Commander'
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    )

    # Display the chart in Streamlit.
    st.altair_chart(chart, use_container_width=True)


def show_launches_by_commander(df: pd.DataFrame, commander: str):
    """Show the number of launches by AircraftCommander in a table.

    Args:
        df (pd.DataFrame): The data to be displayed.
        commander (str): The AircraftCommander to filter by.
    """
    # Filter the data by AircraftCommander, if specified.
    if commander:
        filtered_df = df[df["AircraftCommander"] == commander]
    else:
        filtered_df = df
        commander = "All"

    # Format the data for display in Streamlit.
    display_df = format_data_for_table(filtered_df)
    st.header("Logbook Helper")
    st.text(f"Launches by {commander}")
    st.dataframe(
        data=display_df,
        hide_index=True,
        use_container_width=True
    )


def date_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter the data by date.

    Args:
        df (pd.DataFrame): The data to be filtered.

    Returns:
        pd.DataFrame: The filtered data.
    """
    # Add a date filter to the sidebar.
    st.sidebar.markdown("## Date Filter")

    # Get the date range from the user.
    min_date = df["Date"].min()
    max_date = df["Date"].max()

    # Add a date filter to the sidebar.
    start_date = st.sidebar.date_input(
        "Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        help="Select the start date",
    )
    end_date = st.sidebar.date_input(
        "End Date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        help="Select the end date",
    )

    # Convert the date to a pandas datetime object.
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    # Validate the date range.
    if start_date <= end_date:
        # Filter the data by the date range.
        filtered_df = df[
            (df["Date"] >= start_date) & (df["Date"] <= end_date)
        ]
    else:
        st.error("Error: End date must fall after start date.")
        filtered_df = df
    return filtered_df


def main():
    """Main Streamlit App Code."""
    # Set the page title.
    st.markdown("# 661 VGS Dashboard")
    st.sidebar.markdown("# Dashboard Filters")

    # Fetch data from MongoDB
    if "df" not in st.session_state:
        st.session_state.df = fetch_data_from_mongodb()

    # Refresh data button.
    if st.button("🔃 Refresh Data"):
        st.session_state.df = fetch_data_from_mongodb()
        st.success("Data Refreshed!", icon="✅")

    # Get the data from the session state.
    df = st.session_state.df

    # Filter by AircraftCommander.
    commander = st.sidebar.selectbox(
        "Filter by AircraftCommander",
        sorted(df["AircraftCommander"].unique()),
        index=None,
        help="Select the AircraftCommander to filter by.",
        placeholder="All",
    )

    # Add a date filter to the sidebar.
    filtered_df = date_filter(df)

    # Plot the number of launches by unique AircraftCommander.
    plot_launches_by_commander(filtered_df)

    # Logbook helper by AircraftCommander.
    show_launches_by_commander(filtered_df, commander)


if __name__ == '__main__':
    main()

"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

import subprocess
import pymongo
import streamlit as st
import pandas as pd
import altair as alt
from log_keeper.get_config import Config


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
    data_df["Date"] = data_df["Date"].dt.strftime("%d %b %y")

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
        db_config = Config()
        if not db_config.validate():
            db_config.update_credentials()

        # Create the DB connection URL
        db_url = (
            f"mongodb+srv://{db_config.db_username}:"
            f"{db_config.db_password}@{db_config.db_hostname}"
            "/?retryWrites=true&w=majority"
        )

        # Connect to MongoDB
        client = pymongo.MongoClient(db_url)
        db = client[db_config.db_name]
        collection = db[db_config.db_collection_name]

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


def show_logbook_helper(df: pd.DataFrame, commander: str):
    """Show the number of launches by AircraftCommander in a table.

    Args:
        df (pd.DataFrame): The data to be displayed.
        commander (str): The AircraftCommander to filter by.
    """
    # Filter the data by AircraftCommander, if specified.
    if commander:
        # Get launches where the pilot is commander.
        filtered_df = df[df["AircraftCommander"] == commander]

        # Get launches where the pilot is second pilot and the
        # duty contains SCT or AGT.
        second_pilot_df = df[df["SecondPilot"] == commander]
        sct_df = second_pilot_df[second_pilot_df["Duty"].str.contains(
            "SCT|AGT", case=False
        )]

        # Merge the commander and sct dataframes.
        filtered_df = pd.concat([filtered_df, sct_df])

        # Sort the data by date in descending order.
        filtered_df = filtered_df.sort_values(by="Date", ascending=False)
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


def quarterly_summary(df: pd.DataFrame,
                      commander: str,
                      quarter: str) -> pd.DataFrame:
    """ Show a quarterly summary of the number of launches
    for each AircraftCommander.

    Args:
        df (pd.DataFrame): The data to be summarized.
        commander (str): The AircraftCommander to filter by.
        quarter (str): The quarter to display."""

    # Get all elements where the pilot is commander.
    commander_df = df[df["AircraftCommander"] == commander]

    # Get elements where the duty contains SCT or AGT and the pilot
    # is second pilot.
    sct_df = df[df["Duty"].str.contains(
        "SCT|AGT", case=False
    )]
    sct_df = sct_df[sct_df["SecondPilot"] == commander]

    # Merge the commander and sct dataframes.
    commander_df = pd.concat([commander_df, sct_df])

    # Extract the quarter from the date.
    quarterly_df = commander_df.copy()
    quarterly_df["Quarter"] = quarterly_df["Date"].dt.to_period("Q")
    quarterly_df = quarterly_df[quarterly_df["Quarter"] == quarter]
    quarterly_df = quarterly_df.drop(columns=["Quarter"])

    # Find the last date where PLF was true. This is the last date where:
    # - 'SecondPilot' is commander
    # - 'PLF' is true
    # - 'Duty' contains 'SCT'
    # Find the last SCT and PLF dates.
    sct_in_quarter = sct_df[
        sct_df["Date"].dt.to_period("Q") <= quarter
    ]

    if sct_in_quarter.empty:
        last_sct = "N/A"
        last_plf = "N/A"
    else:
        last_sct = sct_in_quarter["Date"].max().strftime("%d %b %y")
        last_plf = sct_in_quarter["Date"].max().strftime("%d %b %y")

    # Create a summary table for the selected quarter.
    # Count launches and hours flown by AircraftCommander.
    summary = pd.DataFrame({
        "Aircraft Commander": commander,
        "Launches": quarterly_df.shape[0],
        "Hours": quarterly_df["FlightTime"].sum(),
        "Last SCT": last_sct,
        "Last PLF": last_plf
    }, index=[0])

    # Convert the FlightTime (minutes) to a string in HH:MM format.
    summary["Hours"] = summary["Hours"].apply(
        lambda x: f"{x//60}:{x%60:02d}"
    )

    # Display the summary table.
    st.header("Quarterly Summary Helper")
    st.dataframe(
        data=summary,
        hide_index=True,
    )


def plot_all_launches(df: pd.DataFrame):
    """ Plot all launches in the data.

    Args:
        df (pd.DataFrame): The data to be plotted.
    """
    # Sort the data by date in descending order.
    df = df.sort_values(by="Date", ascending=False)
    df = df.drop(columns=["_id"])

    # Format the date.
    df["Date"] = df["Date"].dt.strftime("%d %b %y")

    # Convert the FlightTime (minutes) to a string in HH:MM format.
    df["FlightTime"] = df["FlightTime"].apply(
        lambda x: f"{x//60}:{x%60:02d}"
    )

    # Format TakeOffTime and LandingTime.
    df["TakeOffTime"] = df["TakeOffTime"].dt.strftime("%H:%M")
    df["LandingTime"] = df["LandingTime"].dt.strftime("%H:%M")

    # Make date the first column.
    df = df[["Date"] + [col for col in df.columns if col != "Date"]]

    # Plot all data.
    st.dataframe(df, use_container_width=True)


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

    tabs = ["Statistics", "All Data"]
    stats_tab, all_data_tab = st.tabs(tabs)

    with stats_tab:

        # Plot the number of launches by unique AircraftCommander.
        plot_launches_by_commander(filtered_df)

        # Logbook helper by AircraftCommander.
        show_logbook_helper(filtered_df, commander)

        # Show a quarterly summary of the number of launches
        # for each AircraftCommander.
        st.sidebar.markdown("## Quarterly Summary")

        # Create a list of quarters from the data.
        quarters = filtered_df["Date"].dt.to_period("Q").unique()

        quarter = st.sidebar.selectbox(
            "Select Quarter",
            quarters,
            index=None,
            help="Select the quarter to display."
        )

        # Filter the data by the selected quarter.
        if quarter and commander:
            quarterly_summary(filtered_df, commander, quarter)

    with all_data_tab:
        plot_all_launches(filtered_df)


def display_dashboard():
    """Run the Streamlit app."""
    subprocess.run(["streamlit", "run", "src/dashboard/dashboard.py"],
                   check=True)


if __name__ == '__main__':
    main()

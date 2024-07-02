"""plots.py - Create plots for the dashboard"""

# Get packages.
import altair as alt
import pandas as pd
import streamlit as st


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
        lambda x: f"{x//60}:{x % 60:02d}"
    )

    # Reorder the columns
    desired_order = ["Date", "Aircraft", "AircraftCommander",
                     "SecondPilot", "Duty", "Launches", "FlightTime"]
    # Ensure all desired columns are in the DataFrame before
    # reordering to avoid KeyError. This also implicitly filters
    # out any columns not listed in `desired_order`
    data_df = data_df[desired_order]
    return data_df


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

def plot_firstlast_launch_table(df: pd.DataFrame):
    # Ensure the TakeOffTime is in datetime format (if it's not already)
    df['TakeOffTime'] = pd.to_datetime(df['TakeOffTime'])

    # Convert Date column to date-only format
    df['Date'] = pd.to_datetime(df['Date']).dt.date

    # Group by Date and calculate the first and last launch times
    first_last_launch = df.groupby('Date')['TakeOffTime'].agg(['min', 'max']).reset_index()

    # Rename the columns to match the desired output
    first_last_launch.columns = ['Date', 'FirstLaunch', 'LastLaunch']

    # Sort by Date in descending order
    first_last_launch = first_last_launch.sort_values(by='Date', ascending=False).reset_index(drop=True)

    # Convert Date to the desired format
    first_last_launch['Date'] = first_last_launch['Date'].apply(lambda x: x.strftime('%d %b %y'))

    # Convert FirstLaunch and LastLaunch to time-only format
    first_last_launch['FirstLaunch'] = first_last_launch['FirstLaunch'].apply(lambda x: x.strftime('%H:%M'))
    first_last_launch['LastLaunch'] = first_last_launch['LastLaunch'].apply(lambda x: x.strftime('%H:%M'))

# Display the DataFrame in Streamlit
    st.header("First & Last Launch Times")
    st.dataframe(first_last_launch, hide_index=True)

def plot_longest_flight_times(df: pd.DataFrame):
    """Plot the top ten longest flight times"""

    # Sort the DataFrame by FlightTime in descending order
    df = df.sort_values(by='FlightTime', ascending=False)

    # Drop duplicates based on AircraftCommander, keeping the first occurrence
    df = df.drop_duplicates(subset='AircraftCommander')

    # Select the top 10 entries
    top_10 = df.head(10)

    # Create a horizontal bar plot with Altair
    chart = alt.Chart(top_10).mark_bar().encode(
        x='FlightTime:Q',
        y=alt.Y('AircraftCommander:N', sort='-x'),
        color=alt.value('blue'),  # Set bar color
        tooltip=['AircraftCommander', 'FlightTime']
    ).properties(
        title='Top 10 Longest Flight Times'
    ).interactive()

    # Display the chart in Streamlit
    st.altair_chart(chart, use_container_width=True)

def generate_stats_helper_table(df: pd.DataFrame):
    # Convert 'Date' column to datetime format
    df['Date'] = pd.to_datetime(df['Date'])

    # Group by 'Date' and 'Duty', count the number of launches
    grouped = df.groupby(['Date', 'Duty']).size().reset_index(name='Launches')

    # Sort by 'Date' in descending order
    grouped = grouped.sort_values(by='Date', ascending=False)

    # Convert 'Date' to format DD MMM YY
    grouped['Date'] = grouped['Date'].dt.strftime('%d %b %y')

    # Limit to the first 15 rows
    grouped = grouped.head(15)

    # Display in Streamlit app
    st.header('Stats Helper')
    st.dataframe(grouped, hide_index=True)

def generate_gur_helper(df: pd.DataFrame):
    # Convert 'Date' column to datetime
    df['Date'] = pd.to_datetime(df['Date'])

    # Convert 'TakeOffTime' and 'LandingTime' to datetime if needed
    # df['TakeOffTime'] = pd.to_datetime(df['TakeOffTime'])
    # df['LandingTime'] = pd.to_datetime(df['LandingTime'])

    # Convert 'FlightTime' to numeric if needed
    # df['FlightTime'] = pd.to_numeric(df['FlightTime'])

    # Convert 'Date' to week start format
    df['Week_Start'] = df['Date'] - pd.to_timedelta(df['Date'].dt.weekday, unit='D')

    # Group by week start and Aircraft
    gur_helper = df.groupby(['Week_Start', 'Aircraft']).agg({
        'Date': 'count',             # Total launches
        'FlightTime': 'sum'          # Total flight time in minutes
    }).reset_index()

    # Rename columns
    gur_helper.columns = ['Week Start', 'Aircraft', 'Total Launches', 'Total Flight Time (mins)']

    # Sort by Week Start descending
    gur_helper = gur_helper.sort_values(by='Week Start', ascending=False)

    # Format 'Week Start' column to DD MMM YY format
    gur_helper['Week Start'] = gur_helper['Week Start'].dt.strftime('%d %b %y')

    # Limit to last 16 rows
    gur_helper = gur_helper.head(16)

    # Display using Streamlit st.dataframe
    st.title('GUR Helper')
    st.dataframe(gur_helper, hide_index=True)

def plot_duty_pie_chart(df: pd.DataFrame):
    """Plot the proportion of launches by duty"""

    # Aggregate the data by duty
    duty_counts = df['Duty'].value_counts().reset_index()
    duty_counts.columns = ['Duty', 'Count']

    # Create a pie chart with Altair
    pie_chart = alt.Chart(duty_counts).mark_arc().encode(
        theta=alt.Theta(field='Count', type='quantitative'),
        color=alt.Color(field='Duty', type='nominal'),
        tooltip=['Duty', 'Count']
    ).properties(
        title='Launches by Duty'
    )

    # Display the pie chart in Streamlit
    st.altair_chart(pie_chart, use_container_width=True)

def plot_monthly_launches(df: pd.DataFrame):
    """Plot launches by month"""

    # Convert launch date to datetime format if it's not already
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])

    # Extract month and year from LaunchDate and format as MMM YY
    df['Month'] = df['Date'].dt.strftime('%b %y')

    # Aggregate launches by month
    monthly_launches = df['Month'].value_counts().reset_index()
    monthly_launches.columns = ['Month', 'Launches']

    # Sort months chronologically
    months_order = pd.to_datetime(monthly_launches['Month'], format='%b %y').sort_values().dt.strftime('%b %y').tolist()
    monthly_launches['Month'] = pd.Categorical(monthly_launches['Month'], categories=months_order, ordered=True)
    monthly_launches = monthly_launches.sort_values('Month')

    # Create a bar chart with Altair
    bar_chart = alt.Chart(monthly_launches).mark_bar().encode(
        x=alt.X('Month', title='Month'),
        y=alt.Y('Launches', title='Number of Launches'),
        tooltip=['Month', 'Launches']
    ).properties(
        title='Launches by Month'
    )

    # Display the bar chart in Streamlit
    st.altair_chart(bar_chart, use_container_width=True)

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
        lambda x: f"{x//60}:{x % 60:02d}"
    )

    # Format TakeOffTime and LandingTime.
    df["TakeOffTime"] = df["TakeOffTime"].dt.strftime("%H:%M")
    df["LandingTime"] = df["LandingTime"].dt.strftime("%H:%M")

    # Make date the first column.
    df = df[["Date"] + [col for col in df.columns if col != "Date"]]

    # Plot all data.
    st.dataframe(df, use_container_width=True)


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
        lambda x: f"{x//60}:{x % 60:02d}"
    )

    # Display the summary table.
    st.header("Quarterly Summary Helper")
    st.dataframe(
        data=summary,
        hide_index=True,
    )

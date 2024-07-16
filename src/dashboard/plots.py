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
    """ Plot the first and last launch times for each date.

    Args:
        df (pd.DataFrame): The data to be plotted.
    """
    # Group by Date and calculate the first and last launch times
    first_last_launch = df.groupby('Date')['TakeOffTime'].agg(
        ['min', 'max']
    ).reset_index()

    # Rename the columns to match the desired output
    first_last_launch.columns = ['Date', 'FirstLaunch', 'LastLaunch']

    # Sort by Date in descending order and limit to the first N rows.
    n_rows_to_display = 20
    first_last_launch = first_last_launch.sort_values(
        by='Date',
        ascending=False
    ).reset_index(drop=True).head(n_rows_to_display)

    # Convert Date to the desired format
    first_last_launch['Date'] = first_last_launch[
        'Date'
    ].dt.strftime('%d %b %y')

    # Convert first and last launches to time-only format
    first_last_launch['FirstLaunch'] = first_last_launch[
        'FirstLaunch'
    ].dt.strftime('%H:%M')
    first_last_launch['LastLaunch'] = first_last_launch[
        'LastLaunch'
    ].dt.strftime('%H:%M')

    # Display the DataFrame in Streamlit
    st.subheader("First & Last Launch Times")
    st.dataframe(first_last_launch, hide_index=True)


def plot_longest_flight_times(df: pd.DataFrame):
    """Plot the longest flight times

    Args:
        df (pd.DataFrame): The data to be plotted
    """
    # Sort the DataFrame by FlightTime in descending order
    df = df.sort_values(by='FlightTime', ascending=False)

    # Drop duplicates based on AircraftCommander, keeping the first occurrence
    df = df.drop_duplicates(subset='AircraftCommander')

    # Select the top entries
    n_rows_to_display = 10
    top_flight_times = df.head(n_rows_to_display)

    # Create a horizontal bar plot with Altair
    chart = alt.Chart(top_flight_times).mark_bar().encode(
        x='FlightTime:Q',
        y=alt.Y('AircraftCommander:N', sort='-x'),
        color=alt.value('blue'),  # Set bar color
        tooltip=['AircraftCommander', 'FlightTime']
    ).interactive()

    # Display the chart in Streamlit
    st.subheader('Longest Flight Times')
    st.altair_chart(chart, use_container_width=True)


def launches_by_type_table(df: pd.DataFrame):
    """Display the number of launches by type in a table for each day

    Args:
        df (pd.DataFrame): The data to be displayed
    """
    # Group by 'Date' and 'Duty', count the number of launches
    grouped = df.groupby(['Date', 'Duty']).size().reset_index(name='Launches')

    # Sort by 'Date' in descending order
    grouped = grouped.sort_values(by='Date', ascending=False)

    # Convert 'Date' to format DD MMM YY
    grouped['Date'] = grouped['Date'].dt.strftime('%d %b %y')

    # Limit to the first rows
    n_rows_to_display = 30
    grouped = grouped.head(n_rows_to_display)

    # Display in Streamlit app
    st.subheader('Launches by Type')
    st.dataframe(grouped, hide_index=True)


def generate_aircraft_weekly_summary(df: pd.DataFrame):
    """Generate a summary of launches and flight time by week and aircraft

    Args:
        df (pd.DataFrame): The data to be summarized
    """
    # Convert 'Date' to week start format
    df['Week Start'] = df['Date'] - pd.to_timedelta(
        df['Date'].dt.weekday,
        unit='D'
    )

    # Group by week start and Aircraft
    gur_helper = df.groupby(['Week Start', 'Aircraft']).agg({
        'Date': 'count',             # Total launches
        'FlightTime': 'sum'          # Total flight time in minutes
    }).reset_index()

    # Rename columns
    gur_helper.columns = [
        'Week Start',
        'Aircraft',
        'Total Launches',
        'Total Flight Time'
    ]

    # Sort by Week Start descending
    gur_helper = gur_helper.sort_values(by='Week Start', ascending=False)

    # Format 'Week Start' column to DD MMM YY format
    gur_helper['Week Start'] = gur_helper['Week Start'].dt.strftime('%d %b %y')

    # Format 'Total Flight Time' to HH:MM format
    gur_helper['Total Flight Time'] = gur_helper['Total Flight Time'].apply(
        lambda x: f"{x//60}:{x % 60:02d}"
    )

    # Limit to last rows
    n_rows_to_display = 16
    gur_helper = gur_helper.head(n_rows_to_display)

    # Display using Streamlit st.dataframe
    st.subheader('Weekly Summary by Aircraft')
    st.dataframe(gur_helper, hide_index=True)


def generate_aircraft_daily_summary(df: pd.DataFrame):
    """Generate a summary of launches and flight time by day and aircraft

    Args:
        df (pd.DataFrame): The data to be summarized
    """
    # Group by 'Date' and 'Aircraft'
    gur_helper = df.groupby(['Date', 'Aircraft']).agg(
        Launches=('Date', 'count'),             # Total launches
        TotalFlightTime=('FlightTime', 'sum')   # Total flight time in minutes
    ).reset_index()

    # Rename columns
    gur_helper.columns = [
        'Date',
        'Aircraft',
        'Launches',
        'Flight Time'
    ]

    # Sort by 'Date' descending
    gur_helper = gur_helper.sort_values(by='Date', ascending=False)

    # Format 'Date' column to DD MMM YY format
    gur_helper['Date'] = gur_helper['Date'].dt.strftime('%d %b %y')

    # Format 'Flight Time' to HH:MM format
    gur_helper['Flight Time'] = gur_helper['Flight Time'].apply(
        lambda x: f"{x//60}:{x % 60:02d}"
    )

    # Limit to last rows
    n_rows_to_display = 16
    gur_helper = gur_helper.head(n_rows_to_display)

    # Display using Streamlit st.dataframe
    st.subheader('Daily Summary by Aircraft')
    st.dataframe(gur_helper, hide_index=True)


def plot_duty_pie_chart(df: pd.DataFrame):
    """Plot the proportion of launches by duty"""

    # Aggregate the data by duty and percentage.
    duty_counts = df['Duty'].value_counts().reset_index()
    duty_counts.columns = ['Duty', 'Count']
    duty_counts['Percentage'] = (
        duty_counts['Count'] / duty_counts['Count'].sum()
    ) * 100
    duty_counts['Percentage'] = duty_counts['Percentage'].round(1)

    # Add a column for the percentage as text.
    duty_counts['PercentageText'] = duty_counts['Percentage'].astype(str) + '%'

    # Create base chart.
    base = alt.Chart(duty_counts).encode(
        theta=alt.Theta("Count:Q", stack=True),
        color=alt.Color("Duty:N", legend=alt.Legend(title="Duty")),
        order=alt.Order('Count:Q', sort='descending')
    )

    # Create pie chart.
    pie = base.mark_arc(outerRadius=120).encode(
        tooltip=['Duty', 'Count', 'Percentage']
    )

    # Add text to the base chart.
    text = base.mark_text(radius=140).encode(
        text=alt.Text('PercentageText:N'),
    )

    # Combine pie and text.
    chart = pie + text

    # Display the pie chart in Streamlit
    st.subheader('Launches by Duty')
    st.altair_chart(chart, use_container_width=True)


def plot_monthly_launches(df: pd.DataFrame):
    """Plot launches by month

    Args:
        df (pd.DataFrame): The data to be plotted
    """
    
    monthly_aggregated = df.set_index('Date', inplace=True)
    monthly_aggregated = monthly_aggregated.resample('M').size()
    
    # Extract month and year.
    df['Month'] = df['Date'].dt.to_period('M')

    # Aggregate launches by month
    monthly_launches = df['Month'].value_counts().reset_index()
    monthly_launches.columns = ['Month', 'Launches']

    # TODO: Start here.
    # Sort months chronologically
    months_order = pd.to_datetime(
        monthly_launches['Month'],
        format='%b %y'
    ).sort_values().dt.strftime('%b %y').tolist()
    monthly_launches['Month'] = pd.Categorical(
        monthly_launches['Month'],
        categories=months_order,
        ordered=True
    )
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

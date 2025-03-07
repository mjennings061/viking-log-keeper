"""plots.py - Create plots for the dashboard"""

# Get packages.
import altair as alt
import pandas as pd
import streamlit as st
from pathlib import Path

# User-defined imports.
from dashboard.utils import get_financial_year
from dashboard.utils import total_launches_for_financial_year
from dashboard.utils import delta_launches_previous_day
from dashboard.utils import gifs_flown_per_day
from dashboard.utils import filter_by_financial_year
from dashboard.utils import format_minutes_to_HHHH_mm


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
        FlightTime=("FlightTime", "sum"),
        PLFs=("PLF", "sum")
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

    # Make PLF column blank if the value is zero.
    data_df["PLFs"] = data_df["PLFs"].apply(
        lambda x: "" if x == 0 else x
    )

    # Convert the PLF to a string.
    data_df["PLFs"] = data_df["PLFs"].astype(str)

    # Reorder the columns
    desired_order = ["Date", "Aircraft", "AircraftCommander",
                     "SecondPilot", "Duty", "Launches", "FlightTime",
                     "PLFs"]
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
    launches_by_commander = df.groupby("AircraftCommander").agg(
        Launches=("Date", "count")
    ).reset_index()

    # Drop those with less than 5 launches.
    min_launches = 5
    launches_by_commander = launches_by_commander[
        launches_by_commander["Launches"] >= min_launches]

    # Dynamically set label based on the number of commanders.
    n_labels = len(launches_by_commander)
    label_height = 30
    height = n_labels * label_height

    # Sort launches by commander in descending order explicitly in the chart
    chart = alt.Chart(launches_by_commander).mark_bar().encode(
        # Quantitative scale for Number of Launches
        x=alt.X('Launches:Q', sort=None),
        # Sort by Number of Launches in descending order
        y=alt.Y('AircraftCommander:N', sort='-x'),
        color=alt.value('blue'),  # Set bar color
        tooltip=['AircraftCommander', 'Launches']  # Tooltip on hover
    ).properties(
        # Adjust the height based on the number of commanders.
        height=height
    )

    # Display the value of the bar on the chart.
    text = chart.mark_text(
        align='left',
        baseline='middle',
        dx=6,  # Nudge text to right so it doesn't overlap with the bar
        size=15
    ).encode(
        text='Launches:Q'  # Display the number of launches
    )

    # Combine the chart and text.
    chart = chart + text

    # Display the chart in Streamlit.
    st.subheader('Launches by Pilot')
    st.text(f"Only pilots with {min_launches} or more launches shown.")
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
    # Convert ObjectId to string if present.
    if '_id' in df.columns:
        df = df.copy()
        df['_id'] = df['_id'].astype(str)

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
    )

    # Display the value of the bar on the chart.
    text = chart.mark_text(
        align='left',
        baseline='middle',
        dx=5,  # Nudge text to right so it doesn't overlap with the bar
        size=15
    ).encode(
        text='FlightTime:Q'  # Display the flight time
    )

    # Combine the chart and text.
    chart = chart + text

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


def get_aircraft_weekly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Generate a summary of launches and flight time by week and aircraft

    Args:
        df (pd.DataFrame): The data to be summarized

    Returns:
        pd.DataFrame: The summarized data"""
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
    return gur_helper


def table_aircraft_weekly_summary(df: pd.DataFrame):
    """Show a summary of launches and flight time by week and aircraft

    Args:
        df (pd.DataFrame): The data to be summarized"""
    # Get the weekly summary.
    gur_helper = get_aircraft_weekly_summary(df)

    # Limit to last rows
    n_rows_to_display = 16

    # Display using Streamlit st.dataframe
    st.subheader('Weekly Summary by Aircraft')
    st.dataframe(gur_helper.head(n_rows_to_display), hide_index=True)


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
        color=alt.Color("Duty:N", legend=None),
        order=alt.Order('Count:Q', sort='descending')
    )

    # Create pie chart.
    radius = 120
    pie = base.mark_arc(outerRadius=radius).encode(
        tooltip=['Duty', 'Count', 'Percentage']
    )

    # Add text to the base chart.
    duty_text = base.mark_text(radius=radius+25, dy=5).encode(
        text=alt.Text('Duty:N'),
    )
    percentage_text = base.mark_text(radius=radius+25, dy=-5).encode(
        text=alt.Text('PercentageText:N'),
    )

    # Combine pie and text.
    chart = pie + duty_text + percentage_text

    # Display the pie chart in Streamlit
    st.subheader('Launches by Duty')
    st.altair_chart(chart, use_container_width=True)


def plot_monthly_launches(df: pd.DataFrame):
    """Plot launches by month

    Args:
        df (pd.DataFrame): The data to be plotted
    """
    # Extract month and year.
    df = df.copy()
    df.loc[:, 'YearMonth'] = df['Date'].dt.to_period('M')

    # Aggregate launches and flight time by month.
    month_df = df.groupby('YearMonth').agg(
        Launches=('Date', 'count'),
        FlightTime=('FlightTime', 'sum')
    ).reset_index()

    # Melting the DataFrame to have a single column for the value.
    melt_df = month_df.melt(
        id_vars='YearMonth',
        value_vars=['Launches', 'FlightTime'],
        var_name='Metric',
        value_name='Value'
    ).sort_values(by=['YearMonth', 'Metric']).reset_index(drop=True)

    # Convert year and month to string format.
    melt_df['YearMonthText'] = melt_df['YearMonth'].dt.strftime('%b %Y')
    year_month_order = melt_df['YearMonthText'].unique().tolist()

    # Create the base chart.
    base = alt.Chart(melt_df).encode(
        x=alt.X('YearMonthText:O', title='Date', sort=year_month_order),
    )

    # Create bar chart for launches.
    bar_launches = base.transform_filter(
        alt.datum.Metric == 'Launches'
    ).mark_bar().encode(
        y=alt.Y('Value:Q', title='Launches'),
        color=alt.value('blue'),
        xOffset='Metric:O',
        tooltip=['YearMonthText', 'Metric', 'Value'],
    )

    # Create bar chart for flight time.
    bar_flight_time = base.transform_filter(
        alt.datum.Metric == 'FlightTime'
    ).mark_bar().encode(
        y=alt.Y('Value:Q', title='Flight Time'),
        color=alt.value('red'),
        xOffset='Metric:O',
        tooltip=['YearMonthText', 'Metric', 'Value'],
    )

    # Combine the two charts.
    combined_chart = alt.layer(
        bar_launches,
        bar_flight_time
    ).resolve_scale(y='independent')

    # Create a legend for the chart.
    legend_data = melt_df[['Metric']].drop_duplicates()
    legend_data['Colour'] = ['red', 'blue']
    legend = alt.Chart(legend_data).mark_point().encode(
        y=alt.Y('Metric:N', axis=alt.Axis(orient='right'), title=None),
        color=alt.Color('Colour:N', scale=None, legend=None),
    )

    # Combine the chart and legend.
    final_chart = alt.hconcat(
        combined_chart,
        legend
    ).resolve_legend(
        color='independent'
    )

    # Display the bar chart in Streamlit
    st.subheader('Monthly Launches')
    st.altair_chart(final_chart, use_container_width=True)


def table_all_launches(df: pd.DataFrame):
    """ Plot all launches in the data.

    Args:
        df (pd.DataFrame): The data to be plotted.
    """
    # Handle an empty DataFrame.
    if df.empty:
        st.write("No data to display.")
        return

    # Sort the data by date in descending order.
    df = df.sort_values(by="TakeOffTime", ascending=False)

    # If the '_id' column is present, drop it.
    if '_id' in df.columns:
        df = df.drop(columns=['_id'])

        # Create a filter for the Duty column.
    unique_duties = df["Duty"].unique()
    selected_duties = st.sidebar.multiselect(
        "Filter by Duty",
        options=unique_duties,
        default=unique_duties
    )

    # Create a filter for the Aircraft column.
    unique_aircraft = df["Aircraft"].unique()
    selected_aircraft = st.sidebar.multiselect(
        "Filter by Aircraft",
        options=unique_aircraft,
        default=unique_aircraft
    )

    # Create a flight time slider to filter minumum flight time.
    min_flight_time = st.sidebar.slider(
        "Minimum Flight Time (minutes)",
        min_value=1,
        max_value=df["FlightTime"].max(),
        value=1,
        step=1
    )

    # Create a filter for SPC.
    spc = df['SPC'].unique()
    selected_spc = st.sidebar.multiselect(
        "Filter by sortie profile code",
        options=spc,
        default=spc
    )

    # Apply the Duty filter to the DataFrame.
    df = df[df["Duty"].isin(selected_duties)]

    # Apply the Aircraft filter to the DataFrame.
    df = df[df["Aircraft"].isin(selected_aircraft)]

    # Apply the Flight Time filter to the DataFrame.
    df = df[df["FlightTime"] >= min_flight_time]

    # Apply the SPC filter to the DataFrame.
    df = df[df["SPC"].isin(selected_spc)]

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

    # Reset the index.
    df = df.reset_index(drop=True)

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
        filtered_df = filtered_df.sort_values(
            by="TakeOffTime",
            ascending=False
        )
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


def show_launch_delta_metric(df: pd.DataFrame):
    """Show the difference in launches between the last two days.

    Args:
        df (pd.DataFrame): The data to be displayed.
    """
    financial_year = get_financial_year(df)
    launches_fy = total_launches_for_financial_year(
        df=df,
        year=financial_year
    )
    delta_launches = delta_launches_previous_day(df)

    # Display total launches.
    st.metric(
        f"Total Launches {financial_year}",
        launches_fy,
        delta=delta_launches,
        help="Difference in launches between the last two days."
    )


def show_logo(logo_path: Path):
    """Add the logo to the page.

    Args:
        logo_path (Path): The path to the logo.
    """
    st.logo(str(logo_path))
    _, centre, _ = st.columns(3)
    with centre:
        st.image(str(logo_path), use_column_width="auto")

    # Show centred text.
    st.markdown(
        "<h2 style='text-align: center;'>"
        "Volunteer Gliding Squadron Dashboard</h1>",
        unsafe_allow_html=True
    )


def aircraft_flown_per_day(df: pd.DataFrame):
    """Plot a table of how many aircraft were flown each day.

    Args:
        df (pd.DataFrame): The data to be displayed."""
    # Group by 'Date'. Count the number of unique 'Aircraft'.
    grouped = df.groupby('Date')['Aircraft'].nunique()

    # Sort by 'Date' in descending order.
    grouped = grouped.sort_index(ascending=False).reset_index()

    # Convert 'Date' to format DD MMM YY.
    grouped['Date'] = grouped['Date'].dt.strftime('%d %b %y')

    # Limit to the first rows.
    n_rows_to_display = 30
    grouped = grouped.head(n_rows_to_display)

    # Display in Streamlit app.
    st.subheader('Aircraft Flown per Day')
    st.dataframe(grouped, hide_index=True)


def launches_daily_summary(df: pd.DataFrame):
    """Plot a table of the daily summary of launches and hours flown.

    Args:
        pd.DataFrame: The data to be displayed."""
    # Group by 'Date'. Aggregate the number of launches and total flight time.
    grouped = df.groupby('Date').agg(
        Launches=('Date', 'count'),             # Total launches
        TotalFlightTime=('FlightTime', 'sum')   # Total flight time in minutes
    ).reset_index()

    # Rename columns.
    grouped.columns = ['Date', 'Launches', 'Flight Time']

    # Sort by 'Date' in descending order.
    grouped = grouped.sort_values(by='Date', ascending=False)

    # Convert 'Date' to format DD MMM YY.
    grouped['Date'] = grouped['Date'].dt.strftime('%d %b %y')

    # Format 'Flight Time' to HH:MM format.
    grouped['Flight Time'] = grouped['Flight Time'].apply(
        lambda x: f"{x//60}:{x % 60:02d}"
    )

    # Limit to last rows.
    n_rows_to_display = 16
    grouped = grouped.head(n_rows_to_display)

    # Display in Streamlit app.
    st.subheader('Daily Summary')
    st.dataframe(grouped, hide_index=True)


def table_gifs_per_date(df: pd.DataFrame):
    """Plot a table of GIFs flown per date.

    Args:
        df (pd.DataFrame): The data to be displayed."""
    # Get the total number of GIFs flown each day.
    gif_df = gifs_flown_per_day(df)

    # Convert 'Date' to format DD MMM YY.
    gif_df['Date'] = gif_df['Date'].dt.strftime('%d %b %y')

    # Limit to the first rows.
    n_rows_to_display = 15
    gif_df = gif_df.head(n_rows_to_display)

    # Display in Streamlit app.
    st.subheader('GIFs Flown per Day')
    st.dataframe(gif_df, hide_index=True)


def plot_gif_bar_chart(df: pd.DataFrame):
    """Plot cumulative chart of GIFs flown per day.

    Args:
        df (pd.DataFrame): The data to be displayed."""
    # Get the total number of GIFs flown each day.
    gif_df = gifs_flown_per_day(df)

    # Filter by financial year.
    year = get_financial_year(gif_df)
    gif_year_df = filter_by_financial_year(gif_df, year)

    # Add a week column to group by.
    gif_year_df['WeekStart'] = gif_year_df['Date'] - pd.to_timedelta(
        gif_year_df['Date'].dt.weekday,
        unit='D'
    )

    # Group by week and sum the GIFs flown.
    gif_year_df = gif_year_df.groupby('WeekStart').agg(
        GIFsFlown=('GIFs Flown', 'sum')
    ).reset_index()

    # Produce a cumulative sum of GIFs flown for each day.
    gif_year_df['GIFs Cumsum'] = gif_year_df['GIFsFlown'].cumsum()

    # Tooltips.
    x_tooltip = alt.Tooltip('WeekStart:T', format='%d %b %y')
    y_tooltip = alt.Tooltip('GIFs Cumsum:Q', format=',d', title='GIFs Flown')

    # Create an area chart with Altair.
    base = alt.Chart(gif_year_df).mark_area(color='blue').encode(
        x=alt.X(
            'WeekStart:T',
            title='Week Start',
            axis=alt.Axis(labelAngle=-90, format='%d %b %y', grid=True)
        ),
        y=alt.Y('GIFs Cumsum:Q', title='Total GIFs Flown'),
        tooltip=[x_tooltip, y_tooltip]
    ).properties(
        width=600  # Adjust width as needed
    )

    # Create the line chart to show the cumulative GIFs flown over time.
    line = base.mark_line(color='blue').encode()

    # Create the scatter plot (dots) to highlight each data point.
    points = base.mark_circle(color='red', size=100).encode()

    # Add text to the chart.
    text = base.mark_text(
        align='center',
        baseline='middle',
        dx=20,  # Nudge up so it doesn't overlap with the bar.
        size=12,
        angle=270,
        color='blue'
    ).encode(
        text='GIFs Cumsum:Q'  # Display the number of GIFs flown
    )

    # Combine the line and dots into one chart.
    chart = (base + line + points + text).properties(
        width=600  # Adjust width as needed
    )

    # Display the chart in Streamlit.
    st.subheader('Cumulative GIFs Flown per Week')
    st.text(f"Financial Year: {year}")
    st.altair_chart(chart, use_container_width=True)


def get_aircraft_totals(aircraft_df: pd.DataFrame) -> pd.DataFrame:
    """Get summary of launches and flight time by aircraft.

    Args:
        aircraft_df (pd.DataFrame): The data to be displayed.

    Returns:
        pd.DataFrame: The last entry for each aircraft.
    """
    # Handle an empty dataframe.
    if aircraft_df is None:
        st.warning("No aircraft data to display.")
        return

    # Sort the aircraft list by date in descending order.
    aircraft_df = aircraft_df.sort_values(by='Date', ascending=False)

    # Get unique aircraft.
    aircraft_list = aircraft_df['Aircraft'].unique()

    # Get a list of the most recent entry for each aircraft.
    last_entry_list = []
    for aircraft in aircraft_list:
        # Get the most recent entry for the aircraft.
        aircraft_entry = aircraft_df[
            aircraft_df['Aircraft'] == aircraft
        ].iloc[0]
        # Add the entry to the list.
        last_entry_list.append(aircraft_entry)

    # Put the data into a DataFrame.
    last_entry_df = pd.DataFrame(last_entry_list)

    # Apply the formatting to 'Hours After' column
    if 'Hours After' in last_entry_df.columns:
        last_entry_df['Hours After'] = last_entry_df['Hours After'].apply(
            format_minutes_to_HHHH_mm
        )
    return last_entry_df


def table_aircraft_totals(aircraft_df: pd.DataFrame):
    """"Show the number of launches by aircraft in a table.

    Args:
        aircraft_df (pd.DataFrame): The data to be displayed.
    """
    # Get the last entry for each aircraft.
    last_entry_df = get_aircraft_totals(aircraft_df)

    # Remove "_id" column.
    last_entry_df = last_entry_df.drop(columns=["_id"])

    # Convert 'Date' to format DD MMM YY.
    last_entry_df['Date'] = last_entry_df['Date'].dt.strftime('%d %b %y')

    # Change "Launches After" to "Launches" for display.
    last_entry_df.rename(
        columns={'Launches After': 'Launches', 'Hours After': 'Hours'},
        inplace=True
    )

    # Display the data in Streamlit.
    st.subheader('Aircraft Totals')
    st.dataframe(last_entry_df, hide_index=True)


def table_gur_summary(aircraft_df: pd.DataFrame,
                      launches_df: pd.DataFrame):
    """Show weekly aircraft summaries in a GUR format.

    Args:
        aircraft_df (pd.DataFrame): Aircraft data to be displayed.
        launches_df (pd.DataFrame): Launch data to be displayed.
    """
    # Handle an empty dataframe.
    if aircraft_df is None or launches_df is None:
        st.warning("No aircraft data to display.")
        return

    # Get the last entry for each aircraft.
    last_entry_df = get_aircraft_totals(aircraft_df)

    # Get aircraft weekly launches and total launches.
    gur_summary = get_aircraft_weekly_summary(launches_df)

    # Filter last entry by those over six months old.
    six_months_ago = pd.Timestamp.now() - pd.DateOffset(months=6)
    last_entry_df = last_entry_df[last_entry_df['Date'] > six_months_ago]

    # Filter gur summary by aircraft in last entry.
    gur_summary = gur_summary[gur_summary['Aircraft'].isin(
        last_entry_df['Aircraft']
    )]

    # Get the first entry for each unique aircraft in gur_summary.
    last_weekly_summary = gur_summary.drop_duplicates(
        subset='Aircraft',
        keep='first'
    ).reset_index(drop=True)

    # Merge the first entry with last_entry_df.
    last_entry_df = last_entry_df.merge(
        last_weekly_summary,
        on='Aircraft',
        how='left',
        suffixes=('', '_first')
    )

    # Set totals columns to zero if they are not this week.
    latest_week = last_entry_df['Date'].max()
    last_entry_df.loc[
        last_entry_df['Date'] != latest_week,
        ['Total Launches', 'Total Flight Time']
    ] = 0

    # Sort by aircraft.
    last_entry_df = last_entry_df.sort_values(by='Aircraft')

    # Display the data in Streamlit.
    columns_to_display = {
        'Aircraft': 'Aircraft',
        'Total Launches': 'Weekly Launches',
        'Launches After': 'Total Launches',
        'Total Flight Time': 'Weekly Flight Time',
        'Hours After': 'Total Flight Time'
    }
    last_entry_df.rename(columns=columns_to_display, inplace=True)

    st.subheader('GUR Summary')
    st.dataframe(
        last_entry_df[columns_to_display.values()],
        hide_index=True
    )

"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

from log_keeper.get_config import get_config
import pymongo
import streamlit as st
import plotly.express as px
import pandas as pd
import matplotlib.pyplot as plt


def format_data_for_display(raw_df):
    """Format the data for display in Streamlit.
    Args:
        data_df (pd.DataFrame): The data to be formatted.

    Returns:
        pd.DataFrame: The formatted data.
    """
    # Format the date and time columns.
    data_df = raw_df.copy()
    data_df["TakeOffTime"] = raw_df["TakeOffTime"].dt.strftime("%H:%M")
    data_df["LandingTime"] = raw_df["LandingTime"].dt.strftime("%H:%M")

    # Format the date column.
    data_df["Date"] = raw_df["Date"].dt.strftime("%Y-%m-%d")

    # Remove _id column.
    data_df = data_df.drop(columns=["_id"])
    return data_df


# Function to fetch data from MongoDB


def fetch_data_from_mongodb():
    """Fetch data from MongoDB and return as a DataFrame.
    Returns:
        pd.DataFrame: The data from MongoDB.
        pymongo.collection.Collection: The MongoDB collection object."""
    
    # Construct the MongoDB connection URI
    db_config = get_config()
    DB_HOSTNAME = db_config["DB_HOSTNAME"]
    DB_USERNAME = db_config["DB_USERNAME"]
    DB_PASSWORD = db_config["DB_PASSWORD"]
    DB_COLLECTION_NAME = db_config["DB_COLLECTION_NAME"]
    DB_NAME = db_config["DB_NAME"]

    # Create the DB connection URL
    db_url = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOSTNAME}" + \
        "/?retryWrites=true&w=majority"

    # Connect to MongoDB
    client = pymongo.MongoClient(db_url)
    db = client[DB_NAME]
    collection = db[DB_COLLECTION_NAME]

    # Convert list of dictionaries to DataFrame
    df = pd.DataFrame(collection.find())

    return df, collection


def main():
    """Main Streamlit App Code."""

    # Set the page title.
    st.markdown("# 661 VGS Dashboard")
    
    # Fetch data from MongoDB
    df, collection = fetch_data_from_mongodb()

    # Define the financial year start and end dates
    financial_year_start = pd.Timestamp(2023, 4, 1)
    financial_year_end = pd.Timestamp(2024, 3, 31)

    # Retrieve data from the collection for the financial year
    query = {"Date": {"$gte": financial_year_start, "$lte": financial_year_end}}
    cursor = collection.find(query)

    # Convert cursor to list of dictionaries
    data_list = list(cursor)

    # Convert list of dictionaries to DataFrame
    df_financial_year = pd.DataFrame(data_list)

    # Calculate total number of launches for the financial year
    total_launches_financial_year = len(df_financial_year)

    # Display total number of launches for the financial year in a box in the sidebar
    st.sidebar.write(
    f'<div style="text-align: center; font-size: 24px; border: 2px solid black; padding: 10px;">'
    f'<b>Total Number of Launches (FY 23-24): <span style="color: red;">{total_launches_financial_year}</span></b>'
    f'</div>', 
    unsafe_allow_html=True
    )

    # Group data by DutyType and calculate total launches for each duty type
    duty_type_totals = df.groupby('Duty').size().reset_index(name='Launches')

    # Plot pie chart
    fig = px.pie(duty_type_totals, values='Launches', names='Duty', title='Total Launches by Duty Type')

    # Set layout for the pie chart
    fig.update_layout(
        showlegend=True,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        annotations=[
            dict(
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                text="",
                showarrow=False,
                bgcolor="black",
                bordercolor="black",
                borderwidth=4,
                opacity=1
            )
        ]
    )

    # Display pie chart
    st.plotly_chart(fig)

    # Filter by AircraftCommander
    commander = st.sidebar.selectbox(
        "Filter by AircraftCommander", 
        df["AircraftCommander"].unique()
    )
    filtered_df = df[df["AircraftCommander"] == commander]

    # Group by AircraftCommander and count launches
    launches_by_commander = df.groupby("AircraftCommander").size()

    # Sort launches by commander in descending order
    launches_by_commander_sorted = launches_by_commander.sort_values(
        ascending=False
    )

    # Create a custom bar chart with text color
    fig, ax = plt.subplots()
    launches_by_commander_sorted.plot(kind='bar', ax=ax, color='green',width=0.8)
    ax.set_ylabel('Number of Launches',fontweight='bold')
    ax.set_xlabel('Aircraft Commander',fontweight='bold')
    ax.set_title('Launches by Aircraft Commander',fontweight='bold')
    # Change label color
    ax.tick_params(axis='x', rotation=90, labelcolor='black')
    ax.tick_params(axis='y', labelcolor='black')
    st.pyplot(fig)

    # Display the data in a table.
    display_df = format_data_for_display(filtered_df)
    st.dataframe(
            data=display_df,
            hide_index=True,
    )

    # Add a button to manually refresh data
    if st.button('Refresh Data'):
        data = fetch_data_from_mongodb()
        display_df = format_data_for_display(data)
        st.dataframe(
            data=display_df,
            hide_index=True,
        )


if __name__ == '__main__':
    main()
    
"""dashboard.py - Streamlit app for displaying the stats dashboard.
"""

from log_keeper.get_config import get_config
import pymongo
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.markdown("# 661 VGS Dashboard")
st.sidebar.markdown("# 661 VGS Dashboard")

# Function to fetch data from MongoDB
def fetch_data_from_mongodb():
    """Fetch data from MongoDB and return as a DataFrame.
    Returns:
        pd.DataFrame: The data from MongoDB."""

    # Construct the MongoDB connection URI
    db_config = get_config()
    DB_HOSTNAME = db_config["DB_HOSTNAME"]
    DB_USERNAME = db_config["DB_USERNAME"]
    DB_PASSWORD = db_config["DB_PASSWORD"]
    DB_COLLECTION_NAME = db_config["DB_COLLECTION_NAME"]
    DB_NAME = db_config["DB_NAME"]

    # Connect to MongoDB
    client = pymongo.MongoClient(db_url)
    db = client[DB_NAME]
    collection = db[DB_COLLECTION_NAME]

    # Convert list of dictionaries to DataFrame
    df = pd.DataFrame(collection.find())

    return df


def main():
    """Main Streamlit App Code."""

    # Fetch data from MongoDB
    df = fetch_data_from_mongodb()

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
    launches_by_commander_sorted.plot(kind='bar', ax=ax, color='green')
    ax.set_ylabel('Number of Launches')
    ax.set_xlabel('Aircraft Commander')
    ax.set_title('Launches by Aircraft Commander')
    # Change label color
    ax.tick_params(axis='x', rotation=90, labelcolor='black')
    ax.tick_params(axis='y', labelcolor='black')
    st.pyplot(fig)

    # Display data in Streamlit
    st.write(filtered_df)

    # Add a button to manually refresh data
    if st.button('Refresh Data'):
        data = fetch_data_from_mongodb()
        st.dataframe(
            data=data,
            hide_index=True,
    )


if __name__ == '__main__':
    main()
    
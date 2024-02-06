#Stats Dashboard

import streamlit as st
import pymongo
import pandas as pd
import matplotlib.pyplot as plt

st.markdown("# 661 VGS Dashboard")
st.sidebar.markdown("# 661 VGS Dashboard")

# Function to fetch data from MongoDB
def fetch_data_from_mongodb():

    # Construct the MongoDB connection URI
    DB_USERNAME = "661vgs"
    DB_PASSWORD = "Viking2022"
    DB_HOSTNAME = "661vgs.pcc7txt.mongodb.net"
    db_url = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOSTNAME}/?retryWrites=true&w=majority"

    # Connect to MongoDB
    client = pymongo.MongoClient(db_url)
    db = client["661vgs"]
    collection = db["log_sheets"]

    # Retrieve data from the collection
    cursor = collection.find({})

    # Convert cursor to list of dictionaries
    data_list = list(cursor)

    # Convert list of dictionaries to DataFrame
    df = pd.DataFrame(data_list)

    return df

# Main Streamlit App Code
def main():

    # Fetch data from MongoDB
    df = fetch_data_from_mongodb()

    # Filter by AircraftCommander
    commander = st.sidebar.selectbox("Filter by AircraftCommander", df["AircraftCommander"].unique())
    filtered_df = df[df["AircraftCommander"] == commander]

    # Group by AircraftCommander and count launches
    launches_by_commander = df.groupby("AircraftCommander").size()

    # Sort launches by commander in descending order
    launches_by_commander_sorted = launches_by_commander.sort_values(ascending=False)

    # Create a custom bar chart with text color
    fig, ax = plt.subplots()
    launches_by_commander_sorted.plot(kind='bar', ax=ax, color='green')
    ax.set_ylabel('Number of Launches')
    ax.set_xlabel('Aircraft Commander')
    ax.set_title('Launches by Aircraft Commander')
    ax.tick_params(axis='x', rotation=90, labelcolor='black')  # Change label color
    ax.tick_params(axis='y', labelcolor='black')  # Change label color
    st.pyplot(fig)

    # Display data in Streamlit
    st.write(filtered_df)

    # Add a button to manually refresh data
    if st.button('Refresh Data'):
        data = fetch_data_from_mongodb()
        st.write(data)

if __name__ == '__main__':
    main()

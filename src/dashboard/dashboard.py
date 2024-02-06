#my website

import streamlit as st
import pymongo

st.markdown("# 661 VGS Stats Dashboard")
st.sidebar.markdown("# 661 VGS Stats Dashboard")

# streamlit_app.py

# Initialize connection.
# Uses st.cache_resource to only run once.
@st.cache_resource
def init_connection():
    return pymongo.MongoClient(**st.secrets["mongo"])

client = init_connection()

# Pull data from the collection.
# Uses st.cache_data to only rerun when the query changes or after 10 min.
@st.cache_data(ttl=600)
def get_data():
    db = client["661vgs"]
    items = db.log_sheets.find()
    items = list(items)  # make hashable for st.cache_data
    return items

items = get_data()

# Print results.
for item in items:
    st.write(item['test'])

import streamlit as st
import datetime
import requests

st.title("Timesheets Daily ⏰")
st.write("This app shows the current time and the last time the daily job ran.")

# Current time in UTC (when the page is loaded)
now_utc = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
st.write(f"Current time (UTC) when this page loaded: **{now_utc}**")

# Raw GitHub URL of last_run.txt in your repo
RAW_URL = "https://raw.githubusercontent.com/qa317/timesheets_daily/main/last_run.txt"

st.write("---")
st.subheader("Last scheduled run (from GitHub Actions)")

try:
    response = requests.get(RAW_URL, timeout=5)
    if response.status_code == 200:
        st.code(response.text.strip())
    else:
        st.write(f"Could not load last run time (HTTP status: {response.status_code})")
except Exception as e:
    st.write("Error while trying to load last run time.")

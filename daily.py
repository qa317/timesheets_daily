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
import requests
import json
import pandas as pd
import gspread
from datetime import datetime, timedelta, timezone



st_date="2026-01-01T00:00:00.000Z"
end_date="2026-02-01T00:00:00.000Z"
last_n_hours=24





gname = 'https://docs.google.com/spreadsheets/d/1nSJtG7BkgHm-ImRtEagZSzi54TZRh2VzVaBUkUh5HXE/edit?gid=0#gid=0'

api_key = st.secrets["api"]["api_key"]
workspace_id0 = ['67c0124e07582d1d96dcb6f9','6596b45a79710760f43ae181','6731a5adf2103568429a76f2']

headers = {
    'X-Api-Key': api_key,
    'Content-Type': 'application/json'
}

credentials = st.secrets["google"]["credentials"]

gc = gspread.service_account_from_dict(credentials)
sheet = gc.open_by_url(gname)
wks3 = sheet.worksheet('data1')
df_old = pd.DataFrame(wks3.get_all_records())

# Define 24-hour window
now_utc = datetime.now(timezone.utc)
cutoff_utc = now_utc - timedelta(hours=last_n_hours)

payload = {
    "dateRangeStart": st_date,  # can remain broad
    "dateRangeEnd": end_date,
    "detailedFilter": {
        "page": 1,
        "pageSize": 1000
    }
}

for workspace_id in workspace_id0:
    url = f'https://reports.api.clockify.me/v1/workspaces/{workspace_id}/reports/detailed'
    extracted_data = []
    page = 1

    while True:
        payload["detailedFilter"]["page"] = page
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        report_data = response.json()

        time_entries = report_data.get('timeentries', [])
        if not time_entries:
            break

        for entry in time_entries:
            start_time_str = entry['timeInterval'].get('start', 'N/A')
            end_time_str = entry['timeInterval'].get('end', 'N/A')

            # Convert start time to datetime (UTC)
            try:
                start_dt = pd.to_datetime(start_time_str, utc=True)
            except Exception:
                continue

            # ✅ Keep only entries started in last 24 hours
            if not (cutoff_utc <= start_dt <= now_utc):
                continue

            extracted_data.append({
                'id': entry.get('_id', 'N/A'),
                'Username': entry.get('userName', 'N/A'),
                'Project': entry.get('projectName', 'N/A'),
                'Start Time': start_time_str,
                'End Time': end_time_str,
                'Duration': entry['timeInterval'].get('duration', 'N/A'),
                'Task': entry.get('taskName', 'N/A')
            })

        page += 1

    if not extracted_data:
        continue

    df = pd.DataFrame(extracted_data)
    df = df.sort_values('Start Time')

    # remove already existing IDs
    if 'Id' in df_old.columns:
        df = df[~df['id'].isin(df_old['Id'])]
    elif 'id' in df_old.columns:
        df = df[~df['id'].isin(df_old['id'])]

    if not df.empty:
        sheet.values_append('data1', {'valueInputOption': 'USER_ENTERED'}, {'values': df.values.tolist()})
        print(f"Added {len(df)} new entries for workspace {workspace_id}")
    else:
        print(f"No new entries for workspace {workspace_id}")


try:
    response = requests.get(RAW_URL, timeout=5)
    if response.status_code == 200:
        st.code(response.text.strip())
    else:
        st.write(f"Could not load last run time (HTTP status: {response.status_code})")
except Exception as e:
    st.write("Error while trying to load last run time.")




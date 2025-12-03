import requests
import json
from datetime import datetime, timedelta, timezone
import datetime as dt  # alias for module to use at the end
import pandas as pd
import streamlit as st
import gspread


# =========================
# HARD-CODED CONFIG
# =========================

# Clockify
CLOCKIFY_API_KEY = "YOUR_CLOCKIFY_API_KEY"

WORKSPACE_IDS = [
    "67c0124e07582d1d96dcb6f9",
    "6596b45a79710760f43ae181",
    "6731a5adf2103568429a76f2",
]

# Date range defaults (Clockify expects ISO with time & Z)
DEFAULT_START_DATE_STR = "2025-12-01T00:00:00.000Z"
DEFAULT_END_DATE_STR = "2026-01-01T00:00:00.000Z"
DEFAULT_LAST_N_HOURS = 24

# Google Sheets
GSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1nSJtG7BkgHm-ImRtEagZSzi54TZRh2VzVaBUkUh5HXE/edit?gid=0#gid=0"
)

# Put your real service account JSON values here:
GCP_SERVICE_ACCOUNT_CREDENTIALS = {
    "type": "service_account",
    "project_id": "grand-highway-367317",
    "private_key_id": "1176145f2833a0ba5a27a589fafbb2de8100d247",
    "private_key": """-----BEGIN PRIVATE KEY-----
YOUR_PRIVATE_KEY_GOES_HERE
-----END PRIVATE KEY-----\n""",
    "client_email": "qa-api@grand-highway-367317.iam.gserviceaccount.com",
    "client_id": "104713468791756278919",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/qa-api%40grand-highway-367317.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}


# =========================
# HELPERS
# =========================

def get_gspread_client():
    try:
        gc = gspread.service_account_from_dict(GCP_SERVICE_ACCOUNT_CREDENTIALS)
        return gc
    except Exception as e:
        st.error(f"Error initializing gspread client: {e}")
        return None


def fetch_clockify_entries(workspace_ids, st_date, end_date, last_n_hours):
    """
    Fetch detailed time entries from Clockify for the given workspace IDs,
    filtered to only include entries started in the last `last_n_hours`.
    """
    headers = {
        "X-Api-Key": CLOCKIFY_API_KEY,
        "Content-Type": "application/json",
    }

    now_utc = datetime.now(timezone.utc)
    cutoff_utc = now_utc - timedelta(hours=last_n_hours)

    payload = {
        "dateRangeStart": st_date,
        "dateRangeEnd": end_date,
        "detailedFilter": {
            "page": 1,
            "pageSize": 1000,
        },
    }

    all_new_rows = []

    progress = st.progress(0)
    status_text = st.empty()
    total_workspaces = len(workspace_ids)

    for i, workspace_id in enumerate(workspace_ids, start=1):
        url = f"https://reports.api.clockify.me/v1/workspaces/{workspace_id}/reports/detailed"
        extracted_data = []
        page = 1

        status_text.write(f"Fetching data for workspace `{workspace_id}`, page {page}...")

        while True:
            payload["detailedFilter"]["page"] = page
            response = requests.post(url, headers=headers, data=json.dumps(payload))

            try:
                response.raise_for_status()
            except Exception as e:
                st.error(f"Error for workspace {workspace_id}, page {page}: {e}")
                break

            report_data = response.json()
            time_entries = report_data.get("timeentries", [])

            if not time_entries:
                break

            for entry in time_entries:
                start_time_str = entry["timeInterval"].get("start", "N/A")
                end_time_str = entry["timeInterval"].get("end", "N/A")

                # Convert start time to datetime (UTC)
                try:
                    start_dt = pd.to_datetime(start_time_str, utc=True)
                except Exception:
                    continue

                # Keep only entries started in last N hours
                if not (cutoff_utc <= start_dt <= now_utc):
                    continue

                extracted_data.append(
                    {
                        "id": entry.get("_id", "N/A"),
                        "Username": entry.get("userName", "N/A"),
                        "Project": entry.get("projectName", "N/A"),
                        "Start Time": start_time_str,
                        "End Time": end_time_str,
                        "Duration": entry["timeInterval"].get("duration", "N/A"),
                        "Task": entry.get("taskName", "N/A"),
                    }
                )

            page += 1
            status_text.write(f"Fetching data for workspace `{workspace_id}`, page {page}...")

        if extracted_data:
            df_ws = pd.DataFrame(extracted_data)
            df_ws["workspace_id"] = workspace_id  # optional
            all_new_rows.append(df_ws)

        progress.progress(i / total_workspaces)

    status_text.write("Finished fetching data from Clockify.")
    if all_new_rows:
        return pd.concat(all_new_rows, ignore_index=True)
    return pd.DataFrame()


# =========================
# STREAMLIT APP
# =========================

def main():
    st.title("Clockify → Google Sheets Sync")

    st.markdown(
        "This app pulls Clockify detailed reports for the last **N hours** "
        "and appends new entries to the Google Sheet worksheet named `data1`."
    )

    # --- Inputs (pre-filled with your hard-coded defaults but still editable in UI) ---

    gsheet_url = st.text_input("Google Sheet URL", value=GSHEET_URL)

    # Extract dates from the default ISO strings
    default_start_date = datetime.fromisoformat(
        DEFAULT_START_DATE_STR.replace("Z", "+00:00")
    ).date()
    default_end_date = datetime.fromisoformat(
        DEFAULT_END_DATE_STR.replace("Z", "+00:00")
    ).date()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Report start date", default_start_date)
    with col2:
        end_date = st.date_input("Report end date", default_end_date)

    st_date_iso = start_date.isoformat() + "T00:00:00.000Z"
    end_date_iso = end_date.isoformat() + "T00:00:00.000Z"

    last_n_hours = st.slider(
        "Last N hours",
        min_value=1,
        max_value=168,
        value=DEFAULT_LAST_N_HOURS,
    )

    workspace_ids_text = st.text_area(
        "Clockify workspace IDs (one per line)",
        value="\n".join(WORKSPACE_IDS),
    )
    workspace_ids = [w.strip() for w in workspace_ids_text.splitlines() if w.strip()]

    if st.button("Sync now"):
        if not gsheet_url:
            st.error("Please provide a Google Sheet URL.")
            return
        if not workspace_ids:
            st.error("Please provide at least one workspace ID.")
            return

        # --- Connect to Google Sheets ---
        gc = get_gspread_client()
        if gc is None:
            return

        try:
            sheet = gc.open_by_url(gsheet_url)
            wks = sheet.worksheet("data1")
        except Exception as e:
            st.error(f"Error opening worksheet 'data1': {e}")
            return

        # Existing data
        df_old = pd.DataFrame(wks.get_all_records())
        st.write("Loaded existing rows from sheet:", len(df_old))

        # --- Fetch Clockify data ---
        df_new = fetch_clockify_entries(
            workspace_ids=workspace_ids,
            st_date=st_date_iso,
            end_date=end_date_iso,
            last_n_hours=last_n_hours,
        )

        if df_new.empty:
            st.info("No entries found for the selected time window.")
            return

        # --- Remove already existing IDs ---
        if "Id" in df_old.columns:
            df_filtered = df_new[~df_new["id"].isin(df_old["Id"])]
        elif "id" in df_old.columns:
            df_filtered = df_new[~df_new["id"].isin(df_old["id"])]
        else:
            df_filtered = df_new  # no id column in old sheet

        df_filtered = df_filtered.sort_values("Start Time")

        if df_filtered.empty:
            st.info("No new entries to append. Everything is already in the sheet.")
            return

        # --- Append to sheet ---
        values_to_append = df_filtered.values.tolist()
        try:
            sheet.values_append(
                "data1",
                {"valueInputOption": "USER_ENTERED"},
                {"values": values_to_append},
            )
        except Exception as e:
            st.error(f"Error appending rows to sheet: {e}")
            return

        st.success(f"Added {len(df_filtered)} new entries.")
        st.subheader("New entries preview")
        st.dataframe(df_filtered)


if __name__ == "__main__":
    main()

# =========================
# EXTRA: Last GitHub Actions run
# =========================

# Current time in UTC (when the page is loaded)
now_utc = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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

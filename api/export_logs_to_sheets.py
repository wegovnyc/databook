#!/usr/bin/env python3
"""
Export MCP logs to Google Sheets.

This script fetches logs from the MCP server and appends them to a Google Sheet.
It tracks the last export time to only export new logs.

Usage:
    # Set up credentials first:
    export GOOGLE_SHEETS_CREDENTIALS=/path/to/service-account.json
    
    # Run export
    python export_logs_to_sheets.py
    
    # Or run as a cron job every 5 minutes
    */5 * * * * cd /path/to && python export_logs_to_sheets.py
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gspread", "google-auth"])
    import gspread
    from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = "1B68hCdjZOvAFkfc32KVR10MaR46MC7bCDEU5H6TYGRA"
MCP_LOGS_URL = "https://api.databook.nyc/admin/logs"
STATE_FILE = "/tmp/mcp_logs_export_state.json"

# Google Sheets scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_sheets_client() -> Optional[gspread.Client]:
    """Initialize gspread client with service account credentials."""
    creds_path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    
    if not creds_path:
        # Try common locations
        common_paths = [
            "/app/google-credentials.json",
            "/home/ubuntu/google-credentials.json",
            os.path.expanduser("~/.config/gspread/service_account.json"),
        ]
        for path in common_paths:
            if os.path.exists(path):
                creds_path = path
                break
    
    if not creds_path or not os.path.exists(creds_path):
        print("ERROR: Google Sheets credentials not found.")
        print("Set GOOGLE_SHEETS_CREDENTIALS environment variable to the path of your service account JSON file.")
        return None
    
    try:
        credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        return gspread.authorize(credentials)
    except Exception as e:
        print(f"ERROR: Failed to authenticate with Google Sheets: {e}")
        return None


def fetch_logs() -> List[Dict]:
    """Fetch logs from the MCP server."""
    try:
        response = requests.get(MCP_LOGS_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("logs", [])
    except Exception as e:
        print(f"ERROR: Failed to fetch logs from {MCP_LOGS_URL}: {e}")
        return []


def load_state() -> Dict:
    """Load the last export state."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {"last_timestamp": None, "exported_count": 0}


def save_state(state: Dict):
    """Save the export state."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Warning: Failed to save state: {e}")


def export_logs_to_sheet(logs: List[Dict], gc: gspread.Client) -> int:
    """Export logs to Google Sheet, returning count of new rows added."""
    try:
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.sheet1
        
        # Get existing data to find header row and last row
        existing_data = worksheet.get_all_values()
        
        # Define headers
        headers = ["timestamp", "session_id", "request_num", "tool_name", "args", 
                   "elapsed_ms", "row_count", "error", "result_preview"]
        
        # If sheet is empty, add headers
        if not existing_data:
            worksheet.append_row(headers)
            existing_data = [headers]
        
        # Get existing timestamps to avoid duplicates
        existing_timestamps = set()
        if len(existing_data) > 1:
            timestamp_col = headers.index("timestamp") if "timestamp" in existing_data[0] else 0
            for row in existing_data[1:]:
                if row and len(row) > timestamp_col:
                    existing_timestamps.add(row[timestamp_col])
        
        # Filter and prepare new logs
        new_rows = []
        for log in logs:
            timestamp = log.get("timestamp", "")
            if timestamp and timestamp not in existing_timestamps:
                row = [
                    log.get("timestamp", ""),
                    log.get("session_id", ""),
                    str(log.get("request_num", "")),
                    log.get("tool_name", ""),
                    log.get("args", ""),
                    str(log.get("elapsed_ms", "")),
                    str(log.get("row_count", "") or ""),
                    log.get("error", "") or "",
                    (log.get("result_preview", "") or "")[:500]  # Truncate long results
                ]
                new_rows.append(row)
        
        # Append new rows in batches
        if new_rows:
            # Use batch update for efficiency
            worksheet.append_rows(new_rows, value_input_option='RAW')
            print(f"Exported {len(new_rows)} new log entries to Google Sheet")
        else:
            print("No new logs to export")
        
        return len(new_rows)
        
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"ERROR: Spreadsheet not found. Make sure the service account has access to: {SPREADSHEET_ID}")
        print("Share the spreadsheet with your service account email (found in the JSON credentials file)")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to export to Google Sheet: {e}")
        return 0


def main():
    """Main export function."""
    print(f"[{datetime.now().isoformat()}] Starting MCP logs export...")
    
    # Initialize Google Sheets client
    gc = get_sheets_client()
    if not gc:
        sys.exit(1)
    
    # Fetch logs
    logs = fetch_logs()
    if not logs:
        print("No logs to export")
        return
    
    print(f"Fetched {len(logs)} logs from MCP server")
    
    # Export to sheet
    exported = export_logs_to_sheet(logs, gc)
    
    # Update state
    if logs and exported > 0:
        state = load_state()
        state["last_timestamp"] = logs[-1].get("timestamp")
        state["exported_count"] = state.get("exported_count", 0) + exported
        save_state(state)
    
    print(f"[{datetime.now().isoformat()}] Export complete")


if __name__ == "__main__":
    main()

import os
import json
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

def audit_sheet():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=creds)
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    # Get the first budget sheet
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_title = [s['properties']['title'] for s in spreadsheet['sheets'] if s['properties']['title'].startswith("ENTITY-")][0]
    
    # Read the first 10 rows to see headers and controls
    res = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A1:Z10",
        valueRenderOption="FORMULA"
    ).execute()
    
    print(f"--- BLUEPRINT AUDIT: {sheet_title} ---")
    rows = res.get("values", [])
    for i, row in enumerate(rows):
        print(f"Row {i+1}: {row}")

if __name__ == "__main__":
    audit_sheet()

import json
import os
from typing import Any, List, Dict, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.config import config

class SheetsService:
    def __init__(self, blueprint_path: Optional[str] = None):
        if blueprint_path:
            with open(blueprint_path, 'r') as f:
                self.blueprint = json.load(f)
        else:
            self.blueprint = None
        
        self.credentials = service_account.Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self.service = build("sheets", "v4", credentials=self.credentials, cache_discovery=False)
        self.spreadsheet_id = config.GOOGLE_SHEET_ID

    def get_spreadsheet_metadata(self) -> Dict[str, Any]:
        return self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()

    def update_status(self, sheet_title: str, status: str, sync_done: bool = False):
        """Updates the status cell if a blueprint is loaded."""
        if not self.blueprint or "controls" not in self.blueprint:
            return
            
        status_cell = self.blueprint["controls"]["status"]["cell"]
        sync_cell = self.blueprint["controls"]["sync"]["cell"]
        
        requests = [
            {
                "range": f"'{sheet_title}'!{status_cell}",
                "values": [[status]]
            }
        ]
        
        if sync_done:
            requests.append({
                "range": f"'{sheet_title}'!{sync_cell}",
                "values": [[False]]
            })
 
        for req in requests:
            try:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=req["range"],
                    valueInputOption="RAW",
                    body={"values": req["values"]},
                ).execute()
            except:
                pass # Silently fail if cells don't exist yet

    def ensure_sheet(self, title: str, target_sheet_id: Optional[int] = None) -> Dict[str, Any]:
        """Ensures a sheet exists by title or ID. Clears it if it exists."""
        spreadsheet = self.get_spreadsheet_metadata()
        
        if target_sheet_id is not None:
            for sheet in spreadsheet.get("sheets", []):
                if sheet["properties"]["sheetId"] == target_sheet_id:
                    self.service.spreadsheets().values().clear(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"'{sheet['properties']['title']}'",
                        body={},
                    ).execute()
                    return sheet["properties"]

        for sheet in spreadsheet.get("sheets", []):
            props = sheet.get("properties", {})
            if props.get("title") == title:
                self.service.spreadsheets().values().clear(
                    spreadsheetId=self.spreadsheet_id,
                    range=title,
                    body={},
                ).execute()
                return props

        reply = self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title, "gridProperties": {"rowCount": 250, "columnCount": 35}}}}]},
        ).execute()
        return reply["replies"][0]["addSheet"]["properties"]

    def write_raw_values(self, sheet_title: str, values: List[List[Any]]):
        """Clears a sheet and writes raw values."""
        self.service.spreadsheets().values().clear(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{sheet_title}'",
            body={}
        ).execute()
        
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{sheet_title}'!A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

    def write_rows(self, sheet_id: int, rows: List[Dict[str, Any]]):
        """Writes a list of RowData objects to the sheet starting at A1."""
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateCells": {
                            "rows": rows,
                            "fields": "userEnteredValue,userEnteredFormat",
                            "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0}
                        }
                    }
                ]
            }
        ).execute()

    def batch_update(self, requests: List[Dict[str, Any]]):
        if not requests:
            return
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": requests},
        ).execute()

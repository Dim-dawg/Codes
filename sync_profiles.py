import json
import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build


DEFAULT_HEADERS = [
    "id",
    "name",
    "type",
    "default_category_id",
    "account_type",
    "address",
    "description",
    "notes",
    "keyword_match",
    "tags",
    "keywords",
    "exclude_keywords",
]


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
      raise RuntimeError(f"Missing required env var: {name}")
    return value


def split_csv(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    return str(value)


def get_supabase_headers() -> dict[str, str]:
    token = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or require_env("SUPABASE_ANON_KEY")
    return {
        "apikey": token,
        "Authorization": f"Bearer {token}",
    }


def fetch_profiles() -> list[dict[str, Any]]:
    base_url = require_env("SUPABASE_URL").rstrip("/")
    user_id = require_env("SUPABASE_USER_ID")
    endpoint = f"{base_url}/rest/v1/profiles"
    params = {
        "user_id": f"eq.{user_id}",
        "select": "id,name,type,address,notes,description,tags,keyword_match,default_category_id,keywords,exclude_keywords,default_category:categories(account_type)",
        "order": "name.asc",
    }

    response = requests.get(endpoint, headers=get_supabase_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def map_profile(profile: dict[str, Any]) -> list[str]:
    default_category = profile.get("default_category") or {}
    return [
        str(profile.get("id") or ""),
        str(profile.get("name") or ""),
        str(profile.get("type") or ""),
        str(profile.get("default_category_id") or ""),
        str(default_category.get("account_type") or ""),
        str(profile.get("address") or ""),
        str(profile.get("description") or ""),
        str(profile.get("notes") or ""),
        str(profile.get("keyword_match") or ""),
        split_csv(profile.get("tags")),
        split_csv(profile.get("keywords")),
        split_csv(profile.get("exclude_keywords")),
    ]


def get_sheets_service():
    credentials_path = require_env("GOOGLE_SERVICE_ACCOUNT_FILE")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_file(credentials_path, scopes=scopes)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def get_target_sheet_metadata(service, spreadsheet_id: str) -> dict[str, Any]:
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    target_gid = os.getenv("GOOGLE_WORKSHEET_GID", "").strip()
    target_name = os.getenv("GOOGLE_WORKSHEET_NAME", "").strip()

    for sheet in spreadsheet.get("sheets", []):
        props = sheet.get("properties", {})
        if target_gid and str(props.get("sheetId")) == target_gid:
            return props
        if target_name and props.get("title") == target_name:
            return props

    available = [sheet.get("properties", {}).get("title", "") for sheet in spreadsheet.get("sheets", [])]
    raise RuntimeError(
        "Target worksheet not found. "
        f"GOOGLE_WORKSHEET_NAME={target_name or '<blank>'}, "
        f"GOOGLE_WORKSHEET_GID={target_gid or '<blank>'}, "
        f"available={available}"
    )


def sync_sheet(rows: list[list[str]]) -> dict[str, Any]:
    spreadsheet_id = require_env("GOOGLE_SHEET_ID")
    service = get_sheets_service()
    props = get_target_sheet_metadata(service, spreadsheet_id)
    title = props["title"]
    values = [DEFAULT_HEADERS] + rows

    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=title,
        body={}
    ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    format_sheet(service, spreadsheet_id, props["sheetId"], len(values), len(DEFAULT_HEADERS))

    return {
        "spreadsheet_title": service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute().get("properties", {}).get("title"),
        "worksheet_title": title,
        "worksheet_gid": props["sheetId"],
        "row_count": len(rows),
        "column_count": len(DEFAULT_HEADERS),
    }


def format_sheet(service, spreadsheet_id: str, sheet_id: int, row_count: int, column_count: int) -> None:
    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 1,
                    }
                },
                "fields": "gridProperties.frozenRowCount"
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": column_count,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.07, "green": 0.42, "blue": 0.33},
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            "bold": True,
                            "fontSize": 10,
                        },
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": row_count,
                    "startColumnIndex": 0,
                    "endColumnIndex": column_count,
                },
                "cell": {
                    "userEnteredFormat": {
                        "wrapStrategy": "WRAP",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"
            }
        },
        {
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": row_count,
                        "startColumnIndex": 0,
                        "endColumnIndex": column_count,
                    }
                }
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": 240},
                "fields": "pixelSize"
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 1,
                    "endIndex": 5,
                },
                "properties": {"pixelSize": 180},
                "fields": "pixelSize"
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 5,
                    "endIndex": column_count,
                },
                "properties": {"pixelSize": 260},
                "fields": "pixelSize"
            }
        },
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests}
    ).execute()


def main() -> int:
    load_dotenv()

    try:
        profiles = fetch_profiles()
        rows = [map_profile(profile) for profile in profiles]
        result = sync_sheet(rows)
        preview = [row[1] for row in rows[:3]]
        print(json.dumps({
            "ok": True,
            "synced_profiles": result["row_count"],
            "worksheet_title": result["worksheet_title"],
            "worksheet_gid": result["worksheet_gid"],
            "sample_names": preview,
        }, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
        }, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())

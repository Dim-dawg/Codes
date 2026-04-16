import calendar
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load the rigid blueprint
blueprint_path = os.path.join(os.path.dirname(__file__), 'DESIGN_BLUEPRINT.json')
with open(blueprint_path, 'r') as f:
    BLUEPRINT = json.load(f)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Use colors and labels from blueprint
SECTION_CONFIG = [
    (s["label"], s["id"], s["color"]) for s in BLUEPRINT["sections"]
]


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def get_supabase_headers() -> dict[str, str]:
    token = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or require_env("SUPABASE_ANON_KEY")
    return {
        "apikey": token,
        "Authorization": f"Bearer {token}",
    }


def supabase_get(path: str, params: dict[str, str]) -> list[dict[str, Any]]:
    base_url = require_env("SUPABASE_URL").rstrip("/")
    response = requests.get(
        f"{base_url}/rest/v1/{path}",
        headers=get_supabase_headers(),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_profiles() -> list[dict[str, Any]]:
    user_id = require_env("SUPABASE_USER_ID")
    return supabase_get(
        "profiles",
        {
            "user_id": f"eq.{user_id}",
            "select": "id,name,type,address,notes,default_category_id,default_category:categories(name,account_type)",
            "order": "name.asc",
        },
    )


def fetch_budgets(month_year: str) -> list[dict[str, Any]]:
    user_id = require_env("SUPABASE_USER_ID")
    return supabase_get(
        "budgets",
        {
            "user_id": f"eq.{user_id}",
            "month": f"eq.{month_year}",
            "select": "category_id,amount",
        },
    )


def fetch_transactions(month_year: str) -> list[dict[str, Any]]:
    user_id = require_env("SUPABASE_USER_ID")
    year, month = month_year.split("-")
    last_day = calendar.monthrange(int(year), int(month))[1]
    return supabase_get(
        "transactions",
        {
            "user_id": f"eq.{user_id}",
            "and": f"(date.gte.{month_year}-01,date.lte.{month_year}-{last_day:02d})",
            "select": "id,date,amount,type,profile_id,category_id,category:categories(account_type)",
            "order": "date.asc",
        },
    )


def normalize_account_type(profile: dict[str, Any]) -> str:
    # 1. Get raw type from category
    raw = str((profile.get("default_category") or {}).get("account_type") or "").upper().strip()
    
    # 2. Map specific DB types to our 3 main UI sections
    if raw == "INCOME":
        return "INCOME"
    
    if raw == "EXPENSE":
        return "EXPENSE"
    
    # Everything else (Assets, Liabilities, Equity) goes to Savings & Investments
    if raw in ["CURRENT_ASSET", "LONG_TERM_LIAB", "EQUITY", "SAVINGS", "INVESTMENT"]:
        return "SAVINGS"
        
    # Default to EXPENSE if unknown
    return "EXPENSE"


def build_budget_map(profiles: list[dict[str, Any]], budgets: list[dict[str, Any]]) -> dict[str, float]:
    category_budget_map = {row["category_id"]: float(row.get("amount") or 0) for row in budgets}
    result = {}
    for profile in profiles:
        result[profile["id"]] = category_budget_map.get(profile.get("default_category_id"), 0.0)
    return result


def build_daily_actuals(transactions: list[dict[str, Any]]) -> tuple[dict[str, dict[int, float]], int]:
    result: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    unlinked_count = 0
    for txn in transactions:
        profile_id = txn.get("profile_id")
        if not profile_id:
            unlinked_count += 1
            continue
        day = int(str(txn["date"]).split("T")[0].split("-")[2])
        amount = float(txn.get("amount") or 0)
        
        # Use category account_type for signing (Income is positive, everything else negative)
        cat_type = (txn.get("category") or {}).get("account_type", "").upper()
        signed = abs(amount) if cat_type == "INCOME" else -abs(amount)
        
        result[profile_id][day] += signed
    return result, unlinked_count


def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        require_env("GOOGLE_SERVICE_ACCOUNT_FILE"),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def update_status(service, spreadsheet_id: str, sheet_title: str, status: str, sync_done: bool = False):
    """Updates the status cell and resets checkbox based on BLUEPRINT"""
    status_cell = BLUEPRINT["controls"]["status"]["cell"]
    sync_cell = BLUEPRINT["controls"]["sync"]["cell"]
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!{status_cell}",
        valueInputOption="RAW",
        body={"values": [[status]]},
    ).execute()
    
    if sync_done:
        # Reset checkbox to FALSE
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_title}'!{sync_cell}",
            valueInputOption="RAW",
            body={"values": [[False]]},
        ).execute()


def ensure_sheet(service, spreadsheet_id: str, title: str, target_sheet_id: int = None) -> dict[str, Any]:
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    
    # If target_sheet_id is provided, we are updating IN PLACE
    if target_sheet_id is not None:
        # Clear the sheet
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"'{title}'",
            body={},
        ).execute()
        # Find the props for the given ID
        for sheet in spreadsheet.get("sheets", []):
            if sheet["properties"]["sheetId"] == target_sheet_id:
                return sheet["properties"]

    # Otherwise, check by title
    for sheet in spreadsheet.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == title:
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=title,
                body={},
            ).execute()
            return props

    reply = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": title, "gridProperties": {"rowCount": 250, "columnCount": 35}}}}]},
    ).execute()
    return reply["replies"][0]["addSheet"]["properties"]


def column_letter(col: int) -> str:
    result = ""
    current = col
    while current > 0:
        mod = (current - 1) % 26
        result = chr(65 + mod) + result
        current = (current - 1) // 26
    return result


def write_month_sheet(month_year: str, target_sheet_id: int = None, current_title: str = None) -> dict[str, Any]:
    parsed = datetime.strptime(month_year, "%Y-%m")
    last_day = calendar.monthrange(parsed.year, parsed.month)[1]
    total_cols = 3 + last_day  # A, B, C + days
    spreadsheet_id = require_env("GOOGLE_SHEET_ID")
    service = get_sheets_service()
    
    sheet_title = f"ENTITY-{month_year}"
    
    # If we have an existing sheet to update, use its title or the new title if we are renaming
    effective_title = current_title if current_title else sheet_title
    
    props = ensure_sheet(service, spreadsheet_id, effective_title, target_sheet_id)
    sheet_id = props["sheetId"]

    # Update status immediately
    update_status(service, spreadsheet_id, effective_title, "🔄 Syncing data...")

    profiles = fetch_profiles()
    budgets = fetch_budgets(month_year)
    transactions = fetch_transactions(month_year)
    
    # Only include profiles that have transactions for this month
    profile_ids_with_transactions = {t["profile_id"] for t in transactions if t.get("profile_id")}
    profiles = [p for p in profiles if p["id"] in profile_ids_with_transactions]
    
    budget_map = build_budget_map(profiles, budgets)
    daily_actuals, unlinked_txn_count = build_daily_actuals(transactions)

    enriched_profiles = []
    for profile in profiles:
        name = str(profile.get("name") or "Unnamed").strip()
        cat_name = (profile.get("default_category") or {}).get("name") or "Uncategorized"
        
        enriched_profiles.append({
            "id": profile["id"],
            "name": name,
            "category_name": cat_name,
            "account_type": normalize_account_type(profile),
        })

    # Sort profiles by name (no category grouping)
    enriched_profiles.sort(key=lambda x: x["name"])

    sections = {
        "INCOME": [p for p in enriched_profiles if p["account_type"] == "INCOME"],
        "EXPENSE": [p for p in enriched_profiles if p["account_type"] == "EXPENSE"],
        "SAVINGS": [p for p in enriched_profiles if p["account_type"] == "SAVINGS"],
    }

    values: list[list[Any]] = []
    row_formats: list[dict[str, Any]] = []
    formula_cells: list[dict[str, Any]] = []

    # Row 1 & 2 Headers/Controls from BLUEPRINT
    c = BLUEPRINT["controls"]
    row1 = [""] * 34
    row1[ord(c["year"]["label"][0]) - 65] = "Year:"
    row1[ord(c["year"]["cell"][0]) - 65] = parsed.year
    row1[ord(c["status"]["label"][0]) - 65] = "Status:"
    row1[ord(c["status"]["cell"][0]) - 65] = "🔄 Processing..."
    values.append(row1)

    row2 = [""] * 34
    row2[ord(c["month"]["label"][0]) - 65] = "Month:"
    row2[ord(c["month"]["cell"][0]) - 65] = MONTH_NAMES[parsed.month - 1]
    row2[ord(c["sync"]["label"][0]) - 65] = "Sync Now:"
    row2[ord(c["sync"]["cell"][0]) - 65] = False
    values.append(row2)

    values.append([BLUEPRINT["headers"]["columns"]["A"], 
                   BLUEPRINT["headers"]["columns"]["B"], 
                   BLUEPRINT["headers"]["columns"]["C"]] + list(range(1, last_day + 1)))

    current_row = 4
    summary_refs: dict[str, int] = {}
    for label, key, color in SECTION_CONFIG:
        # 1. Main Section Header (e.g. INCOME SOURCE)
        values.append([label] + [""] * 33)
        row_formats.append({"row": current_row, "color": color, "kind": "section"})
        current_row += 1

        section_start = current_row
        row_numbers = []

        # 2. Add profiles directly (no category sub-headers)
        for profile in sections[key]:
            planned = budget_map.get(profile["id"], 0.0)
            daily = [round(daily_actuals[profile["id"]].get(day, 0.0), 2) for day in range(1, last_day + 1)]
            
            # Profile Name
            values.append([profile['name'], planned, ""] + daily)
            row_numbers.append(current_row)
            row_formats.append({"row": current_row, "color": None, "kind": "entity"})
            formula_cells.append({"row": current_row, "col": 3, "formula": f"=SUM(D{current_row}:AH{current_row})"})
            current_row += 1

        # 4. Section Total
        total_row = current_row
        label_text = f"TOTAL {label}" if key != "SAVINGS" else "TOTAL SAVINGS & INVESTMENTS"
        values.append([label_text, "", ""] + [""] * last_day)
        row_formats.append({"row": total_row, "color": color, "kind": "total"})

        if row_numbers:
            formula_cells.append({"row": total_row, "col": 2, "formula": f"=SUM(B{section_start}:B{total_row - 1})"})
            formula_cells.append({"row": total_row, "col": 3, "formula": f"=SUM(C{section_start}:C{total_row - 1})"})
            for col in range(4, 4 + last_day):
                letter = column_letter(col)
                formula_cells.append({"row": total_row, "col": col, "formula": f"=SUM({letter}{section_start}:{letter}{total_row - 1})"})
        summary_refs[key] = total_row
        current_row += 2

    values.append([BLUEPRINT["summary"]["net_summary_label"]] + [""] * (total_cols - 1))
    row_formats.append({"row": current_row, "color": "#444444", "kind": "section"})
    current_row += 1

    cash_flow_row = current_row
    values.append(["CASH FLOW", "", ""] + [""] * last_day)
    row_formats.append({"row": current_row, "color": None, "kind": "summary"})
    formula_cells.append({"row": current_row, "col": 2, "formula": f"=B{summary_refs['INCOME']}+B{summary_refs['EXPENSE']}"})
    formula_cells.append({"row": current_row, "col": 3, "formula": f"=C{summary_refs['INCOME']}+C{summary_refs['EXPENSE']}"})
    current_row += 1

    values.append(["REMAINING", "", ""] + [""] * last_day)
    row_formats.append({"row": current_row, "color": None, "kind": "summary"})
    formula_cells.append({"row": current_row, "col": 2, "formula": f"=B{cash_flow_row}+B{summary_refs['SAVINGS']}"})
    formula_cells.append({"row": current_row, "col": 3, "formula": f"=C{cash_flow_row}+C{summary_refs['SAVINGS']}"})
    last_row = current_row

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{effective_title}'!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    formula_requests = []
    for cell in formula_cells:
        formula_requests.append({
            "updateCells": {
                "rows": [{"values": [{"userEnteredValue": {"formulaValue": cell["formula"]}}]}],
                "fields": "userEnteredValue",
                "start": {
                    "sheetId": sheet_id,
                    "rowIndex": cell["row"] - 1,
                    "columnIndex": cell["col"] - 1,
                },
            }
        })

    batch_requests = build_format_requests(sheet_id, last_row, row_formats, last_day, total_cols)
    
    # Rename sheet if title doesn't match the new month
    if effective_title != sheet_title:
        batch_requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "title": sheet_title,
                },
                "fields": "title",
            }
        })

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": formula_requests + batch_requests},
    ).execute()

    update_status(service, spreadsheet_id, sheet_title, "✅ Ready", sync_done=True)

    return {
        "worksheet_title": sheet_title,
        "worksheet_gid": sheet_id,
        "profiles": len(enriched_profiles),
        "rows_written": len(values),
        "unlinked_transactions": unlinked_txn_count,
    }


def build_format_requests(sheet_id: int, last_row: int, row_formats: list[dict[str, Any]], last_day: int, total_cols: int) -> list[dict[str, Any]]:
    h_style = BLUEPRINT["headers"]["style"]
    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": BLUEPRINT["frozen_rows"],
                        "frozenColumnCount": BLUEPRINT["frozen_cols"],
                    },
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        },
        {
            # A1:B2 controls background/bold
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 2},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        "textFormat": {"bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            # C1:D2 status/sync labels
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 2, "startColumnIndex": 2, "endColumnIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "RIGHT"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        {
            # B1: Year formatting (Plain Number) from BLUEPRINT
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": BLUEPRINT["controls"]["year"]["format"], "pattern": BLUEPRINT["controls"]["year"]["pattern"]}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            # B2: Month formatting (Text) from BLUEPRINT
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": BLUEPRINT["controls"]["month"]["format"]}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            # D2: Sync Checkbox from BLUEPRINT
            "setDataValidation": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 3, "endColumnIndex": 4},
                "rule": {"condition": {"type": "BOOLEAN"}}
            }
        },
        {
            # Headers row (3) from BLUEPRINT style
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": 34},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": hex_to_rgb(h_style["bg"]),
                        "textFormat": {"foregroundColor": hex_to_rgb(h_style["text"]), "bold": h_style["bold"]},
                        "horizontalAlignment": h_style["align"],
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        {
            "setBasicFilter": {
                "filter": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": last_row, "startColumnIndex": 0, "endColumnIndex": total_cols}
                }
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 220},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 3},
                "properties": {"pixelSize": 110},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": total_cols},
                "properties": {"pixelSize": 42},
                "fields": "pixelSize",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": total_cols},
                "cell": {
                    "userEnteredFormat": {
                        "verticalAlignment": "MIDDLE",
                        "wrapStrategy": "CLIP",
                    }
                },
                "fields": "userEnteredFormat(verticalAlignment,wrapStrategy)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": last_row, "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "LEFT",
                    }
                },
                "fields": "userEnteredFormat.horizontalAlignment",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": last_row, "startColumnIndex": 1, "endColumnIndex": total_cols},
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat.horizontalAlignment",
            }
        },
    ]

    for item in row_formats:
        row_index = item["row"] - 1
        kind = item["kind"]
        if kind == "section":
            color = hex_to_rgb(item["color"])
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color,
                            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
                            "horizontalAlignment": "LEFT",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            })
            requests.append({
                "mergeCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": total_cols},
                    "mergeType": "MERGE_ALL",
                }
            })
        elif kind == "total":
            color = hex_to_rgb(item["color"])
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color,
                            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            })
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00;$(#,##0.00)"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            })
        elif kind == "summary":
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": 3},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.98, "green": 0.98, "blue": 0.98},
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                }
            })
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": 3},
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00;$(#,##0.00)"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            })
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 3, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                        }
                    },
                    "fields": "userEnteredFormat.backgroundColor",
                }
            })
        elif kind == "entity" and item["row"] % 2 == 0:
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": total_cols},
                    "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.97, "green": 0.98, "blue": 0.98}}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            })
        if kind == "entity":
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00;$(#,##0.00)"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            })

    return requests


def hex_to_rgb(value: str) -> dict[str, float]:
    value = value.lstrip("#")
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }


def main() -> int:
    load_dotenv()
    
    month_year = None
    for arg in sys.argv[1:]:
        if "=" in arg:
            key, value = arg.split("=", 1)
            if key == "month":
                month_year = value

    if not month_year:
        try:
            spreadsheet_id = require_env("GOOGLE_SHEET_ID")
            service = get_sheets_service()
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheet_title = spreadsheet.get("sheets", [{}])[0].get("properties", {}).get("title", "Sheet1")
            
            res = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_title}'!B1:B2"
            ).execute()
            rows = res.get("values", [])
            
            if len(rows) >= 2:
                year = str(rows[0][0]).strip()
                month_name = str(rows[1][0]).strip()
                month_num = MONTH_NAMES.index(month_name) + 1
                month_year = f"{year}-{month_num:02d}"
        except Exception:
            month_year = datetime.now().strftime("%Y-%m")

    try:
        result = write_month_sheet(month_year)
        print(json.dumps({"ok": True, **result}, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())

import os
import sys
from datetime import datetime
from collections import defaultdict
from zoneinfo import ZoneInfo
from .supabase_service import SupabaseService
from .sheets_service import SheetsService
from .validator import SyncValidator
from .config import config
from .logger import setup_logger

logger = setup_logger("sync_engine")

# 🎨 Cipher Money Brand Colors
COLORS = {
    "bg_dark":       {"red": 0.035, "green": 0.035, "blue": 0.055},
    "accent_cyan":   {"red": 0.0,   "green": 1.0,   "blue": 0.8},
    "accent_gold":   {"red": 1.0,   "green": 0.84,  "blue": 0.0},
    "income_bg":     {"red": 0.06,  "green": 0.18,  "blue": 0.12},
    "expense_bg":    {"red": 0.22,  "green": 0.06,  "blue": 0.06},
    "savings_bg":    {"red": 0.06,  "green": 0.10,  "blue": 0.22},
    "section_hdr":   {"red": 0.08,  "green": 0.08,  "blue": 0.14},
    "total_row":     {"red": 0.12,  "green": 0.12,  "blue": 0.20},
    "zebra_even":    {"red": 0.04,  "green": 0.04,  "blue": 0.07},
    "zebra_odd":     {"red": 0.07,  "green": 0.07,  "blue": 0.11},
    "text_white":    {"red": 1.0,   "green": 1.0,   "blue": 1.0},
    "text_muted":    {"red": 0.6,   "green": 0.6,   "blue": 0.7},
}

class BudgetSyncApp:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        blueprint_path = os.path.join(base_dir, "DESIGN_BLUEPRINT.json")
        self.db = SupabaseService()
        self.sheets = SheetsService(blueprint_path=blueprint_path)
        self.validator = SyncValidator()

    def run_sync(self, month_year: str):
        logger.info(f"Initiating Strict-Brand Sync for {month_year}")
        try:
            profiles = self.db.fetch_profiles()
            budgets = self.db.fetch_budgets(month_year)
            transactions = self.db.fetch_transactions(month_year)
            
            if not profiles:
                return {"status": "error", "message": "Profiles not found."}

            budget_map = {b["category_id"]: float(b.get("amount") or 0) for b in budgets}
            profile_daily_map = defaultdict(lambda: defaultdict(float))
            uncategorized_profile = {"id": "uncategorized", "name": "UNCATEGORIZED TRANSACTIONS", "default_category": {"account_type": "EXPENSE"}}
            has_uncategorized = False
            
            for t in transactions:
                p_id = t.get("profile_id")
                if not p_id:
                    p_id = "uncategorized"
                    has_uncategorized = True
                
                try:
                    date_str = t["date"]
                    # If the database returns a pure date (YYYY-MM-DD), use it literally to prevent time shifts
                    if len(date_str) == 10:
                        day_idx = int(date_str.split('-')[2])
                    else:
                        dt_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        # Ensure timezone awareness before conversion to prevent system-local fallback
                        if dt_utc.tzinfo is None:
                            dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
                        dt_local = dt_utc.astimezone(ZoneInfo("America/Belize"))
                        day_idx = dt_local.day
                except Exception as e:
                    logger.warning(f"Failed to parse date for transaction {t.get('id')}: {e}. Falling back to day 1.")
                    day_idx = 1
                
                profile_daily_map[p_id][day_idx] += abs(float(t.get("amount_signed") or 0))
            
            if has_uncategorized and not any(p["id"] == "uncategorized" for p in profiles):
                profiles.append(uncategorized_profile)

            row_data_list = []
            
            # Row 1: Title
            row_data_list.append({
                "values": [{
                    "userEnteredValue": {"stringValue": f"Cipher Money Hub | Budget: {month_year}"},
                    "userEnteredFormat": {
                        "backgroundColor": COLORS["bg_dark"],
                        "textFormat": {"fontSize": 14, "bold": True, "foregroundColor": COLORS["accent_cyan"]},
                        "horizontalAlignment": "LEFT"
                    }
                }]
            })
            
            # Row 2: Headers
            headers = ["Profile Name", "Planned", "Actual"] + [str(d) for d in range(1, 32)]
            row_data_list.append({
                "values": [{
                    "userEnteredValue": {"stringValue": h},
                    "userEnteredFormat": {
                        "backgroundColor": COLORS["bg_dark"],
                        "textFormat": {"bold": True, "foregroundColor": COLORS["accent_cyan"]},
                        "horizontalAlignment": "CENTER"
                    }
                } for h in headers]
            })

            sections = [
                {"label": "INCOME", "types": ["INCOME"], "bg": COLORS["income_bg"]},
                {"label": "EXPENSE", "types": ["EXPENSE", "LONG_TERM_LIAB"], "bg": COLORS["expense_bg"]},
                {"label": "SAVINGS", "types": ["CURRENT_ASSET", "EQUITY"], "bg": COLORS["savings_bg"]}
            ]
            
            section_totals = {}
            letters = ["D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z","AA","AB","AC","AD","AE","AF","AG","AH"]

            for sec in sections:
                label_name = sec["label"]
                sec_profiles = [p for p in profiles if (p.get("default_category") or {}).get("account_type") in sec["types"]]
                
                # Section Header
                row_data_list.append({
                    "values": [{
                        "userEnteredValue": {"stringValue": f"--- {label_name} ---"},
                        "userEnteredFormat": {
                            "backgroundColor": COLORS["section_hdr"],
                            "textFormat": {"bold": True, "foregroundColor": COLORS["accent_gold"]}
                        }
                    }]
                })
                
                start_idx = len(row_data_list) + 1
                for i, profile in enumerate(sec_profiles):
                    p_id = profile["id"]
                    row_color = COLORS["zebra_even"] if i % 2 == 0 else COLORS["zebra_odd"]
                    curr_row = len(row_data_list) + 1
                    
                    cells = [
                        {"userEnteredValue": {"stringValue": profile["name"]}, "userEnteredFormat": {"backgroundColor": row_color, "textFormat": {"foregroundColor": COLORS["text_white"]}}},
                        {"userEnteredValue": {"numberValue": budget_map.get(profile.get("default_category_id"), 0.0)}, "userEnteredFormat": {"backgroundColor": row_color, "numberFormat": {"type": "CURRENCY", "pattern": '[$BZ$]#,##0.00'}, "textFormat": {"foregroundColor": COLORS["text_white"]}}},
                        {"userEnteredValue": {"formulaValue": f"=SUM(D{curr_row}:AH{curr_row})"}, "userEnteredFormat": {"backgroundColor": row_color, "numberFormat": {"type": "CURRENCY", "pattern": '[$BZ$]#,##0.00'}, "textFormat": {"bold": True, "foregroundColor": COLORS["text_white"]}}}
                    ]
                    for day in range(1, 32):
                        val = profile_daily_map[p_id].get(day, 0.0)
                        cells.append({
                            "userEnteredValue": {"numberValue": val} if val != 0 else {"stringValue": ""},
                            "userEnteredFormat": {"backgroundColor": row_color, "numberFormat": {"type": "NUMBER", "pattern": '#,##0.00'}, "textFormat": {"foregroundColor": COLORS["text_muted"]}}
                        })
                    row_data_list.append({"values": cells})
                
                end_idx = len(row_data_list)
                total_row_idx = len(row_data_list) + 1
                section_totals[label_name] = total_row_idx
                
                # Safe SUM formula for section totals
                sum_b = f"=SUM(B{start_idx}:B{end_idx})" if start_idx <= end_idx else "=0"
                sum_c = f"=SUM(C{start_idx}:C{end_idx})" if start_idx <= end_idx else "=0"
                
                sub_cells = [
                    {"userEnteredValue": {"stringValue": f"TOTAL {label_name}"}, "userEnteredFormat": {"backgroundColor": COLORS["total_row"], "textFormat": {"bold": True, "foregroundColor": COLORS["accent_cyan"]}}},
                    {"userEnteredValue": {"formulaValue": sum_b}, "userEnteredFormat": {"backgroundColor": COLORS["total_row"], "numberFormat": {"type": "CURRENCY", "pattern": '[$BZ$]#,##0.00'}, "textFormat": {"bold": True, "foregroundColor": COLORS["accent_cyan"]}}},
                    {"userEnteredValue": {"formulaValue": sum_c}, "userEnteredFormat": {"backgroundColor": COLORS["total_row"], "numberFormat": {"type": "CURRENCY", "pattern": '[$BZ$]#,##0.00'}, "textFormat": {"bold": True, "foregroundColor": COLORS["accent_cyan"]}}}
                ]
                for l in letters:
                    sum_col = f"=SUM({l}{start_idx}:{l}{end_idx})" if start_idx <= end_idx else "=0"
                    sub_cells.append({"userEnteredValue": {"formulaValue": sum_col}, "userEnteredFormat": {"backgroundColor": COLORS["total_row"], "numberFormat": {"type": "NUMBER", "pattern": '#,##0.00'}, "textFormat": {"bold": True, "foregroundColor": COLORS["accent_cyan"]}}})
                
                row_data_list.append({"values": sub_cells})
                row_data_list.append({"values": []})

            # Grand Summary
            row_data_list.append({"values": [{"userEnteredValue": {"stringValue": "FINANCIAL PERFORMANCE SUMMARY"}, "userEnteredFormat": {"backgroundColor": COLORS["section_hdr"], "textFormat": {"bold": True, "foregroundColor": COLORS["accent_gold"]}}}]})
            
            for label, row_idx in [("TOTAL INCOME", section_totals.get("INCOME")), ("TOTAL EXPENSES", section_totals.get("EXPENSE")), ("TOTAL SAVINGS", section_totals.get("SAVINGS"))]:
                val_dict = {"formulaValue": f"=C{row_idx}"} if row_idx else {"numberValue": 0}
                row_data_list.append({"values": [
                    {"userEnteredValue": {"stringValue": label}, "userEnteredFormat": {"backgroundColor": COLORS["bg_dark"], "textFormat": {"foregroundColor": COLORS["text_white"]}}},
                    {"userEnteredValue": val_dict, "userEnteredFormat": {"backgroundColor": COLORS["bg_dark"], "numberFormat": {"type": "CURRENCY", "pattern": '[$BZ$]#,##0.00'}, "textFormat": {"bold": True, "foregroundColor": COLORS["text_white"]}}}
                ]})
            
            i_row = section_totals.get("INCOME")
            e_row = section_totals.get("EXPENSE")
            s_row = section_totals.get("SAVINGS")
            parts = []
            if i_row: parts.append(f"C{i_row}")
            if e_row: parts.append(f"-C{e_row}")
            if s_row: parts.append(f"-C{s_row}")
            net_formula = "=" + "".join(parts) if parts else "=0"
            if net_formula.startswith("=-"): net_formula = "=0" + net_formula[1:]
            
            row_data_list.append({"values": [
                {"userEnteredValue": {"stringValue": "NET POSITION (UNALLOCATED)"}, "userEnteredFormat": {"backgroundColor": COLORS["total_row"], "textFormat": {"bold": True, "foregroundColor": COLORS["accent_cyan"]}}},
                {"userEnteredValue": {"formulaValue": net_formula}, "userEnteredFormat": {"backgroundColor": COLORS["total_row"], "numberFormat": {"type": "CURRENCY", "pattern": '[$BZ$]#,##0.00'}, "textFormat": {"bold": True, "foregroundColor": COLORS["accent_cyan"]}}}
            ]})

            # Write values and formatting
            effective_title = f"ENTITY-{month_year}"
            sheet_props = self.sheets.ensure_sheet(effective_title)
            sheet_id = sheet_props["sheetId"]
            self.sheets.write_rows(sheet_id, row_data_list)
            
            # Additional Formatting (Theme, Freeze & Widths)
            self.sheets.batch_update([
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet_id},
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": COLORS["bg_dark"],
                                "textFormat": {"foregroundColor": COLORS["text_white"]}
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)"
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {
                                "frozenRowCount": 2,
                                "frozenColumnCount": 1
                            }
                        },
                        "fields": "gridProperties(frozenRowCount,frozenColumnCount)"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                        "properties": {"pixelSize": 200},
                        "fields": "pixelSize"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 3},
                        "properties": {"pixelSize": 90},
                        "fields": "pixelSize"
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 34},
                        "properties": {"pixelSize": 45},
                        "fields": "pixelSize"
                    }
                }
            ])
            
            logger.info(f"Brand Sync successful for {effective_title}")
            return {"status": "success", "month": month_year}

        except Exception as e:
            logger.error(f"Brand Sync failed: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    app = BudgetSyncApp()
    app.run_sync("2025-02")

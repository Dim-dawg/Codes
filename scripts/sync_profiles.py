import json
import sys
from datetime import datetime
from src.supabase_service import SupabaseService
from src.sheets_service import SheetsService
from src.config import config

def sync_profiles_to_sheet():
    print("[SYNC] Initiating Profile Summary Sync...")
    
    db = SupabaseService()
    sheets = SheetsService()
    
    try:
        profiles = db.fetch_profiles()
        print(f"[DATA] Found {len(profiles)} profiles.")
        
        headers = ["Profile Name", "Account Type", "Notes", "Last Updated"]
        values = [headers]
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for p in profiles:
            cat = p.get("default_category") or {}
            values.append([
                p.get("name", "Unknown"),
                cat.get("account_type", "EXPENSE"),
                p.get("notes", ""),
                now
            ])
            
        sheet_name = "Profile Summary"
        sheets.write_raw_values(sheet_name, values)
        
        print(f"[SUCCESS] Synced {len(values)-1} profiles to '{sheet_name}'.")
        return len(values) - 1
        
    except Exception as e:
        print(f"[ERROR] Sync failure: {str(e)}")
        raise e

if __name__ == "__main__":
    sync_profiles_to_sheet()

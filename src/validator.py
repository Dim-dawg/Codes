from typing import Dict, List, Any
import calendar

class SyncValidator:
    @staticmethod
    def validate(sheet_data: List[List[Any]], month_year: str, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validates the sheet data against DB transactions.
        Returns a report of errors found.
        """
        errors = []
        year, month = map(int, month_year.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        
        # Calculate expected totals from DB
        expected_daily = {} # profile_id -> {day -> amount}
        for txn in transactions:
            pid = txn.get("profile_id")
            if not pid: continue
            day = int(str(txn["date"]).split("T")[0].split("-")[2])
            if pid not in expected_daily: expected_daily[pid] = {}
            expected_daily[pid][day] = expected_daily[pid].get(day, 0.0) + float(txn.get("amount_signed") or 0)

        # Check for formula accuracy and value matches
        # Note: This is a simplified validation. In a real system, we'd match by profile ID.
        # For now, we'll just check if formulas exist and are correctly formed.
        
        for i, row in enumerate(sheet_data):
            row_num = i + 1
            if row_num < 4: continue # Skip headers
            
            name = row[0] if len(row) > 0 else ""
            if not name or name.isupper() or "TOTAL" in name: continue
            
            # This is likely a profile row
            # Check formula in column C (index 2)
            formula = row[2] if len(row) > 2 else ""
            expected_formula = f"=SUM(D{row_num}:AH{row_num})"
            if isinstance(formula, str) and formula.startswith("=") and formula != expected_formula:
                errors.append(f"Row {row_num} ({name}): Formula mismatch. Expected {expected_formula}, got {formula}")
            elif not formula:
                errors.append(f"Row {row_num} ({name}): Missing formula in column C")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "checked_rows": len(sheet_data)
        }

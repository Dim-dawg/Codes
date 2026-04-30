from datetime import datetime
from zoneinfo import ZoneInfo

BELIZE_TZ = ZoneInfo("America/Belize")

# -----------------------------
# 1. DATA FETCHERS (REAL SOURCES)
# -----------------------------

def fetch_supabase_transactions(supabase_client, start, end):
    """
    Pull raw truth from Supabase.
    MUST include ALL rows, no filtering beyond time window.
    """
    response = supabase_client.table("public.transactions") \
        .select("*") \
        .gte("date", start) \
        .lt("date", end) \
        .execute()

    return response.data


# -----------------------------
# 2. ENGINE SIMULATION LAYER
# -----------------------------

def run_engine(transactions):
    """
    Replicates sync_engine.py logic exactly.
    """

    profile_daily_map = {}
    processed_ids = set()

    for t in transactions:
        processed_ids.add(t["id"])

        # timezone canonicalization
        try:
            dt_utc = datetime.fromisoformat(t["date"].replace("Z", "+00:00"))
            dt_local = dt_utc.astimezone(BELIZE_TZ)
            day = dt_local.day
        except Exception:
            day = 1

        p_id = t.get("profile_id")
        if not p_id:
            p_id = "uncategorized"

        if p_id not in profile_daily_map:
            profile_daily_map[p_id] = {}

        profile_daily_map[p_id][day] = profile_daily_map[p_id].get(day, 0) + float(
            t.get("amount_signed") or 0
        )

    return {
        "processed_ids": processed_ids,
        "profile_daily_map": profile_daily_map
    }


# -----------------------------
# 3. SHEET LAYER LOADER
# -----------------------------

def load_sheet_data(sheet_rows):
    """
    Expect pre-exported sheet data (CSV or API dump).
    Must include transaction_id column.
    """
    ids = set()
    totals = 0
    profile_map = {}

    for row in sheet_rows:
        ids.add(row["transaction_id"])

        profile = row.get("profile_id", "uncategorized")
        amount = float(row.get("amount_signed", 0))

        profile_map[profile] = profile_map.get(profile, 0) + amount
        totals += amount

    return {
        "ids": ids,
        "totals": totals,
        "profile_map": profile_map
    }


# -----------------------------
# 4. RECONCILIATION TESTS
# -----------------------------

def test_row_consistency(db_ids, engine_ids, sheet_ids):
    return {
        "test": "row_consistency",
        "status": "PASS" if db_ids == engine_ids == sheet_ids else "FAIL",
        "missing_in_engine": list(db_ids - engine_ids),
        "missing_in_sheet": list(db_ids - sheet_ids),
        "extra_in_sheet": list(sheet_ids - db_ids),
    }


def test_financial_totals(db_total, engine_total, sheet_total):
    delta = abs(db_total - engine_total) + abs(db_total - sheet_total)

    return {
        "test": "financial_totals",
        "status": "PASS" if delta == 0 else "FAIL",
        "delta": delta
    }


def test_duplicate_ids(all_ids):
    seen = set()
    dupes = set()

    for i in all_ids:
        if i in seen:
            dupes.add(i)
        seen.add(i)

    return {
        "test": "duplicates",
        "status": "PASS" if len(dupes) == 0 else "FAIL",
        "duplicates": list(dupes)
    }


# -----------------------------
# 5. FINAL ORCHESTRATOR
# -----------------------------

def reconcile_month(supabase_client, sheet_rows, start, end):
    db = fetch_supabase_transactions(supabase_client, start, end)
    engine = run_engine(db)
    sheet = load_sheet_data(sheet_rows)

    db_ids = set(t["id"] for t in db)

    engine_ids = engine["processed_ids"]
    sheet_ids = sheet["ids"]

    db_total = sum(float(t.get("amount_signed") or 0) for t in db)
    engine_total = sum(sum(d.values()) for d in engine["profile_daily_map"].values())
    sheet_total = sheet["totals"]

    results = [
        test_row_consistency(db_ids, engine_ids, sheet_ids),
        test_financial_totals(db_total, engine_total, sheet_total),
        test_duplicate_ids(db_ids | engine_ids | sheet_ids),
    ]

    overall = "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL"

    return {
        "month": f"{start} -> {end}",
        "overall_status": overall,
        "tests": results,
        "db_total": db_total,
        "engine_total": engine_total,
        "sheet_total": sheet_total
    }

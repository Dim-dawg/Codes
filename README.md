# Budget Sheet Sync Service

A Python service that syncs budget data from Supabase to Google Sheets with dynamic formatting.

## Overview

This project synchronizes profile budgets and transaction data to a dynamically formatted Google Sheet. The sheet structure adapts automatically based on the number of days in each month.

## Features

- **Dynamic Sheet Structure**: Automatically adjusts columns and rows based on month length (28-31 days)
- **Flat Profile Layout**: Displays profiles directly under section headers (INCOME, EXPENSE, SAVINGS) with no category sub-headers
- **Automatic Calculations**: Generates SUM formulas for daily actuals and section totals
- **Smart Profile Filtering**: Only includes profiles that have transactions for the selected month
- **Google Sheets API Integration**: Batch updates for efficient formatting and data sync

## Prerequisites

- Python 3.10+
- Google Sheets API credentials (service account JSON)
- Supabase project with profiles, budgets, and transactions tables
- `.env` file with required environment variables

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate it:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create `.env` file with:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   GOOGLE_SHEET_ID=your_sheet_id
   GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
   ```

## Usage

Sync budget data for a specific month:

```bash
python sync_entity_budget.py month=2026-02
```

Output:
```json
{
  "ok": true,
  "worksheet_title": "ENTITY-2026-02",
  "worksheet_gid": 1349697541,
  "profiles": 13,
  "rows_written": 25,
  "unlinked_transactions": 0
}
```

- `worksheet_title`: The Google Sheet tab name (ENTITY-YYYY-MM)
- `worksheet_gid`: Google Sheets internal ID for the worksheet
- `profiles`: Number of profiles with transactions in this month
- `rows_written`: Total rows written to sheet (including headers, section totals, summary)
- `unlinked_transactions`: Count of transactions without a profile_id (orphaned transactions)

### Diagnostic: List Unlinked Transactions

List all unlinked (orphaned) transactions for a month:

```bash
python sync_entity_budget.py unlinked month=2026-02
```

Output:
```
Unlinked Transactions for 2026-02:
Date         Amount Type     Category             ID
------
2026-02-15   $150.00 expense Office Supplies      xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Use the transaction ID to trace the transaction in your Supabase database and either:
- Link it to a profile (set the `profile_id` field)
- Delete it if it's an error
- Update or investigate why it's orphaned

### Handling Unlinked Transactions

If `unlinked_transactions` is greater than 0, it means there are transactions in your Supabase database that are not linked to any profile. These transactions are:
- **Not displayed** on the budget sheet (no profile to associate with)
- **Not included** in any calculations
- **Tracked** and reported for visibility

To resolve unlinked transactions:
1. Log into your Supabase dashboard
2. Query the `transactions` table for rows with NULL `profile_id`
3. Either link them to a profile or delete them as appropriate
4. Re-run the sync to verify all transactions are now accounted for

## Architecture

- `sync_entity_budget.py`: Main sync orchestrator
- `DESIGN_BLUEPRINT.json`: Configuration for sheet formatting, colors, and structure
- `SHEET_SPECS.md`: Detailed specification of the budget sheet layout

## Recent Changes

- Simplified sheet structure to remove category sub-headers (flat profile list under sections)
- Dynamic month-based day calculation for flexible date ranges
- Profile filtering to show only those with transactions
- Unlinked transaction detection and diagnostic reporting

## Troubleshooting

### Unlinked Transactions Not Appearing on Sheet

**Issue:** Some transactions are missing from the budget sheet.

**Cause:** Transactions without a `profile_id` (unlinked transactions) cannot be displayed since they belong to no account.

**Solution:**
1. Run the diagnostic: `python sync_entity_budget.py unlinked month=2026-02`
2. For each transaction ID returned:
   - Log into Supabase → `transactions` table
   - Find the transaction by ID
   - Set the `profile_id` field to the appropriate profile
3. Re-run the sync: `python sync_entity_budget.py month=2026-02`

### Zero Profiles Appearing

**Cause:** The selected month has no transactions linked to any profiles.

**Symptom:** Output shows `"profiles": 0`

**Solution:**
- Check if transactions exist in Supabase for the month
- Verify transactions are linked to profiles (`profile_id` is not NULL)
- Use the diagnostic to find unlinked transactions

### Environment Variable Errors

**Issue:** `Missing required env var: SUPABASE_USER_ID`

**Solution:** Ensure your `.env` file includes all required variables:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_USER_ID=your_user_uuid
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account-key.json
```

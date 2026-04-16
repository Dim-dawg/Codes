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
  "rows_written": 25
}
```

## Architecture

- `sync_entity_budget.py`: Main sync orchestrator
- `DESIGN_BLUEPRINT.json`: Configuration for sheet formatting, colors, and structure
- `SHEET_SPECS.md`: Detailed specification of the budget sheet layout

## Recent Changes

- Simplified sheet structure to remove category sub-headers (flat profile list under sections)
- Dynamic month-based day calculation for flexible date ranges
- Profile filtering to show only those with transactions

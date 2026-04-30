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
- **Modular Architecture**: Clean separation of concerns between database, sheets, and formatting.

## Prerequisites

- Python 3.10+
- Google Sheets API credentials (service account JSON)
- Supabase project with required tables and views
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

4. Configure `.env` (see `.env.example` or legacy docs for details)

## Usage

Sync budget data for a specific month:

```bash
python sync_entity_budget.py month=2026-02
```

### Diagnostic: List Unlinked Transactions

List all unlinked (orphaned) transactions for a month:

```bash
python sync_entity_budget.py unlinked month=2026-02
```

## Architecture

The project has been refactored into a modular structure:

- `sync_entity_budget.py`: Main entry point.
- `src/`: Core logic modules.
  - `config.py`: Configuration and environment variables.
  - `supabase_service.py`: Supabase API interactions.
  - `sheets_service.py`: Google Sheets API interactions.
  - `sheets_formatting.py`: Spreadsheet layout and styling logic.
  - `models.py`: Data models and structures.
  - `utils.py`: Shared helper functions.
- `gs_reference/`: Legacy Google Apps Script source files for reference.
- `DESIGN_BLUEPRINT.json`: Configuration for sheet formatting, colors, and structure.
- `SHEET_SPECS.md`: Detailed specification of the budget sheet layout.

## Recent Changes

- **Code Cleanup**: Modularized the monolithic script into specialized services.
- **Improved Formatting**: Isolated layout logic into a dedicated module.
- **Enhanced Error Handling**: More robust environment variable validation and API error reporting.
- **File Organization**: Moved legacy reference files to a dedicated directory.

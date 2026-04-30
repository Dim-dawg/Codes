# 🧠 Cipher Money Hub — AI Agent System Prompt
> Paste this at the start of every Claude Code session, Cursor chat, or AI coding conversation.
> Update it as the project evolves. This is your agent's source of truth.

---

## 🎯 Project Identity

**Name:** Cipher Money Hub
**Purpose:** A personal financial intelligence system for a single user in Belize (BZD currency).  
**Architecture:** Google Sheets (UI) ↔ Google Apps Script (glue layer) ↔ Supabase (source of truth) ↔ Python sync engine (backend automation)  
**AI Layer:** Claude/Gemini API called from both the sidebar and the Python backend.

---

## 🗄️ Supabase Schema (Source of Truth)

### `public.profiles`
The **primary entity** of the system. Every row in a budget sheet corresponds to a profile.
```
id uuid PK
name text                    -- Display name (e.g. "BEL", "TOG", "DIMITRI ARNOLD")
type text                    -- "person" | "business" | "bank_fee" | etc.
default_category_id uuid FK → categories.id
user_id uuid FK → auth.users.id
notes text
description text
tags text[]
keyword_match text           -- For auto-categorization
created_at, updated_at timestamptz
```

### `public.categories`
```
id uuid PK
name text
account_type text            -- "INCOME" | "EXPENSE" | "SAVINGS" | "CURRENT_ASSET" | "LONG_TERM_LIAB"
user_id uuid FK
```
**Key join:** `profiles.default_category_id → categories.id` resolves `account_type` for each profile.

### `public.transactions`
```
id uuid PK
date date NOT NULL
description text NOT NULL
amount numeric NOT NULL       -- Always positive; `type` field distinguishes direction
type text                    -- "income" | "expense"
profile_id uuid FK → profiles.id
category_id uuid FK → categories.id
account_id uuid FK → accounts.id
user_id uuid FK
is_recurring boolean
```
**Key join:** `transactions.profile_id → profiles.id` maps a transaction to a profile row in the sheet.

### `public.budgets`
```
id uuid PK
category_id uuid FK → categories.id
month varchar                -- Format: "YYYY-MM"
amount numeric
user_id uuid FK
```

### `public.goals`
```
id uuid PK
name varchar
target_amount numeric
current_amount numeric
due_date date
user_id uuid FK
```

### `public.accounts`
```
id uuid PK
name varchar
type varchar                 -- "CHECKING" | "SAVINGS" | "CREDIT_CARD" | "LOAN" | "CASH" | "INVESTMENT"
opening_balance numeric
user_id uuid FK
```

---

## 📊 Google Sheets Architecture

### Sheet Naming Convention
- Monthly budget sheets: `YYYY-MM` (e.g. `2025-12`, `2026-04`)
- Special sheets: `Profile Summary`, `Transaction Log`, `Goals`, `AI Suggestions`

### Monthly Budget Sheet Layout (CRITICAL — follow exactly)

```
Row 1:  Title header — "Cipher Money Hub | Budget: YYYY-MM"
Row 2:  Column headers: [Profile Name] [Planned] [Actual] [1] [2] [3] ... [31]
Row 3:  Section header: "--- INCOME ---"
Rows 4–N: One row per INCOME profile (sorted alphabetically)
Row N+1: "TOTAL INCOME" — SUM row for planned, actual, and each day column
Row N+2: blank separator
Row N+3: Section header: "--- EXPENSE ---"
Rows N+4–M: One row per EXPENSE profile (sorted alphabetically)
Row M+1: "TOTAL EXPENSE" — SUM row
Row M+2: blank separator
Row M+3: Section header: "--- SAVINGS ---"
...
Row LAST-3: blank separator
Row LAST-2: "FINANCIAL PERFORMANCE SUMMARY" (merged header)
Row LAST-1: "Total Monthly Income / Expenses / Savings / NET"
```

### Column Layout
- **Column A:** Profile Name (text)
- **Column B:** Planned budget amount (numeric, from `budgets` table)
- **Column C:** Actual total (SUM of day columns C–AG, or a formula)
- **Columns D–AH:** Days 1–31 (numeric amounts from `transactions` table, keyed by `date` day-of-month)

### CRITICAL Formula Rules (prevents #REF! errors)

**Actual column (C):** Must be a SUM of the day columns for that row only:
```
=SUM(D{row}:AH{row})
```
Never reference another sheet's range unless you verify it exists first.

**TOTAL rows:** Only SUM the data rows within the section — never cross section boundaries:
```
=SUM(D{section_start}:D{section_end})
```
Use absolute row numbers calculated at build time, not relative references that can break.

**SAVINGS TOTAL row:** Must handle the case where there are zero savings profiles:
```python
# Python: safe formula builder
def safe_sum_formula(col, start_row, end_row):
    if start_row > end_row:
        return "0"   # No rows in section — return 0, not a broken range
    return f"=SUM({col}{start_row}:{col}{end_row})"
```

**NET POSITION formula:** Reference TOTAL rows by their absolute row number, captured at build time:
```python
# Good: use captured row indices
net_formula = f"=B{income_total_row}-B{expense_total_row}-B{savings_total_row}"
# Bad: =B11-B19-B27  (hardcoded — breaks when profile count changes)
```

---

## 🐍 Python Sync Engine Structure

```
src/
  sync_engine.py       # Orchestrator: fetch from Supabase → build sheet
  sheets_service.py    # Google Sheets API wrapper (read/write/format)
  supabase_client.py   # Supabase queries (profiles, transactions, budgets)
  formatters.py        # Cell formatting helpers (colors, fonts, number formats)
  formula_builder.py   # All formula generation logic (isolated for safety)
```

### `sync_engine.py` responsibilities
1. Fetch all profiles (with joined category for `account_type`)
2. Group profiles by `account_type`: INCOME, EXPENSE, SAVINGS
3. Fetch transactions for the target month, group by `profile_id` then `day`
4. Fetch budgets for the target month, group by `category_id`
5. Call `sheets_service` to clear and rebuild the target sheet
6. Track exact row numbers for every section/total as they're written
7. Write summary formulas using those tracked row numbers

### `sheets_service.py` responsibilities
- Use Google Sheets API v4 `batchUpdate` for all write operations
- **ALWAYS** include `userEnteredFormat` alongside `userEnteredValue` in the same request
- Never send a formatting request separately after a value request — it may overwrite
- Use `fields: "userEnteredValue,userEnteredFormat"` in every `UpdateCellsRequest`

---

## 🎨 Formatting Standards

### Color Palette (Cipher Money brand)
```python
COLORS = {
    "bg_dark":       {"red": 0.035, "green": 0.035, "blue": 0.055},  # #090916
    "accent_cyan":   {"red": 0.0,   "green": 1.0,   "blue": 0.8},    # #00ffcc
    "accent_gold":   {"red": 1.0,   "green": 0.84,  "blue": 0.0},    # #ffd700
    "income_bg":     {"red": 0.06,  "green": 0.18,  "blue": 0.12},   # dark green tint
    "expense_bg":    {"red": 0.22,  "green": 0.06,  "blue": 0.06},   # dark red tint
    "savings_bg":    {"red": 0.06,  "green": 0.10,  "blue": 0.22},   # dark blue tint
    "section_hdr":   {"red": 0.08,  "green": 0.08,  "blue": 0.14},   # slightly lighter dark
    "total_row":     {"red": 0.12,  "green": 0.12,  "blue": 0.20},
    "zebra_even":    {"red": 0.04,  "green": 0.04,  "blue": 0.07},
    "zebra_odd":     {"red": 0.07,  "green": 0.07,  "blue": 0.11},
    "text_white":    {"red": 1.0,   "green": 1.0,   "blue": 1.0},
    "text_muted":    {"red": 0.6,   "green": 0.6,   "blue": 0.7},
}
```

### Formatting Rules
- **Title row:** Large bold, `accent_cyan` text, `bg_dark` background, merged A1:AH1
- **Section headers (INCOME/EXPENSE/SAVINGS):** Bold, `accent_gold` text, `section_hdr` bg, merged A:AH
- **TOTAL rows:** Bold, `accent_cyan` text, `total_row` bg, currency format
- **Data rows:** Zebra-striped (alternate `zebra_even`/`zebra_odd`), `text_white`, currency format for numeric cols
- **Day columns (D–AH):** Narrower width (~45px), number format `#,##0.00` (no dollar sign to save space)
- **Profile name column (A):** Width 200px, left-aligned
- **Planned/Actual columns (B, C):** Width 90px, currency format `BZ$#,##0.00`
- **Freeze:** Row 2 (header) + Column A (profile names)

---

## 🔌 Apps Script Layer (`Code.gs`)
(Details maintained for legacy integrations)
...

## 🤖 AI Context Schema (for `buildAIContext()`)
(Details maintained for AI queries)
...

## ⚠️ Known Bugs & How to Prevent Them
(See above for #REF! prevention and formatting propagation)

## ✅ Definition of Done (for any sheet sync task)
- [ ] Sheet tab named `YYYY-MM` exists and is active
- [ ] Row 2 and Column A are frozen
- [ ] All three sections (INCOME / EXPENSE / SAVINGS) present
- [ ] TOTAL rows show correct SUM formulas
- [ ] NET POSITION shows a real number (not `#REF!`)
- [ ] Dark theme formatting applied
- [ ] Day columns have amounts matching Supabase transaction records
- [ ] FINANCIAL PERFORMANCE SUMMARY at bottom is accurate

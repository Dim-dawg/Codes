# 🧠 Cipher Money Hub — System Contract & Financial Core Definition
> This document is the immutable source of truth for the financial integrity, temporal logic, and data flow of the Cipher Money Hub.

---

### A. SYSTEM DEFINITION (FINAL VERSION)

**System Purpose:**  
The Cipher Money Hub is a deterministic, time-bound financial ledger and reporting engine designed to track, categorize, and visualize personal financial data for a single user in Belize.

**What the system is NOT allowed to do:**  
- Mutate, delete, or obscure raw transaction data retrieved from the bank/source.
- Perform any date-based filtering or grouping that relies on client-side timezones or naive UTC extraction.
- Apply implicit database joins that drop rows containing null relations (e.g., missing categories or profiles).

**Source of Truth Definition:**  
"Truth" is defined exclusively by the raw records stored in `public.transactions` within Supabase. Every downstream system (views, Python sync engine, Google Sheets) is strictly a read-only projection of this truth.

---

### B. DATA CONTRACT SPECIFICATION

**Data Truth Hierarchy:**
1. **Primary Truth (Layer 0):** `public.transactions` (PostgreSQL) — Immutable ledger of events.
2. **Enriched Truth (Layer 1):** `public.transaction_sheet_view` — Read-only join layer that strictly appends categorization/entity decisions without filtering underlying transactions.
3. **Aggregated Truth (Layer 2):** Python Sync Engine — Memory-safe transformation layer that enforces timezone canonicalization and UNCATEGORIZED bucketing.
4. **Presentation Truth (Layer 3):** Google Sheets — The visual rendering of Layer 2.

**Transformation Rules:**
- **Allowed:** Transforming UTC timestamps to Belize local time for grouping. Grouping transactions by Profile ID. Summing amounts by Day.
- **Forbidden:** Deleting rows. Filtering out "ignored" transactions in the API layer. Using `INNER JOIN` in any presentation view. 

*Rule: No derived layer is allowed to delete or mutate financial truth, only represent it.*

---

### C. TIME & MONTH RULE ENGINE

**Canonical Timezone:** `America/Belize` (UTC-6)
**Storage Timezone:** UTC (allowed ONLY for database persistence)
**Display & Grouping Timezone:** Belize ONLY

**Rules for Time Handling:**
1. **Month Boundaries:** Queries for a specific month must use exclusive upper bounds based on the 1st of the *following* month. 
   - *Example:* February 2025 data = `date >= 2025-02-01` AND `date < 2025-03-01`.
2. **Day Extraction:** Raw UTC timestamps must be parsed, converted to `ZoneInfo("America/Belize")`, and *then* the `.day`, `.month`, or `.year` properties can be extracted.
3. **Reporting Periods:** A "Month" is defined strictly as the period from the first millisecond of the 1st day of the month to the last millisecond of the last day of the month, evaluated in Belize local time.

*Explicitly Forbidden: Mixing UTC-derived grouping logic or performing `.lte.YYYY-MM-DD` truncation.*

---

### D. TRANSACTION LIFECYCLE MAP

**1. Ingestion:** Transaction hits `public.transactions`. Timestamp is recorded in UTC.
**2. Enrichment:** `transaction_sheet_view` attempts to `LEFT JOIN` profiles and categories. Missing relations yield `NULL`.
**3. Fetching:** Python backend queries the view using an exclusive upper-bound time filter (`.lt.{next_month}`). No transactions are dropped.
**4. Canonicalization:** Python parses ISO strings and converts every transaction to `America/Belize` time.
**5. Grouping:** Transactions are grouped by `profile_id`. If `profile_id` is `NULL`, it is forcefully bucketed into `UNCATEGORIZED TRANSACTIONS`.
**6. Rendering:** Grouped data is written to Google Sheets. The sum of the sheet mathematically guarantees to equal the sum of the raw DB query.

*Rule: A transaction must always exist in at least one visible aggregation bucket.*

---

### E. FORBIDDEN LOGIC LIST

The following anti-patterns are strictly banned from the codebase:
1. **Timezone-based month shifting:** Extracting `.day` or `.month` from a UTC timestamp without localizing it first.
2. **End-of-month truncation:** Using `<=` or `.lte` with a `YYYY-MM-DD` string on a timestamp column, which truncates data after `00:00:00`.
3. **Implicit Joins:** Using `INNER JOIN` or implicit comma-joins in views that could drop transactions lacking secondary metadata.
4. **Silent Loop Drops:** Using `if not value: continue` when iterating over financial data arrays. All edge cases must be bucketed and logged.
5. **Double Filtering:** Applying date filters in the DB query, and then applying them again in the Python or JS code.

---

### F. IMPLEMENTATION GUARDRAILS (CODE-LEVEL RULES)

1. **Python Date Handling Guardrail:**
   ```python
   # REQUIRED IMPLEMENTATION FOR ALL DATE PARSING
   from zoneinfo import ZoneInfo
   dt_utc = datetime.fromisoformat(t["date"].replace("Z", "+00:00"))
   dt_local = dt_utc.astimezone(ZoneInfo("America/Belize"))
   ```

2. **API Month Filtering Guardrail:**
   ```python
   # REQUIRED IMPLEMENTATION FOR MONTH API QUERIES
   next_month = int(month) + 1 if int(month) < 12 else 1
   next_year = int(year) if int(month) < 12 else int(year) + 1
   f"and=(date.gte.{year}-{month:02d}-01,date.lt.{next_year}-{next_month:02d}-01)"
   ```

3. **Missing Metadata Guardrail:**
   ```python
   # REQUIRED FALLBACK FOR MISSING PROFILES
   p_id = t.get("profile_id")
   if not p_id:
       p_id = "uncategorized" # Must map to a visible error bucket
   ```

4. **SQL Join Guardrail:**
   ```sql
   -- REQUIRED JOIN STRUCTURE FOR TRANSACTION VIEWS
   FROM public.transactions t
   LEFT JOIN public.categories c ON ...
   LEFT JOIN public.profiles p ON ...
   ```

---
*End of System Contract.*

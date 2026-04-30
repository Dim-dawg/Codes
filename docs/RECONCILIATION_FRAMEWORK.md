# 🧪 FINAL LEDGER RECONCILIATION TEST FRAMEWORK
> “Supabase vs Engine vs Sheets — deterministic financial truth verification”

---

## 🎯 OBJECTIVE
For any selected month(s), prove:
> Every single transaction in Supabase exists exactly once in:
1. Python aggregation output
2. Google Sheets output
3. With identical financial totals per profile and per month

If not:
> the system is classified as **financially inconsistent**

---

## 🧱 TEST ARCHITECTURE (3-LAYER RECONCILIATION)

### 🔵 LAYER 0 — RAW TRUTH (Supabase)
Source: `public.transactions`
This is the ONLY authority.

### 🟡 LAYER 1 — ENGINE OUTPUT (Python)
Source: `sync_engine.py` aggregated result
This includes:
* Belize timezone conversion
* grouping logic
* UNCATEGORIZED handling

### 🟢 LAYER 2 — PRESENTATION OUTPUT (Sheets)
Source: Google Sheets export
This is final UI truth.

---

## 🧪 TEST 1 — ROW-LEVEL ID RECONCILIATION (NO LOSS TEST)
**Pass Condition:** `Supabase IDs == Python IDs == Sheet IDs`
**Requirement:** No missing IDs, duplicates, or extra rows.

## 🧪 TEST 2 — FINANCIAL SUM RECONCILIATION
**Pass Condition:** `Supabase Net Total == Python Net Position == Sheets Net Position`
**Requirement:** 0.00 difference tolerance.

## 🧪 TEST 3 — PROFILE BREAKDOWN RECONCILIATION
**Pass Condition:** All rows match exactly per profile between DB, Engine, and Sheets.

## 🧪 TEST 4 — TIMEZONE CONSISTENCY STRESS TEST
**Pass Condition:** No transaction shifts months incorrectly. All mapping matches Belize-local interpretation.

## 🧪 TEST 5 — UNCATEGORIZED SAFETY TEST
**Pass Condition:** `COUNT(DB NULL profile_id rows) == COUNT(UNCATEGORIZED rows across all layers)`

## 🧪 TEST 6 — DUPLICATION DETECTION TEST
**Pass Condition:** NO duplicate transaction IDs in any layer.

## 🧪 TEST 7 — LOSSLESS PIPELINE CHECK
**Pass Condition:** `Loss = Supabase rows - (Python rows OR Sheet rows) == 0`

---
*Definition of Truthful System: Every transaction in Supabase can be traced through every layer without mutation, loss, or duplication. No exceptions.*

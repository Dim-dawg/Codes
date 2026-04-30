import argparse
import hashlib
import json
import os
import re
from typing import Any

import requests
from dotenv import load_dotenv


NOISE_RE = re.compile(
    r"\b(POS PURCHASE|VIA INTERNET BANKING|INTERNET BANKING|TRANSFER TO|TRANSFER FROM|RE:)\b",
    re.IGNORECASE,
)
LONG_NUMBER_RE = re.compile(r"[0-9]{6,}")
NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def headers() -> dict[str, str]:
    token = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or require_env("SUPABASE_ANON_KEY")
    return {
        "apikey": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def fetch_transactions(limit: int) -> list[dict[str, Any]]:
    base_url = require_env("SUPABASE_URL").rstrip("/")
    user_id = os.getenv("SUPABASE_USER_ID", "").strip()
    params = {
        "select": (
            "id,user_id,date,description,original_description,amount,type,"
            "account_id,document_id,debit_amount,credit_amount"
        ),
        "order": "date.desc,id.asc",
        "limit": str(limit),
    }
    if user_id:
        params["user_id"] = f"eq.{user_id}"

    response = requests.get(
        f"{base_url}/rest/v1/transactions",
        headers=headers(),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def normalize_description(description: str | None) -> str:
    text = (description or "").upper()
    text = NOISE_RE.sub(" ", text)
    text = LONG_NUMBER_RE.sub(" ", text)
    text = NON_ALNUM_RE.sub(" ", text)
    return " ".join(text.split())


def derive_amount_signed(row: dict[str, Any]) -> float:
    amount = float(row.get("amount") or 0)
    debit = float(row.get("debit_amount") or 0)
    credit = float(row.get("credit_amount") or 0)
    tx_type = str(row.get("type") or "").lower()

    if credit > 0 and debit == 0:
        return abs(credit)
    if debit > 0 and credit == 0:
        return -abs(debit)
    if tx_type == "income":
        return abs(amount)
    if tx_type == "expense":
        return -abs(amount)
    if amount < 0:
        return amount
    return abs(amount)


def derive_direction(amount_signed: float) -> str:
    return "out" if amount_signed < 0 else "in"


def dedupe_hash(row: dict[str, Any], normalized_description_value: str, amount_signed: float) -> str:
    parts = [
        str(row.get("user_id") or ""),
        str(row.get("account_id") or ""),
        str(row.get("source_transaction_id") or ""),
        str(row.get("document_id") or ""),
        str(row.get("date") or ""),
        normalized_description_value,
        str(amount_signed),
        str(row.get("type") or ""),
    ]
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


def normalized_projection(row: dict[str, Any]) -> dict[str, Any]:
    raw_description = row.get("original_description") or row.get("description")
    normalized = normalize_description(raw_description)
    signed = derive_amount_signed(row)
    return {
        "id": row["id"],
        "date": row["date"],
        "description_before": row.get("description"),
        "type_before": row.get("type"),
        "amount_before": row.get("amount"),
        "normalized_description_after": normalized,
        "amount_signed_after": signed,
        "direction_after": derive_direction(signed),
        "dedupe_hash_after": dedupe_hash(row, normalized, signed),
    }


def preview(limit: int) -> None:
    rows = fetch_transactions(limit)
    projections = [normalized_projection(row) for row in rows]
    valid_direction = sum(1 for row in projections if row["direction_after"] in {"in", "out"})
    pct = (valid_direction / len(projections) * 100) if projections else 0
    print(json.dumps({
        "rows_previewed": len(projections),
        "valid_direction_preview_count": valid_direction,
        "valid_direction_preview_percent": round(pct, 2),
        "sample": projections,
    }, indent=2))


def main() -> int:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Preview transaction normalization output.")
    parser.add_argument("command", choices=["preview"])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.command == "preview":
        preview(args.limit)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

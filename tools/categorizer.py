import argparse
import json
import os
from typing import Any

import psycopg
from dotenv import load_dotenv


def require_database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("Missing DATABASE_URL.")
    return value


def preview(limit: int) -> dict[str, Any]:
    sql = """
      with target_transactions as (
        select t.id, t.date, t.description, t.direction, t.category_id, c.name as current_category
        from public.transactions t
        join public.categories c on c.id = t.category_id
        order by t.date desc, t.id asc
        limit %s
      )
      select
        tt.id,
        tt.date,
        tt.description,
        tt.direction,
        tt.current_category as before_category,
        result.category_name as after_category,
        result.method,
        result.confidence,
        result.reason,
        result.priority
      from target_transactions tt
      cross join lateral public.categorize_transaction_v1(tt.id) result
      order by tt.date desc, tt.id asc;
    """
    with psycopg.connect(require_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            cols = [desc.name for desc in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

            cur.execute(
                """
                select count(*) as active_rules,
                       count(*) filter (where condition <> '{}'::jsonb) as condition_rules,
                       count(*) filter (where priority is not null) as priority_rules
                from public.rules
                where is_active;
                """
            )
            rule_cols = [desc.name for desc in cur.description]
            rule_metrics = dict(zip(rule_cols, cur.fetchone()))

    changed = sum(1 for row in rows if row["before_category"] != row["after_category"])
    return {
        "rows_evaluated": len(rows),
        "category_changes_proposed": changed,
        "rule_metrics": rule_metrics,
        "rows": rows,
    }


def main() -> int:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Run deterministic categorizer previews.")
    parser.add_argument("command", choices=["preview"])
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if args.command == "preview":
        print(json.dumps(preview(args.limit), default=str, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

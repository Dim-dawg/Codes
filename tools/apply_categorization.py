import argparse
import json
import os
import uuid
from typing import Any

import psycopg
from dotenv import load_dotenv


def require_database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("Missing DATABASE_URL.")
    return value


def apply_categorization(threshold: float) -> dict[str, Any]:
    run_id = uuid.uuid4()
    with psycopg.connect(require_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.transactions where lower(category) = 'uncategorized';")
            uncategorized_before = cur.fetchone()[0]

            cur.execute(
                """
                with results as (
                  select
                    %s::uuid as decision_run_id,
                    t.id as transaction_id,
                    t.category_id as previous_category_id,
                    t.entity_id,
                    p.rule_id,
                    p.category_id,
                    p.method,
                    p.confidence,
                    p.reason
                  from public.transactions t
                  cross join lateral public.categorize_transaction_v1(t.id) p
                ),
                inserted as (
                  insert into public.categorization_decisions (
                    decision_run_id,
                    transaction_id,
                    previous_category_id,
                    category_id,
                    rule_id,
                    entity_id,
                    method,
                    confidence,
                    reason,
                    applied
                  )
                  select
                    decision_run_id,
                    transaction_id,
                    previous_category_id,
                    category_id,
                    rule_id,
                    entity_id,
                    method,
                    confidence,
                    reason,
                    confidence >= %s and method <> 'fallback'
                  from results
                  returning id, transaction_id, previous_category_id, category_id, confidence, method, applied
                ),
                updated as (
                  update public.transactions t
                  set category_id = i.category_id,
                      updated_at = now()
                  from inserted i
                  where t.id = i.transaction_id
                    and i.applied
                    and t.category_id is distinct from i.category_id
                  returning t.id
                )
                select
                  (select count(*) from inserted) as decisions_inserted,
                  (select count(*) from inserted where applied) as high_confidence_decisions,
                  (select count(*) from updated) as transactions_updated;
                """,
                (str(run_id), threshold),
            )
            metrics = dict(zip([desc.name for desc in cur.description], cur.fetchone()))

            cur.execute("select count(*) from public.transactions where lower(category) = 'uncategorized';")
            uncategorized_after = cur.fetchone()[0]

            cur.execute(
                """
                select
                  d.id as decision_id,
                  t.id as transaction_id,
                  t.date,
                  t.description,
                  prev.name as previous_category,
                  new_cat.name as decided_category,
                  d.method,
                  d.confidence,
                  d.reason,
                  d.applied,
                  d.created_at
                from public.categorization_decisions d
                join public.transactions t on t.id = d.transaction_id
                left join public.categories prev on prev.id = d.previous_category_id
                join public.categories new_cat on new_cat.id = d.category_id
                where d.decision_run_id = %s
                order by d.applied desc, d.confidence desc, t.date desc
                limit 12;
                """,
                (str(run_id),),
            )
            sample = [dict(zip([desc.name for desc in cur.description], row)) for row in cur.fetchall()]

            cur.execute(
                """
                select
                  t.id,
                  t.date,
                  t.description as raw_description,
                  t.normalized_description,
                  t.amount,
                  t.amount_signed,
                  t.direction,
                  e.canonical_name as entity,
                  prev.name as previous_category,
                  final.name as current_category,
                  d.method,
                  d.confidence,
                  d.reason,
                  d.applied
                from public.categorization_decisions d
                join public.transactions t on t.id = d.transaction_id
                left join public.entities e on e.id = d.entity_id
                left join public.categories prev on prev.id = d.previous_category_id
                join public.categories final on final.id = t.category_id
                where d.decision_run_id = %s
                  and d.applied
                  and d.previous_category_id is distinct from d.category_id
                order by d.confidence desc, t.date desc
                limit 1;
                """,
                (str(run_id),),
            )
            trace_cols = [desc.name for desc in cur.description]
            trace_row = cur.fetchone()
            trace = dict(zip(trace_cols, trace_row)) if trace_row else None

        conn.commit()

    return {
        "decision_run_id": str(run_id),
        "threshold": threshold,
        "uncategorized_before": uncategorized_before,
        "uncategorized_after": uncategorized_after,
        **metrics,
        "sample_decisions": sample,
        "trace": trace,
    }


def main() -> int:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Log and apply deterministic categorization decisions.")
    parser.add_argument("command", choices=["apply"])
    parser.add_argument("--threshold", type=float, default=0.80)
    args = parser.parse_args()

    if args.command == "apply":
        print(json.dumps(apply_categorization(args.threshold), default=str, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

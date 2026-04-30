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


def route(threshold: float) -> dict[str, Any]:
    with psycopg.connect(require_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) from public.reclassification_proposals;")
            proposals_before = cur.fetchone()[0]

            cur.execute(
                """
                with latest_decisions as (
                  select distinct on (d.transaction_id)
                    d.id as decision_id,
                    d.transaction_id,
                    d.previous_category_id,
                    d.category_id,
                    d.method,
                    d.confidence,
                    d.reason,
                    d.rule_id,
                    d.created_at
                  from public.categorization_decisions d
                  order by d.transaction_id, d.created_at desc
                ),
                candidates as (
                  select
                    ld.*,
                    t.user_id,
                    current_cat.name as current_category,
                    proposed_cat.name as proposed_category,
                    r.keyword as rule_keyword
                  from latest_decisions ld
                  join public.transactions t on t.id = ld.transaction_id
                  left join public.categories current_cat on current_cat.id = ld.previous_category_id
                  join public.categories proposed_cat on proposed_cat.id = ld.category_id
                  left join public.rules r on r.id = ld.rule_id
                  where ld.confidence < %s
                ),
                inserted as (
                  insert into public.reclassification_proposals (
                    transaction_id,
                    current_category_id,
                    current_category,
                    proposed_category_id,
                    proposed_category,
                    rule_keyword,
                    confidence,
                    strong_match,
                    reason,
                    status,
                    user_id,
                    decision_id
                  )
                  select
                    transaction_id,
                    previous_category_id,
                    current_category,
                    category_id,
                    proposed_category,
                    rule_keyword,
                    confidence::double precision,
                    false,
                    reason,
                    'pending',
                    user_id,
                    decision_id
                  from candidates
                  on conflict (transaction_id) where status = 'pending'
                  do nothing
                  returning id
                )
                select
                  (select count(*) from candidates) as low_confidence_candidates,
                  (select count(*) from inserted) as proposals_inserted;
                """,
                (threshold,),
            )
            metrics = dict(zip([desc.name for desc in cur.description], cur.fetchone()))

            cur.execute("select count(*) from public.reclassification_proposals;")
            proposals_after = cur.fetchone()[0]

            cur.execute(
                """
                select
                  rp.id,
                  t.date,
                  t.description,
                  rp.current_category,
                  rp.proposed_category,
                  rp.confidence,
                  rp.reason,
                  rp.status,
                  rp.created_at
                from public.reclassification_proposals rp
                join public.transactions t on t.id = rp.transaction_id
                where rp.status = 'pending'
                order by rp.confidence asc, rp.created_at desc
                limit 12;
                """
            )
            sample = [dict(zip([desc.name for desc in cur.description], row)) for row in cur.fetchall()]

            cur.execute(
                """
                select id
                from public.reclassification_proposals
                where status = 'pending'
                order by confidence asc, created_at desc
                limit 1;
                """
            )
            workflow_id = cur.fetchone()
            workflow = None
            if workflow_id:
                proposal_id = workflow_id[0]
                cur.execute(
                    """
                    select id, status, reviewed_at
                    from public.reclassification_proposals
                    where id = %s;
                    """,
                    (proposal_id,),
                )
                before = dict(zip([desc.name for desc in cur.description], cur.fetchone()))

                cur.execute(
                    """
                    update public.reclassification_proposals
                    set status = 'rejected',
                        reviewed_at = now(),
                        review_note = 'Validation workflow state change: rejected low-confidence fallback.'
                    where id = %s
                    returning id, status, reviewed_at, review_note;
                    """,
                    (proposal_id,),
                )
                after = dict(zip([desc.name for desc in cur.description], cur.fetchone()))
                workflow = {"before": before, "after": after}

        conn.commit()

    return {
        "threshold": threshold,
        "proposals_before": proposals_before,
        "proposals_after": proposals_after,
        **metrics,
        "sample_pending": sample,
        "workflow_state_change": workflow,
    }


def main() -> int:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Route low-confidence categorizations to review.")
    parser.add_argument("command", choices=["route"])
    parser.add_argument("--threshold", type=float, default=0.80)
    args = parser.parse_args()

    if args.command == "route":
        print(json.dumps(route(args.threshold), default=str, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

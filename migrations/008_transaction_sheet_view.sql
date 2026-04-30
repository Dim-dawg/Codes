-- Frontend source-of-truth view.
-- This is a read-only presentation layer over transactions + latest decisions.

create or replace view public.transaction_sheet_view as
with latest_decision as (
  select distinct on (d.transaction_id)
    d.id as decision_id,
    d.transaction_id,
    d.category_id,
    d.rule_id,
    d.entity_id,
    d.method,
    d.confidence,
    d.reason,
    d.applied,
    d.created_at
  from public.categorization_decisions d
  order by d.transaction_id, d.created_at desc, d.id desc
),
pending_review as (
  select distinct on (rp.transaction_id)
    rp.transaction_id,
    rp.id as review_proposal_id,
    rp.status as review_status,
    rp.created_at as review_created_at
  from public.reclassification_proposals rp
  order by rp.transaction_id, rp.created_at desc, rp.id desc
)
select
  t.id,
  t.user_id,
  t.account_id,
  t.profile_id,
  coalesce(ld.entity_id, t.entity_id) as entity_id,
  e.canonical_name as entity_name,
  t.date,
  t.description,
  t.original_description,
  t.normalized_description,
  t.amount,
  t.amount_signed,
  t.direction,
  t.type as legacy_type,
  ld.decision_id,
  ld.category_id,
  c.name as category_name,
  c.account_type as category_account_type,
  ld.method as category_method,
  ld.confidence as confidence_score,
  case
    when ld.confidence >= 0.85 then 'high'
    when ld.confidence >= 0.60 then 'medium'
    when ld.confidence is not null then 'low'
    else 'missing'
  end as confidence_band,
  ld.reason as decision_reason,
  ld.created_at as decision_created_at,
  coalesce(ld.applied, false) as decision_applied,
  pr.review_proposal_id,
  coalesce(pr.review_status, case when ld.confidence < 0.80 then 'pending' else 'none' end) as review_status,
  pr.review_created_at
from public.transactions t
left join latest_decision ld
  on ld.transaction_id = t.id
left join public.categories c
  on c.id = ld.category_id
left join public.entities e
  on e.id = coalesce(ld.entity_id, t.entity_id)
left join pending_review pr
  on pr.transaction_id = t.id;

comment on view public.transaction_sheet_view is
  'Frontend read model: transaction rows enriched with latest categorization decision, category, confidence, method, reason, entity, and review state. Does not read transactions.category.';

notify pgrst, 'reload schema';

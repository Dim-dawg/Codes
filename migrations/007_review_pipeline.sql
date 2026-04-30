-- Step 7: Activate review pipeline using reclassification_proposals.

alter table public.reclassification_proposals
  add column if not exists decision_id uuid references public.categorization_decisions(id) on delete set null,
  add column if not exists reviewed_at timestamp with time zone,
  add column if not exists review_note text;

update public.reclassification_proposals
set status = lower(status)
where status is not null;

alter table public.reclassification_proposals
  alter column status set default 'pending';

alter table public.reclassification_proposals
  drop constraint if exists reclassification_proposals_status_check;

alter table public.reclassification_proposals
  add constraint reclassification_proposals_status_check
  check (status in ('pending', 'approved', 'rejected'));

create unique index if not exists reclassification_proposals_one_pending_per_tx_idx
  on public.reclassification_proposals (transaction_id)
  where status = 'pending';

create index if not exists reclassification_proposals_status_created_idx
  on public.reclassification_proposals (status, created_at desc);

-- Step 6: Append-only categorization decision log.

create table if not exists public.categorization_decisions (
  id uuid primary key default gen_random_uuid(),
  decision_run_id uuid not null default gen_random_uuid(),
  transaction_id uuid not null references public.transactions(id) on delete cascade,
  previous_category_id uuid references public.categories(id),
  category_id uuid not null references public.categories(id),
  rule_id uuid references public.rules(id),
  entity_id uuid references public.entities(id),
  method text not null,
  confidence numeric not null,
  reason text not null,
  applied boolean not null default false,
  created_at timestamp with time zone not null default now()
);

create index if not exists categorization_decisions_transaction_created_idx
  on public.categorization_decisions (transaction_id, created_at desc);

create index if not exists categorization_decisions_run_idx
  on public.categorization_decisions (decision_run_id);

create index if not exists categorization_decisions_method_confidence_idx
  on public.categorization_decisions (method, confidence);

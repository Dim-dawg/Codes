-- Step 5: Entity resolution v1.

create table if not exists public.entities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  canonical_name text not null,
  entity_type text not null default 'merchant',
  default_category_id uuid references public.categories(id),
  default_confidence numeric not null default 0.72,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

create unique index if not exists entities_user_canonical_name_idx
  on public.entities (user_id, canonical_name);

create table if not exists public.entity_aliases (
  id uuid primary key default gen_random_uuid(),
  entity_id uuid not null references public.entities(id) on delete cascade,
  user_id uuid not null references auth.users(id),
  alias text not null,
  normalized_alias text not null,
  source text not null default 'detected',
  confidence numeric not null default 0.80,
  created_at timestamp with time zone default now()
);

create unique index if not exists entity_aliases_user_normalized_alias_idx
  on public.entity_aliases (user_id, normalized_alias);

alter table public.transactions
  add column if not exists entity_id uuid references public.entities(id);

alter table public.rules
  add column if not exists entity_id uuid references public.entities(id);

with user_scope as (
  select distinct user_id from public.transactions
),
category_ids as (
  select
    user_id,
    max(id::text) filter (where name = 'Payroll')::uuid as payroll_id,
    max(id::text) filter (where name = 'Office Supplies')::uuid as office_supplies_id,
    max(id::text) filter (where name = 'Withdrawal')::uuid as withdrawal_id
  from public.categories
  group by user_id
),
seed_entities as (
  select u.user_id, 'GARESHA JONES'::text as canonical_name, 'person'::text as entity_type, c.payroll_id as default_category_id, 0.78::numeric as default_confidence
  from user_scope u join category_ids c using (user_id)
  union all
  select u.user_id, 'CHUN S YA AX NAH ENTERPRISE', 'merchant', c.office_supplies_id, 0.82
  from user_scope u join category_ids c using (user_id)
  union all
  select u.user_id, 'ATM ALBERT ST', 'atm', c.withdrawal_id, 0.88
  from user_scope u join category_ids c using (user_id)
  union all
  select u.user_id, 'WINGS AND FEATHERS', 'merchant', null::uuid, 0.55
  from user_scope u
)
insert into public.entities (
  user_id,
  canonical_name,
  entity_type,
  default_category_id,
  default_confidence
)
select user_id, canonical_name, entity_type, default_category_id, default_confidence
from seed_entities
where not exists (
  select 1
  from public.entities e
  where e.user_id = seed_entities.user_id
    and e.canonical_name = seed_entities.canonical_name
);

with aliases as (
  select e.id as entity_id, e.user_id, alias, normalized_alias, source, confidence
  from public.entities e
  cross join lateral (
    values
      ('GARESHA JONES', 'GARESHA JONES', 'detected_profile_and_transaction', 0.88::numeric),
      ('TPT MS GARESHA JONES', 'TPT MS GARESHA JONES', 'detected_transaction', 0.86),
      ('MS GARESHA JONES', 'MS GARESHA JONES', 'detected_profile', 0.82)
  ) a(alias, normalized_alias, source, confidence)
  where e.canonical_name = 'GARESHA JONES'

  union all

  select e.id, e.user_id, alias, normalized_alias, source, confidence
  from public.entities e
  cross join lateral (
    values
      ('CHUN S YA AX NAH', 'CHUN S YA AX NAH', 'detected_transaction_cluster', 0.90::numeric),
      ('CHUN S YA AX NAH ENTERPRI', 'CHUN S YA AX NAH ENTERPRI', 'detected_profile_and_transaction', 0.88),
      ('CHUN S YA AX NAH ENTERPRISE CAYO', 'CHUN S YA AX NAH ENTERPRISE CAYO', 'detected_transaction', 0.84)
  ) a(alias, normalized_alias, source, confidence)
  where e.canonical_name = 'CHUN S YA AX NAH ENTERPRISE'

  union all

  select e.id, e.user_id, alias, normalized_alias, source, confidence
  from public.entities e
  cross join lateral (
    values
      ('ATM ALBERT ST', 'ATM ALBERT ST', 'detected_transaction_cluster', 0.90::numeric),
      ('ATM ALBERT ST BELIZE BZ', 'ATM ALBERT ST BELIZE BZ', 'detected_transaction', 0.88),
      ('4A ALBERT ST BELIZE CIT', '4A ALBERT ST BELIZE CIT', 'detected_profile_and_transaction', 0.78)
  ) a(alias, normalized_alias, source, confidence)
  where e.canonical_name = 'ATM ALBERT ST'

  union all

  select e.id, e.user_id, alias, normalized_alias, source, confidence
  from public.entities e
  cross join lateral (
    values
      ('WINGS AND FEATHERS', 'WINGS AND FEATHERS', 'detected_profile', 0.84::numeric),
      ('WINGS AND FEATHERS LTD', 'WINGS AND FEATHERS LTD', 'detected_profile_and_transaction', 0.82)
  ) a(alias, normalized_alias, source, confidence)
  where e.canonical_name = 'WINGS AND FEATHERS'
)
insert into public.entity_aliases (
  entity_id,
  user_id,
  alias,
  normalized_alias,
  source,
  confidence
)
select entity_id, user_id, alias, normalized_alias, source, confidence
from aliases
where not exists (
  select 1
  from public.entity_aliases existing
  where existing.user_id = aliases.user_id
    and existing.normalized_alias = aliases.normalized_alias
);

with matches as (
  select
    t.id as transaction_id,
    ea.entity_id,
    row_number() over (
      partition by t.id
      order by length(ea.normalized_alias) desc, ea.confidence desc
    ) as rn
  from public.transactions t
  join public.entity_aliases ea
    on ea.user_id = t.user_id
   and t.normalized_description like '%' || ea.normalized_alias || '%'
)
update public.transactions t
set entity_id = m.entity_id,
    updated_at = now()
from matches m
where t.id = m.transaction_id
  and m.rn = 1;

create or replace function public.categorize_transaction_v1(p_transaction_id uuid)
returns table (
  transaction_id uuid,
  rule_id uuid,
  category_id uuid,
  category_name text,
  confidence numeric,
  method text,
  reason text,
  priority integer
)
language plpgsql
stable
as $$
begin
  return query
  select
    t.id as transaction_id,
    r.id as rule_id,
    r.target_category_id as category_id,
    c.name as category_name,
    r.confidence,
    'rule'::text as method,
    coalesce(r.reason, 'Matched rule: ' || r.keyword) as reason,
    r.priority
  from public.transactions t
  join public.rules r
    on r.user_id = t.user_id
   and r.is_active
   and (r.entity_id is null or r.entity_id = t.entity_id)
   and (r.direction is null or r.direction = t.direction)
   and public.rule_condition_matches(t.normalized_description, r.condition)
  join public.categories c
    on c.id = r.target_category_id
  where t.id = p_transaction_id
  order by r.priority desc, r.updated_at desc, r.created_at desc
  limit 1;

  if found then
    return;
  end if;

  return query
  select
    t.id as transaction_id,
    null::uuid as rule_id,
    c.id as category_id,
    c.name as category_name,
    e.default_confidence as confidence,
    'entity_default'::text as method,
    'Matched resolved entity default: ' || e.canonical_name as reason,
    10::integer as priority
  from public.transactions t
  join public.entities e
    on e.id = t.entity_id
  join public.categories c
    on c.id = e.default_category_id
  where t.id = p_transaction_id
    and e.default_category_id is not null
    and (
      (t.direction = 'in' and upper(c.account_type) = 'INCOME')
      or (t.direction = 'out' and upper(c.account_type) <> 'INCOME')
    )
  limit 1;

  if found then
    return;
  end if;

  return query
  select
    t.id as transaction_id,
    null::uuid as rule_id,
    c.id as category_id,
    c.name as category_name,
    0.20::numeric as confidence,
    'fallback'::text as method,
    'No active rule or entity default matched'::text as reason,
    0::integer as priority
  from public.transactions t
  join public.categories c
    on c.user_id = t.user_id
   and lower(c.name) = 'uncategorized'
  where t.id = p_transaction_id
  limit 1;
end;
$$;

create index if not exists transactions_entity_id_idx
  on public.transactions (entity_id);

create index if not exists rules_entity_id_idx
  on public.rules (entity_id)
  where entity_id is not null;

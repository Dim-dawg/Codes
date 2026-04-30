-- Step 4: Rule engine v1.

alter table public.rules
  add column if not exists priority integer not null default 100,
  add column if not exists condition jsonb not null default '{}'::jsonb,
  add column if not exists direction text,
  add column if not exists is_active boolean not null default true,
  add column if not exists confidence numeric not null default 0.85,
  add column if not exists reason text;

alter table public.rules
  drop constraint if exists rules_direction_check;

alter table public.rules
  add constraint rules_direction_check
  check (direction is null or direction in ('in', 'out'));

update public.rules
set
  priority = coalesce(priority, 100),
  condition = case
    when condition = '{}'::jsonb and keyword is not null
      then jsonb_build_object('description_any', jsonb_build_array(upper(keyword)))
    else condition
  end,
  direction = coalesce(direction, case when upper(target_type) = 'EXPENSE' then 'out' else null end),
  confidence = coalesce(confidence, 0.85),
  reason = coalesce(reason, 'Matched legacy keyword rule: ' || keyword),
  is_active = coalesce(is_active, true);

create or replace function public.rule_condition_matches(
  p_normalized_description text,
  p_condition jsonb
)
returns boolean
language sql
immutable
as $$
  select
    (
      not (coalesce(p_condition, '{}'::jsonb) ? 'description_any')
      or exists (
        select 1
        from jsonb_array_elements_text(coalesce(p_condition, '{}'::jsonb) -> 'description_any') term
        where upper(coalesce(p_normalized_description, '')) like '%' || upper(term) || '%'
      )
    )
    and (
      not (coalesce(p_condition, '{}'::jsonb) ? 'description_all')
      or not exists (
        select 1
        from jsonb_array_elements_text(coalesce(p_condition, '{}'::jsonb) -> 'description_all') term
        where upper(coalesce(p_normalized_description, '')) not like '%' || upper(term) || '%'
      )
    )
    and (
      not (coalesce(p_condition, '{}'::jsonb) ? 'description_not_any')
      or not exists (
        select 1
        from jsonb_array_elements_text(coalesce(p_condition, '{}'::jsonb) -> 'description_not_any') term
        where upper(coalesce(p_normalized_description, '')) like '%' || upper(term) || '%'
      )
    );
$$;

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
    0.20::numeric as confidence,
    'fallback'::text as method,
    'No active rule matched'::text as reason,
    0::integer as priority
  from public.transactions t
  join public.categories c
    on c.user_id = t.user_id
   and lower(c.name) = 'uncategorized'
  where t.id = p_transaction_id
  limit 1;
end;
$$;

with category_ids as (
  select
    user_id,
    max(id::text) filter (where name = 'Withdrawal')::uuid as withdrawal_id,
    max(id::text) filter (where name = 'Payroll Income')::uuid as payroll_income_id,
    max(id::text) filter (where name = 'Bank Fees')::uuid as bank_fees_id,
    max(id::text) filter (where name = 'Transfers')::uuid as transfers_id
  from public.categories
  group by user_id
)
insert into public.rules (
  keyword,
  target_category_id,
  user_id,
  target_type,
  priority,
  condition,
  direction,
  is_active,
  confidence,
  reason
)
select *
from (
  select
    'atm_withdrawal_v1'::text as keyword,
    withdrawal_id as target_category_id,
    user_id,
    'EXPENSE'::text as target_type,
    320 as priority,
    '{"description_any":["ATM","WITHDRAWL","WITHDRAWAL"],"description_not_any":["FEE","CHARGE","CHRG","SERVICE CHARGE"]}'::jsonb as condition,
    'out'::text as direction,
    true as is_active,
    0.92::numeric as confidence,
    'ATM withdrawal keywords with outgoing direction and no fee terms'::text as reason
  from category_ids
  where withdrawal_id is not null

  union all

  select
    'salary_payroll_income_v1',
    payroll_income_id,
    user_id,
    'INCOME',
    330,
    '{"description_any":["SALARY","PAYROLL","E SALARY"]}'::jsonb,
    'in',
    true,
    0.94,
    'Salary or payroll keyword with incoming direction'
  from category_ids
  where payroll_income_id is not null

  union all

  select
    'bank_fee_v1',
    bank_fees_id,
    user_id,
    'EXPENSE',
    340,
    '{"description_any":["SERVICE CHARGE","SERV CHARGE","FEE","CHRG","TRF CHAR","OVERDRAFT INTEREST","MIN BALANCE CHARGE"]}'::jsonb,
    'out',
    true,
    0.93,
    'Bank fee keyword with outgoing direction'
  from category_ids
  where bank_fees_id is not null

  union all

  select
    'transfer_basic_v1',
    transfers_id,
    user_id,
    'TRANSFER',
    120,
    '{"description_any":["TRANSFER","TRF","IFT"]}'::jsonb,
    null,
    true,
    0.68,
    'Basic transfer keyword match'
  from category_ids
  where transfers_id is not null
) rules_to_insert
where not exists (
  select 1
  from public.rules r
  where r.user_id = rules_to_insert.user_id
    and r.keyword = rules_to_insert.keyword
);

create index if not exists rules_user_active_priority_idx
  on public.rules (user_id, is_active, priority desc);

create index if not exists rules_condition_gin_idx
  on public.rules using gin (condition);

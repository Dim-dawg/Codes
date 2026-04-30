-- Step 2: Backfill account context.
-- Only assign account_id when a user has exactly one account.

with one_account_per_user as (
  select user_id, (array_agg(id order by created_at, id::text))[1] as account_id
  from public.accounts
  group by user_id
  having count(*) = 1
)
update public.transactions t
set account_id = a.account_id,
    updated_at = now()
from one_account_per_user a
where t.user_id = a.user_id
  and t.account_id is null;

-- account_id participates in dedupe_hash, so recompute after backfill.
update public.transactions
set dedupe_hash = md5(
  concat_ws(
    '|',
    coalesce(user_id::text, ''),
    coalesce(account_id::text, ''),
    coalesce(source_transaction_id, ''),
    coalesce(document_id, ''),
    coalesce(date::text, ''),
    coalesce(normalized_description, ''),
    coalesce(amount_signed::text, ''),
    coalesce(type, '')
  )
)
where dedupe_hash is not null;

create index if not exists transactions_account_id_idx
  on public.transactions (account_id);

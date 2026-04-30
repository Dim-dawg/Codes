-- Step 1: Transaction normalization foundation.
-- Apply with a SQL-capable Supabase/Postgres connection.

alter table public.transactions
  add column if not exists normalized_description text,
  add column if not exists amount_signed numeric,
  add column if not exists direction text,
  add column if not exists dedupe_hash text,
  add column if not exists source_transaction_id text;

alter table public.transactions
  drop constraint if exists transactions_direction_check;

alter table public.transactions
  add constraint transactions_direction_check
  check (direction is null or direction in ('in', 'out'));

update public.transactions
set
  normalized_description =
    nullif(
      trim(
        regexp_replace(
          regexp_replace(
            regexp_replace(
              upper(coalesce(original_description, description, '')),
              '(POS PURCHASE|VIA INTERNET BANKING|INTERNET BANKING|TRANSFER TO|TRANSFER FROM|RE:)',
              ' ',
              'g'
            ),
            '[0-9]{6,}',
            ' ',
            'g'
          ),
          '[^A-Z0-9]+',
          ' ',
          'g'
        )
      ),
      ''
    ),
  amount_signed =
    case
      when coalesce(credit_amount, 0) > 0 and coalesce(debit_amount, 0) = 0
        then abs(credit_amount)
      when coalesce(debit_amount, 0) > 0 and coalesce(credit_amount, 0) = 0
        then -abs(debit_amount)
      when lower(type) = 'income'
        then abs(amount)
      when lower(type) = 'expense'
        then -abs(amount)
      when amount < 0
        then amount
      else abs(amount)
    end,
  direction =
    case
      when coalesce(credit_amount, 0) > 0 and coalesce(debit_amount, 0) = 0
        then 'in'
      when coalesce(debit_amount, 0) > 0 and coalesce(credit_amount, 0) = 0
        then 'out'
      when lower(type) = 'income'
        then 'in'
      when lower(type) = 'expense'
        then 'out'
      when amount < 0
        then 'out'
      else 'in'
    end,
  source_transaction_id = source_transaction_id;

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
);

create index if not exists transactions_normalized_description_idx
  on public.transactions (normalized_description);

create index if not exists transactions_direction_idx
  on public.transactions (direction);

create index if not exists transactions_dedupe_hash_idx
  on public.transactions (dedupe_hash);

create index if not exists transactions_source_transaction_id_idx
  on public.transactions (source_transaction_id)
  where source_transaction_id is not null;

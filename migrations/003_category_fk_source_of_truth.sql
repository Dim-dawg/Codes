-- Step 3: category_id is the source of truth.
-- Keep transactions.category as a legacy read-through cache only.

update public.transactions t
set category = c.name,
    updated_at = now()
from public.categories c
where t.category_id = c.id
  and t.category is distinct from c.name;

create or replace function public.set_transaction_category_cache()
returns trigger
language plpgsql
as $$
begin
  select c.name
    into new.category
  from public.categories c
  where c.id = new.category_id;

  return new;
end;
$$;

drop trigger if exists set_transaction_category_cache_trigger on public.transactions;

create trigger set_transaction_category_cache_trigger
before insert or update of category_id
on public.transactions
for each row
execute function public.set_transaction_category_cache();

comment on column public.transactions.category is
  'Deprecated category name cache. public.transactions.category_id is the source of truth.';

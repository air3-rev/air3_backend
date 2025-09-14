-- Add explicit fields for filtering
alter table public.paper_chunks
    add column created_at timestamptz default now(),
    add column updated_at timestamptz default now();

-- Function to update updated_at
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Trigger on paper_chunks
create trigger trg_set_updated_at
before update on public.paper_chunks
for each row
execute function set_updated_at();


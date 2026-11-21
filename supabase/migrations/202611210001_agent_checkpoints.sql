begin;

create table if not exists public.agent_checkpoints (
  user_id uuid primary key references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 80),
  checkpoint jsonb not null check (jsonb_typeof(checkpoint) = 'object'),
  updated_at timestamptz not null default now()
);

alter table public.agent_checkpoints enable row level security;
revoke all on public.agent_checkpoints from anon;
grant select, insert, update, delete on public.agent_checkpoints to authenticated;

drop policy if exists agent_checkpoints_select_own on public.agent_checkpoints;
create policy agent_checkpoints_select_own on public.agent_checkpoints
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists agent_checkpoints_insert_own on public.agent_checkpoints;
create policy agent_checkpoints_insert_own on public.agent_checkpoints
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists agent_checkpoints_update_own on public.agent_checkpoints;
create policy agent_checkpoints_update_own on public.agent_checkpoints
  for update to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists agent_checkpoints_delete_own on public.agent_checkpoints;
create policy agent_checkpoints_delete_own on public.agent_checkpoints
  for delete to authenticated using ((select auth.uid()) = user_id);

commit;

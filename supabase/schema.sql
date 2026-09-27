-- Table de sauvegarde des données de l'app : une ligne par compte, toutes les données dans un JSON.
-- À exécuter une fois dans Supabase → SQL Editor.
create table if not exists public.user_data (
  user_id uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- Chaque compte ne peut lire et modifier que sa propre ligne.
alter table public.user_data enable row level security;

create policy "Lire ses données" on public.user_data
  for select using (auth.uid() = user_id);
create policy "Créer ses données" on public.user_data
  for insert with check (auth.uid() = user_id);
create policy "Modifier ses données" on public.user_data
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

grant select, insert, update on public.user_data to authenticated;

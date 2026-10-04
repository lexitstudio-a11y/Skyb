-- Sécurité : chaque compte ne voit et ne modifie QUE sa propre ligne de « user_data ».
-- À exécuter dans Supabase → SQL Editor (sans risque si déjà fait : le script peut être relancé).

alter table public.user_data enable row level security;
alter table public.user_data force row level security;

drop policy if exists "Lire ses données" on public.user_data;
drop policy if exists "Créer ses données" on public.user_data;
drop policy if exists "Modifier ses données" on public.user_data;
drop policy if exists "Supprimer ses données" on public.user_data;

create policy "Lire ses données" on public.user_data
  for select to authenticated using (auth.uid() = user_id);
create policy "Créer ses données" on public.user_data
  for insert to authenticated with check (auth.uid() = user_id);
create policy "Modifier ses données" on public.user_data
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Supprimer ses données" on public.user_data
  for delete to authenticated using (auth.uid() = user_id);

-- Aucun accès sans être connecté ; les comptes connectés passent par les règles ci-dessus.
revoke all on public.user_data from anon;
revoke all on public.user_data from public;
grant select, insert, update, delete on public.user_data to authenticated;

-- Vérification : doit afficher rowsecurity = true et les 4 règles.
select relname, relrowsecurity as rowsecurity, relforcerowsecurity as force from pg_class where relname = 'user_data';
select policyname, cmd, roles from pg_policies where tablename = 'user_data';

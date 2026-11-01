begin;
-- Repeat-play marker: a random per-browser ID for analysis, never shown publicly.
alter table public.sessions add column device_id uuid;
create index sessions_device_idx on public.sessions(device_id);
commit;

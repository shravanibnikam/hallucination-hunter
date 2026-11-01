begin;
-- Repeat-play marker: a random per-browser ID for analysis, never shown publicly.
alter table public.sessions add column device_id uuid;
create index sessions_device_idx on public.sessions(device_id);
-- Real span: every fake is its real answer with one unique real_span swapped for fabricated_span.
-- Attention checks are built the same way, so the rule covers every pair.
alter table public.pairs add column real_span text;
-- Existing pairs have no real_span and assigned pairs are immutable: retire them and import revisions under new UUIDs.
update public.pairs set is_active = false where is_active;
-- NOT VALID leaves only those retired rows unchecked; every insert and update is checked.
alter table public.pairs add constraint pairs_real_span_check check (
 real_span is not null and real_span <> '' and real_span <> fabricated_span
 and strpos(answer_real, real_span) > 0
 and strpos(substr(answer_real, strpos(answer_real, real_span) + 1), real_span) = 0
 and answer_fake = overlay(answer_real placing fabricated_span from strpos(answer_real, real_span) for length(real_span))
) not valid;
commit;

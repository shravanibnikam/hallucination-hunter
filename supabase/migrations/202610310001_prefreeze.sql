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
-- Study switch: only STUDY_STATUS=open creates study sessions; closed free play has no consent step.
-- Earlier sessions default to non-study: they are pre-freeze development data.
alter table public.sessions add column is_study boolean not null default false;
alter table public.sessions alter column consent_given_at drop not null, alter column age_confirmed drop not null;
alter table public.sessions add constraint sessions_study_consent_check check (not is_study or (consent_given_at is not null and age_confirmed is true));
-- Exposure balancing counts study judgments only, like public totals and default exports.
create or replace view public.pair_exposure_counts with (security_invoker = true) as
 select p.id as pair_id, count(g.id) filter (where s.is_study and not s.is_pilot) as judgment_count
 from public.pairs p left join public.guesses g on g.pair_id=p.id
 left join public.sessions s on s.id=g.session_id group by p.id;
revoke all on public.pair_exposure_counts from public;
do $$ begin
 if exists (select from pg_roles where rolname='anon') then
  revoke all on public.pair_exposure_counts from anon;
 end if;
 if exists (select from pg_roles where rolname='authenticated') then
  revoke all on public.pair_exposure_counts from authenticated;
 end if;
end $$;
commit;

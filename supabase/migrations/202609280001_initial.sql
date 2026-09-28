begin;
create table public.pairs (
 id uuid primary key default gen_random_uuid(),
 question text not null check (length(trim(question)) > 0),
 category text not null check (length(trim(category)) > 0),
 answer_real text not null check (length(trim(answer_real)) > 0),
 answer_fake text not null,
 fabricated_span text not null check (length(fabricated_span) > 0 and strpos(answer_fake, fabricated_span) > 0),
 hallucination_type text not null check (hallucination_type in ('wrong_number','wrong_entity','wrong_date','invented_citation','other')),
 explanation text not null check (length(trim(explanation)) > 0),
 source_url text check (source_url ~ '^https?://[^[:space:]]+$'),
 model_name text,
 origin text not null check (origin in ('natural','synthetic')),
 is_attention_check boolean not null default false,
 is_active boolean not null default true,
 dataset_version text not null check (length(trim(dataset_version)) > 0),
 created_at timestamptz not null default now()
);
create table public.sessions (
 id uuid primary key default gen_random_uuid(),
 created_at timestamptz not null default now(),
 condition text not null check (condition in ('paired','single')),
 consent_given_at timestamptz not null,
 age_confirmed boolean not null check (age_confirmed = true),
 nickname text check (nickname ~ '^[A-Za-z0-9 _-]{2,20}$' and length(trim(nickname)) >= 2),
 device_type text check (device_type in ('mobile','desktop')),
 ai_usage_frequency text check (ai_usage_frequency in ('never','monthly','weekly','daily')),
 background text check (background in ('cs_engineering','other_stem','non_stem','prefer_not_to_say')),
 ai_knowledge_rating smallint check (ai_knowledge_rating between 1 and 5),
 total_items smallint not null check (total_items between 1 and 10),
 completed boolean not null default false,
 completed_at timestamptz,
 final_score smallint check (final_score between 0 and total_items),
 best_streak smallint check (best_streak between 0 and total_items),
 failed_attention_check boolean,
 is_pilot boolean not null default false,
 app_version text not null,
 check ((not completed and completed_at is null and final_score is null and best_streak is null and failed_attention_check is null) or (completed and completed_at is not null and final_score is not null and best_streak is not null and failed_attention_check is not null))
);
create table public.session_items (
 id uuid primary key default gen_random_uuid(),
 session_id uuid not null references public.sessions(id),
 pair_id uuid not null references public.pairs(id),
 position smallint not null check (position between 1 and 10),
 fake_shown_on text check (fake_shown_on in ('left','right')),
 shown_answer text check (shown_answer in ('real','fake')),
 served_at timestamptz,
 unique (session_id, position), unique (session_id, pair_id),
 unique (id, session_id, pair_id),
 check ((fake_shown_on is not null) <> (shown_answer is not null))
);
create table public.guesses (
 id uuid primary key default gen_random_uuid(),
 session_item_id uuid not null unique,
 session_id uuid not null references public.sessions(id),
 pair_id uuid not null references public.pairs(id),
 chosen_side text check (chosen_side in ('left','right')),
 judgment text check (judgment in ('yes','no')),
 is_correct boolean not null,
 confidence smallint not null check (confidence between 1 and 5),
 response_time_ms integer not null check (response_time_ms between 0 and 600000),
 flagged_too_fast boolean not null,
 created_at timestamptz not null default now(),
 app_version text not null,
 dataset_version text not null,
 foreign key (session_item_id,session_id,pair_id) references public.session_items(id,session_id,pair_id),
 check ((chosen_side is not null) <> (judgment is not null))
);
create index guesses_session_idx on public.guesses(session_id);
create index guesses_pair_idx on public.guesses(pair_id);
create index items_pair_idx on public.session_items(pair_id);
create index leaderboard_idx on public.sessions(final_score desc, best_streak desc, completed_at) where completed and not is_pilot and failed_attention_check = false and nickname is not null;
create view public.pair_exposure_counts with (security_invoker = true) as
 select p.id as pair_id, count(g.id) filter (where s.is_pilot = false) as judgment_count
 from public.pairs p left join public.guesses g on g.pair_id=p.id
 left join public.sessions s on s.id=g.session_id group by p.id;
alter table public.pairs enable row level security;
alter table public.sessions enable row level security;
alter table public.session_items enable row level security;
alter table public.guesses enable row level security;
revoke all on public.pairs, public.sessions, public.session_items, public.guesses, public.pair_exposure_counts from public;
-- Supabase roles exist in production; plain local PostgreSQL need not have them.
do $$ begin
 if exists (select from pg_roles where rolname='anon') then
  revoke all on public.pairs, public.sessions, public.session_items, public.guesses, public.pair_exposure_counts from anon;
 end if;
 if exists (select from pg_roles where rolname='authenticated') then
  revoke all on public.pairs, public.sessions, public.session_items, public.guesses, public.pair_exposure_counts from authenticated;
 end if;
end $$;
-- Keep the source facts of an assigned round stable, including across imports.
create function public.protect_assigned_pair() returns trigger language plpgsql set search_path = '' as $$
begin
 if (to_jsonb(new) - 'is_active') is distinct from (to_jsonb(old) - 'is_active') and exists (select 1 from public.session_items where pair_id=old.id) then
  raise exception 'Assigned pairs are immutable; import a revision with a new UUID';
 end if;
 return new;
end $$;
create trigger protect_assigned_pair before update on public.pairs for each row execute function public.protect_assigned_pair();
commit;

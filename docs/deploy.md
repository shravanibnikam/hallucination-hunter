# Free deployment checklist

This is a manual pre-deploy checklist, not an automatic deployment script. Use Supabase Free, Vercel Hobby, and the public GitHub repository. Do not enter payment details or enable paid upgrades. Vercel Hobby is intended for personal, non-commercial projects; check its current terms before changing the study's use.

## Before publishing

- [ ] Run lint, typecheck, unit tests, database integration tests, and both-condition Playwright tests as described in the README.
- [ ] Replace the placeholder study contact on About and Privacy.
- [ ] Replace `[SAMPLE]` facts with Shravani's validated study dataset; include an active attention check, stable UUIDs, exact fabricated and real spans, sources, origin, and dataset version.
- [ ] Review the consent and publication wording for the intended study. Keep raw exports private; remove aliases and coarsen timestamps before sharing anonymized data.
- [ ] Review `ROUND_LENGTH` and `TOO_FAST_MS` in `lib/constants.ts`. If round length is changed above 10, update the database constraints, schemas, and share bounds together. Bump the package version when behavior or study rules change.
- [ ] Ensure `.env` files and `research/data/exports/` are absent from the Git index. Keep production credentials only in your local environment and Vercel's environment settings.

## Supabase Free

1. Create a Free project in your own Supabase account. Choose a database password and store it privately. Use the default project URL and features; no paid IPv4 add-on, custom domain, branching, or scheduled work is necessary.
2. Open **Connect** in the project dashboard. For Vercel functions, copy the **transaction pooler** PostgreSQL URL (normally port 6543). Set a server-only `DATABASE_URL` with SSL enabled, such as the dashboard-provided URL with `sslmode=require`. URL-encode special characters in passwords. The driver disables prepared statements for transaction pooling and keeps at most three connections per process.
3. For migrations and Python tools, use the dashboard's **session pooler** URL (normally port 5432) or a working direct connection, also with SSL. The session pooler provides IPv4 connectivity without a paid add-on. Keep this URL in your local `DATABASE_URL` for those commands; use the transaction URL in Vercel.
4. Apply the SQL migration once to the fresh production database, through the Supabase SQL editor or locally:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/202609280001_initial.sql
research/.venv/bin/python research/import_pairs.py path/to/validated_pairs.csv --dry-run
research/.venv/bin/python research/import_pairs.py path/to/validated_pairs.csv
```

Future migrations must be new files applied in order; never rewrite a migration already deployed. `202610310001_prefreeze.sql` deactivates every existing pair, because pairs from before `real_span` cannot be revised in place; import the dataset again (with new UUIDs for any pair a round has used) before playing. The sample CSV is suitable only for development or a clearly labeled pilot.

## Verify database access

Run these in the SQL editor:

```sql
select relname, relrowsecurity
from pg_class
where oid in ('public.pairs'::regclass, 'public.sessions'::regclass,
              'public.session_items'::regclass, 'public.guesses'::regclass);

select tablename, roles, cmd
from pg_policies
where schemaname = 'public'
  and tablename in ('pairs', 'sessions', 'session_items', 'guesses');

select reloptions from pg_class where oid = 'public.pair_exposure_counts'::regclass;

select role_name, table_name,
       has_table_privilege(role_name, 'public.' || table_name, 'SELECT') as can_select,
       has_table_privilege(role_name, 'public.' || table_name, 'INSERT') as can_insert,
       has_table_privilege(role_name, 'public.' || table_name, 'UPDATE') as can_update,
       has_table_privilege(role_name, 'public.' || table_name, 'DELETE') as can_delete
from (values ('anon'), ('authenticated')) as r(role_name)
cross join (values ('pairs'), ('sessions'), ('session_items'), ('guesses')) as t(table_name);
```

Expected: RLS is true for all four tables; no policies; `security_invoker=true` on the view; no public-role table privileges. Do not add permissive policies to make the app work. It uses a privileged server connection. Never give the browser a service-role key or `DATABASE_URL`, and never prefix a credential with `NEXT_PUBLIC_`.

## Vercel Hobby

1. Import `shravanibnikam/hallucination-hunter` into your personal Hobby account. Use the Next.js preset, repository root, Node.js 24, and pnpm. Keep the default free `vercel.app` domain.
2. Set these **server** environment variables:

| Variable | Production value |
| --- | --- |
| `DATABASE_URL` | Supabase transaction-pooler URL with SSL |
| `APP_URL` | The canonical HTTPS URL of this deployment, for share metadata |
| `NEXT_TELEMETRY_DISABLED` | `1`, also set by the package scripts |

Do not set `TEST_DATABASE_URL` in production. Give previews a separate development database, or omit their database credentials. Never point test fixtures at production.

3. Build with `pnpm build`. Do not enable Analytics, Speed Insights, monitoring integrations, cron, or other add-ons. The app has no LLM requests, email service, image CDN, or external font requests.
4. After deployment, play `/play?pilot=1` in both random conditions. Check refresh, single-real reveal, confidence, keyboard controls, mobile layout, and `/share?score=8&total=10` including its image. Verify no labels appear in item-network responses before submission. Pilot rounds must be absent from public totals and the leaderboard.
5. Replace the README demo link once the owner is ready to recruit. Monitor free-plan usage manually in the provider dashboards. If a free limit is reached, pause recruitment; do not add a payment method or auto-upgrade.

## Resume a paused Supabase project

Free projects can pause after a period of low activity (Supabase documents a seven-day period). This app deliberately has no keep-alive cron or background worker.

1. Sign in to the Supabase dashboard and open the paused project.
2. Use the dashboard's **Restore** or **Resume** action and wait for the database to become healthy.
3. Recheck the connection details and update Vercel's server environment only if they changed. Redeploy if an environment value changes.
4. Open the landing counter and play a pilot round. The counter may take up to 60 seconds to refresh.
5. If the dashboard no longer offers restoration, follow the recovery options it presents and use your own saved dataset/export files as appropriate. Do not treat Free hosting as a long-term backup.

Manual exports stay in the ignored exports folder. Export before long inactivity or major changes. No paid backup or monitoring feature is required by this application.

## Known limits

The in-memory limiter is per instance and resets on restart; it is not distributed protection. Timing and coarse screen size are self-reported by the browser. Anonymous sessions cannot prove unique participants or prevent replaying rounds in a new tab. Hosting providers may retain operational connection logs outside the study database. These limitations should inform recruitment and analysis; the application does not silently remove questionable rows.

## Official references

- [Supabase database connections and poolers](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase availability and Free project pausing](https://supabase.com/docs/guides/deployment/going-into-prod)
- [Vercel Hobby plan](https://vercel.com/docs/plans/hobby)

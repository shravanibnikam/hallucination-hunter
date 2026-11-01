# Hallucination Hunter

**Can you catch the AI lying?** A fast web game and anonymous human-evaluation study on how people detect fabricated facts in AI answers.

## Live demo

[Coming soon — deployment link placeholder](#live-demo)

## Screenshot

Screenshot placeholder — add an image after the research dataset and deployment are ready.

## How it works

1. Consent to anonymous research and confirm you are 18 or older. A made-up leaderboard nickname and three profile questions are optional.
2. Your session is randomly assigned to **paired** answers (pick the fabrication) or a **single** answer (judge Yes / No). The round contains up to 10 items, including one attention check when available.
3. Choose an answer, rate your confidence, then see the fabricated detail, explanation, and source. Finish for your score, streak, category accuracy, and confidence calibration.

The study runs only while the server's `STUDY_STATUS` is exactly `open`. Otherwise `/play` skips consent and the profile, says the study has ended, and records non-study sessions that are excluded from totals, the leaderboard, exposure counts, and default exports, like pilots.

Use A/B or Y/N to choose, 1–5 for confidence, and Enter to continue. Refreshing resumes the next unguessed item in the same tab. Add `?pilot=1` to `/play` for a pilot round, excluded from public totals, exposure counts, and default exports.

## Research questions

1. Can people reliably detect hallucinations in AI-generated answers?
2. Which kinds fool people most: wrong numbers, names, dates, or invented citations?
3. Does confidence match accuracy?
4. Is comparing two answers easier than judging a single answer alone?

The fourth question uses random between-session assignment, not a player-selected mode. Public participant counts represent completed sessions; the anonymous design cannot deduplicate individual people.

## Findings

Coming soon. No study findings are claimed from the development samples.

## Dataset

[Research dataset — coming soon](#dataset). The included [sample CSV](research/data/sample_pairs.csv) has six ordinary examples and two attention checks, all prefixed `[SAMPLE]` and versioned `sample-v1`. Each row names the `real_span` its fake replaces. The demonstration round has seven items: six ordinary facts plus one randomly selected check. Replace these examples before recruitment.

Dataset generation and analysis are owned by Shravani. Their folders contain only placeholder READMEs.

## Tech stack

Next.js 16 App Router, strict TypeScript, React, Tailwind CSS, Lucide icons, Zod, Postgres.js with PostgreSQL via Supabase, Vitest, and Playwright. Python 3.11+ tools use psycopg and pandas. The lockfile pins the tested dependency tree; TypeScript 6 and ESLint 9 currently match the Next.js lint plugins.

Deployment uses **Supabase Free**, **Vercel Hobby**, and this public **GitHub Free** repository with **GitHub Actions**. No payment details, paid APIs, LLM calls, analytics, cron jobs, workers, or paid add-ons are needed. All direct dependencies are open source. Fonts use the system stack.

## Architecture

The browser only calls Next.js route handlers. A server-only PostgreSQL driver connects through `DATABASE_URL`; there are no public database credentials. All four tables have RLS enabled with no policies for `anon` or `authenticated`; privileges are also revoked, and the exposure view uses invoker security.

A session and its entire randomized layout are written in one transaction. The item route constructs an explicit public response containing only position, round length, question, category, and unlabeled display text. Answer labels, spans, explanations, metadata, and pair IDs stay on the server until a guess is stored.

Guess writes lock the session, require that the item was served and the previous item answered, enforce the assigned condition, and compute correctness from the stored layout. A unique constraint prevents duplicate guesses even during concurrent requests. Scores, streaks, completion, and attention-check results are computed server-side. Once assigned, a pair's contents cannot be edited; deactivate it and import a revision with a new UUID.

No IPs or user-agent strings enter the study tables. The random session UUID is a bearer capability stored only in `sessionStorage`; do not share it. A separate random device ID in `localStorage` (`hh_device_id`) marks repeat play: it is stored in `sessions.device_id`, exported for analysis, and never shown publicly. The app sets no cookies. Rate limits are intentionally basic and per process; see [decisions](docs/decisions.md). Calibration, mean confidence, and category accuracy exclude attention checks; the game score and streaks include them.

## Local setup

Prerequisites: Git, Node.js **24 LTS**, pnpm **11.20.0**, Python **3.11+**, and PostgreSQL **15+** (17 is tested) with `psql` and `createdb`. On macOS, `brew install node@24 postgresql@17` installs the missing runtimes; put their `bin` directories on your PATH. Alternatively, select Node 24 using your existing version manager and `.nvmrc`.

```sh
git clone https://github.com/shravanibnikam/hallucination-hunter.git
cd hallucination-hunter
pnpm install --frozen-lockfile
cp .env.example .env.local
python3 -m venv research/.venv
research/.venv/bin/pip install -r research/requirements.txt
```

For a Homebrew installation on macOS, start the local database and select the installed LTS runtime:

```sh
export PATH="$(brew --prefix node@24)/bin:$(brew --prefix postgresql@17)/bin:$PATH"
brew services start postgresql@17
createdb hallucination_hunter
```

On another platform, start your installed PostgreSQL server and create the same database using your configured database role. Set `DATABASE_URL` in `.env.local` to its connection URL (for the default Homebrew role, `postgresql://localhost/hallucination_hunter`). Set `APP_URL=http://localhost:3000`, and `STUDY_STATUS=open` to run the consent flow (unset means closed free play). You can instead use a dedicated Supabase Free development project with the connection details described in [deploy.md](docs/deploy.md). Never commit `.env.local`.

The Python tools and `psql` read environment variables, not Next.js env files. For the trusted `.env.local` you just wrote, load it into your shell:

```sh
set -a
. ./.env.local
set +a
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/202609280001_initial.sql
research/.venv/bin/python research/import_pairs.py research/data/sample_pairs.csv --dry-run
research/.venv/bin/python research/import_pairs.py research/data/sample_pairs.csv
pnpm dev
```

Apply each migration **once**, in filename order, to a fresh database. Open `http://localhost:3000`. Next.js reads `.env.local` automatically. The app returns a friendly study-not-ready error if no active items exist.

### Checks and tests

```sh
pnpm lint
pnpm typecheck
pnpm test
research/.venv/bin/python -m unittest discover -s tests -p 'research_test.py'
```

Database and browser tests require a **separate disposable database** whose name ends in `_test`. Integration tests truncate its study tables. Never point `TEST_DATABASE_URL` at research data. Example using a running local PostgreSQL instance and your configured local database role:

```sh
createdb hunter_test
export TEST_DATABASE_URL='postgresql://localhost/hunter_test'
export STUDY_STATUS=open
pnpm test:prepare
pnpm test:integration
DATABASE_URL="$TEST_DATABASE_URL" research/.venv/bin/python research/import_pairs.py research/data/sample_pairs.csv --deactivate-missing
pnpm exec playwright install chromium
pnpm test:e2e
```

Adjust the local database URL for your username, port, and authentication. Playwright builds and starts the production app on port 3100 and runs the full game in both conditions at 375px and desktop widths. It covers consent gating, confidence, keyboard controls, refresh, reveal, results, sharing, page widths, and OG output. It obtains real random assignments rather than enabling a test-only production override.

GitHub Actions runs lint, typecheck, unit tests, a disposable PostgreSQL integration suite, and Playwright on pushes and pull requests. No secrets are needed for CI; its database credentials belong only to an ephemeral service container.

### Import and export

```sh
research/.venv/bin/python research/import_pairs.py path/to/pairs.csv --dry-run
research/.venv/bin/python research/import_pairs.py path/to/pairs.csv
research/.venv/bin/python research/import_pairs.py path/to/pairs.csv --deactivate-missing
research/.venv/bin/python research/export_data.py
research/.venv/bin/python research/export_data.py --include-pilot
research/.venv/bin/python research/export_data.py --include-nonstudy
```

Imports require stable UUIDs and validate required fields, enums, exact fabricated spans, and HTTP(S) URLs. Every pair, attention checks included, needs a `real_span` that appears exactly once in `answer_real` and differs from `fabricated_span`, and `answer_fake` must be `answer_real` with that one occurrence replaced by `fabricated_span`; a database check constraint enforces the same rule. Valid rows are upserted transactionally, invalid rows are reported with line numbers, and a nonzero status reports errors. Deactivation refuses invalid or empty files and never deletes data.

Exports are timestamped CSVs in ignored `research/data/exports/`. They include incomplete sessions and quality flags (`completed`, `failed_attention_check`, `flagged_too_fast`), so exclusion choices remain explicit. `device_round_number` is 1 for a browser's first session by creation time, counting every session including pilot ones; it is empty without a `device_id`. Each row carries the item's round `position` (1–10) with `is_study`, `device_id`, and `device_round_number`. Pilot guesses and non-study (closed free-play) guesses are excluded by default; `--include-pilot` and `--include-nonstudy` add them, and `is_pilot` and `is_study` keep them distinguishable. Raw exports include optional aliases and precise timestamps: review and anonymize them before public release. The export script is data transport, not an analysis pipeline.

## Project structure

```text
app/                    Pages and server API route handlers
components/             Consent, profile, game, results, and public UI
lib/                    Round selection, schemas, scoring, database access
  design-tokens.ts      All colors, radii, and type sizes
supabase/migrations/    Schema, RLS, constraints, exposure view
research/               Import/export tools and sample CSV
  dataset_generation/   Owner's placeholder only
  analysis/             Owner's placeholder only
tests/                  Unit, integration, Python validation, and browser tests
scripts/                Disposable test database preparation
docs/                   Decision log and deployment checklist
```

See [deployment instructions](docs/deploy.md) for environment variables, production migrations, RLS verification, and restoring an inactive Supabase project. See [decisions](docs/decisions.md) for tradeoffs and limits.

## How it was built

Application built with Codex from a specification written by Shravani. Study design, dataset pipeline and analysis by Shravani.

## License

[MIT](LICENSE) — Copyright Shravani.

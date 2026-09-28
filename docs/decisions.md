# Decisions

- Use a server-only PostgreSQL driver with Supabase's transaction pooler, rather than a browser Supabase client. This allows atomic round creation and locked guess writes.
- Use a system font stack so builds and play never need font downloads.
- Use local PostgreSQL for repeatable database verification. Production uses Supabase Free; no additional hosted services are required.
- The six ordinary samples plus two attention checks form eight CSV rows. Samples are demonstrations, not a validated research dataset.
- Dataset rows require stable UUIDs for safe, repeatable upserts. Omitted optional CSV values use database defaults; importing an existing pair cannot change its content once a round references it (use a new UUID for revisions).
- Pin TypeScript to major version 6 because the current Next.js ESLint parser rejects TypeScript 7. Next.js itself uses the latest stable release.
- Pin ESLint to major version 9; the React plugin currently bundled by eslint-config-next uses APIs removed in ESLint 10.
- Without any attention-check pair, keep the specified N−1 ordinary items and shorten the round by one (up to 9). If the pool is empty, return a friendly 503 rather than creating an empty session.
- The random session UUID is an anonymous bearer capability, kept only in sessionStorage. A minimal GET session endpoint returns progress for refresh recovery; it exposes no item IDs or answer metadata. No cookies are needed.
- Refresh resumes at the next unguessed item; an unsubmitted answer is discarded. The timer restarts on render, while the first served_at stays unchanged. A submitted guess is never rewritten.
- Viewport widths below 768px are recorded as mobile; all others are desktop. This is a coarse screen classification, not user-agent collection.

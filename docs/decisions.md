# Decisions

- Use a server-only PostgreSQL driver with Supabase's transaction pooler, rather than a browser Supabase client. This allows atomic round creation and locked guess writes.
- Use a system font stack so builds and play never need font downloads.
- Use local PostgreSQL for repeatable database verification. Production uses Supabase Free; no additional hosted services are required.
- The six ordinary samples plus two attention checks form eight CSV rows. Samples are demonstrations, not a validated research dataset.
- Dataset rows require stable UUIDs for safe, repeatable upserts. Omitted optional CSV values use database defaults; importing an existing pair cannot change its content once a round references it (use a new UUID for revisions).
- Pin TypeScript to major version 6 because the current Next.js ESLint parser rejects TypeScript 7. Next.js itself uses the latest stable release.
- Pin ESLint to major version 9; the React plugin currently bundled by eslint-config-next uses APIs removed in ESLint 10.

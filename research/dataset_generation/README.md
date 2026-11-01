# Dataset generation (v1)

Builds the v1 study dataset: 80 pairs, 20 of each `hallucination_type` (`wrong_number`, `wrong_entity`, `wrong_date`, `invented_citation`), plus 4 attention checks. The pipeline generates about twice what is needed and stops for a hand check before anything is selected or imported.

Everything here is Python, needs no API key, account or payment, and writes its data to `research/data/`.

## Setup

From the repository root, with the research virtual environment described in the main README:

```sh
research/.venv/bin/pip install -r research/requirements.txt
```

Network access is needed for the English Wikipedia and Wikidata APIs and the Crossref API. Every response is cached in `research/dataset_generation/.cache/` (ignored by Git), so reruns repeat the same answers; delete that folder to fetch fresh ones. Whole articles are fetched because a fake must not appear anywhere in its source article; each article is stored once and linked under both its title and its revision.

## Stage 1: candidate real answers

Input: `research/data/candidates_v1.csv`, 160 candidates (40 per type, split 14/13/13 across `science`, `geography` and `history`). Columns: `id`, `hallucination_type`, `category`, `question`, `answer_real`, `real_span`, `source_url`. Every row has a UUID that later stages keep.

Provenance: the candidates were written by Claude (`claude-opus-5-5`) in a Claude Code session, from its own knowledge, following the rules below. They were not copied from Wikipedia; Wikipedia and Crossref are used only to check them. No topic appears twice, so one item never gives away another.

Rules for each candidate:

- `answer_real` reads like an assistant's answer: 25 to 60 words, 1 to 3 sentences, confident, with no hedging words. A `wrong_date` span is written `20 July 1969`, `July 20, 1969` or `1969`.
- `real_span` appears exactly once. The row must pass `research/import_pairs.py`'s own validation (reused, not copied), checked with a placeholder fake.
- `source_url` is an English Wikipedia article. For `invented_citation`, the answer cites a real paper and `source_url` is its DOI link.

Run:

```sh
cd research/dataset_generation
../.venv/bin/python check_sources.py --offline   # format rules only, no network
../.venv/bin/python check_sources.py
```

`check_sources.py` checks each candidate against its source:

- Wikipedia: fetches the article's rendered text through the MediaWiki `parse` API and confirms `real_span` appears. The infobox counts; footnote markers (`[45]`) and reference lists do not, because their numbers are not article content. Numbers match as whole numbers after removing thousands separators, whether commas or spaced groups (`1,538` matches `1538 °C`, and `149,597,870,700` matches `149 597 870 700`), but `46` never matches `1946` and `21,196` does not match `21,196.18`. Full dates match in the common written forms (`20 July 1969`, `July 20, 1969`).
- Crossref (`api.crossref.org`, no key): looks up the DOI and requires the same title (up to case, punctuation and a subtitle), the first author's family name in the answer, and the publication year in the answer (a year off by one is flagged, not failed).

Outputs:

- `research/data/candidates_v1_failed.csv`: every failing candidate with its reasons. Nothing is dropped silently.
- `research/data/sources_v1.csv`: each candidate's `status`, the exact Wikipedia revision (or DOI) checked, and any flags. Later stages check against that same revision.

## Attention checks

`research/data/attention_checks_v1.csv` holds 4 attention checks written by hand, one per type, each with an obviously absurd fabricated span ("four hundred thousand" legs, "a bowl of tomato soup"). They are complete import rows and pass the importer's rules, including the real-span rule.

## Tests

```sh
research/.venv/bin/python -m unittest discover -s tests -p '*_test.py'
```

`tests/dataset_test.py` mocks every Wikipedia, Wikidata and Crossref call.

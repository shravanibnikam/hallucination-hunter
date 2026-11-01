# Dataset generation (v1)

Builds the v1 study dataset: 80 pairs, 20 of each `hallucination_type` (`wrong_number`, `wrong_entity`, `wrong_date`, `invented_citation`), plus 4 attention checks. The pipeline generates about twice what is needed and stops for a hand check before anything is selected or imported.

Everything here is Python, needs no API key, account or payment, and writes its data to `research/data/`.

## Your hand check: `research/data/review_v1.csv`

Open `research/data/review_v1.csv` (126 rows, sorted by `hallucination_type`, then `category`) and fill in `keep` on every row:

| `keep` | Meaning |
|---|---|
| `yes` | Use the pair as shown (`answer_fake`, with `fabricated_span`). |
| `alt2` | Use `alt_fake_2` instead: it replaces `real_span` in `answer_real` the same way. |
| `alt3` | Use `alt_fake_3` instead. |
| `no` | Drop the candidate. |

Use `notes` for anything else, such as a correction to the real answer or a better explanation.

**You need at least 20 rows marked `yes`, `alt2` or `alt3` in each `hallucination_type`** (80 in total), spread across `science`, `geography` and `history` as evenly as you can (7/7/6). Available rows:

| Type | science | geography | history | Total |
|---|---|---|---|---|
| `wrong_number` | 11 | 10 | 7 | 28 |
| `wrong_entity` | 13 | 6 | 6 | 25 |
| `wrong_date` | 13 | 13 | 13 | 39 |
| `invented_citation` | 12 | 9 | 13 | 34 |

`wrong_entity` is the tightest: with 6 in geography and 6 in history, the best possible split is 8/6/6, and you can drop at most 5 entity rows.

For each row, check that the real answer is right, that the fake is wrong but believable, and that nothing other than the span gives it away. `flags` points at rows worth a second look:

- `claim_wrong` or `claim_unverified`: a fact check found a problem with another claim in the real answer. The claim and evidence are in `research/data/claims_v1.csv` (match on `id`). Fix the answer in `notes` or mark `no`.
- `length_ratio_…`: the fake is much shorter or longer than the real span, a possible tell. `alt2:`/`alt3:` prefixes mean the same for an alternate.
- `crossref_year_…`: the year in the answer is one off the year Crossref gives.

Citation fakes run shorter than the real titles (stage 3 below), so prefer citation fakes or alternates close in length to the real title.

Do not rerun `make_review.py` once you have started: it refuses to overwrite a sheet with entries, but your copy is the record. Nothing is selected or imported until the hand check is done.

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

## Stage 2: fakes

Model: `microsoft/Phi-3-mini-4k-instruct-gguf`, file `Phi-3-mini-4k-instruct-q4.gguf` at revision `a64113399c2f6b8ad3e11c394733a2ddadaa7f33`, SHA-256 `8a83c7fb9049a9b2e92266fa7ad04933bb53aa1e85136b7b30f1b8000ff2edef` (MIT licence, not gated). Phi is not one of the families evaluated later (Gemma, Llama, Qwen). It runs locally on CPU through `llama-cpp-python` 0.3.36, one candidate at a time, with `n_gpu_layers=0`, `n_threads=6`, `n_ctx=2048`, temperature 0.7, top-p 0.95, at most 256 new tokens, and seed `20261101`, reset for every candidate so each result does not depend on run order. Source fetches and checks run in 4 worker threads alongside generation. Replies are constrained to the JSON schema `{"replacements": [3 strings]}`. The local build used `CMAKE_ARGS="-DGGML_METAL=OFF"` so no GPU code is compiled; other machines may differ in the last digits of sampling, so the committed outputs are the record.

Run (the script downloads the pinned file on first use and refuses one whose SHA-256 differs):

```sh
CMAKE_ARGS="-DGGML_METAL=OFF" research/.venv/bin/pip install llama-cpp-python==0.3.36   # once
cd research/dataset_generation
../.venv/bin/python make_fakes.py
```

The model's chat template has no system role, so the whole prompt is one user message. The exact template (Python `str.format`, with `{rule}` filled from the list below):

```text
You are helping build a research quiz about spotting AI hallucinations.

Question: {question}
Correct answer: {answer}

Write 3 different wrong replacements for the exact text "{span}" in the correct answer. {rule} Each replacement must read naturally when swapped into the answer, so that a careful reader might believe it. Give only the replacement text, not the whole answer. Reply in JSON as {"replacements": ["...", "...", "..."]}.
```

Rules by type. `{span}` is the real span; `{pattern}` is the real number with each digit shown as `#` (`1,538` gives `#,###`); `{kind}` is `person` when the real entity is a human on Wikidata, and otherwise the English labels of its first two Wikidata "instance of" classes (`business or public company` for Intel).

- `wrong_number`: Each must be a different, believable number written with exactly the pattern "{pattern}", where each # stands for one digit: the same separators and decimal places, with no units or words added. Avoid round numbers.
- `wrong_date`: Each must be a different, believable date written in exactly the same format as "{span}" and no more than 30 years away from it.
- `wrong_entity`: Each must be the name of a different, real {kind} that has its own English Wikipedia article, so it is the same kind of thing as "{span}". Give the name only.
- `invented_citation`: Each must be an invented title of a publication that does not exist, with the same style, capitalization and length as "{span}". Never use the title of a real work.

Each of the 3 replacements replaces only that one occurrence of `real_span`, and is kept only if it passes:

- `wrong_number`: the same shape as the real value (every digit in the same place, so the same unit, separators, decimals and digit count), no leading zero, a different value, and not round (ending in 0) unless the real value is round.
- `wrong_date`: the same written format and precision (`20 July 1969`, `July 20, 1969` or a year), a real calendar date, within 30 years, and different.
- `wrong_entity`: resolves to an unambiguous English Wikipedia article, is a different Wikidata item, and shares at least one Wikidata "instance of" (P31) class with the real one (person with person, city with city).
- `invented_citation`: the same title style (title or sentence case, subtitle colon, final punctuation), and Crossref returns no work with a matching title.
- All types: not already in the real answer, not anywhere in the source article (the same Wikipedia revision checked in stage 1; DOI-sourced citations have no article text, so the Crossref check covers them), and the completed pair passes `import_pairs.validate`. A fabricated span outside 0.7 to 1.3 times the real span's length is flagged (`length_ratio_…`), not dropped.

The first passing replacement is the main fake and up to two more become alternates.

Outputs:

- `research/data/fakes_v1.csv`: candidates with a main fake, alternates `alt_fake_2` and `alt_fake_3` (fabricated spans), the source revision, flags and `model_name`.
- `research/data/fakes_v1_failed.csv`: candidates with no passing replacement, with every replacement's reasons.
- `research/data/fakes_v1_attempts.csv`: every replacement the model gave, with its verdict, reasons and flags.

## Stage 3: artifact check

`artifact_check.py` asks whether surface features alone can pick the fake in a pair. Each pair (real answer, main fake) is shown in a shuffled order with exactly half the fakes first, and a logistic regression (scikit-learn 1.9.1, no intercept, features scaled but not centred) sees only the differences, first minus second, in answer length, span length, digit count and punctuation count. Because the two answers differ only in the span, the answer-length and span-length differences are equal, so there are three independent signals. Accuracy comes from 10-fold stratified cross-validation (seed 20261101) with a 95% Wilson interval, and the check passes if that interval includes 50%.

```sh
cd research/dataset_generation
../.venv/bin/python artifact_check.py                                      # all passing candidates
../.venv/bin/python artifact_check.py --input FINAL.csv --output OUT.json   # later, on the final 80
```

The result, with accuracy by type and the fitted coefficients, is written to `research/data/artifact_check_v1.json`.

Result on the 126 candidates with a passing fake: accuracy 56.3%, 95% CI [47.6%, 64.7%], so the check **passes**. By type, the pooled model scores 39% on numbers, 48% on entities and 59% on dates, but **74% on citations**: 26 of 34 citation fakes are shorter than the real title (median 0.83 of its length), and on citations alone the interval [0.57, 0.85] excludes 50%. When selecting the final citations, prefer fakes (or alternates) close in length to the real title, then rerun this check on the final 80.

## Stage 4: review sheet

`make_review.py` writes `research/data/review_v1.csv`, one row per candidate with a passing fake, sorted by `hallucination_type` and then `category`, with empty `keep` and `notes` columns. `alt_fake_2` and `alt_fake_3` hold the alternate fabricated spans, which replace `real_span` in `answer_real` exactly as the main fake does. It refuses to overwrite a sheet that already has entries in `keep` or `notes`.

```sh
cd research/dataset_generation
../.venv/bin/python make_review.py
```

`flags` gathers everything worth a second look: `length_ratio_…` (the fake is much shorter or longer than the real span, a possible tell), the same for an alternate (`alt2:…`, `alt3:…`), `crossref_year_…` (the cited year is one off Crossref's), and `claim_wrong` or `claim_unverified` from the fact check below.

`research/data/claims_v1.csv` is an advisory fact check of every other claim in each real answer (dates, co-authors, superlatives), since stage 1 verifies only `real_span`. Four Claude subagents (`claude-opus-5-5`, one per type) read the stage 1 revision of each cited article, the Crossref record for citations, and other English Wikipedia pages, and recorded `ok`, `wrong` (a source contradicts the claim) or `unverified`, with the claim and a short quote as evidence. Treat it as a pointer for the hand check, not a verdict.

## Attention checks

`research/data/attention_checks_v1.csv` holds 4 attention checks written by hand, one per type, each with an obviously absurd fabricated span ("four hundred thousand" legs, "a bowl of tomato soup"). They are complete import rows and pass the importer's rules, including the real-span rule.

## Tests

```sh
research/.venv/bin/python -m unittest discover -s tests -p '*_test.py'
```

`tests/dataset_test.py` mocks every Wikipedia, Wikidata and Crossref call.

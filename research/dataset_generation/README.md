# Dataset generation (v1)

Builds the v1 study dataset: 80 pairs, 20 of each `hallucination_type` (`wrong_number`, `wrong_entity`, `wrong_date`, `invented_citation`), plus 4 attention checks. The pipeline generates about twice what is needed, and two independent AI review passes decide which rows are kept before anything is selected or imported; no human reviewed the rows.

Everything here is Python, needs no API key, account or payment, and writes its data to `research/data/`.

## Review: `research/data/review_v1.csv`

No human reviewed the rows. The review was done by two independent AI passes, each source-quoted, and a row is kept only when both passes agree.

`research/data/review_v1.csv` has one row per candidate with a passing fake (214 rows, sorted by `hallucination_type`, then `category`). For each row, two passes, A and B, each decided `yes`, `alt2`, `alt3` or `no`. Each pass of each type was a separate Claude subagent (`claude-opus-5-5`) started fresh, told not to open the other pass's output, `claims_v1.csv` or `review_v1_passes.csv`, and given the same instructions:

1. Real answer: split `answer_real` into its claims and, for every claim, quote the sentence or infobox line from the source that supports it (the stage 1 Wikipedia revision, or for citations the Crossref record and the publisher page the DOI resolves to). Any claim without a supporting quote fails the row. Never rely on your own knowledge.
2. Choose `no` if the source gives varying figures or accounts for a claim, or if a knowledgeable player could reasonably think the real answer is wrong.
3. Fake: plausible to a non-expert, definitely false according to the source, and in the same style as the real answer. Patterned numbers (`1,234,567`, repeated digits) fail.
4. If the main fake passes, `yes`; else the first passing alternate (`alt2`, then `alt3`); else `no`.
5. When in doubt, `no`.

Both passes, with every claim's quote, a verdict on each fake and a one-sentence reason, are in `research/data/review_v1_passes.csv` (`id`, `pass`, `hallucination_type`, `decision`, `real_answer_quotes`, `fake_assessment`, `reason`; two rows per review row). Every quote from a Wikipedia source was matched against the cached article text, ignoring spacing and punctuation: 1,033 of 1,034 match word for word, and the one paraphrase is on a row both passes rejected. Citation claims are quoted from Crossref record fields.

`finalize.py combine` writes the combined decision into `keep`: the shared decision when both passes made the same keep decision (both `yes`, or both the same alternate), and `no` for every disagreement. `notes` gets a one-line reason (for a rejection, the rejecting pass's reason).

| `keep` | Meaning |
|---|---|
| `yes` | Use the pair as shown (`answer_fake`, with `fabricated_span`). |
| `alt2` | Use `alt_fake_2` instead: it replaces `real_span` in `answer_real` the same way. |
| `alt3` | Use `alt_fake_3` instead. |
| `no` | Drop the candidate. |

Agreement and kept rows, including the 68 top-up rows that got a fake (stage 1 explains the top-ups):

| Type | Rows | Passes agree | Kept | science | geography | history |
|---|---|---|---|---|---|---|
| `wrong_number` | 52 | 46 (88%) | 28 | 11 | 10 | 7 |
| `wrong_entity` | 55 | 51 (93%) | 31 | 12 | 10 | 9 |
| `wrong_date` | 39 | 37 (95%) | 31 | 11 | 10 | 10 |
| `invented_citation` | 68 | 62 (91%) | 30 | 9 | 11 | 10 |
| All | 214 | 196 (92%) | 120 | | | |

The selection needs 20 kept rows per type. After the first top-up `invented_citation` had 16, so a second round of 20 citations was added with the same design. The final selection is below.

Other columns: `length_diff` is the main fake span's length minus the real span's, in characters. `flags` lists `length_ratio_…` (the fake is much shorter or longer than the real span; `alt2:`/`alt3:` for an alternate), `crossref_year_…` (the answer's year is one off Crossref's) and `claim_wrong` or `claim_unverified` from the fact check in stage 4.

## Setup

From the repository root, with the research virtual environment described in the main README:

```sh
research/.venv/bin/pip install -r research/requirements.txt              # checks, artifact check, review sheet, tests
research/.venv/bin/pip install -r research/requirements-generation.txt   # adds llama-cpp-python, only to regenerate fakes
```

`llama-cpp-python` builds from source, so it lives in `requirements-generation.txt` and CI never installs it; `make_fakes.py` imports it only inside the function that runs the model.

Network access is needed for the English Wikipedia and Wikidata APIs and the Crossref API. Every response is cached in `research/dataset_generation/.cache/` (ignored by Git), so reruns repeat the same answers; delete that folder to fetch fresh ones. Whole articles are fetched because a fake must not appear anywhere in its source article; each article is stored once and linked under both its title and its revision.

## Stage 1: candidate real answers

Input: `research/data/candidates_v1.csv`: 160 candidates (40 per type, split 14/13/13 across `science`, `geography` and `history`), then 40 more for margin where checks are strict: 12 `invented_citation` (6 science, 6 geography), 20 `wrong_entity` (10 geography, 10 history) and 8 `wrong_number` (history), 200 in total. After the review passes left three types below 20 kept rows, 60 more were added, 20 per short type: 20 `invented_citation` (8 science, 7 history, 5 geography), 20 `wrong_number` (10 science, 10 geography) and 20 `wrong_entity` (12 science, 8 geography), 260 in total. Citations still had only 16 kept rows, so a second round of 20 citations (7 science, 8 geography, 5 history) was added the same way, 280 in total. Columns: `id`, `hallucination_type`, `category`, `question`, `answer_real`, `real_span`, `source_url`. Every row has a UUID that later stages keep.

Provenance: the candidates were written by Claude (`claude-opus-5-5`) in a Claude Code session, from its own knowledge, following the rules below. They were not copied from Wikipedia; Wikipedia and Crossref are used only to check them. No topic appears twice, so one item never gives away another. The 28 entity and number candidates added last were drafted by three Claude subagents (`claude-opus-5-5`), one per type and category, under the same rules; each draft passed this stage's format and source checks and a Wikidata lookup before it was added. Of the 60 top-up candidates, Claude (`claude-opus-5-5`) wrote the 20 citations in the main session, and four Claude subagents drafted the 40 number and entity rows under the same rules plus the reasons the review had rejected earlier rows: a figure the article gives more than one way, a claim the source does not state in so many words, disputed "first" credits, and context that makes any fake an obvious mismatch. Each top-up citation states only fields of its Crossref record (authors as recorded, journal, year, volume, pages), and its title has no punctuation other than a colon, since hyphenated titles rarely got a passing fake.

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
CMAKE_ARGS="-DGGML_METAL=OFF" research/.venv/bin/pip install -r research/requirements-generation.txt   # once
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
- `invented_citation`: Each must be an invented title of a publication that does not exist, exactly {words} words long like "{span}": keep its small words (such as "of", "the", "and", "for") and its punctuation in the same places, and replace every other word with a different word of about the same length on a related topic, with the same capitalization. Never use the title of a real work.

Each of the 3 replacements replaces only that one occurrence of `real_span`, and is kept only if it passes:

- `wrong_number`: the same shape as the real value (every digit in the same place, so the same unit, separators, decimals and digit count), no leading zero, a different value, and not round (ending in 0) unless the real value is round.
- `wrong_date`: the same written format and precision (`20 July 1969`, `July 20, 1969` or a year), a real calendar date, within 30 years, and different.
- `wrong_entity`: resolves to an unambiguous English Wikipedia article, is a different Wikidata item, and shares at least one Wikidata "instance of" (P31) class with the real one (person with person, city with city).
- `invented_citation`: the same title style (title or sentence case, subtitle colon, final punctuation); exactly the same punctuation characters as the real title in the same order (hyphens, en and em dashes, colons, commas, apostrophes, slashes and any others); a length between 0.85 and 1.15 times the real title's; and Crossref returns no work with a matching title.
- All types: not already in the real answer, not anywhere in the source article (the same Wikipedia revision checked in stage 1; DOI-sourced citations have no article text, so the Crossref check covers them), and the completed pair passes `import_pairs.validate`. A fabricated span outside 0.7 to 1.3 times the real span's length is flagged (`length_ratio_…`), not dropped.

For every type except citations, the first passing replacement is the main fake and up to two more become alternates. Citations get two asks of 3 replacements, with seeds `20261101` and `20261102` (6 replacements), and the passing title closest in character length to the real one becomes the main fake, with the next closest as alternates, so length gives as little away as possible. The `seed` column of the attempts log records which ask produced each replacement.

`--types` and `--ids` regenerate a subset and keep every other row as it is. A subset run reuses a different llama.cpp prompt cache than a full run, so its sampling can differ slightly; the committed attempts log is the record. `--rejudge ID...` re-checks the logged replies of those rows against their current `answer_real` without running the model, which is how rewritten answers keep their fakes (stage 4). For a rewritten row, generation always prompts with the answer the model first saw (`answer_real_before` in `claims_v1.csv`).

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

It runs once on all pairs and again with a separate model for each type, so a tell confined to one type cannot hide in the pool; it passes only if every interval includes 50%. Result on all 214 candidates with a passing fake, including the 68 top-up rows (on the first 146 it was 48.6% overall, with citations at 58.8%):

| | Pairs | Accuracy | 95% CI | |
|---|---|---|---|---|
| Overall | 214 | 54.7% | [48.0%, 61.2%] | pass |
| `wrong_number` | 52 | 50.0% | [36.9%, 63.1%] | pass |
| `wrong_entity` | 55 | 41.8% | [29.7%, 55.0%] | pass |
| `wrong_date` | 39 | 51.3% | [36.2%, 66.1%] | pass |
| `invented_citation` | 68 | 58.8% | [47.0%, 69.7%] | pass |

An earlier citation run failed on its own (74%, then 71%): fake titles were shorter and dropped hyphens. The punctuation check, the 0.85 to 1.15 length bound, two asks per citation and closest-length selection removed the tell.

## Stage 4: review sheet

`make_review.py` writes `research/data/review_v1.csv`, one row per candidate with a passing fake, sorted by `hallucination_type` and then `category`, with empty `keep` and `notes` columns. `length_diff` is the main fake span's length minus the real span's, in characters. `alt_fake_2` and `alt_fake_3` hold the alternate fabricated spans, which replace `real_span` in `answer_real` exactly as the main fake does. It refuses to overwrite a sheet that already has entries in `keep` or `notes`.

```sh
cd research/dataset_generation
../.venv/bin/python make_review.py
```

`flags` gathers everything worth a second look: `length_ratio_…` (the fake is much shorter or longer than the real span, a possible tell), the same for an alternate (`alt2:…`, `alt3:…`), `crossref_year_…` (the cited year is one off Crossref's), and `claim_wrong` or `claim_unverified` from the fact check below.

`research/data/claims_v1.csv` is an advisory fact check of every other claim in each real answer (dates, co-authors, superlatives), since stage 1 verifies only `real_span`. Four Claude subagents (`claude-opus-5-5`, one per type) read the stage 1 revision of each cited article, the Crossref record for citations, and other English Wikipedia pages, and recorded `ok`, `wrong` (a source contradicts the claim) or `unverified`, with the claim and a short quote as evidence. Three more subagents checked the 80 top-up candidates the same way (all `ok`). Treat it as a pointer, not a verdict.

Review rows flagged `wrong` or `unverified` were rewritten to fix the flagged claim using only facts confirmed in each row's own source (the cited Wikipedia article, or the Crossref record for citations), keeping `real_span` and the 25 to 60 word rule. `claims_v1.csv` logs each rewrite in `answer_real_before` and `answer_real_after`; their fakes were rebuilt with `make_fakes.py --rejudge` from the same logged replies, and a fresh fact check of the new answers is in `recheck_verdict`, `recheck_claim` and `recheck_evidence`. Flags follow the recheck when there is one.

## Attention checks

`research/data/attention_checks_v1.csv` holds 4 attention checks written by Claude (`claude-opus-5-5`) in a Claude Code session, one per type, each with an obviously absurd fabricated span ("four hundred thousand" legs, "a bowl of tomato soup"). They are complete import rows and pass the importer's rules, including the real-span rule.

## Final v1 dataset: `research/data/pairs_v1.csv`

**Frozen.** SHA-256 `e5bf5fbfb80f88ad7348ff293240fdf5b3b5854eaffb0d179a43a603dd19c9d6`. 84 rows in the import format: 80 pairs and 4 attention checks, all with `dataset_version` `v1` and the UUIDs from stage 1.

```sh
cd research/dataset_generation
../.venv/bin/python finalize.py check     # validate review_v1.csv, reading only id, keep and notes
../.venv/bin/python finalize.py select    # research/data/selection_v1.csv
../.venv/bin/python finalize.py explain   # research/data/explanations_v1.csv
../.venv/bin/python finalize.py build     # research/data/pairs_v1.csv, with its SHA-256
```

Every field except `keep` and `notes` comes from the pipeline's own data, matched by `id`. Each type gets 20 pairs split 7/7/6, and the category with the fewest kept rows gets 6 (a tie goes to the earlier of science, geography, history). Every kept row has a note written by `combine`, so the preference for empty notes had no effect, and rows were drawn at random with seed 20261103. Where `keep` is `alt2` or `alt3`, that alternate is the fake (4 `alt2`, 3 `alt3`). 8 of the 20 citation fakes are longer than the real title, inside the 8 to 12 rule, so no length swaps were needed.

| Type | science | geography | history | Total |
|---|---|---|---|---|
| `wrong_number` | 7 | 7 | 6 | 20 |
| `wrong_entity` | 7 | 7 | 6 | 20 |
| `wrong_date` | 7 | 6 | 7 | 20 |
| `invented_citation` | 6 | 7 | 7 | 20 |

The 4 attention checks (one per type) are added unchanged apart from their explanations. Each explanation has at most 30 words and names the real value and its source; it contains `real_span` exactly once and no number or date that is not in `answer_real` or the source title. `Explanations` in `tests/dataset_test.py` enforces both rules on all 84.

Artifact check on the final 80 (attention checks excluded), written to `research/data/artifact_check_final_v1.json`. Every interval includes 50%, so no swaps were made:

| | Pairs | Accuracy | 95% CI | |
|---|---|---|---|---|
| Overall | 80 | 46.2% | [35.7%, 57.1%] | pass |
| `wrong_number` | 20 | 50.0% | [29.9%, 70.1%] | pass |
| `wrong_entity` | 20 | 40.0% | [21.9%, 61.3%] | pass |
| `wrong_date` | 20 | 40.0% | [21.9%, 61.3%] | pass |
| `invented_citation` | 20 | 40.0% | [21.9%, 61.3%] | pass |

`research/import_pairs.py --dry-run` on `pairs_v1.csv`, with `DATABASE_URL` set to a throwaway local PostgreSQL 17 database with both migrations applied: 84 valid rows, 0 invalid, nothing written. An import into that same throwaway database also accepted all 84 rows under the schema's constraints. Nothing has been imported into a real Supabase project.

`tests/dataset-v1.test.ts` builds rounds from the real v1 pool with `lib/round-builder.ts`: 1,000 seeded paired rounds and 1,000 seeded single rounds with random exposure counts. Every round has 10 items with exactly one attention check and each type 2 or 3 times. No category has more than 3 of the 9 ordinary items, so the category cap holds. Single rounds show the fake on 4 (486 rounds) or 5 (514 rounds) of the 9 ordinary items, and the attention check always shows its fake. The extra type slot is spread evenly (487 to 516 per type), and all 80 pairs appear (183 to 275 times each).

## Tests

```sh
research/.venv/bin/python -m unittest discover -s tests -p '*_test.py'
```

`tests/dataset_test.py` mocks every Wikipedia, Wikidata and Crossref call.

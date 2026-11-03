"""Stage 2: ask a small local model for 3 fabricated replacements of each real_span, keep only those that pass.

Every replacement and its verdict go to research/data/fakes_v1_attempts.csv; candidates with at least one passing
replacement go to research/data/fakes_v1.csv and the rest to research/data/fakes_v1_failed.csv.
"""

import argparse
import collections
import hashlib
import json
import re
import sys
import unicodedata
import urllib.request
from datetime import date

import common

# Phi is not one of the families evaluated later (Gemma, Llama, Qwen).
MODEL = {
    "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
    "revision": "a64113399c2f6b8ad3e11c394733a2ddadaa7f33",
    "file": "Phi-3-mini-4k-instruct-q4.gguf",
    "sha256": "8a83c7fb9049a9b2e92266fa7ad04933bb53aa1e85136b7b30f1b8000ff2edef",
}
MODEL_NAME = f"{MODEL['repo']}/{MODEL['file']}"
MODEL_PATH = common.HERE / "models" / MODEL["file"]
# Fixed for reproducibility: the seed is reset for every candidate, and CPU thread count affects float summation order.
SEED = 20261101
# Citations are asked twice, 3 replacements per ask, with these two seeds; every other type once with SEED.
CITATION_SEEDS = (20261101, 20261102)
TEMPERATURE = 0.7
TOP_P = 0.95
MAX_TOKENS = 256
N_THREADS = 6
CANDIDATES = common.DATA / "candidates_v1.csv"
SOURCES = common.DATA / "sources_v1.csv"
FAKES = common.DATA / "fakes_v1.csv"
FAILED = common.DATA / "fakes_v1_failed.csv"
CLAIMS = common.DATA / "claims_v1.csv"
ATTEMPTS = common.DATA / "fakes_v1_attempts.csv"
FAKE_FIELDS = (
    "id",
    "hallucination_type",
    "category",
    "question",
    "answer_real",
    "real_span",
    "answer_fake",
    "fabricated_span",
    "alt_fake_2",
    "alt_fake_3",
    "source_url",
    "source_revision",
    "flags",
    "model_name",
)
SCHEMA = {
    "type": "object",
    "properties": {
        "replacements": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        }
    },
    "required": ["replacements"],
}
RULES = {
    "wrong_number": 'Each must be a different, believable number written with exactly the pattern "{pattern}", where each # stands for one digit: the same separators and decimal places, with no units or words added. Avoid round numbers.',
    "wrong_date": 'Each must be a different, believable date written in exactly the same format as "{span}" and no more than 30 years away from it.',
    "wrong_entity": 'Each must be the name of a different, real {kind} that has its own English Wikipedia article, so it is the same kind of thing as "{span}". Give the name only.',
    "invented_citation": 'Each must be an invented title of a publication that does not exist, exactly {words} words long like "{span}": keep its small words (such as "of", "the", "and", "for") and its punctuation in the same places, and replace every other word with a different word of about the same length on a related topic, with the same capitalization. Never use the title of a real work.',
}
PROMPT = (
    "You are helping build a research quiz about spotting AI hallucinations.\n\n"
    "Question: {question}\nCorrect answer: {answer}\n\n"
    'Write 3 different wrong replacements for the exact text "{span}" in the correct answer. {rule} '
    "Each replacement must read naturally when swapped into the answer, so that a careful reader might believe it. "
    "Give only the replacement text, not the whole answer. {reply}"
)
REPLY = 'Reply in JSON as {"replacements": ["...", "...", "..."]}.'
SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "in",
    "into",
    "its",
    "of",
    "on",
    "or",
    "over",
    "the",
    "their",
    "to",
    "under",
    "with",
    "between",
    "among",
    "via",
}


def prompt(row, kind="thing"):
    """kind names what an entity is (from Wikidata), so the model is told what the replacements must be."""
    span = row["real_span"]
    rule = RULES[row["hallucination_type"]].format(span=span, pattern=re.sub(r"\d", "#", span), kind=kind, words=len(span.split()))
    return PROMPT.format(question=row["question"], answer=row["answer_real"], span=span, rule=rule, reply=REPLY)


def entity_kind(span):
    """'person' for humans, else the real entity's first two Wikidata instance-of labels ('city or capital city')."""
    found = common.wikidata_entity(span)
    if not found:
        return "thing"
    if "Q5" in found[1]:
        return "person"
    return " or ".join(common.wikidata_labels(sorted(found[1])[:2])) or "thing"


def parse_replacements(text):
    """Up to 3 distinct, stripped replacement strings from the model's JSON reply."""
    try:
        items = json.loads(text).get("replacements", [])
    except (json.JSONDecodeError, AttributeError):
        return []
    seen = []
    for item in items:
        value = str(item).strip().strip("\"“”'").strip()
        if value and value.casefold() not in (s.casefold() for s in seen):
            seen.append(value)
    return seen[:3]


def _values(span):
    """Every number in the span, so 3-5 and 3-7 differ."""
    return [float(n) for n in common.NUMBER.findall(span.replace(",", ""))]


def is_round(span):
    """Ends in a zero (2,300 or 130) with no nonzero decimals; 54 and 146.6 are not round."""
    whole, _, decimals = re.sub(r"[^\d.]", "", span).partition(".")
    return not decimals.strip("0") and len(whole) >= 2 and whole.endswith("0")


def number_errors(real, fake):
    if re.sub(r"\d", "0", fake) != re.sub(r"\d", "0", real):
        return ["number: unit, formatting or digit count differs"]
    # Only the start of a number counts: 1,052 has a thousands group that starts with 0, not a leading zero.
    if re.search(r"(?<![\d.,])0\d", fake):
        return ["number: leading zero"]
    if _values(fake) == _values(real):
        return ["number: same value as the real span"]
    if is_round(fake) and not is_round(real):
        return ["number: round number for a non-round real value"]
    return []


def _written(parsed):
    form, year, month, day = parsed
    name = common.MONTHS[month - 1].capitalize() if month else ""
    return {
        "year": str(year),
        "dmy": f"{day} {name} {year}",
        "mdy": f"{name} {day}, {year}",
    }[form]


def date_errors(real, fake):
    r, f = common.parse_date(real), common.parse_date(fake)
    if not r:
        return ["date: real span is not in a supported date format"]
    if not f or f[0] != r[0] or _written(f) != fake.strip():
        return ["date: format or precision differs"]
    if not common.valid_date(f):
        return ["date: not a real calendar date"]
    if f[1:] == r[1:]:
        return ["date: same as the real span"]
    apart = abs((date(*f[1:]) - date(*r[1:])).days) / 365.2425 if r[0] != "year" else abs(f[1] - r[1])
    if apart > 30:
        return ["date: more than 30 years from the real date"]
    return []


def entity_errors(real, fake, lookup):
    found_real, found_fake = lookup(real), lookup(fake)
    if not found_real:
        return ["entity: real span has no unambiguous Wikipedia article"]
    if not found_fake:
        return ["entity: fake has no unambiguous Wikipedia article"]
    if found_fake[0] == found_real[0]:
        return ["entity: names the same thing as the real span"]
    if not found_real[1] & found_fake[1]:
        return ["entity: not the same kind of thing (Wikidata instance-of differs)"]
    return []


def citation_style(title):
    """(title case or sentence case, has a subtitle colon, ends in punctuation); acronyms are ignored."""
    words = re.findall(r"[^\W\d_][\w'’-]*", title)
    content = [
        w
        for w in words[1:]
        if w.lower() not in SMALL_WORDS and not (len(w) > 1 and w.isupper())
    ]
    case = (
        "title"
        if content and sum(w[0].isupper() for w in content) / len(content) >= 0.6
        else "sentence"
    )
    return case, ":" in title, title.rstrip()[-1:] in ".?!"


def punctuation(text):
    """Every punctuation character, in order: hyphens, dashes, colons, commas, apostrophes, slashes and the rest."""
    return [c for c in text if unicodedata.category(c).startswith("P")]


def original_answers():
    """Answers rewritten after the fact check, keyed by id: generation keeps the answer the model first saw, and every
    check runs against the rewritten answer."""
    return {c["id"]: c["answer_real_before"] for c in common.read_csv(CLAIMS) if c.get("answer_real_before")} if CLAIMS.exists() else {}


def seeds(row):
    return CITATION_SEEDS if row["hallucination_type"] == "invented_citation" else (SEED,)


def citation_errors(real, fake, search):
    if citation_style(fake) != citation_style(real):
        return [
            "citation: format differs (capitalisation, subtitle colon or final punctuation)"
        ]
    if punctuation(fake) != punctuation(real):
        return ["citation: punctuation differs from the real title"]
    # A fake title shorter or longer than the real one is a surface tell (stage 3 found shorter fakes in the first runs).
    if not 0.85 <= len(fake) / len(real) <= 1.15:
        return ["citation: length outside 0.85 to 1.15 times the real title"]
    if any(common.same_title(fake, found) for found in search(fake)):
        return ["citation: Crossref finds a work with this title"]
    return []


def check(
    row, fake, source_text, lookup=common.wikidata_entity, search=common.crossref_titles
):
    """(errors, flags) for one replacement; any error rejects it, flags are kept for review."""
    real, kind = row["real_span"], row["hallucination_type"]
    if common.normalize(fake) == common.normalize(real):
        return ["same as the real span"], []
    if common.appears(fake, row["answer_real"]):
        return ["fabricated span already appears in the real answer"], []
    if kind == "wrong_number":
        errors = number_errors(real, fake)
    elif kind == "wrong_date":
        errors = date_errors(real, fake)
    elif kind == "wrong_entity":
        errors = entity_errors(real, fake, lookup)
    else:
        errors = citation_errors(real, fake, search)
    # DOI-sourced citations have no article text; Crossref's title check covers them.
    if source_text and common.appears(fake, source_text):
        errors.append("fabricated span appears in the source article")
    errors += common.import_errors(
        row, row["answer_real"].replace(real, fake, 1), fake, MODEL_NAME
    )
    ratio = len(fake) / len(real)
    return errors, [] if 0.7 <= ratio <= 1.3 else [f"length_ratio_{ratio:.2f}"]


def judge(row, replacements, source_text, asked_with=(), **lookups):
    """Attempt log rows plus the kept replacements in reply order; asked_with gives each replacement's seed."""
    attempts, kept = [], []
    for rank, fake in enumerate(replacements, 1):
        errors, flags = check(row, fake, source_text, **lookups)
        attempts.append(
            {
                "id": row["id"],
                "rank": rank,
                "seed": asked_with[rank - 1] if asked_with else "",
                "replacement": fake,
                "status": "rejected" if errors else "kept",
                "reasons": "; ".join(errors),
                "flags": ";".join(flags),
            }
        )
        if not errors:
            kept.append((fake, flags))
    return attempts, kept


def ensure_model():
    """Download the pinned model file once and refuse any file whose SHA-256 differs."""
    if not MODEL_PATH.exists():
        MODEL_PATH.parent.mkdir(exist_ok=True)
        url = f"https://huggingface.co/{MODEL['repo']}/resolve/{MODEL['revision']}/{MODEL['file']}"
        partial = MODEL_PATH.with_suffix(".part")
        with (
            urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": common.USER_AGENT})
            ) as response,
            open(partial, "wb") as target,
        ):
            while chunk := response.read(1 << 20):
                target.write(chunk)
        partial.rename(MODEL_PATH)
    digest = hashlib.sha256()
    with open(MODEL_PATH, "rb") as source:
        while chunk := source.read(1 << 20):
            digest.update(chunk)
    if digest.hexdigest() != MODEL["sha256"]:
        raise SystemExit(
            f"{MODEL_PATH} has SHA-256 {digest.hexdigest()}, expected {MODEL['sha256']}"
        )


def evaluate(row, source, replacements, asked_with=(), **lookups):
    """Check one candidate's replacements against the stage 1 revision of its source (runs in a worker thread)."""
    title = common.wikipedia_title(row["source_url"])
    source_text = common.wikipedia_page(revision=source["source_revision"])["text"] if title else ""
    logged, kept = judge(row, replacements, source_text, asked_with, **lookups)
    if row["hallucination_type"] == "invented_citation":
        # The passing title closest in length to the real one is the main fake, then the next closest, so length gives least away.
        kept.sort(key=lambda k: abs(len(k[0]) - len(row["real_span"])))
    if not logged:
        logged = [{"id": row["id"], "rank": 0, "seed": "", "replacement": "", "status": "rejected", "reasons": "model reply had no usable replacements", "flags": ""}]
    if not kept:
        return logged, None, {**row, "reason": " | ".join(f"{a['replacement']}: {a['reasons']}" for a in logged)}
    (fake, flags), alternates = kept[0], kept[1:]
    flags = [f for f in source["flags"].split(";") if f] + flags + [f"alt{n}:{f}" for n, (_, alt_flags) in enumerate(alternates, 2) for f in alt_flags]
    fake_row = {**row, "answer_fake": row["answer_real"].replace(row["real_span"], fake, 1), "fabricated_span": fake, "alt_fake_2": alternates[0][0] if alternates else "", "alt_fake_3": alternates[1][0] if len(alternates) > 1 else "", "source_revision": source["source_revision"], "flags": ";".join(flags), "model_name": MODEL_NAME}
    return logged, fake_row, None


def generate(rows, sources):
    """Ask the model (once, or twice for citations) and check the replies as they arrive."""
    from concurrent.futures import ThreadPoolExecutor

    from llama_cpp import Llama

    ensure_model()
    llm = Llama(str(MODEL_PATH), n_ctx=2048, n_threads=N_THREADS, n_gpu_layers=0, seed=SEED, verbose=False)
    original = original_answers()
    # Generation stays sequential on the CPU; source fetches and checks overlap with it in a few polite threads.
    with ThreadPoolExecutor(max_workers=4) as pool:
        kinds = dict(zip((r["id"] for r in rows), pool.map(lambda r: entity_kind(r["real_span"]) if r["hallucination_type"] == "wrong_entity" else "thing", rows)))
        jobs = []
        for number, row in enumerate(rows, 1):
            asked = []
            for seed in seeds(row):
                shown = {**row, "answer_real": original.get(row["id"], row["answer_real"])}
                reply = llm.create_chat_completion(messages=[{"role": "user", "content": prompt(shown, kinds[row["id"]])}], temperature=TEMPERATURE, top_p=TOP_P, max_tokens=MAX_TOKENS, seed=seed, response_format={"type": "json_object", "schema": SCHEMA})
                for text in parse_replacements(reply["choices"][0]["message"]["content"]):
                    if text.casefold() not in (t.casefold() for t, _ in asked):
                        asked.append((text, seed))
            jobs.append(pool.submit(evaluate, row, sources[row["id"]], [t for t, _ in asked], [s for _, s in asked]))
            print(f"{number}/{len(rows)} generated", flush=True)
        return [job.result() for job in jobs]


def rejudge(rows, sources):
    """Re-check each row's logged replies, with their original order and seeds, against its current answer_real; no model."""
    logged = collections.defaultdict(list)
    for a in common.read_csv(ATTEMPTS):
        if a["replacement"]:
            logged[a["id"]].append(a)
    results = []
    for row in rows:
        replies = sorted(logged[row["id"]], key=lambda a: int(a["rank"]))
        results.append(evaluate(row, sources[row["id"]], [a["replacement"] for a in replies], [int(a.get("seed") or SEED) for a in replies]))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--types", nargs="+", choices=common.TYPES, help="regenerate only these types; other rows are kept as they are")
    parser.add_argument("--ids", nargs="+", help="regenerate only these candidate ids; other rows are kept as they are")
    parser.add_argument("--rejudge", nargs="+", metavar="ID", help="re-check these ids' logged replies against their current answer_real, without the model")
    args = parser.parse_args(argv)
    sources = {s["id"]: s for s in common.read_csv(SOURCES) if s["status"] == "pass"}
    passing = [r for r in common.read_csv(CANDIDATES) if r["id"] in sources]
    chosen = set(args.ids or []) | set(args.rejudge or [])
    rows = [r for r in passing if (not args.types or r["hallucination_type"] in args.types) and (not chosen or r["id"] in chosen)]
    # A subset run reuses a different prompt cache than a full run, so its sampling can differ: the attempts log is the record.
    results = rejudge(rows, sources) if args.rejudge else generate(rows, sources)
    partial = bool(args.types or chosen)
    order = {r["id"]: n for n, r in enumerate(passing)}
    redone = {r["id"] for r in rows}
    kept = lambda path: [{"seed": str(SEED), **r} for r in common.read_csv(path) if r["id"] in order and r["id"] not in redone] if partial and path.exists() else []
    attempts = sorted(kept(ATTEMPTS) + [a for logged, _, _ in results for a in logged], key=lambda a: (order[a["id"]], int(a["rank"])))
    fakes = sorted(kept(FAKES) + [fake for _, fake, _ in results if fake], key=lambda r: order[r["id"]])
    failed = sorted(kept(FAILED) + [fail for _, _, fail in results if fail], key=lambda r: order[r["id"]])
    common.write_csv(FAKES, fakes, FAKE_FIELDS)
    common.write_csv(FAILED, failed, ("id", "hallucination_type", "category", "question", "real_span", "source_url", "reason"))
    common.write_csv(ATTEMPTS, attempts, ("id", "rank", "seed", "replacement", "status", "reasons", "flags"))
    counts = collections.Counter((f["hallucination_type"], f["category"]) for f in fakes)
    for kind in common.TYPES:
        print(f"{kind:18}", "  ".join(f"{c} {counts[kind, c]}" for c in common.CATEGORIES))
    print(f"{len(fakes)} of {len(passing)} candidates have a passing fake ({len(rows)} {'re-checked' if args.rejudge else 'regenerated'}); failures in {FAILED.name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

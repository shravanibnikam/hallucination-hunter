"""Stage 1: check every candidate against the format rules and its source.

Failures go to research/data/candidates_v1_failed.csv with their reasons; every candidate's status and the
exact source revision checked go to research/data/sources_v1.csv for the later stages.
"""

import collections
import re
import sys

import common

CANDIDATES = common.DATA / "candidates_v1.csv"
FAILED = common.DATA / "candidates_v1_failed.csv"
SOURCES = common.DATA / "sources_v1.csv"
FIELDS = (
    "id",
    "hallucination_type",
    "category",
    "question",
    "answer_real",
    "real_span",
    "source_url",
)
PLACEHOLDER = "⟨fabricated⟩"
# Lowercase "may" only: May the month is not a hedge.
HEDGES = re.compile(
    r"\b(?i:approximately|about|around|roughly|nearly|almost|perhaps|possibly|probably|likely|might|could|believed|estimated|reportedly|arguably|apparently|supposedly)\b|\bmay\b"
)
ABBREVIATIONS = {"st", "mt", "dr", "mr", "mrs", "ms", "jr", "sr", "no", "vs"}


def sentence_count(text):
    count = 0
    for match in re.finditer(r'[.!?]+(?=\s+["“(]?[A-Z]|["”)]?\s*$)', text):
        word = re.search(r"(\w+)\W*$", text[: match.start()])
        # Initials (S. Grant) and abbreviations (St. Helens) do not end a sentence; Roman numeral I (World War I.) does.
        if word and (
            (len(word.group(1)) == 1 and word.group(1).isupper() and word.group(1) != "I")
            or word.group(1).lower() in ABBREVIATIONS
        ):
            continue
        count += 1
    return count


def local_errors(row):
    """Format rules, plus the importer's own rules on a row completed with a placeholder fake."""
    answer, span = row["answer_real"], row["real_span"]
    errors = common.import_errors(
        row, answer.replace(span, PLACEHOLDER, 1) if span else answer, PLACEHOLDER
    )
    if row["hallucination_type"] not in common.TYPES:
        errors.append("hallucination_type: must be one of " + ", ".join(common.TYPES))
    if row["category"] not in common.CATEGORIES:
        errors.append("category: must be one of " + ", ".join(common.CATEGORIES))
    words = len(answer.split())
    if not 25 <= words <= 60:
        errors.append(f"answer_real: {words} words, needs 25 to 60")
    if not 1 <= (sentences := sentence_count(answer)) <= 3:
        errors.append(f"answer_real: {sentences} sentences, needs 1 to 3")
    if hedge := HEDGES.search(answer):
        errors.append(f'answer_real: hedging word "{hedge.group(0)}"')
    if row["hallucination_type"] == "wrong_date" and not common.parse_date(row["real_span"]):
        errors.append('real_span: dates must read "20 July 1969", "July 20, 1969" or "1969"')
    citation = row["hallucination_type"] == "invented_citation"
    if not common.wikipedia_title(row["source_url"]) and not (
        citation and common.doi_of(row["source_url"])
    ):
        errors.append(
            "source_url: must be an English Wikipedia article"
            + (" or a DOI link" if citation else "")
        )
    return errors


def source_check(row):
    """(errors, revision, flags): the real span must appear in the Wikipedia article, or the cited work must exist in Crossref."""
    errors, flags, revision = [], [], ""
    title, doi = (
        common.wikipedia_title(row["source_url"]),
        common.doi_of(row["source_url"]),
    )
    if title:
        page = common.wikipedia_page(title)
        if not page:
            return ["source: Wikipedia article not found"], "", []
        revision = page["revision"]
        if not common.appears(row["real_span"], page["text"]):
            errors.append("source: real_span not found in the Wikipedia article")
    if row["hallucination_type"] != "invented_citation":
        return errors, revision, flags
    if doi:
        work = common.crossref_work(doi)
        if not work:
            return ["source: DOI not found in Crossref"], "", []
        revision = doi
        found = common.html_text((work.get("title") or [""])[0])
        if not common.same_title(row["real_span"], found):
            errors.append(f'source: Crossref title differs ("{found}")')
        family = ((work.get("author") or [{}])[0].get("family") or "").strip()
        if family and family.casefold() not in row["answer_real"].casefold():
            errors.append(f'source: first author "{family}" not named in the answer')
        year = next(
            iter((work.get("issued") or {}).get("date-parts", [[None]])[0]), None
        )
        if year and str(year) not in row["answer_real"]:
            if any(str(y) in row["answer_real"] for y in (year - 1, year + 1)):
                flags.append(f"crossref_year_{year}")
            else:
                errors.append(f"source: Crossref year {year} not in the answer")
    elif not any(
        common.same_title(row["real_span"], found)
        for found in common.crossref_titles(row["real_span"])
    ):
        errors.append("source: work not found in Crossref")
    return errors, revision, flags


def main(offline=False):
    rows = common.read_csv(CANDIDATES)
    seen_ids, seen_questions = set(), set()
    failed, sources = [], []
    for row in rows:
        errors = local_errors(row)
        if row["id"] in seen_ids:
            errors.append("id: duplicate")
        if row["question"].casefold() in seen_questions:
            errors.append("question: duplicate")
        seen_ids.add(row["id"])
        seen_questions.add(row["question"].casefold())
        revision, flags = "", []
        if not offline and not errors:
            source_errors, revision, flags = source_check(row)
            errors += source_errors
        if errors:
            failed.append({**row, "reason": "; ".join(errors)})
        sources.append(
            {
                "id": row["id"],
                "status": "fail" if errors else "pass",
                "source_revision": revision,
                "flags": ";".join(flags),
            }
        )
    if offline:
        for row in failed:
            print(row["id"], row["reason"])
        return int(bool(failed))
    common.write_csv(FAILED, failed, (*FIELDS, "reason"))
    common.write_csv(SOURCES, sources, ("id", "status", "source_revision", "flags"))
    passed = {s["id"] for s in sources if s["status"] == "pass"}
    counts = collections.Counter(
        (r["hallucination_type"], r["category"], r["id"] in passed) for r in rows
    )
    for kind in common.TYPES:
        cells = [
            f"{c} {counts[kind, c, True]}/{counts[kind, c, True] + counts[kind, c, False]}"
            for c in common.CATEGORIES
        ]
        print(f"{kind:18}", "  ".join(cells))
    print(f"{len(passed)} of {len(rows)} candidates passed; failures in {FAILED.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(offline="--offline" in sys.argv))

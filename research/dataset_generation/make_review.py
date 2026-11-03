"""Stage 4: write research/data/review_v1.csv, one row per candidate with a passing fake, for the review.

Rows are sorted by hallucination_type, then category. keep and notes start empty and are filled in by finalize.py combine from the two independent AI review passes
(see the README). Flags include claim_wrong or claim_unverified from research/data/claims_v1.csv, the fact check
of each answer's other claims. The script refuses to overwrite a sheet that already has review entries.
"""

import collections
import sys

import common

FAKES = common.DATA / "fakes_v1.csv"
CLAIMS = common.DATA / "claims_v1.csv"
REVIEW = common.DATA / "review_v1.csv"
FIELDS = (
    "id",
    "hallucination_type",
    "category",
    "question",
    "answer_real",
    "answer_fake",
    "real_span",
    "fabricated_span",
    "length_diff",
    "alt_fake_2",
    "alt_fake_3",
    "source_url",
    "flags",
    "keep",
    "notes",
)


def review_rows(fakes, claims=()):
    """Answers whose other claims the fact check found wrong or unverified get a claim_wrong / claim_unverified flag."""
    # A recheck after a rewrite replaces the original verdict.
    verdicts = {c["id"]: c.get("recheck_verdict") or c["verdict"] for c in claims}
    verdicts = {i: v for i, v in verdicts.items() if v != "ok"}
    rows = []
    for row in fakes:
        flags = [f for f in row["flags"].split(";") if f] + ([f"claim_{verdicts[row['id']]}"] if row["id"] in verdicts else [])
        rows.append({**row, "length_diff": len(row["fabricated_span"]) - len(row["real_span"]), "flags": ";".join(flags), "keep": "", "notes": ""})
    return sorted(rows, key=lambda r: (r["hallucination_type"], r["category"], r["question"]))


def main():
    if REVIEW.exists() and any(
        r["keep"] or r["notes"] for r in common.read_csv(REVIEW)
    ):
        raise SystemExit(
            f"{REVIEW.name} already has review entries; move it aside before regenerating it."
        )
    rows = review_rows(common.read_csv(FAKES), common.read_csv(CLAIMS) if CLAIMS.exists() else [])
    common.write_csv(REVIEW, rows, FIELDS)
    counts = collections.Counter(r["hallucination_type"] for r in rows)
    print(
        ", ".join(f"{kind} {counts[kind]}" for kind in common.TYPES),
        f"({len(rows)} rows in {REVIEW.name})",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

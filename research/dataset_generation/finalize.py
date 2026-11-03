"""Final v1 selection, one subcommand per step:

combine   both review passes -> keep and notes in review_v1.csv (kept only when the passes agree)
check     validate review_v1.csv (reads only id, keep and notes) and count kept rows
select    choose 80 pairs, 20 per type split 7/7/6 by category -> selection_v1.csv
explain   write an explanation for each selected pair and attention check -> explanations_v1.csv
build     write pairs_v1.csv in the import format and print its SHA-256
"""

import collections
import hashlib
import random
import re
import sys

import common
import make_fakes

REVIEW = common.DATA / "review_v1.csv"
PASSES = common.DATA / "review_v1_passes.csv"
SELECTION = common.DATA / "selection_v1.csv"
EXPLANATIONS = common.DATA / "explanations_v1.csv"
ATTENTION = common.DATA / "attention_checks_v1.csv"
PAIRS = common.DATA / "pairs_v1.csv"
SEED = 20261103
PER_TYPE = 20
KEEP_VALUES = {"yes", "no", "alt2", "alt3", ""}
CHOICE_FIELD = {"yes": "fabricated_span", "alt2": "alt_fake_2", "alt3": "alt_fake_3"}
PAIR_FIELDS = (
    "id",
    "question",
    "category",
    "answer_real",
    "answer_fake",
    "fabricated_span",
    "real_span",
    "hallucination_type",
    "explanation",
    "source_url",
    "model_name",
    "origin",
    "is_attention_check",
    "is_active",
    "dataset_version",
)
# Attention checks are hand-made absurd items, so their explanations are fixed text rather than a template.
ATTENTION_EXPLANATIONS = {
    "eight": "Wikipedia's article on spiders says a spider has eight legs. This deliberately absurd answer checks attention.",
    "the Pacific Ocean": "Wikipedia confirms that the largest ocean on Earth is the Pacific Ocean. This deliberately absurd answer checks attention.",
    "1945": "Wikipedia's article on World War II gives 1945 as the year the war ended. This deliberately absurd answer checks attention.",
    "Hamlet": "Wikipedia confirms that Hamlet is the Shakespeare play about a Danish prince. This deliberately absurd answer checks attention.",
}


def pipeline():
    """Every field except keep and notes comes from the pipeline's own data, matched by id."""
    return {r["id"]: r for r in common.read_csv(make_fakes.FAKES)}


def combine():
    passes = collections.defaultdict(dict)
    for p in common.read_csv(PASSES):
        passes[p["id"]][p["pass"]] = p
    rows = common.read_csv(REVIEW)
    fields = list(rows[0])
    for row in rows:
        a, b = passes[row["id"]]["A"], passes[row["id"]]["B"]
        if a["decision"] == b["decision"] != "no":
            row["keep"], row["notes"] = (
                a["decision"],
                f"Both passes chose {a['decision']}: every claim quoted from the source and the fake passed.",
            )
        elif a["decision"] == b["decision"]:
            row["keep"], row["notes"] = "no", f"Both passes chose no: {a['reason']}"
        else:
            row["keep"], row["notes"] = (
                "no",
                f"Passes disagreed (A {a['decision']}, B {b['decision']}): {(a if a['decision'] == 'no' else b)['reason']}",
            )
    common.write_csv(REVIEW, rows, fields)


def check():
    """(kept rows with their chosen fake, problems); only id, keep and notes are read from the review sheet."""
    data, kept, problems = pipeline(), [], []
    for row in common.read_csv(REVIEW):
        rid, keep, notes = row["id"], row["keep"].strip(), row["notes"].strip()
        if keep not in KEEP_VALUES:
            problems.append(
                f"{rid}: keep value {keep!r} is not yes, no, alt2, alt3 or empty"
            )
        elif rid not in data:
            problems.append(f"{rid}: id not in the pipeline data")
        elif keep in CHOICE_FIELD and not data[rid][CHOICE_FIELD[keep]]:
            problems.append(f"{rid}: keep is {keep} but that alternate does not exist")
        elif keep in CHOICE_FIELD:
            fake = data[rid][CHOICE_FIELD[keep]]
            kept.append(
                {
                    **data[rid],
                    "choice": keep,
                    "chosen_fake": fake,
                    "length_diff": len(fake) - len(data[rid]["real_span"]),
                    "notes": notes,
                }
            )
    return kept, problems


def quotas(available):
    """7/7/6 by category; the category with the fewest kept rows gets 6, and any shortfall moves to the others."""
    order = sorted(
        common.CATEGORIES, key=lambda c: (available[c], common.CATEGORIES.index(c))
    )
    want = {c: 7 for c in common.CATEGORIES}
    want[order[0]] = 6
    quota = {c: min(want[c], available[c]) for c in common.CATEGORIES}
    while sum(quota.values()) < PER_TYPE and any(
        quota[c] < available[c] for c in common.CATEGORIES
    ):
        spare = max(
            common.CATEGORIES,
            key=lambda c: (available[c] - quota[c], -common.CATEGORIES.index(c)),
        )
        quota[spare] += 1
    return quota


def select(kept, rng):
    """Per type and category: rows with empty notes first, then a seeded random order. Citations get 8 to 12 longer fakes."""
    chosen, report = [], []
    for kind in common.TYPES:
        pools = {
            c: [
                r
                for r in kept
                if r["hallucination_type"] == kind and r["category"] == c
            ]
            for c in common.CATEGORIES
        }
        for c in common.CATEGORIES:
            rng.shuffle(pools[c])
            pools[c].sort(key=lambda r: bool(r["notes"]))
        quota = quotas({c: len(pools[c]) for c in common.CATEGORIES})
        if sum(quota.values()) < PER_TYPE:
            raise SystemExit(f"{kind}: only {sum(quota.values())} kept rows")
        picked = {c: pools[c][: quota[c]] for c in common.CATEGORIES}
        if kind == "invented_citation":
            picked = balance_lengths(picked, pools, report)
        report.append(
            f"{kind}: " + ", ".join(f"{c} {quota[c]}" for c in common.CATEGORIES)
        )
        chosen += [r for c in common.CATEGORIES for r in picked[c]]
    return chosen, report


def balance_lengths(picked, pools, report, low=8, high=12):
    """Swap within a category until 8 to 12 of the 20 citation fakes are longer than the real title."""
    longer = lambda rows: sum(r["length_diff"] > 0 for rows_ in rows for r in rows_)
    while not low <= longer(picked.values()) <= high:
        need_longer = longer(picked.values()) < low
        for c in common.CATEGORIES:
            out = next(
                (
                    r
                    for r in reversed(picked[c])
                    if (r["length_diff"] > 0) != need_longer
                ),
                None,
            )
            into = next(
                (
                    r
                    for r in pools[c]
                    if r not in picked[c] and (r["length_diff"] > 0) == need_longer
                ),
                None,
            )
            if out and into:
                picked[c] = [into if r is out else r for r in picked[c]]
                report.append(
                    f"length balance: swapped {out['id'][:8]} for {into['id'][:8]} in {c}"
                )
                break
        else:
            raise SystemExit(
                "cannot reach 8 to 12 longer citation fakes with the kept rows"
            )
    return picked


def explanation(row):
    """At most 30 words, naming the real value and its source, with no number or date beyond the answer and source title."""
    span, kind = row["real_span"], row["hallucination_type"]
    if row.get("is_attention_check") == "true":
        return ATTENTION_EXPLANATIONS[span]
    if kind == "invented_citation":
        return f'The fabricated title does not exist. The real paper is "{span}", as listed in its Crossref record.'
    article = common.wikipedia_title(row["source_url"])
    if kind == "wrong_number":
        return f"Wikipedia's article on {article} gives the correct figure as {span}{unit_after(row)}."
    if kind == "wrong_date":
        return f"Wikipedia's article on {article} gives the correct date as {span}."
    return (
        f"Wikipedia's article on {article} confirms that the correct answer is {span}."
    )


UNITS = (
    "metres per second",
    "square kilometres",
    "degrees Celsius",
    "degrees Fahrenheit",
    "kilometres",
    "metres",
    "miles",
    "days",
    "years",
    "bones",
    "teeth",
    "chromosomes",
    "passengers",
    "people",
    "ships",
    "places",
    "soldiers",
    "casualties",
)


def unit_after(row):
    rest = row["answer_real"][
        row["answer_real"].index(row["real_span"]) + len(row["real_span"]) :
    ]
    return next((f" {u}" for u in UNITS if re.match(rf"\s+{u}\b", rest)), "")


def explanation_errors(row, text):
    """The rules the explanations must follow, shared by explain and the tests."""
    errors = []
    if len(text.split()) > 30:
        errors.append("more than 30 words")
    if text.count(row["real_span"]) != 1:
        errors.append("real_span must appear exactly once")
    title = common.wikipedia_title(row["source_url"]) or row["real_span"]
    allowed = set(
        common.NUMBER.findall(common.normalize(row["answer_real"] + " " + title))
    )
    extra = set(common.NUMBER.findall(common.normalize(text))) - allowed
    if extra:
        errors.append(
            "numbers not in answer_real or the source title: "
            + ", ".join(sorted(extra))
        )
    return errors


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "combine":
        combine()
        return 0
    kept, problems = check()
    counts = collections.Counter((r["hallucination_type"], r["category"]) for r in kept)
    for p in problems:
        print("PROBLEM", p)
    for kind in common.TYPES:
        print(
            f"{kind:18}",
            "  ".join(f"{c} {counts[kind, c]}" for c in common.CATEGORIES),
            " total",
            sum(counts[kind, c] for c in common.CATEGORIES),
        )
    if step == "check":
        return (
            1
            if problems
            or any(
                sum(counts[k, c] for c in common.CATEGORIES) < PER_TYPE
                for k in common.TYPES
            )
            else 0
        )
    if step == "select":
        chosen, report = select(kept, random.Random(SEED))
        print("\n".join(report))
        common.write_csv(
            SELECTION,
            chosen,
            (
                "id",
                "hallucination_type",
                "category",
                "choice",
                "chosen_fake",
                "length_diff",
            ),
        )
        return 0
    data = pipeline()
    selected = [
        {**data[s["id"]], "chosen_fake": s["chosen_fake"]}
        for s in common.read_csv(SELECTION)
    ]
    attention = common.read_csv(ATTENTION)
    if step == "explain":
        rows = [
            {"id": r["id"], "explanation": explanation(r)} for r in selected + attention
        ]
        bad = [
            (r["id"], e)
            for r, out in zip(selected + attention, rows)
            if (e := explanation_errors(r, out["explanation"]))
        ]
        if bad:
            raise SystemExit(f"explanations break the rules: {bad}")
        common.write_csv(EXPLANATIONS, rows, ("id", "explanation"))
        return 0
    if step == "build":
        explained = {e["id"]: e["explanation"] for e in common.read_csv(EXPLANATIONS)}
        pairs = [
            {
                **r,
                "answer_fake": r["answer_real"].replace(
                    r["real_span"], r["chosen_fake"], 1
                ),
                "fabricated_span": r["chosen_fake"],
                "explanation": explained[r["id"]],
                "origin": "synthetic",
                "is_attention_check": "false",
                "is_active": "true",
                "dataset_version": "v1",
            }
            for r in selected
        ]
        pairs += [{**r, "explanation": explained[r["id"]]} for r in attention]
        errors = [
            (p["id"], e) for p in pairs if (e := common.import_pairs.validate(p)[1])
        ]
        if errors:
            raise SystemExit(f"pairs fail the import rules: {errors}")
        common.write_csv(PAIRS, pairs, PAIR_FIELDS)
        print(
            f"{len(pairs)} rows in {PAIRS.name}; SHA-256 {hashlib.sha256(PAIRS.read_bytes()).hexdigest()}"
        )
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main())

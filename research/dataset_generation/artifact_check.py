"""Stage 3: can surface features alone pick the fake in a real/fake pair?

Each pair is put in a random order, and a logistic regression sees only the differences (first minus second) in
answer length, span length, digit count and punctuation count. Accuracy from 10-fold cross-validation gets a 95%
Wilson interval; the check passes if that interval includes 50%, meaning those features give no usable signal.

It runs once on all pairs and once per type, and passes only if every interval includes 50%. Run on all passing
candidates now (default input) and later on the final 80 with --input.
"""

import argparse
import json
import math
import random
import sys
import unicodedata

import common

SEED = 20261101
FEATURES = ("answer_length", "span_length", "digit_count", "punctuation_count")


def surface(answer, span):
    return (
        len(answer),
        len(span),
        sum(c.isdigit() for c in answer),
        sum(unicodedata.category(c).startswith("P") for c in answer),
    )


def pair_features(pairs, seed=SEED):
    """X: feature differences, first shown minus second; y: 1 when the fake is shown first.

    Exactly half the pairs show the fake first (shuffled), so pairs with no surface difference score 50%, not the
    share of a coin flip. Answers differ only in the span, so the answer and span length differences are equal.
    """
    order = [i < len(pairs) // 2 for i in range(len(pairs))]
    random.Random(seed).shuffle(order)
    X, y = [], []
    for (real_answer, real_span, fake_answer, fake_span), fake_first in zip(pairs, order):
        first, second = surface(fake_answer, fake_span), surface(real_answer, real_span)
        if not fake_first:
            first, second = second, first
        X.append([a - b for a, b in zip(first, second)])
        y.append(int(fake_first))
    return X, y


def wilson(correct, n, z=1.959964):
    p = correct / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def run(rows, folds=10, seed=SEED):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X, y = pair_features(
        [
            (r["answer_real"], r["real_span"], r["answer_fake"], r["fabricated_span"])
            for r in rows
        ],
        seed,
    )
    # No intercept and no centring: with order randomised, only the features themselves may predict the fake.
    model = make_pipeline(
        StandardScaler(with_mean=False), LogisticRegression(fit_intercept=False)
    )
    # Small subsets (one type) cannot have more folds than members of the smaller class.
    folds = min(folds, y.count(0), y.count(1))
    predicted = cross_val_predict(model, X, y, cv=StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed))
    hits = [int(p == t) for p, t in zip(predicted, y)]
    low, high = wilson(sum(hits), len(hits))
    return {
        "pairs": len(hits),
        "folds": folds,
        "seed": seed,
        "accuracy": sum(hits) / len(hits),
        "ci95": [low, high],
        "passes": low <= 0.5 <= high,
        "coefficients": dict(zip(FEATURES, (float(c) for c in model.fit(X, y)[-1].coef_[0]))),
    }


def check(rows):
    """One model on all pairs, and a separate model per type so a tell confined to one type cannot hide in the pool."""
    overall = run(rows)
    by_type = {kind: run([r for r in rows if r["hallucination_type"] == kind]) for kind in common.TYPES if any(r["hallucination_type"] == kind for r in rows)}
    return {"passes": overall["passes"] and all(t["passes"] for t in by_type.values()), "overall": overall, "by_type": by_type}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(common.DATA / "fakes_v1.csv"))
    parser.add_argument("--output", default=str(common.DATA / "artifact_check_v1.json"))
    args = parser.parse_args()
    result = {"input": args.input.split("research/")[-1], **check(common.read_csv(args.input))}
    with open(args.output, "w", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    for name, part in [("overall", result["overall"]), *result["by_type"].items()]:
        low, high = part["ci95"]
        print(f"{name:18} accuracy {part['accuracy']:.3f} on {part['pairs']:3} pairs, 95% CI [{low:.3f}, {high:.3f}]: {'PASS' if part['passes'] else 'FAIL'}")
    return 0 if result["passes"] else 1

if __name__ == "__main__":
    sys.exit(main())

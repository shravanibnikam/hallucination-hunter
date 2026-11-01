"""Dataset pipeline checks. Wikipedia, Wikidata, Crossref and the model are mocked; no network is used."""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "dataset_generation"))
import artifact_check
import check_sources
import common
import make_fakes
import make_review

ARTICLE = {
    "parse": {
        "title": "Iron",
        "revid": 42,
        "text": '<p>Pure iron melts at 1,538&nbsp;°C.<sup class="reference"><a>[45]</a></sup></p><p>Apollo landed on July 20, 1969, decades after 1946.<br/></p><table class="infobox"><tr><td>8,848.86 m</td></tr></table><style>.x{color:red}</style><ol class="references"><li>Smith 2003, p. 27</li></ol><p><b>Iron</b> is a metal.</p>',
    }
}
WORK = {
    "message": {
        "title": [
            "Molecular Structure of Nucleic Acids: A Structure for Deoxyribose Nucleic Acid"
        ],
        "author": [{"family": "WATSON"}],
        "issued": {"date-parts": [[1953, 4, 25]]},
    }
}
REAL = "Pure iron melts at 1,538 degrees Celsius, a temperature far higher than copper or tin, which is why early smiths worked bronze for centuries before they were able to cast iron in furnaces."
CITED = 'James Watson and Francis Crick proposed the double helix in their 1953 Nature paper "Molecular Structure of Nucleic Acids: A Structure for Deoxyribose Nucleic Acid", which drew on X-ray data.'


def responses(table):
    """A stand-in for common.get_json that answers by URL fragment."""

    def get(url, pause=0):
        for fragment, value in table.items():
            if fragment in url:
                return value
        raise AssertionError("unexpected request: " + url)

    return get


def candidate(**changes):
    row = {
        "id": "6f1c1d5e-8a4b-4c3d-9e2f-0a1b2c3d4e5f",
        "hallucination_type": "wrong_number",
        "category": "science",
        "question": "What is the melting point of iron?",
        "answer_real": REAL,
        "real_span": "1,538",
        "source_url": "https://en.wikipedia.org/wiki/Iron",
    }
    return {**row, **changes}


def citation(**changes):
    return candidate(
        **{
            "hallucination_type": "invented_citation",
            "answer_real": CITED,
            "real_span": "Molecular Structure of Nucleic Acids: A Structure for Deoxyribose Nucleic Acid",
            "source_url": "https://doi.org/10.1038/171737a0",
            **changes,
        }
    )


class SpanMatching(unittest.TestCase):
    def setUp(self):
        self.text = common.html_text(ARTICLE["parse"]["text"])

    def test_number_and_date_formatting(self):
        self.assertTrue(common.appears("149,597,870,700", "defined as 149 597 870 700 metres"))
        # A year followed by another number is not one spaced figure.
        self.assertFalse(common.appears("1,969,100", "on 20 July 1969 100 metres"))
        for span in (
            "1,538",
            "1538",
            "8,848.86",
            "20 July 1969",
            "July 20, 1969",
            "1969",
            "iron",
        ):
            with self.subTest(span=span):
                self.assertTrue(common.appears(span, self.text))
        # Whole numbers and whole words only: 46 is not 1946, 1,539 is not 1,538, and styles are not text.
        # Footnote markers ([45]) and reference lists (2003, p. 27) are not article content.
        for span in (
            "46",
            "1,539",
            "8,848",
            "21 July 1969",
            "Iro",
            "color",
            "45",
            "2003",
            "27",
        ):
            with self.subTest(span=span):
                self.assertFalse(common.appears(span, self.text))

    def test_titles_match_up_to_case_punctuation_and_subtitles(self):
        self.assertTrue(
            common.same_title(
                "Molecular Structure of Nucleic Acids", WORK["message"]["title"][0]
            )
        )
        self.assertTrue(
            common.same_title(
                "A Programmable Dual-RNA–Guided DNA Endonuclease",
                "A programmable dual-RNA-guided DNA endonuclease",
            )
        )
        self.assertFalse(
            common.same_title(
                "The Nature of Cities", "Industrial Expansion and Location"
            )
        )


class SourceChecks(unittest.TestCase):
    def test_wikipedia(self):
        with mock.patch.object(
            common, "get_json", responses({"en.wikipedia.org": ARTICLE})
        ):
            self.assertEqual(check_sources.source_check(candidate()), ([], "42", []))
            errors = check_sources.source_check(
                candidate(answer_real=REAL.replace("1,538", "1,600"), real_span="1,600")
            )[0]
            self.assertEqual(
                errors, ["source: real_span not found in the Wikipedia article"]
            )
        with mock.patch.object(
            common,
            "get_json",
            responses({"en.wikipedia.org": {"error": {"code": "missingtitle"}}}),
        ):
            self.assertEqual(
                check_sources.source_check(candidate())[0],
                ["source: Wikipedia article not found"],
            )

    def test_crossref(self):
        with mock.patch.object(
            common, "get_json", responses({"api.crossref.org": WORK})
        ):
            self.assertEqual(
                check_sources.source_check(citation()), ([], "10.1038/171737a0", [])
            )
            self.assertEqual(
                check_sources.source_check(
                    citation(answer_real=CITED.replace("1953", "1954"))
                )[2],
                ["crossref_year_1953"],
            )
            errors = check_sources.source_check(
                citation(answer_real=CITED.replace("James Watson", "James Brown"))
            )[0]
            self.assertEqual(
                errors, ['source: first author "WATSON" not named in the answer']
            )
        wrong = {
            "message": {
                **WORK["message"],
                "title": ["Industrial Expansion and Location"],
            }
        }
        with mock.patch.object(
            common, "get_json", responses({"api.crossref.org": wrong})
        ):
            self.assertIn(
                "source: Crossref title differs",
                check_sources.source_check(citation())[0][0],
            )
        with mock.patch.object(
            common, "get_json", responses({"api.crossref.org": None})
        ):
            self.assertEqual(
                check_sources.source_check(citation())[0],
                ["source: DOI not found in Crossref"],
            )


class FormatRules(unittest.TestCase):
    def test_valid_candidate(self):
        self.assertEqual(check_sources.local_errors(candidate()), [])
        self.assertEqual(check_sources.local_errors(citation()), [])

    def test_rejections(self):
        cases = {
            "short": (
                candidate(answer_real="Iron melts at 1,538 degrees Celsius."),
                "answer_real: 6 words, needs 25 to 60",
            ),
            "hedge": (
                candidate(answer_real=REAL.replace("far higher", "around twice")),
                'answer_real: hedging word "around"',
            ),
            "four sentences": (
                candidate(
                    answer_real="Iron melts at 1,538 degrees. It is hot. Smiths used bronze first. Cast iron came much later in the furnaces of China and then of Europe and the rest of the world."
                ),
                "answer_real: 4 sentences, needs 1 to 3",
            ),
            "other type": (
                candidate(hallucination_type="other"),
                "hallucination_type: must be one of wrong_number, wrong_entity, wrong_date, invented_citation",
            ),
            "category": (
                candidate(category="sport"),
                "category: must be one of science, geography, history",
            ),
            "doi for a number": (
                candidate(source_url="https://doi.org/10.1038/171737a0"),
                "source_url: must be an English Wikipedia article",
            ),
            "span twice (importer rule)": (
                candidate(real_span="iron"),
                "real_span: must appear exactly once in answer_real",
            ),
        }
        for name, (row, error) in cases.items():
            with self.subTest(name):
                self.assertIn(error, check_sources.local_errors(row))

    def test_months_initials_and_abbreviations(self):
        self.assertEqual(
            check_sources.local_errors(
                candidate(answer_real=REAL.replace("Pure iron", "In May, pure iron"))
            ),
            [],
        )
        self.assertEqual(
            check_sources.sentence_count(
                "President Ulysses S. Grant signed it. Mount St. Helens erupted."
            ),
            2,
        )
        # A sentence can end in the Roman numeral I, so a four-sentence answer is not counted as three.
        self.assertEqual(
            check_sources.sentence_count(
                "It ended World War I. It was long. It cost much. It was sad."
            ),
            4,
        )

    def test_dates_must_be_in_a_supported_format(self):
        row = candidate(
            hallucination_type="wrong_date",
            answer_real=REAL.replace("1,538 degrees Celsius", "July 1969 temperatures"),
            real_span="July 1969",
        )
        self.assertIn(
            'real_span: dates must read "20 July 1969", "July 20, 1969" or "1969"',
            check_sources.local_errors(row),
        )

    def test_attention_checks(self):
        rows = common.read_csv(common.DATA / "attention_checks_v1.csv")
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            sorted(r["hallucination_type"] for r in rows), sorted(common.TYPES)
        )
        for row in rows:
            with self.subTest(row["question"]):
                self.assertEqual(common.import_pairs.validate(row)[1], [])
                self.assertEqual(
                    (row["is_attention_check"], row["dataset_version"]), ("true", "v1")
                )


KINDS = {
    "Canberra": ("Q3114", {"Q515", "Q5119"}),
    "Sydney": ("Q3130", {"Q515", "Q1637706"}),
    "Tasmania": ("Q34366", {"Q5852411"}),
    "Canberra, ACT": ("Q3114", {"Q515"}),
    "Queanbeyan City": ("Q1027", {"Q515"}),
}


class FakeChecks(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(make_fakes.number_errors("1,538", "1,547"), [])
        self.assertEqual(make_fakes.number_errors("2,300", "2,100"), [])
        # A thousands group starting with 0 is not a leading zero.
        self.assertEqual(make_fakes.number_errors("17,098,246", "16,098,246"), [])
        self.assertEqual(make_fakes.number_errors("1,052", "1,067"), [])
        self.assertEqual(make_fakes.number_errors("3-5", "3-7"), [])
        cases = {
            ("1,538", "1538"): "number: unit, formatting or digit count differs",
            ("1,538", "15,380"): "number: unit, formatting or digit count differs",
            ("146.6", "146.60"): "number: unit, formatting or digit count differs",
            ("1,538", "1,538"): "number: same value as the real span",
            ("54", "60"): "number: round number for a non-round real value",
            ("54", "07"): "number: leading zero",
        }
        for (real, fake), error in cases.items():
            with self.subTest(fake=fake):
                self.assertEqual(make_fakes.number_errors(real, fake), [error])
        rounds = [
            make_fakes.is_round(s)
            for s in ("2,300", "130", "54", "146.6", "8,848.86", "7")
        ]
        self.assertEqual(rounds, [True, True, False, False, False, False])

    def test_dates(self):
        self.assertEqual(make_fakes.date_errors("20 July 1969", "16 July 1972"), [])
        self.assertEqual(make_fakes.date_errors("1969", "1971"), [])
        self.assertEqual(
            make_fakes.date_errors("1 January 1969", "31 December 1998"), []
        )
        self.assertEqual(
            make_fakes.date_errors("1 January 1969", "31 December 1999"),
            ["date: more than 30 years from the real date"],
        )
        self.assertEqual(
            make_fakes.date_errors("July 1969", "1972"),
            ["date: real span is not in a supported date format"],
        )
        cases = {
            "July 16, 1972": "date: format or precision differs",
            "1972": "date: format or precision differs",
            "06 July 1972": "date: format or precision differs",
            "20 july 1972": "date: format or precision differs",
            "31 February 1970": "date: not a real calendar date",
            "20 July 1969": "date: same as the real span",
            "20 July 2000": "date: more than 30 years from the real date",
        }
        for fake, error in cases.items():
            with self.subTest(fake=fake):
                self.assertEqual(make_fakes.date_errors("20 July 1969", fake), [error])

    def test_entities(self):
        lookup = KINDS.get
        self.assertEqual(make_fakes.entity_errors("Canberra", "Sydney", lookup), [])
        self.assertEqual(
            make_fakes.entity_errors("Canberra", "Tasmania", lookup),
            ["entity: not the same kind of thing (Wikidata instance-of differs)"],
        )
        self.assertEqual(
            make_fakes.entity_errors("Canberra", "Canberra, ACT", lookup),
            ["entity: names the same thing as the real span"],
        )
        self.assertEqual(
            make_fakes.entity_errors("Canberra", "Nowhereville", lookup),
            ["entity: fake has no unambiguous Wikipedia article"],
        )

    def test_citations(self):
        real = "A Mathematical Theory of Communication"
        unrelated = lambda title: ["Something Else Entirely"]
        style_error = "citation: format differs (capitalisation, subtitle colon or final punctuation)"
        self.assertEqual(
            make_fakes.citation_errors(
                real, "A Statistical Theory of Signal Exchange", unrelated
            ),
            [],
        )
        self.assertEqual(
            make_fakes.citation_errors(
                real, "A statistical theory of signal exchange", unrelated
            ),
            [style_error],
        )
        self.assertEqual(
            make_fakes.citation_errors(real, "A Theory: Of Signal Exchange", unrelated),
            [style_error],
        )
        existing = lambda title: ["The Mathematical Theory of Communication"]
        self.assertEqual(
            make_fakes.citation_errors(
                real, "The Mathematical Theory of Communication", existing
            ),
            ["citation: Crossref finds a work with this title"],
        )
        self.assertEqual(
            make_fakes.citation_style(
                "DNA sequencing with chain-terminating inhibitors"
            ),
            ("sentence", False, False),
        )

    def test_checks_for_all_types(self):
        dated = candidate(
            hallucination_type="wrong_date",
            answer_real=REAL.replace(
                "1,538 degrees Celsius", "temperatures first measured on 20 July 1969"
            ),
            real_span="20 July 1969",
        )
        self.assertEqual(
            make_fakes.check(dated, "16 July 1972", "Measured on 20 July 1969.")[0], []
        )
        self.assertIn(
            "fabricated span appears in the source article",
            make_fakes.check(dated, "16 July 1972", "Repeated on July 16, 1972.")[0],
        )
        cited = citation()
        fake_title = "Molecular Structure of Viral Proteins: A Model for Ribonucleic Acid Folding"
        self.assertEqual(
            make_fakes.check(
                cited, fake_title, "", search=lambda title: ["Unrelated Work"]
            )[0],
            [],
        )
        self.assertEqual(
            make_fakes.check(cited, fake_title, "", search=lambda title: [title])[0],
            ["citation: Crossref finds a work with this title"],
        )
        article = "Pure iron melts at 1538 °C and boils at 2862 °C."
        self.assertEqual(make_fakes.check(candidate(), "1,547", article), ([], []))
        self.assertIn(
            "fabricated span appears in the source article",
            make_fakes.check(candidate(), "2,862", article)[0],
        )
        repeated = candidate(answer_real=REAL + " Steel melts at 1,425.")
        self.assertEqual(
            make_fakes.check(repeated, "1,425", "")[0],
            ["fabricated span already appears in the real answer"],
        )
        entity = candidate(
            hallucination_type="wrong_entity",
            answer_real=REAL.replace("Pure iron", "In Canberra, pure iron"),
            real_span="Canberra",
        )
        self.assertEqual(
            make_fakes.check(entity, "Sydney", "", lookup=KINDS.get), ([], [])
        )
        # A length outside 0.7 to 1.3 times the real span is flagged for review, not rejected.
        self.assertEqual(
            make_fakes.check(entity, "Queanbeyan City", "", lookup=KINDS.get),
            ([], ["length_ratio_1.88"]),
        )

    def test_prompts_spell_out_pattern_and_kind(self):
        self.assertIn('exactly the pattern "#,###"', make_fakes.prompt(candidate()))
        with mock.patch.object(
            common, "wikidata_entity", lambda name: ("Q35802", {"Q5"})
        ):
            self.assertEqual(make_fakes.entity_kind("Alexander Fleming"), "person")
        with (
            mock.patch.object(
                common,
                "wikidata_entity",
                lambda name: ("Q248", {"Q891723", "Q4830453"}),
            ),
            mock.patch.object(
                common,
                "wikidata_labels",
                lambda qids: [
                    {"Q4830453": "business", "Q891723": "public company"}[q]
                    for q in qids
                ],
            ),
        ):
            self.assertEqual(
                make_fakes.entity_kind("Intel"), "business or public company"
            )
        with mock.patch.object(common, "wikidata_entity", lambda name: None):
            self.assertEqual(make_fakes.entity_kind("Nowhere"), "thing")
        entity = candidate(
            hallucination_type="wrong_entity",
            answer_real=REAL.replace("Pure iron", "Intel iron"),
            real_span="Intel",
        )
        self.assertIn(
            "a different, real business or public company that has its own",
            make_fakes.prompt(entity, "business or public company"),
        )

    def test_reply_parsing_and_kept_order(self):
        reply = '{"replacements": [" \\"1,547\\" ", "1,547", "1,529", "1,561"]}'
        self.assertEqual(
            make_fakes.parse_replacements(reply), ["1,547", "1,529", "1,561"]
        )
        self.assertEqual(make_fakes.parse_replacements("not json"), [])
        attempts, kept = make_fakes.judge(candidate(), ["1538", "1,547", "1,529"], "")
        self.assertEqual([a["status"] for a in attempts], ["rejected", "kept", "kept"])
        self.assertEqual([fake for fake, _ in kept], ["1,547", "1,529"])


def pairs(count, extra=""):
    """Tiny fixture: same-shape number fakes, optionally with a tell-tale suffix on every fake."""
    rows = []
    for i in range(count):
        real, fake = f"{100 + i}", f"{200 + i}"
        answer = (
            f"The tower in example {i} is {{}} metres tall, according to the survey."
        )
        rows.append(
            {
                "hallucination_type": ("wrong_number", "wrong_date")[i % 2],
                "answer_real": answer.format(real),
                "real_span": real,
                "answer_fake": answer.format(fake + extra),
                "fabricated_span": fake + extra,
            }
        )
    return rows


class ArtifactCheck(unittest.TestCase):
    def test_no_surface_signal_passes(self):
        result = artifact_check.run(pairs(40))
        self.assertTrue(result["passes"])
        self.assertLessEqual(result["ci95"][0], 0.5)
        self.assertEqual((result["pairs"], result["folds"]), (40, 10))

    def test_balanced_order_scores_exactly_half_without_signal(self):
        # Exactly half the pairs show the fake first, so all-zero features score 50%, not a coin flip's share.
        self.assertEqual(artifact_check.run(pairs(40))["accuracy"], 0.5)
        self.assertEqual(sum(artifact_check.pair_features([("a", "a", "b", "b")] * 41)[1]), 20)

    def test_noise_features_fit_a_classifier_and_still_pass(self):
        # Fakes vary in length at random, unrelated to which one is fake: a fitted model should not beat chance.
        import random

        rng = random.Random(7)
        rows = []
        for i in range(120):
            real, fake = "x" * rng.randint(3, 12), "y" * rng.randint(3, 12)
            rows.append({"hallucination_type": "wrong_entity", "answer_real": f"It was {real}.", "real_span": real, "answer_fake": f"It was {fake}.", "fabricated_span": fake})
        result = artifact_check.run(rows)
        self.assertTrue(result["passes"])
        self.assertNotEqual(result["coefficients"]["span_length"], 0)

    def test_a_surface_tell_fails(self):
        # Every fake is longer and carries extra digits and punctuation: the classifier finds it.
        result = artifact_check.run(pairs(40, extra=" (est. 2,000)"))
        self.assertFalse(result["passes"])
        self.assertGreater(result["ci95"][0], 0.5)
        self.assertEqual(result["accuracy"], 1.0)

    def test_order_is_random_and_seeded(self):
        X, y = artifact_check.pair_features(
            [
                (
                    r["answer_real"],
                    r["real_span"],
                    r["answer_fake"],
                    r["fabricated_span"],
                )
                for r in pairs(40, extra="!")
            ]
        )
        self.assertTrue(0 < sum(y) < 40)
        self.assertEqual(
            y, artifact_check.pair_features([("a", "a", "bb!", "b!")] * 40)[1]
        )
        self.assertTrue(all((row[0] > 0) == bool(label) for row, label in zip(X, y)))

    def test_wilson_interval(self):
        low, high = artifact_check.wilson(50, 100)
        self.assertAlmostEqual(low, 0.4038, places=3)
        self.assertAlmostEqual(high, 0.5962, places=3)



class ReviewSheet(unittest.TestCase):
    def fake(self, kind, category, question, flags=""):
        return {"id": question, "hallucination_type": kind, "category": category, "question": question, "answer_real": "r", "answer_fake": "f", "real_span": "r", "fabricated_span": "f", "alt_fake_2": "", "alt_fake_3": "", "source_url": "u", "flags": flags}

    def test_sorted_with_empty_keep_notes_and_claim_flags(self):
        fakes = [self.fake("wrong_number", "science", "b"), self.fake("invented_citation", "history", "c", "length_ratio_1.50"), self.fake("wrong_number", "geography", "a")]
        rows = make_review.review_rows(fakes, [{"id": "c", "verdict": "wrong"}, {"id": "a", "verdict": "ok"}])
        self.assertEqual([r["question"] for r in rows], ["c", "a", "b"])
        self.assertEqual([r["flags"] for r in rows], ["length_ratio_1.50;claim_wrong", "", ""])
        self.assertTrue(all(r["keep"] == r["notes"] == "" for r in rows))

    def test_never_overwrites_hand_entries(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            review, fakes = Path(folder) / "review.csv", Path(folder) / "fakes.csv"
            common.write_csv(fakes, [self.fake("wrong_number", "science", "q")], make_fakes.FAKE_FIELDS)
            with mock.patch.object(make_review, "REVIEW", review), mock.patch.object(make_review, "FAKES", fakes), mock.patch.object(make_review, "CLAIMS", Path(folder) / "none.csv"):
                self.assertEqual(make_review.main(), 0)
                rows = common.read_csv(review)
                rows[0]["keep"] = "yes"
                common.write_csv(review, rows, make_review.FIELDS)
                with self.assertRaises(SystemExit):
                    make_review.main()
                self.assertEqual(common.read_csv(review)[0]["keep"], "yes")

if __name__ == "__main__":
    unittest.main()

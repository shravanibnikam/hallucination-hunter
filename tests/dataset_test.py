"""Dataset pipeline checks. Wikipedia, Wikidata, Crossref and the model are mocked; no network is used."""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "dataset_generation"))
import check_sources
import common

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


if __name__ == "__main__":
    unittest.main()

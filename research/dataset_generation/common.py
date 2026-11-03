"""Shared helpers for the v1 dataset pipeline: paths, CSV files, cached HTTP, sources and span matching."""

import csv
import difflib
import functools
import hashlib
import importlib.util
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
DATA = RESEARCH / "data"
CACHE = HERE / ".cache"
TYPES = ("wrong_number", "wrong_entity", "wrong_date", "invented_citation")
# The schema accepts any nonempty category; v1 keeps the three used by the samples.
CATEGORIES = ("science", "geography", "history")
DATASET_VERSION = "v1"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
CROSSREF_API = "https://api.crossref.org/works"
USER_AGENT = "HallucinationHunterDataset/1.0 (research dataset; https://github.com/shravanibnikam/hallucination-hunter)"

# Reuse the importer's validation rather than copying it.
_spec = importlib.util.spec_from_file_location(
    "import_pairs", RESEARCH / "import_pairs.py"
)
import_pairs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(import_pairs)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def import_errors(row, answer_fake, fabricated_span, model_name=""):
    """The importer's errors for a candidate completed into a full pair row."""
    item = {
        **row,
        "answer_fake": answer_fake,
        "fabricated_span": fabricated_span,
        "explanation": row["answer_real"],
        "origin": "synthetic",
        "model_name": model_name,
        "is_attention_check": "false",
        "is_active": "true",
        "dataset_version": DATASET_VERSION,
    }
    return import_pairs.validate(item)[1]


def _cache_path(url):
    return CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")


def get_json(url, pause=0.25):
    """GET JSON once; responses (404 as null) are cached on disk so reruns are reproducible and polite."""
    CACHE.mkdir(exist_ok=True)
    path = _cache_path(url)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(5):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": USER_AGENT}),
                timeout=60,
            ) as response:
                data = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code == 404:
                data = None
                break
            if attempt == 4 or error.code not in (429, 500, 502, 503, 504):
                raise
        except urllib.error.URLError:
            if attempt == 4:
                raise
        time.sleep(2**attempt)
    # Write then rename, so a concurrent reader never sees a half-written file.
    partial = path.with_suffix(f".{uuid.uuid4().hex}.part")
    partial.write_text(json.dumps(data), encoding="utf-8")
    partial.replace(path)
    time.sleep(pause)
    return data


VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}
NOT_CONTENT = {"references", "reflist", "mw-references-wrap"}


class _Text(HTMLParser):
    """Visible text without scripts, styles, footnote markers ([12]) or reference lists: their numbers are not article content."""

    def __init__(self):
        super().__init__()
        self.parts, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        classes = set((dict(attrs).get("class") or "").split())
        hidden = (
            tag in ("style", "script")
            or (tag == "sup" and "reference" in classes)
            or bool(classes & NOT_CONTENT)
        )
        self.stack.append((tag, hidden or bool(self.stack and self.stack[-1][1])))

    def handle_endtag(self, tag):
        if any(open_tag == tag for open_tag, _ in self.stack):
            while self.stack.pop()[0] != tag:
                pass

    def handle_data(self, data):
        if not (self.stack and self.stack[-1][1]):
            self.parts.append(data)


def html_text(markup):
    parser = _Text()
    parser.feed(markup)
    return " ".join(parser.parts)


def wikipedia_title(url):
    match = re.fullmatch(r"https://en\.wikipedia\.org/wiki/([^?#]+)", url)
    return urllib.parse.unquote(match.group(1)).replace("_", " ") if match else None


def doi_of(url):
    match = re.fullmatch(r"https://doi\.org/(10\.\S+)", url)
    return urllib.parse.unquote(match.group(1)) if match else None


def wikipedia_page(title=None, revision=None):
    """Rendered text of an article (latest, or an exact revision); the infobox is included, footnotes are not."""
    url = lambda extra: (
        WIKIPEDIA_API
        + "?"
        + urllib.parse.urlencode(
            {
                "action": "parse",
                "prop": "text|revid",
                "format": "json",
                "formatversion": "2",
                **extra,
            }
        )
    )
    data = get_json(
        url({"oldid": revision} if revision else {"page": title, "redirects": "1"})
    )
    if not data or "parse" not in data:
        return None
    parse = data["parse"]
    by_title, by_revision = (
        _cache_path(url({"page": title, "redirects": "1"})),
        _cache_path(url({"oldid": parse["revid"]})),
    )
    if not revision and by_title.exists() and not by_revision.exists():
        # Stage 2 asks for this exact revision: link it to the same cached file instead of downloading and storing it twice.
        os.link(by_title, by_revision)
    return {
        "title": parse["title"],
        "revision": str(parse["revid"]),
        "text": html_text(parse["text"]),
    }


def wikidata_entity(name):
    """(QID, instance-of QIDs) for the English Wikipedia article a name resolves to; None if missing or ambiguous."""
    name = re.sub(r"^the\s+", "", name.strip(), flags=re.IGNORECASE)
    data = get_json(
        WIKIPEDIA_API
        + "?"
        + urllib.parse.urlencode(
            {
                "action": "query",
                "titles": name,
                "redirects": "1",
                "prop": "pageprops",
                "ppprop": "wikibase_item|disambiguation",
                "format": "json",
                "formatversion": "2",
            }
        )
    )
    pages = (data or {}).get("query", {}).get("pages", [])
    props = (
        pages[0].get("pageprops", {}) if pages and not pages[0].get("missing") else {}
    )
    if "wikibase_item" not in props or "disambiguation" in props:
        return None
    qid = props["wikibase_item"]
    claims = get_json(
        WIKIDATA_API
        + "?"
        + urllib.parse.urlencode(
            {
                "action": "wbgetclaims",
                "entity": qid,
                "property": "P31",
                "format": "json",
            }
        )
    )
    kinds = {
        claim["mainsnak"]["datavalue"]["value"]["id"]
        for claim in (claims or {}).get("claims", {}).get("P31", [])
        if "datavalue" in claim["mainsnak"]
    }
    return qid, kinds


def wikidata_labels(qids):
    """English labels for Wikidata items, in the order given."""
    data = get_json(
        WIKIDATA_API
        + "?"
        + urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(qids),
                "props": "labels",
                "languages": "en",
                "format": "json",
            }
        )
    )
    entities = (data or {}).get("entities", {})
    return [
        entities.get(q, {}).get("labels", {}).get("en", {}).get("value", q)
        for q in qids
    ]


def crossref_work(doi):
    data = get_json(CROSSREF_API + "/" + urllib.parse.quote(doi, safe="/"))
    return data["message"] if data else None


def crossref_titles(title):
    """Titles of the closest Crossref matches for a bibliographic query (no API key needed)."""
    data = get_json(
        CROSSREF_API
        + "?"
        + urllib.parse.urlencode(
            {"query.bibliographic": title, "rows": "10", "select": "DOI,title"}
        )
    )
    return [
        html_text(t)
        for item in (data or {}).get("message", {}).get("items", [])
        for t in item.get("title", [])
    ]


def title_key(title):
    title = unicodedata.normalize("NFKD", html_text(title))
    return " ".join(
        re.sub(
            r"[^\w]+", " ", "".join(c for c in title if not unicodedata.combining(c))
        )
        .casefold()
        .split()
    )


def same_title(a, b):
    """Equal up to case and punctuation, nearly identical, or one is the other plus a subtitle."""
    a, b = title_key(a), title_key(b)
    shorter, longer = sorted((a, b), key=len)
    return (
        a == b
        or difflib.SequenceMatcher(None, a, b).ratio() >= 0.9
        or (len(shorter) >= 20 and longer.startswith(shorter + " "))
    )


def normalize(text):
    text = unicodedata.normalize("NFKC", text)
    for old, new in (
        ("’", "'"),
        ("‘", "'"),
        ("“", '"'),
        ("”", '"'),
        ("–", "-"),
        ("—", "-"),
        ("−", "-"),
    ):
        text = text.replace(old, new)
    # Thousands separators are formatting: 1,538, 1538 and Wikipedia's spaced {{val}} groups (149 597 870 700) are one number.
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    text = re.sub(
        r"(?<![\d.])\d{1,3}(?: \d{3})+(?![\d.])",
        lambda m: m.group(0).replace(" ", ""),
        " ".join(text.split()),
    )
    return text.casefold()


NUMBER = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?!\d)")
MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)


def parse_date(span):
    """(format, year, month, day) for '20 July 1969', 'July 20, 1969' or '1969'; None otherwise."""
    span = span.strip()
    month = "|".join(MONTHS)
    if match := re.fullmatch(
        rf"(\d{{1,2}}) ({month}) (\d{{3,4}})", span, re.IGNORECASE
    ):
        return (
            "dmy",
            int(match.group(3)),
            MONTHS.index(match.group(2).lower()) + 1,
            int(match.group(1)),
        )
    if match := re.fullmatch(
        rf"({month}) (\d{{1,2}}), (\d{{3,4}})", span, re.IGNORECASE
    ):
        return (
            "mdy",
            int(match.group(3)),
            MONTHS.index(match.group(1).lower()) + 1,
            int(match.group(2)),
        )
    if re.fullmatch(r"\d{3,4}", span):
        return "year", int(span), None, None
    return None


def valid_date(parsed):
    try:
        return parsed[0] == "year" or bool(date(parsed[1], parsed[2], parsed[3]))
    except ValueError:
        return False


def date_variants(parsed):
    _, year, month, day = parsed
    name = MONTHS[month - 1].capitalize()
    return (
        f"{day} {name} {year}",
        f"{name} {day}, {year}",
        f"{name} {day} {year}",
        f"{year}-{month:02}-{day:02}",
        f"{year}|{month}|{day}",
    )


@functools.lru_cache(maxsize=32)
def _prepared(text):
    normalized = normalize(text)
    return normalized, frozenset(NUMBER.findall(normalized))


def appears(span, text):
    """Whether span occurs in source text, allowing number formatting (commas, units) and date formats."""
    normalized, numbers = _prepared(text)
    span_text = normalize(span)
    found = lambda needle: (
        re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", normalized) is not None
    )
    parsed = parse_date(span)
    if parsed and parsed[0] != "year":
        return any(found(normalize(variant)) for variant in date_variants(parsed))
    if NUMBER.search(span_text) and not re.search(r"[^\W\d_]", span_text):
        # A purely numeric span matches whole numbers only, so 46 does not match 1946 or 46.5.
        return all(value in numbers for value in NUMBER.findall(span_text))
    return found(span_text) or (span_text.startswith("the ") and found(span_text[4:]))

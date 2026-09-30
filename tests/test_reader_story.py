"""Keep the public reader story tied to the saved development evidence."""

import hashlib
import html
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_reader_story  # noqa: E402


def jsonl(relative):
    return [json.loads(line) for line in (ROOT / relative).read_text().splitlines() if line]


def chapter(page, chapter_id):
    match = re.search(
        rf'<article class="story-chapter" id="{re.escape(chapter_id)}">(.*?)</article>',
        page,
        re.DOTALL,
    )
    assert match, f"Missing {chapter_id} chapter"
    return html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))


class ReaderStoryTests(unittest.TestCase):
    def test_selected_repeat_illustration_matches_closed_records_and_display(self):
        evidence = json.loads((ROOT / "public-site/reader-evidence.json").read_text())
        assert evidence == build_reader_story.build()
        for source in evidence["sources"]:
            path = ROOT / source["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]

        base = "results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/"
        first = {row["id"]: row["decision"] for row in jsonl(base + "fresh1/P1/development.records.jsonl")}
        second = {row["id"]: row["decision"] for row in jsonl(base + "fresh2/P1/development.records.jsonl")}
        references = {row["id"]: row["proposed_labels"] for row in jsonl("data/pilot/proposed_labels.jsonl")}
        assert len(first) == len(second) == len(references) == evidence["denominator"] == 60
        assert first.keys() == second.keys() == references.keys()
        assert all(first[rid]["status"] == second[rid]["status"] == "ok" for rid in references)

        first_matches = {rid for rid in references if first[rid]["prediction"] == references[rid]}
        second_matches = {rid for rid in references if second[rid]["prediction"] == references[rid]}
        changed = {rid for rid in references if first[rid]["prediction"] != second[rid]["prediction"]}
        assert (len(first_matches), len(second_matches), len(changed)) == (36, 39, 11)
        assert (len(second_matches - first_matches), len(first_matches - second_matches)) == (4, 1)
        assert {row["id"] for row in evidence["changes"]} == changed

        page = (ROOT / "public-site/index.html").read_text()
        repeat = chapter(page, "story-repeat")
        assert "Eleven comments got different answers" in repeat
        assert "36 to 39 out of 60" in repeat
        assert "Four comments gained" in repeat and "one lost" in repeat
        assert 'aria-label="11 of 60 comments changed at least one answer' in page


    def test_published_jev_and_prompt_counts_match_source_and_display(self):
        findings = json.loads((ROOT / "public-site/findings-provider-errors-v1.json").read_text())
        meta = findings["meta"]
        for path_key, hash_key in (("sourcePath", "sourceSha256"), ("labelsPath", "labelsSha256")):
            assert hashlib.sha256((ROOT / meta[path_key]).read_bytes()).hexdigest() == meta[hash_key]
        data = json.loads((ROOT / meta["sourcePath"]).read_text())
        jev = findings["charts"]["jev"]
        jev_run = next(row for row in data["runs"] if row["id"] == jev["runId"])
        assert (jev["runId"], jev["correct"], jev["valid"], jev["denominator"]) == (
            "typesafe-jev113-v2", 54, 60, 60
        )
        assert (jev_run["metrics"]["all_four"], jev_run["valid"], jev_run["records"]) == (54, 60, 60)
        assert len(jev["disagreementCaseIds"]) == 6

        strict = next(g for g in findings["charts"]["promptDeltas"]["groups"] if g["id"] == "strict")
        comparison = strict["comparisons"]["P1_to_P2"]
        rows = comparison["rows"]
        assert len(rows) == strict["configurations"] == 39
        assert all(row["delta"] == row["toCorrect"] - row["fromCorrect"] for row in rows)
        counts = (sum(row["delta"] > 0 for row in rows),
                  sum(row["delta"] == 0 for row in rows),
                  sum(row["delta"] < 0 for row in rows))
        assert counts == (comparison["improved"], comparison["tied"], comparison["worsened"]) == (4, 14, 21)

        page = (ROOT / "public-site/index.html").read_text()
        specialist = chapter(page, "story-specialist")
        prompts = chapter(page, "story-prompts")
        assert "Jev matched 54 of the 60 comments" in specialist
        assert "every response could be scored" in specialist.lower()
        assert "lower in 21 of 39 comparisons" in prompts
        assert "improved four setups, left 14 unchanged and lowered 21" in prompts


    def test_hero_example_is_exact_input_with_provisional_reference_answers(self):
        page = (ROOT / "public-site/index.html").read_text()
        hero = re.search(r'<aside class="hero-example".*?</aside>', page, re.DOTALL)
        assert hero
        text = hero.group(0)
        feedback = next(row["feedback"] for row in jsonl("data/pilot/inputs.jsonl") if row["id"] == "DEV-003")
        reference = next(row["proposed_labels"] for row in jsonl("data/pilot/proposed_labels.jsonl")
                         if row["id"] == "DEV-003")
        quote = re.search(r"<blockquote>(.*?)</blockquote>", text, re.DOTALL)
        assert quote and html.unescape(quote.group(1)) == f"“{feedback}”"
        assert "DEV-003" in text and "These are the provisional reference answers" in text
        displayed = re.findall(r"<div><span>(.*?)</span><strong>(.*?)</strong></div>", text)
        assert displayed == [
            ("How was the experience?", reference["sentiment"].title()),
            ("Does someone need to follow up?", reference["follow_up_needed"].title()),
            ("Does it report a serious concern?", reference["serious_concern_reported"].title()),
            ("Could it work as a testimonial?", reference["testimonial_potential"].title()),
        ]

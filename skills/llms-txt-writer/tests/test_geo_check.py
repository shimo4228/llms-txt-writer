"""Tests for geo_check module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.geo_check import (
    CheckResult,
    SectionInfo,
    analyze_file,
    chunk_self_contained,
    count_en_words,
    count_ja_chars,
    definition_density,
    detect_language,
    entity_density,
    main,
    parse_sections,
    question_heading_ratio,
    render_json,
    render_report,
    run_all_checks,
    skyramp_score,
    strip_code_blocks,
)


class FakeEntityExtractor:
    """Deterministic extractor for unit tests — avoids loading GiNZA/spaCy models."""

    def __init__(self, mapping: dict[str, list[str]] | None = None) -> None:
        self._mapping = mapping or {}

    def extract(self, text: str) -> list[str]:
        if text in self._mapping:
            return self._mapping[text]
        # default: split whitespace and treat Capitalize-prefixed tokens as entities
        return [tok for tok in text.split() if tok[:1].isupper() and tok[:1].isalpha()]


@pytest.mark.unit
class TestLanguageDetection:
    def test_english_text_detected_as_en(self) -> None:
        assert detect_language("This is an English sentence with enough words.") == "en"

    def test_japanese_text_detected_as_ja(self) -> None:
        assert detect_language("これは日本語の文章で、十分な文字数があります。") == "ja"

    def test_mixed_text_with_majority_english_is_en(self) -> None:
        text = "This is a sentence about GEO 定量研究 analysis overall results"
        assert detect_language(text) == "en"

    def test_mixed_text_with_majority_japanese_is_ja(self) -> None:
        text = "GEO の定量研究では 44% という結果が出ている analysis"
        assert detect_language(text) == "ja"

    def test_empty_text_defaults_to_en(self) -> None:
        assert detect_language("") == "en"


@pytest.mark.unit
class TestTokenCounting:
    def test_count_en_words_basic(self) -> None:
        assert count_en_words("one two three four five") == 5

    def test_count_en_words_ignores_punctuation(self) -> None:
        assert count_en_words("Hello, world!") == 2

    def test_count_en_words_empty(self) -> None:
        assert count_en_words("") == 0

    def test_count_ja_chars_excludes_punctuation_and_whitespace(self) -> None:
        text = "こんにちは、世界。"  # 7 CJK chars, 2 punctuation
        assert count_ja_chars(text) == 7

    def test_count_ja_chars_includes_kana(self) -> None:
        assert count_ja_chars("カタカナひらがな") == 8


@pytest.mark.unit
class TestStripCodeBlocks:
    def test_removes_fenced_code_block(self) -> None:
        md = "Before\n\n```python\nprint('x')\n```\n\nAfter"
        result = strip_code_blocks(md)
        assert "print" not in result
        assert "Before" in result and "After" in result

    def test_preserves_inline_code(self) -> None:
        md = "Inline `code` stays"
        assert "code" in strip_code_blocks(md)

    def test_removes_tilde_fenced_block(self) -> None:
        md = "Before\n\n~~~\nsecret\n~~~\n\nAfter"
        result = strip_code_blocks(md)
        assert "secret" not in result


@pytest.mark.unit
class TestParseSections:
    def test_splits_by_h2_headings(self) -> None:
        md = "# Title\n\nPreamble text.\n\n## Section One\n\nBody one.\n\n## Section Two\n\nBody two."
        sections = parse_sections(md)
        headings = [s.heading for s in sections]
        assert "Section One" in headings
        assert "Section Two" in headings

    def test_includes_preamble_as_section(self) -> None:
        md = "# Title\n\nOpening paragraph.\n\n## First\n\nbody"
        sections = parse_sections(md)
        assert sections[0].heading == ""
        assert "Opening paragraph" in sections[0].body

    def test_section_body_excludes_heading_line(self) -> None:
        md = "## Heading A\n\nContent A."
        sections = parse_sections(md)
        body = next(s.body for s in sections if s.heading == "Heading A")
        assert "Heading A" not in body
        assert "Content A" in body


@pytest.mark.unit
class TestSkyrampScore:
    def test_uniform_distribution_scores_low(self) -> None:
        # Entities evenly distributed → ratio ≈ 0.3 → score ≈ 0
        text = "Alpha. " * 10
        extractor = FakeEntityExtractor({text: ["Alpha"] * 10})
        result = skyramp_score(text, "en", extractor=extractor)
        assert result.value < 20

    def test_front_heavy_distribution_scores_high(self) -> None:
        # Reasonable ski-ramp concentration but not extreme (first 30% ≈ 60%)
        text_front = "Alpha Beta Gamma Delta Epsilon Zeta " * 3
        text_rest = "word word word word word word word word word word word word " * 5
        full = text_front + text_rest
        result = skyramp_score(full, "en")
        assert result.value >= 50
        assert result.status == "OK"

    def test_empty_entities_returns_fail(self) -> None:
        text = "no entities at all lowercase only words here for testing purposes."
        result = skyramp_score(text, "en", extractor=FakeEntityExtractor({text: []}))
        assert result.status in {"FAIL", "WARN"}

    def test_returns_check_result(self) -> None:
        result = skyramp_score("Alpha Beta word word word", "en")
        assert isinstance(result, CheckResult)
        assert result.name == "skyramp"

    def test_entities_not_found_in_text_returns_fail(self) -> None:
        text = "all lowercase words only here for the test"
        extractor = FakeEntityExtractor({text: ["Phantom"]})
        result = skyramp_score(text, "en", extractor=extractor)
        assert result.status == "FAIL"
        assert result.value == 0.0


@pytest.mark.unit
class TestChunkSelfContained:
    def test_all_sections_in_range_is_ok(self) -> None:
        sections = [
            SectionInfo(level=2, heading="A", body="word " * 100, word_count=100, char_count=500),
            SectionInfo(level=2, heading="B", body="word " * 120, word_count=120, char_count=600),
        ]
        result = chunk_self_contained(sections, "en")
        assert result.status == "OK"

    def test_too_short_section_triggers_warn_or_fail(self) -> None:
        sections = [
            SectionInfo(level=2, heading="A", body="word " * 20, word_count=20, char_count=100),
            SectionInfo(level=2, heading="B", body="word " * 20, word_count=20, char_count=100),
        ]
        result = chunk_self_contained(sections, "en")
        assert result.status in {"WARN", "FAIL"}

    def test_too_long_section_triggers_warn_or_fail(self) -> None:
        sections = [
            SectionInfo(level=2, heading="A", body="word " * 500, word_count=500, char_count=2500),
        ]
        result = chunk_self_contained(sections, "en")
        assert result.status in {"WARN", "FAIL"}

    def test_japanese_range_uses_chars(self) -> None:
        sections = [
            SectionInfo(level=2, heading="A", body="あ" * 300, word_count=0, char_count=300),
            SectionInfo(level=2, heading="B", body="い" * 250, word_count=0, char_count=250),
        ]
        result = chunk_self_contained(sections, "ja")
        assert result.status == "OK"

    def test_suggestions_identify_offending_sections(self) -> None:
        sections = [
            SectionInfo(
                level=2, heading="Good", body="word " * 100, word_count=100, char_count=500
            ),
            SectionInfo(
                level=2, heading="TooLong", body="word " * 400, word_count=400, char_count=2000
            ),
        ]
        result = chunk_self_contained(sections, "en")
        assert any("TooLong" in s for s in result.suggestions)


@pytest.mark.unit
class TestQuestionHeadingRatio:
    def test_en_question_mark_counts(self) -> None:
        sections = [
            SectionInfo(
                level=2, heading="Why does it matter?", body="", word_count=0, char_count=0
            ),
            SectionInfo(level=2, heading="Background", body="", word_count=0, char_count=0),
        ]
        result = question_heading_ratio(sections)
        assert result.value == pytest.approx(0.5)

    def test_ja_fullwidth_question_counts(self) -> None:
        sections = [
            SectionInfo(level=2, heading="なぜ重要か？", body="", word_count=0, char_count=0),
            SectionInfo(level=2, heading="前提", body="", word_count=0, char_count=0),
        ]
        result = question_heading_ratio(sections)
        assert result.value == pytest.approx(0.5)

    def test_ja_ka_ending_counts(self) -> None:
        sections = [
            SectionInfo(level=2, heading="なぜ重要か。", body="", word_count=0, char_count=0),
        ]
        result = question_heading_ratio(sections)
        assert result.value == pytest.approx(1.0)

    def test_zero_h2_returns_fail(self) -> None:
        sections = [
            SectionInfo(level=1, heading="Title", body="", word_count=0, char_count=0),
        ]
        result = question_heading_ratio(sections)
        assert result.status in {"FAIL", "WARN"}

    def test_no_questions_returns_fail(self) -> None:
        sections = [
            SectionInfo(level=2, heading="Background", body="", word_count=0, char_count=0),
            SectionInfo(level=2, heading="Results", body="", word_count=0, char_count=0),
        ]
        result = question_heading_ratio(sections)
        assert result.status == "FAIL"

    def test_above_target_returns_ok(self) -> None:
        sections = [
            SectionInfo(level=2, heading="Why A?", body="", word_count=0, char_count=0),
            SectionInfo(level=2, heading="How B?", body="", word_count=0, char_count=0),
            SectionInfo(level=2, heading="Why C?", body="", word_count=0, char_count=0),
            SectionInfo(level=2, heading="Other", body="", word_count=0, char_count=0),
            SectionInfo(level=2, heading="Conclusion", body="", word_count=0, char_count=0),
        ]
        result = question_heading_ratio(sections)
        assert result.status == "OK"


@pytest.mark.unit
class TestEntityDensity:
    def test_high_density_returns_ok(self) -> None:
        text = "Alpha Beta Gamma Delta Epsilon word word word"
        extractor = FakeEntityExtractor({text: ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]})
        result = entity_density(text, "en", extractor=extractor)
        assert result.status == "OK"
        assert result.value > 0.15

    def test_low_density_returns_warn_or_fail(self) -> None:
        text = "word " * 100 + "Alpha"
        extractor = FakeEntityExtractor({text: ["Alpha"]})
        result = entity_density(text, "en", extractor=extractor)
        assert result.status in {"WARN", "FAIL"}

    def test_zero_entities_returns_fail(self) -> None:
        text = "plain lowercase words only here for test"
        extractor = FakeEntityExtractor({text: []})
        result = entity_density(text, "en", extractor=extractor)
        assert result.status == "FAIL"

    def test_japanese_counts_chars_as_denominator(self) -> None:
        text = "GEOは定量的な技術だ。"
        extractor = FakeEntityExtractor({text: ["GEO"]})
        result = entity_density(text, "ja", extractor=extractor)
        assert 0 < result.value <= 1


@pytest.mark.unit
class TestDefinitionDensity:
    def test_english_defined_as_matches(self) -> None:
        text = "GEO is defined as the practice of optimizing for AI. " + "word " * 95
        result = definition_density(text, "en")
        assert result.value > 0

    def test_english_refers_to_matches(self) -> None:
        text = "AEO refers to answer engine optimization. " + "word " * 90
        result = definition_density(text, "en")
        assert result.value > 0

    def test_japanese_toha_matches(self) -> None:
        text = "GEOとは生成エンジン最適化のことを指す。" + "あ" * 80
        result = definition_density(text, "ja")
        assert result.value > 0

    def test_no_definitions_returns_warn_or_fail(self) -> None:
        text = "word " * 200
        result = definition_density(text, "en")
        assert result.status in {"WARN", "FAIL"}

    def test_empty_text_does_not_crash(self) -> None:
        result = definition_density("", "en")
        assert isinstance(result, CheckResult)


@pytest.mark.unit
class TestRenderReport:
    def test_report_includes_all_check_names(self) -> None:
        sections = [
            SectionInfo(level=2, heading="Why?", body="word " * 80, word_count=80, char_count=400),
        ]
        text = "Alpha Beta is defined as a framework. " + "word " * 80
        report = run_all_checks(
            path="/tmp/x.md",
            text=text,
            sections=sections,
            language="en",
            extractor=FakeEntityExtractor({text: ["Alpha", "Beta"]}),
        )
        output = render_report(report)
        assert "skyramp" in output.lower()
        assert "chunk" in output.lower()
        assert "question" in output.lower()
        assert "entity" in output.lower()
        assert "definition" in output.lower()

    def test_report_shows_language_and_counts(self) -> None:
        sections = [SectionInfo(level=2, heading="A", body="word", word_count=1, char_count=4)]
        text = "word"
        report = run_all_checks(
            path="/tmp/x.md",
            text=text,
            sections=sections,
            language="en",
            extractor=FakeEntityExtractor({text: []}),
        )
        output = render_report(report)
        assert "en" in output.lower()


@pytest.mark.unit
class TestRenderJson:
    def test_output_is_valid_json(self) -> None:
        text = "Alpha word word"
        report = run_all_checks(
            path="/tmp/x.md",
            text=text,
            sections=[SectionInfo(level=2, heading="H", body=text, word_count=3, char_count=15)],
            language="en",
            extractor=FakeEntityExtractor({text: ["Alpha"]}),
        )
        data = json.loads(render_json(report))
        assert data["path"] == "/tmp/x.md"
        assert data["language"] == "en"
        assert len(data["results"]) == 5
        assert {r["name"] for r in data["results"]} >= {"skyramp", "entity_density"}


@pytest.mark.integration
class TestCli:
    def test_main_missing_file_returns_exit_2(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.md"
        assert main([str(missing)]) == 2

    def test_main_success_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md = tmp_path / "article.md"
        md.write_text(
            "# Title\n\n## Why?\n\nAlpha Beta is defined as a framework. " + "word " * 80,
            encoding="utf-8",
        )
        code = main([str(md)])
        assert code == 0
        captured = capsys.readouterr()
        assert "llms-txt-writer score report" in captured.out

    def test_main_json_flag_emits_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        md = tmp_path / "article.md"
        md.write_text("# Title\n\n## Why?\n\nAlpha Beta. " + "word " * 60, encoding="utf-8")
        code = main([str(md), "--json"])
        assert code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "results" in parsed

    def test_analyze_file_returns_text(self, tmp_path: Path) -> None:
        md = tmp_path / "sample.md"
        md.write_text("# T\n\n## H\n\nAlpha word word", encoding="utf-8")
        out = analyze_file(md)
        assert "llms-txt-writer" in out

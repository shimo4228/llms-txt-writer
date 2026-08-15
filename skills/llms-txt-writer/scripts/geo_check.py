"""GEO/AEO static analysis for Markdown files.

Produces a deterministic scorecard across GEO-SFE three layers:
  macro  — skyramp_score (front-30% entity concentration)
  meso   — chunk_self_contained, question_heading_ratio
  micro  — entity_density, definition_density

The semantic interpretation layer (concrete rewrite proposals) is handled by
Claude reading this script's stdout; see SKILL.md Post-script Interpretation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from operator import attrgetter
from pathlib import Path
from typing import Protocol

TARGET_SKYRAMP = 50.0
TARGET_CHUNK_RATIO = 0.8
TARGET_QUESTION_HEADING_RATIO = 0.2
TARGET_ENTITY_DENSITY = 0.15
TARGET_DEFINITION_DENSITY_EN = 1.0
TARGET_DEFINITION_DENSITY_JA = 0.5

EN_WORD_RANGE = (50, 150)
JA_CHAR_RANGE = (150, 450)

EN_COMMON_STOPWORDS = {
    "The",
    "A",
    "An",
    "This",
    "That",
    "These",
    "Those",
    "It",
    "Is",
    "I",
    "We",
    "You",
    "They",
    "He",
    "She",
    "But",
    "And",
    "Or",
    "If",
    "In",
    "On",
    "At",
    "By",
    "For",
    "Of",
    "To",
    "From",
    "With",
    "Without",
    "So",
    "As",
    "When",
    "While",
    "Where",
    "Why",
    "How",
}

EN_DEFINITION_PATTERNS = [
    r"\bis defined as\b",
    r"\bare defined as\b",
    r"\bis\s+defined\s+to\s+mean\b",
    r"\bdefined\s+as\b",
    r"\brefers?\s+to\b",
    r"\bmeans\s+that\b",
    r"\bis\s+a\s+(?:type|kind|form|class|category)\s+of\b",
]

JA_DEFINITION_PATTERNS = [
    r"とは",
    r"と定義",
    r"を指す",
    r"を意味",
    r"のことで",
    r"のことを指す",
]


class EntityExtractor(Protocol):
    """Protocol for entity extraction. Injectable for testing or swapping with GiNZA."""

    def extract(self, text: str) -> list[str]: ...


@dataclass(frozen=True)
class HeuristicExtractor:
    """Lightweight regex-based extractor — no ML model required.

    Covers: ASCII Capitalize tokens (minus stopwords), all-caps acronyms,
    numeric tokens (including decimals + %), katakana runs, kanji runs.
    """

    def extract(self, text: str) -> list[str]:
        entities: list[str] = []
        entities.extend(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
        for match in re.finditer(r"\b[A-Z][A-Za-z0-9]+\b", text):
            tok = match.group()
            if tok not in EN_COMMON_STOPWORDS:
                entities.append(tok)
        entities.extend(re.findall(r"[\u30A0-\u30FF]{2,}", text))
        entities.extend(re.findall(r"[\u4E00-\u9FFF]{2,}", text))
        return entities


@dataclass(frozen=True)
class SectionInfo:
    level: int
    heading: str
    body: str
    word_count: int
    char_count: int


@dataclass(frozen=True)
class CheckResult:
    name: str
    value: float
    target: float
    status: str  # "OK" | "WARN" | "FAIL"
    detail: str
    suggestions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GeoReport:
    path: str
    language: str
    word_count: int
    char_count: int
    sections: list[SectionInfo]
    results: list[CheckResult]


def detect_language(text: str) -> str:
    if not text:
        return "en"
    cjk_chars = sum(1 for ch in text if _is_cjk(ch))
    alpha_chars = sum(1 for ch in text if ch.isalpha() and not _is_cjk(ch))
    denom = cjk_chars + alpha_chars
    if denom == 0:
        return "en"
    return "ja" if cjk_chars / denom > 0.3 else "en"


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0x3040 <= code <= 0x309F  # Hiragana
        or 0x30A0 <= code <= 0x30FF  # Katakana
        or 0x4E00 <= code <= 0x9FFF  # CJK Unified Ideographs
        or 0x3400 <= code <= 0x4DBF  # CJK Extension A
    )


def count_en_words(text: str) -> int:
    return len([t for t in re.split(r"\s+", text.strip()) if t])


def count_ja_chars(text: str) -> int:
    return sum(
        1 for ch in text if not ch.isspace() and not unicodedata.category(ch).startswith("P")
    )


def strip_code_blocks(markdown: str) -> str:
    without_fences = re.sub(
        r"^[ \t]*(```|~~~)[^\n]*\n.*?^[ \t]*\1[^\n]*$",
        "",
        markdown,
        flags=re.DOTALL | re.MULTILINE,
    )
    return without_fences


def parse_sections(markdown: str) -> list[SectionInfo]:
    """Split Markdown into level-2 sections. Preamble (before first H2) is kept as an empty-heading section."""
    stripped = strip_code_blocks(markdown)
    lines = stripped.splitlines()
    sections: list[SectionInfo] = []
    current_heading = ""
    current_level = 1
    current_body: list[str] = []

    def _flush(heading: str, level: int, body_lines: list[str]) -> None:
        body = "\n".join(body_lines).strip()
        if not heading and not body:
            return
        wc = count_en_words(body)
        cc = count_ja_chars(body)
        sections.append(
            SectionInfo(level=level, heading=heading, body=body, word_count=wc, char_count=cc)
        )

    for line in lines:
        h2_match = re.match(r"^##\s+(.+?)\s*$", line)
        h1_match = re.match(r"^#\s+(.+?)\s*$", line)
        if h2_match:
            _flush(current_heading, current_level, current_body)
            current_heading = h2_match.group(1).strip()
            current_level = 2
            current_body = []
        elif h1_match and not sections and not current_heading:
            # Skip the title line without flushing an empty preamble.
            continue
        else:
            current_body.append(line)
    _flush(current_heading, current_level, current_body)
    return sections


def _unique_preserve(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _status(value: float, ok: float, warn: float) -> str:
    if value >= ok:
        return "OK"
    if value >= warn:
        return "WARN"
    return "FAIL"


def skyramp_score(
    text: str, language: str, extractor: EntityExtractor | None = None
) -> CheckResult:
    ext = extractor or HeuristicExtractor()
    entities = ext.extract(text)
    if not entities or not text:
        return CheckResult(
            name="skyramp",
            value=0.0,
            target=TARGET_SKYRAMP,
            status="FAIL",
            detail="no entities detected",
            suggestions=["add brand/tool/author names or concrete numbers"],
        )
    boundary = max(1, int(len(text) * 0.3))
    unique = [e for e in _unique_preserve(entities) if e]
    if not unique:
        return CheckResult(
            name="skyramp",
            value=0.0,
            target=TARGET_SKYRAMP,
            status="FAIL",
            detail="no entities detected",
            suggestions=[],
        )
    pattern = re.compile("|".join(re.escape(e) for e in unique))
    front = 0
    rest = 0
    for match in pattern.finditer(text):
        if match.start() < boundary:
            front += 1
        else:
            rest += 1
    total = front + rest
    if total == 0:
        return CheckResult(
            name="skyramp",
            value=0.0,
            target=TARGET_SKYRAMP,
            status="FAIL",
            detail="entity occurrences not found in text",
            suggestions=[],
        )
    front_ratio = front / total
    raw = (front_ratio - 0.3) / 0.3 * 100
    score = max(0.0, min(100.0, raw))
    status = _status(score, TARGET_SKYRAMP, TARGET_SKYRAMP / 2)
    suggestions: list[str] = []
    if status != "OK":
        suggestions.append(
            f"front-30% holds {front_ratio:.0%} of entity occurrences "
            "(target 45%+). Move concrete numbers / brand names into the opening paragraphs."
        )
    _ = language
    return CheckResult(
        name="skyramp",
        value=round(score, 1),
        target=TARGET_SKYRAMP,
        status=status,
        detail=f"front-30% entity share={front_ratio:.1%}",
        suggestions=suggestions,
    )


def chunk_self_contained(sections: list[SectionInfo], language: str) -> CheckResult:
    valid = [s for s in sections if s.heading or s.body.strip()]
    if not valid:
        return CheckResult(
            name="chunk_self_contained",
            value=0.0,
            target=TARGET_CHUNK_RATIO,
            status="FAIL",
            detail="no sections",
            suggestions=["add `##` headings to split the document"],
        )

    if language == "ja":
        lo, hi = JA_CHAR_RANGE
        unit = "chars"
        get_size = attrgetter("char_count")
    else:
        lo, hi = EN_WORD_RANGE
        unit = "words"
        get_size = attrgetter("word_count")

    ok_count = sum(1 for s in valid if lo <= get_size(s) <= hi)
    ratio = ok_count / len(valid)
    status = _status(ratio, TARGET_CHUNK_RATIO, 0.5)
    suggestions: list[str] = []
    for s in valid:
        sz = get_size(s)
        label = s.heading or "(preamble)"
        if sz > hi:
            suggestions.append(
                f"Section '{label}' too long ({sz} {unit} > {hi}); split into chunks of {lo}-{hi} {unit}"
            )
        elif sz < lo:
            suggestions.append(
                f"Section '{label}' too short ({sz} {unit} < {lo}); merge or expand to {lo}+ {unit}"
            )
    return CheckResult(
        name="chunk_self_contained",
        value=round(ratio, 3),
        target=TARGET_CHUNK_RATIO,
        status=status,
        detail=f"{ok_count} of {len(valid)} sections in {lo}-{hi} {unit} range",
        suggestions=suggestions,
    )


def _is_question_heading(heading: str) -> bool:
    h = heading.rstrip()
    return h.endswith(("?", "？", "か。", "か？"))


def question_heading_ratio(sections: list[SectionInfo]) -> CheckResult:
    h2 = [s for s in sections if s.level == 2]
    if not h2:
        return CheckResult(
            name="question_heading_ratio",
            value=0.0,
            target=TARGET_QUESTION_HEADING_RATIO,
            status="WARN",
            detail="no H2 headings found",
            suggestions=["structure the document with `##` headings"],
        )
    qcount = sum(1 for s in h2 if _is_question_heading(s.heading))
    ratio = qcount / len(h2)
    status = "OK" if ratio >= TARGET_QUESTION_HEADING_RATIO else "FAIL"
    suggestions: list[str] = []
    if status != "OK":
        candidates = [s.heading for s in h2 if not _is_question_heading(s.heading)][:3]
        if candidates:
            suggestions.append(
                f"Rewrite 1-2 of these headings as questions: {', '.join(repr(c) for c in candidates)}"
            )
    return CheckResult(
        name="question_heading_ratio",
        value=round(ratio, 3),
        target=TARGET_QUESTION_HEADING_RATIO,
        status=status,
        detail=f"{qcount} of {len(h2)} H2 headings end with ? / ？ / か。",
        suggestions=suggestions,
    )


def entity_density(
    text: str, language: str, extractor: EntityExtractor | None = None
) -> CheckResult:
    ext = extractor or HeuristicExtractor()
    entities = ext.extract(text)
    if language == "ja":
        denom = count_ja_chars(text)
        numerator = sum(len(e) for e in entities)
    else:
        denom = count_en_words(text)
        numerator = len(entities)
    if denom == 0:
        return CheckResult(
            name="entity_density",
            value=0.0,
            target=TARGET_ENTITY_DENSITY,
            status="FAIL",
            detail="empty text",
            suggestions=[],
        )
    density = numerator / denom
    status = _status(density, TARGET_ENTITY_DENSITY, TARGET_ENTITY_DENSITY / 2)
    suggestions: list[str] = []
    if not entities:
        suggestions.append(
            "no named entities detected — add product / tool / author names and concrete numbers"
        )
    elif status != "OK":
        suggestions.append(
            f"entity density {density:.1%} below target {TARGET_ENTITY_DENSITY:.0%}. "
            "Replace generic nouns ('the tool', 'a library') with specific names."
        )
    return CheckResult(
        name="entity_density",
        value=round(density, 3),
        target=TARGET_ENTITY_DENSITY,
        status=status,
        detail=f"entity/{'char' if language == 'ja' else 'word'} = {density:.1%}",
        suggestions=suggestions,
    )


def definition_density(text: str, language: str) -> CheckResult:
    if language == "ja":
        patterns = JA_DEFINITION_PATTERNS
        denom_base = count_ja_chars(text)
        target = TARGET_DEFINITION_DENSITY_JA
        unit = "chars"
    else:
        patterns = EN_DEFINITION_PATTERNS
        denom_base = count_en_words(text)
        target = TARGET_DEFINITION_DENSITY_EN
        unit = "words"
    count = 0
    for p in patterns:
        count += len(re.findall(p, text, flags=re.IGNORECASE))
    denom_hundred = max(1.0, denom_base / 100.0)
    density = count / denom_hundred
    status = _status(density, target, target / 2)
    suggestions: list[str] = []
    if status != "OK":
        suggestions.append(
            f"definition density {density:.2f}/100 {unit} below target {target}. "
            "Rewrite vague openings into 'X is defined as...' / 'X とは...を指す' form."
        )
    return CheckResult(
        name="definition_density",
        value=round(density, 3),
        target=target,
        status=status,
        detail=f"{count} matches per {denom_base} {unit}",
        suggestions=suggestions,
    )


def run_all_checks(
    path: str,
    text: str,
    sections: list[SectionInfo],
    language: str,
    extractor: EntityExtractor | None = None,
) -> GeoReport:
    results = [
        skyramp_score(text, language, extractor=extractor),
        chunk_self_contained(sections, language),
        question_heading_ratio(sections),
        entity_density(text, language, extractor=extractor),
        definition_density(text, language),
    ]
    return GeoReport(
        path=path,
        language=language,
        word_count=count_en_words(text),
        char_count=count_ja_chars(text),
        sections=sections,
        results=results,
    )


_STATUS_LABEL = {"OK": "OK  ", "WARN": "WARN", "FAIL": "FAIL"}
_LAYER = {
    "skyramp": "Macro",
    "chunk_self_contained": "Meso ",
    "question_heading_ratio": "Meso ",
    "entity_density": "Micro",
    "definition_density": "Micro",
}


def render_report(report: GeoReport) -> str:
    lines: list[str] = []
    lines.append(f"llms-txt-writer score report: {report.path}")
    lines.append(
        f"Language: {report.language} | Words: {report.word_count} | "
        f"Chars: {report.char_count} | Sections: {len([s for s in report.sections if s.level == 2])}"
    )
    lines.append("")
    for r in report.results:
        layer = _LAYER.get(r.name, "     ")
        status = _STATUS_LABEL.get(r.status, r.status)
        lines.append(
            f"[{layer}] {r.name:<24s} value={r.value:<7} target={r.target:<6} {status}  ({r.detail})"
        )
    actions: list[str] = []
    for r in report.results:
        actions.extend(r.suggestions)
    if actions:
        lines.append("")
        lines.append("Actions:")
        for a in actions:
            lines.append(f"  - {a}")
    return "\n".join(lines)


def render_json(report: GeoReport) -> str:
    data = {
        "path": report.path,
        "language": report.language,
        "word_count": report.word_count,
        "char_count": report.char_count,
        "sections": [
            {"level": s.level, "heading": s.heading, "words": s.word_count, "chars": s.char_count}
            for s in report.sections
        ],
        "results": [asdict(r) for r in report.results],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def analyze_file(path: Path, as_json: bool = False) -> str:
    raw = path.read_text(encoding="utf-8")
    text_for_nlp = strip_code_blocks(raw)
    language = detect_language(text_for_nlp)
    sections = parse_sections(raw)
    report = run_all_checks(str(path), text_for_nlp, sections, language)
    return render_json(report) if as_json else render_report(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Markdown file to analyze")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    if not args.path.exists():
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 2
    print(analyze_file(args.path, as_json=args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

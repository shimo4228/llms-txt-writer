# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Documentation

- Added "Companion JSON-LD Graph (Optional)" section to `SKILL.md` describing
  how to wire a `graph.jsonld` companion file via `llms.txt` reading-order
  block and `llms-full.txt` question-form H2. Cross-references the new
  [jsonld-knowledge-graph](https://github.com/shimo4228/jsonld-knowledge-graph)
  skill, which owns the graph schema and design moves.

## [0.2.0] — 2026-05-11

Initial public release.

### What it does

An [Agent Skill](https://agentskills.io/specification) that writes documents
optimized to be cited by AI search engines (ChatGPT / Perplexity / Gemini) and
AI agents. Combines:

1. **[Answer.AI llms.txt standard](https://llmstxt.org/)** compliance — the
   two-file `llms.txt` + `llms-full.txt` layout that AI crawlers preferentially
   consume.
2. **GEO-SFE 3-layer static analysis** — macro (ski-ramp entity placement),
   meso (chunk self-containment, question-heading ratio), and micro (entity
   density, definitional-expression density).

### Components

- `SKILL.md` — usage spec, when-to-use boundaries, post-script interpretation
  rules, ski-ramp optimization techniques (手法 1 / 2 / 3), anti-patterns.
- `scripts/geo_check.py` — 528-line static analyzer. Bilingual (EN / JA).
  Computes 5 GEO metrics against research-backed thresholds. Outputs human
  text report or `--json`.
- `tests/test_geo_check.py` — 48 passing unit + integration tests.
- `fixtures/sample_en.md`, `fixtures/sample_ja.md` — minimal positive examples.

### Research basis (research thresholds)

| Metric | Empirical value | Source |
|---|---|---|
| First-30% citation share | 44.2% | Victorino LLC (1.2M ChatGPT response analysis) |
| Optimal chunk size | 50–150 words (EN) | The Digital Bloom (2.3× citation lift) |
| Entity density | 20.6% (vs. 5–8% normal English) | Victorino LLC |
| Question-format headings | 2.8× citation lift | Position Digital |
| Definitional-expression citation rate | 36.2% vs 20.2% | Omniscient Digital |
| Framework | GEO-SFE macro / meso / micro | arXiv:2603.29979 |

### Real-world validation

Dogfooded on the `contemplative-moltbook` project (2026-04-19): ski-ramp
score raised from **23.5% FAIL → 55.0% OK** using a combination of techniques 1
+ 2 + 3 (Project Facts block, Prior Research table up-front, deletion of
duplicate `- Prior research:` bullets). All 5 metrics ended OK.

### Requirements

- Python >= 3.11
- `uv` for package management
- Dependencies: `markdown-it-py`, `textstat`, `ginza`, `ja-ginza`

### Tests

```bash
cd skills/llms-txt-writer && uv run pytest -v  # 48 tests
```

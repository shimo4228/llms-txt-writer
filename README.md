# llms-txt-writer

An [Agent Skill](https://agentskills.io/specification) that writes documents optimized to be **cited by AI search engines** (ChatGPT / Perplexity / Gemini) and AI agents. Combines [Answer.AI's `llms.txt` standard](https://llmstxt.org/) with GEO-SFE 3-layer static analysis backed by empirical research (Victorino LLC's 1.2M ChatGPT response study, The Digital Bloom, Position Digital, Omniscient Digital, arXiv:2603.29979).

## Install

### Claude Code

```bash
# Copy skill into your global skills directory
cp -r skills/llms-txt-writer ~/.claude/skills/llms-txt-writer
cd ~/.claude/skills/llms-txt-writer && uv sync
```

### SkillsMP

```bash
/skills add shimo4228/llms-txt-writer
```

## How It Works

1. **Target detection** — point the skill at an `llms.txt`, `llms-full.txt`, FAQ page, or glossary.
2. **`geo_check.py` static analysis** — computes 5 GEO metrics in one pass:
   ski-ramp score, chunk self-containment, question-heading ratio, entity density, definitional-expression density.
3. **Score interpretation** — Claude reads the FAIL / WARN list and proposes concrete edits (entity insertion, heading rewrites, chunk splits) keyed to the failing metric.
4. **Diff-mode edits** — each suggestion is presented as a small diff for `y/n` approval (no bulk rewrites).
5. **Re-check** — re-run `geo_check.py` until all 5 metrics are OK.

## Key Concept: AI Primary vs. Human Primary

Documents optimize differently depending on audience. Mixing audiences makes both worse.

| Axis | Human primary | AI primary |
|------|---------------|------------|
| Structure | Narrative, flowing paragraphs | Q&A / definitional, H2-independent chunks |
| Headings | Declarative, terse | Question-form, 20%+ |
| Entity placement | Natural to context | Concentrated 45%+ in first 30% (ski-ramp) |
| Definitions | Inferred from context | Explicit `X is defined as Y` |
| Section length | Proportional to importance | Even, 50–150 words / 150–450 chars |
| Readability | Top priority | Can be sacrificed |

This skill targets **AI primary** only. For human-facing writing (README, articles, blog posts) use [`writing-ecosystem`](https://github.com/shimo4228/claude-skill-writing-ecosystem) + `article-writing` instead.

## Usage

```bash
# Run from anywhere; uv handles the project env
uv run --directory ~/.claude/skills/llms-txt-writer \
  python -m scripts.geo_check /path/to/llms-full.txt

# JSON output for machine consumption
uv run --directory ~/.claude/skills/llms-txt-writer \
  python -m scripts.geo_check --json /path/to/llms-full.txt
```

## GEO Metrics

The skill targets 5 metrics with thresholds derived from empirical studies of AI citation behavior:

| Layer | Metric | OK threshold | Source |
|-------|--------|--------------|--------|
| Macro | Ski-ramp score | 45%+ entities in first 30% → score 50+ | Victorino LLC (44.2% first-30% citation share) |
| Meso | Chunk self-containment | 80%+ of H2 sections within 50–150 words (EN) / 150–450 chars (JA) | The Digital Bloom (2.3× citation lift) |
| Meso | Question-heading ratio | 20%+ of `##` headings end with `?` `？` `か。` | Position Digital (2.8× citation lift) |
| Micro | Entity density | 15%+ overall | Victorino LLC (20.6% observed, vs. 5–8% normal) |
| Micro | Definitional expression density | 1.0+ per 100 words (EN), 0.5+ per 100 chars (JA) | Omniscient Digital (36.2% citation rate vs. 20.2%) |

**Important**: `geo_check.py` counts `##` headings only — H3 and below merge into the parent H2 chunk. Put every FAQ Q&A at H2 level.

## Real-World Results

Dogfooded on the `contemplative-moltbook` project (2026-04-19):

| Step | Ski-ramp | All 5 metrics |
|------|----------|---------------|
| Baseline | 23.5% FAIL | FAIL |
| Technique 1 (Project Facts) alone | 28.4% | FAIL |
| Technique 1 + 2 + 3 combined | **55.0%** OK | **OK** ✅ |

Techniques 2 (Prior Research table up-front) and 3 (delete duplicate `- Prior research:` bullets) carry the ski-ramp lift — Technique 1 alone is insufficient.

## Requirements

- Python >= 3.11
- `uv` (for environment management)
- Dependencies: `markdown-it-py`, `textstat`, `ginza`, `ja-ginza`

## Tests

```bash
cd skills/llms-txt-writer && uv run pytest -v  # 48 tests
```

## Related skills (siblings)

- [`skill-comply`](https://github.com/shimo4228/skill-comply) — measures whether agents actually follow skill / rule definitions
- [`context-sync`](https://github.com/shimo4228/context-sync) — audits and fixes project documentation roles
- [`search-first`](https://github.com/shimo4228/search-first) — research-before-coding workflow
- [`skill-stocktake`](https://github.com/shimo4228/skill-stocktake) — quality audit for skills and commands
- [`rules-distill`](https://github.com/shimo4228/rules-distill) — scan installed skills, extract cross-cutting principles, and distill them into rules
- [`learn-eval`](https://github.com/shimo4228/learn-eval) — extract reusable patterns from sessions, self-evaluate quality, and save to the right location
- [`daily-research`](https://github.com/shimo4228/daily-research) — cron-driven daily research digest — theme selection, multi-stage web research, LLM-as-Judge evaluation

## About this skill

This skill is a **component skill of the [Authorship Strategy](https://github.com/shimo4228/authorship-strategy) research line** ([DOI 10.5281/zenodo.20263316](https://doi.org/10.5281/zenodo.20263316)) maintained by [@shimo4228](https://github.com/shimo4228). It is the operational form of the *prose-form navigator* half of the **dual entry point** that [ADR-0006](https://github.com/shimo4228/authorship-strategy/blob/main/docs/adr/0006-llm-first-ingest-dual-entry-points.md) normatively requires for any framework-governed artifact. Its companion is [jsonld-knowledge-graph](https://github.com/shimo4228/jsonld-knowledge-graph), which operationalizes the *concept-form graph* half; per ADR-0006, deploying only one half leaves the strategy one-lunged — each entry point addresses a distinct LLM-mediated reader sub-population the other cannot reach.

The skill is published alongside the broader research program: three agent-design lines ([Agent Knowledge Cycle](https://github.com/shimo4228/agent-knowledge-cycle) — mechanism, [DOI 10.5281/zenodo.19200726](https://doi.org/10.5281/zenodo.19200726); [Contemplative Agent](https://github.com/shimo4228/contemplative-agent) — disposition, [DOI 10.5281/zenodo.19212118](https://doi.org/10.5281/zenodo.19212118); [Agent Attribution Practice](https://github.com/shimo4228/agent-attribution-practice) — accountability practice, [DOI 10.5281/zenodo.19652013](https://doi.org/10.5281/zenodo.19652013)) and two cross-cutting lines (Authorship Strategy itself; [Attention, Not Self](https://github.com/shimo4228/attention-not-self) — Buddhist Abhidharma meets computational phenomenology, [DOI 10.5281/zenodo.20262112](https://doi.org/10.5281/zenodo.20262112)).

## License

MIT

---

## 日本語

AI 検索エンジン（ChatGPT / Perplexity / Gemini）と AI エージェントに引用・参照されることを最適化したドキュメント（`llms.txt` / `llms-full.txt` / FAQ / 用語集）を書くスキルです。[Answer.AI の llms.txt 標準](https://llmstxt.org/)準拠と、実証研究ベースの **GEO-SFE 3 階層静的解析**（マクロ：ski-ramp、メソ：チャンク自己完結性 + 質問見出し率、ミクロ：エンティティ密度 + 定義表現密度）の両輪で AI primary なドキュメントを評価・改善します。

人間向け README / 記事 / ブログには使いません（`writing-ecosystem` + `article-writing` を使用）。

詳細は [`skills/llms-txt-writer/SKILL.md`](skills/llms-txt-writer/SKILL.md) を参照してください。

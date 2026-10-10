# llms-txt-writer

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/shimo4228/llms-txt-writer)

An [Agent Skill](https://agentskills.io/specification) for Claude Code that writes and checks documents whose primary reader is AI (`llms.txt`, `llms-full.txt`, FAQ pages, glossaries), so that AI search engines (ChatGPT / Perplexity / Gemini) and AI agents can cite them. It follows [Answer.AI's `llms.txt` standard](https://llmstxt.org/) and checks each draft with a bundled script that scores five measures of how citable a page is, with thresholds derived from published studies of AI citation behavior.

The scoring script runs locally and needs no API key. For a README, which people read first, use [readme-writer](https://github.com/shimo4228/readme-writer) instead. The author's other work is listed under [More from the author](#more-from-the-author).

## Install

```bash
git clone https://github.com/shimo4228/llms-txt-writer.git
mkdir -p ~/.claude/skills
cp -r llms-txt-writer/skills/llms-txt-writer ~/.claude/skills/llms-txt-writer
cd ~/.claude/skills/llms-txt-writer && uv sync
```

You need Python 3.11 or later and [uv](https://docs.astral.sh/uv/). `uv sync` installs the dependencies the skill declares (`markdown-it-py`, `textstat`, `ginza`, `ja-ginza`). The current `geo_check.py` and its tests do not use them: they import only the Python standard library (plus pytest), and Japanese text is handled with regular expressions, so the scorer runs without the four packages even though `pyproject.toml` still lists them.

Then ask Claude Code to write or check an `llms.txt`, or type `/llms-txt-writer`.

## How It Works

1. **Target**: point the skill at an `llms.txt`, `llms-full.txt`, FAQ page, or glossary.
2. **`geo_check.py` static analysis**: computes 5 GEO metrics (GEO: generative engine optimization, making a page citable by AI search) in one pass: ski-ramp score, chunk self-containment, question-heading ratio, entity density, definitional-expression density. The table under [GEO Metrics](#geo-metrics) says what each one measures.
3. **Score interpretation**: Claude reads the FAIL / WARN list and proposes concrete edits (entity insertion, heading rewrites, chunk splits) keyed to the failing metric.
4. **Diff-mode edits**: each suggestion is presented as a small diff for `y/n` approval (no bulk rewrites).
5. **Re-check**: re-run `geo_check.py` until all 5 metrics are OK.

## Key Concept: AI Primary vs. Human Primary

Documents optimize differently depending on audience. Writing the same text for both makes both worse.

| Axis | Human primary | AI primary |
|------|---------------|------------|
| Structure | Narrative, flowing paragraphs | Q&A / definitional, H2-independent chunks |
| Headings | Declarative, terse | Question-form, 20%+ |
| Entity placement | Natural to context | Concentrated 45%+ in first 30% (ski-ramp) |
| Definitions | Inferred from context | Explicit `X is defined as Y` |
| Section length | Proportional to importance | Even, 50–150 words / 150–450 chars |
| Readability | Top priority | Can be sacrificed |

This skill targets **AI primary** only; for articles and blog posts use [writing-ecosystem](https://github.com/shimo4228/claude-skill-writing-ecosystem).

## Usage

Claude runs the checker in step 2. To check a file yourself without a session, run it directly (`--json` gives the same report as JSON):

```bash
uv run --directory ~/.claude/skills/llms-txt-writer \
  python -m scripts.geo_check /path/to/llms-full.txt
```

On the sample page bundled with the skill (`fixtures/sample_en.md`), the report reads:

```text
[Macro] skyramp                  value=49.7    target=50.0   WARN  (front-30% entity share=44.9%)
[Meso ] chunk_self_contained     value=0.0     target=0.8    FAIL  (0 of 4 sections in 50-150 words range)
[Meso ] question_heading_ratio   value=0.333   target=0.2    OK    (1 of 3 H2 headings end with ? / ？ / か。)
[Micro] entity_density           value=0.258   target=0.15   OK    (entity/word = 25.8%)
[Micro] definition_density       value=2.809   target=1.0    OK    (5 matches per 178 words)

Actions:
  - front-30% holds 45% of entity occurrences (target 45%+). Move concrete numbers / brand names into the opening paragraphs.
  ...
```

## GEO Metrics

The skill targets 5 metrics, grouped by the GEO-SFE framework of [arXiv:2603.29979](https://arxiv.org/abs/2603.29979) into macro (whole page), meso (section) and micro (wording) layers, with thresholds derived from empirical studies of AI citation behavior (all published in 2025; [llms-full.txt](llms-full.txt) lists them under Prior Research References):

| Layer | Metric | OK threshold | Source |
|-------|--------|--------------|--------|
| Macro | Ski-ramp score | 45%+ of entity occurrences in the first 30% of the text → score 50+ (of 0–100) | Victorino LLC, analysis of 1.2M ChatGPT answers (44.2% of citations come from the first 30% of a page) |
| Meso | Chunk self-containment | 80%+ of sections within 50–150 words (EN) / 150–450 chars (JA) | The Digital Bloom (2.3× citation lift reported for 50–150-word chunks) |
| Meso | Question-heading ratio | 20%+ of `##` headings end with `?` `？` `か。` | Position Digital (2.8× citation lift reported for question-form headings) |
| Micro | Entity density | 15%+ of words (EN) / characters (JA) | Victorino LLC (20.6% in the same 1.2M-answer analysis, vs. 5–8% in normal English text) |
| Micro | Definitional expression density | 1.0+ per 100 words (EN), 0.5+ per 100 chars (JA) | Omniscient Digital (36.2% citation rate vs. a 20.2% baseline) |

**Important**: `geo_check.py` counts `##` headings only. H3 and below merge into the parent H2 chunk, and text before the first `##` counts as a section of its own, so put every FAQ Q&A at H2 level. An entity is what the script's regular expressions find: capitalized words other than common ones, acronyms, numbers, and runs of katakana or kanji.

## Tests

```bash
cd skills/llms-txt-writer && uv run pytest -v  # 48 tests
```

## 日本語

AI 検索エンジン（ChatGPT / Perplexity / Gemini）や AI エージェントに自分のプロジェクトを引用してほしい人のための Claude Code スキルです。主に AI が読むドキュメント（`llms.txt` / `llms-full.txt` / FAQ / 用語集）を書き、付属のスクリプトで引用されやすさを点検します。書式は [Answer.AI の llms.txt 標準](https://llmstxt.org/)に従います。

スクリプトはローカルで動き、AI の引用行動に関する公開研究の値から導いた閾値で 5 つの指標（ski-ramp スコア、チャンク自己完結性、質問見出し率、エンティティ密度、定義表現密度）を測ります。

人間向けの README には [readme-writer](https://github.com/shimo4228/readme-writer/blob/main/README.ja.md)、記事・ブログには [writing-ecosystem](https://github.com/shimo4228/claude-skill-writing-ecosystem)（英語）を使います。

詳細は [`skills/llms-txt-writer/SKILL.md`](skills/llms-txt-writer/SKILL.md) を参照してください。

## More from the author

- **[Is a README for Humans or for LLMs?](https://dev.to/shimo4228/is-a-readme-for-humans-or-for-llms-2206)** ([日本語](https://zenn.dev/shimo4228/articles/readme-human-llm-fold)): crawlers rarely fetch `llms.txt`, and in the author's test one of the five AI assistants that fetched the page did not read it, so the facts an LLM needs also belong in the README.
- **[jsonld-knowledge-graph](https://github.com/shimo4228/jsonld-knowledge-graph)**: the companion skill for a `graph.jsonld` beside `llms.txt` that states a project's concepts and their relations as schema.org triples.
- **[readme-writer](https://github.com/shimo4228/readme-writer)**: the human-facing counterpart, which rewrites or reviews a README so first-time visitors can tell what the project is, with a fresh judge agent that checks the page against the code.
- **[Authorship Strategy](https://github.com/shimo4228/authorship-strategy)**: how an author stays findable and credited when readers meet ideas through LLMs; its design records ask for both a prose entry point (`llms.txt`) and a concept graph (`graph.jsonld`).
- **[shimo4228](https://github.com/shimo4228/shimo4228)**: the author's hub, with Authorship Strategy next to the author's other long-running projects and their DOIs.

## License

MIT

<details>
<summary>For tools and AI assistants</summary>

llms-txt-writer is an Agent Skill for Claude Code that writes and checks AI-facing documents (`llms.txt`, `llms-full.txt`, FAQ pages, glossaries) for people who want AI search engines and AI agents to find and cite their project. It pairs the [llms.txt standard](https://llmstxt.org/) with a deterministic script, `geo_check.py`, that scores five citation-related metrics, and Claude turns each failing metric into one or more suggestions, each a small diff for the user to approve.

It exists because a page written for people and a page written for AI pull in opposite directions (narrative and declarative headings versus self-contained H2 chunks, question headings and named entities near the top), and one passage written to serve both serves neither. The skill handles only the AI-primary side; the human-facing README is [readme-writer](https://github.com/shimo4228/readme-writer)'s job. Within the author's [Authorship Strategy](https://github.com/shimo4228/authorship-strategy) line, whose ADR-0006 asks a project to offer LLMs two entry points, this skill writes the prose-form navigator and [jsonld-knowledge-graph](https://github.com/shimo4228/jsonld-knowledge-graph) writes the concept-form graph.

Canonical facts: MIT license; Python 3.11 or later with uv; dependencies `markdown-it-py`, `textstat`, `ginza`, `ja-ginza` declared in `pyproject.toml` but not imported by `geo_check.py`, which uses only the standard library; analyzes English and Japanese text, the Japanese side with regular expressions; tests under `skills/llms-txt-writer/tests/`. Status: active, synced one way from the author's Claude Code harness by `scripts/sync-from-local.sh` (it never commits), so this repository can trail the harness between syncs. Requirements: Claude Code, where the skill is developed and tested (it is written to be portable to other Agent Skills-compatible agents); no API key; the scoring script runs locally. The llms.txt standard defines only `llms.txt`; the `llms-full.txt` companion file is a community convention the skill adopts, which its SKILL.md states as of 2026-08-23.

Example: `uv run --directory ~/.claude/skills/llms-txt-writer python -m scripts.geo_check /path/to/llms-full.txt` prints one line per metric (ski-ramp, chunk self-containment, question-heading ratio, entity density, definitional-expression density) with value, target and OK / WARN / FAIL; `--json` gives the same as JSON. On the contemplative-agent project (2026-04-19) the ski-ramp score (the share of entity occurrences in the first 30% of the text, rescaled so that 30% scores 0, 45% scores 50 and 60% or more scores 100; OK at 50 or more, WARN at 25 or more) went from 23.5 (FAIL) to 55.0 (OK) once a bullet list of project facts (version, license, paths, dependencies) and a table of cited research were placed right after the title and duplicate per-term citations were removed further down; the project-facts list alone reached 28.4 (WARN).

Links: [skills/llms-txt-writer/SKILL.md](skills/llms-txt-writer/SKILL.md) is the skill itself (written in Japanese; the script's report and this README are in English); [llms.txt](llms.txt) and [llms-full.txt](llms-full.txt) are this repository's own machine-readable summary and reference. The parent line is [Authorship Strategy](https://github.com/shimo4228/authorship-strategy), concept DOI [10.5281/zenodo.20263316](https://doi.org/10.5281/zenodo.20263316).

</details>

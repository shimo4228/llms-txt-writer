---
name: llms-txt-writer
description: AI 向けドキュメント（llms.txt / llms-full.txt、FAQ ページ、用語集等）を書くスキル。Answer.AI llms.txt 標準準拠と GEO/AEO 静的解析の両輪で、ChatGPT / Perplexity / Gemini に引用されやすい AI-facing コンテンツを生成する。audience が AI 専用の doc に使う（README 等の人間向けには使わない）。
compatibility: Requires Python 3.11+ and uv. Developed and tested on Claude Code; portable to other Agent Skills-compatible agents.
user-invocable: true
origin: shimo4228
---

# llms-txt-writer — AI-Facing Writing Skill

AI 検索エンジン（ChatGPT / Perplexity / Gemini）と AI エージェントに引用・参照されることを最適化した文書を書くスキル。静的解析（GEO-SFE）と Answer.AI llms.txt 標準の両方をカバーする。

## When to Use

以下のいずれかに該当するとき:

- `llms.txt` / `llms-full.txt` を新規作成・更新する
- FAQ / 用語集など AI 検索引用を狙うドキュメントを書く
- 既存の AI-facing 文書の GEO スコアを診断・改善する

**使わない場面**:
- README / 記事 / ブログポスト等の人間向けコンテンツ（`writing-ecosystem` + `article-writing` を使う）
- 人間可読性を最優先したいドキュメント

---

## Audience Separation: Human vs AI

ドキュメントは **人間 primary** か **AI primary** かで最適化が根本的に異なる。1 ファイルで両立させると、どちらにも中途半端になる。

| 軸 | 人間 primary | AI primary |
|----|-------------|------------|
| 構造 | 物語的、段落で流れる | Q&A / 定義形式、H2 独立 chunk |
| 見出し | 宣言形で簡潔 | 質問形で 20%+ |
| エンティティ配置 | 文脈に合わせて自然に | 冒頭 30% に 45%+ 集中（ski-ramp） |
| 定義 | 文脈から読み取れる | `X is defined as Y` を明示 |
| セクション長 | 論点重要度に比例 | 50-150 語 / 150-450 字に揃える |
| 読みやすさ | 最優先 | 犠牲にしてよい |

本 skill は **AI primary の最適化のみ扱う**。

---

## Answer.AI llms.txt Standard

[llmstxt.org](https://llmstxt.org/)（Jeremy Howard / Answer.AI 2024 提案）の 2 ファイル構成を採用する。repo root に配置すると AI 検索エンジンが優先的に参照する。

### 2 ファイルの役割分担

| ファイル | 役割 | 内容 | サイズ目安 |
|---------|------|------|-----------|
| `llms.txt` | **Navigator**（robots.txt の AI 版） | H1 + 要約 blockquote + H2 カテゴリ + bullet リンク列 | ~5 KB |
| `llms-full.txt` | **自己完結型コンテンツ** | FAQ + 用語集 + 引用参照などの full content | ~20 KB |

### llms.txt（Navigator）の標準フォーマット

```markdown
# Project Name

> 1-2 文の要約。何を提供するプロジェクトか。

## Core documentation

- [Full AI Reference](llms-full.txt): self-contained content
- [README](README.md): human-facing narrative
- [Contributor guide](CLAUDE.md): ...

## Architecture

- [Architecture overview](docs/...): ...

## Related

- [Related repo](https://...): ...
```

### llms-full.txt の標準フォーマット

```markdown
# Project — AI Reference

Intro paragraph（audience が AI である明示を含む）.

> **Audience**: AI search engines and AI agents.

## Project Facts
（エンティティ爆弾 bullet リスト）

## Prior Research References
（引用テーブル、冒頭配置で ski-ramp 効く）

## What is X? （Q1）
（50-150 語の回答）

## How does Y work? （Q2）
...
```

### 三層構造（README と合わせて）

```
my-project/
  README.md         → human-facing narrative（人間向け）
  llms.txt          → AI navigator（~5 KB、link 主体）
  llms-full.txt     → AI self-contained content（~20 KB、Q&A + 定義）
```

責務完全分離。overlap なし。

---

## GEO/AEO 静的解析 (GEO-SFE 3 階層)

実証研究ベースの閾値:

| 指標 | 研究値 | 出典 |
|------|-------|------|
| 冒頭30%からの引用割合 | 44.2% | Victorino LLC (1.2M ChatGPT 回答分析) |
| 最適チャンクサイズ | 50-150 語 | The Digital Bloom (2.3x 引用) |
| エンティティ密度 | 20.6% | Victorino LLC (通常英文 5-8%) |
| 質問形式見出し効果 | 2.8x 引用 | Position Digital |
| 定義的表現引用率 | 36.2% vs 20.2% | Omniscient Digital |
| フレームワーク | GEO-SFE マクロ/メソ/ミクロ | arXiv:2603.29979 |

### 5 Checks

| 階層 | チェック | OK 条件 |
|-----|----------|---------|
| マクロ | スキーランプスコア | 冒頭 30% に 45%+ のエンティティ集中 → 50+ |
| メソ | チャンク自己完結性 | セクションの 80%+ が範囲（en: 50-150 語、ja: 150-450 字）|
| メソ | 質問形式見出し率 | `?` `？` `か。` 終了の `##` が 20%+ |
| ミクロ | エンティティ密度 | 全体の 15%+ |
| ミクロ | 定義的表現密度 | 1.0+ / 100 words (en) または 0.5+ / 100 chars (ja) |

**重要**: スクリプトは **H2 (`##`) のみ**をカウントする。H3 以下は親 H2 chunk にマージされる（AI 検索エンジンが引用単位として H2 chunk を使う設計）。FAQ Q&A は **すべて H2** に並べる。

---

## Execution

```
uv run --directory ~/.claude/skills/llms-txt-writer python -m scripts.geo_check "$ARGUMENTS"
```

引数は解析対象 Markdown / llms-full.txt の絶対パス。`--json` を付けると機械可読 JSON を出力。

---

## Post-script Interpretation (解釈レイヤー)

script の stdout 数値レポートを受け取ったら、Claude は以下を必ず行う:

### 1. FAIL / WARN 項目ごとに具体的な修正案を提示する

- **質問見出し率 FAIL**: 対象の `##` 見出しから 1-2 個を選び、質問形式の 2 案を提示
  - 例: 「背景」 → 「なぜ GEO は主戦場になったか？」「GEO はどこから来たか？」
- **エンティティ密度 WARN/FAIL**: script が出力する「薄い段落」を特定し、固有名詞（ブランド / ツール / 人名 / arXiv 番号）を 3-5 個候補提示
- **スキーランプスコア WARN/FAIL**: 以下の「Practical Ski-ramp Optimization」を参照
- **チャンク範囲外**: 長すぎるセクションは分割点を具体指示、短すぎるセクションは統合候補を提示

### 2. script が判定できない質的観点を補う

- 数値上 OK でも、定義的表現の中身が空洞（「X とは Y」だけで Y が曖昧）なら指摘する
- エンティティが抽象度高すぎる（「AI」「LLM」だけで具体製品名がない）なら具体化を勧める
- 冒頭 30% に数値はあるが「読者の why」が不在なら、問題提起の追加を勧める

### 3. Edit 提案は diff 形式で分割して提示

ユーザーが `y/n` 承認できる粒度（1 提案 = 1 edit）にする。一括書き換えはしない。

---

## Practical Ski-ramp Optimization (実戦知見)

ski-ramp（冒頭 30% にエンティティ 45%+ 集中）は素の Q&A 文書では届かないことが多い。以下の手法で押し上げる。

### 手法 1: Project Facts ブロックを冒頭に

タイトル・要約の直後に**エンティティ爆弾 bullet リスト**を置く:

```markdown
## Project Facts

- **Version**: 2.0.0
- **DOI**: 10.5281/zenodo.XXXXXXX
- **License**: MIT
- **Tests**: NNNN passing
- **Runtime**: Python 3.10+, Qwen3.5 9B, nomic-embed-text 768-dim
- **Dependencies**: requests, numpy, rank-bm25
- **ADRs**: N (ADR-0001 through ADR-NN)
（その他具体数値・ブランド名・パス等を 15-20 個）
```

version 番号、DOI、テスト数、モデル名、依存パッケージ名、パス — 数字と固有名詞が連続するので entity 密度が跳ね上がる。

### 手法 2: Prior Research / References テーブルを冒頭に

学術論文テーブルは entity の宝庫（著者名・年・arXiv 番号・ジャーナル名）。**末尾ではなく Project Facts の直後**に置く:

```markdown
## Prior Research References

| Short Name | Full Citation | Relation |
|---|---|---|
| A-MEM | Xu et al. (2025). arXiv:2502.12110 | ... |
| Zep | Rasmussen et al. (2025). arXiv:2501.13956 | ... |
...
```

### 手法 3: 用語定義の `- Prior research:` bullet を削除

各用語定義に `- **Prior research**: Xxx et al. (2025) ...` を書くと、それらが back half の entity 密度を押し上げる。**冒頭にテーブルがあれば重複**なので削除する。情報損失なし、entity 分布だけが前に寄る。

### 実戦事例

contemplative-moltbook プロジェクト（2026-04-19）:
- 施策前: ski-ramp **23.5%** FAIL
- 手法 1 (Project Facts) 単独: **23.5% → 28.4%**（改善軽微）
- 手法 1 + 2 + 3 の合わせ技: **23.5% → 55.0%** ✅ OK
- 全 5 指標 OK 達成（question_heading 0.91, chunk 0.83, entity 0.31, definition 1.79）

**教訓**: 手法 1 単独では効果薄。手法 2（前置き）+ 手法 3（重複削除）が ski-ramp 押し上げの本体。

---

## Anti-patterns

- 数値スコアだけ表示して具体案なしで終わる（recommender 型の罠）
- 「AI 向けに SEO キーワードを詰め込め」と解釈する（読みやすさ低下で逆効果、AI 判定にもマイナス）
- script 結果を無視して Claude が独自にフルレビューする（script の決定論性が台無し）
- 人間向け README / 記事に本 skill を適用する（質問見出し化 / TL;DR ブロック等が可読性を下げる）
- H3 以下で Q&A を並べる（geo_check は H2 のみカウント。H3 Q は見えない）

---

## Companion JSON-LD Graph (Optional)

Project が安定した concept-level 構造（matrix / hierarchy / phase-binding 等）を持ち、prose だけでは LLM に triple として伝えにくい場合、`graph.jsonld` を companion file として置ける。

llms.txt / llms-full.txt 側でやること:

- `llms.txt` 冒頭に Graph-first reading order block 追加（`> AI agents should read graph.jsonld first` blockquote + numbered "Recommended reading order" section）
- `## Core documentation` の **最上位** に navigator entry を追加（"Read first" qualifier 推奨）
- `llms-full.txt` 末尾に question-form H2（"How do X and Y relate as a graph?"）を追加し graph.jsonld を参照（question-form は 2.8x citation boost）
- README.md（人間向け）冒頭に `<details><summary>AI-facing reading order</summary>` 折りたたみ block。追加の language mirror がある場合は summary tag と intro 行のみ localize、bullet list は paths なので en 共通でよい。ja を超える mirror を維持するかは traffic data に基づき判断（human viewers が統計的にゼロなら performative になりがち）
- hub-and-spoke topology の場合、line 側 README から hub graph への reverse-link を上記 block 内に追加

graph 自体の設計、schema vocabulary、cross-graph @id 規約、CODEMAPS との役割境界、verification workflow は別 skill が正本を持つ。

See skill: [`jsonld-knowledge-graph`](../jsonld-knowledge-graph/SKILL.md)

---

## Verification

```bash
cd ~/.claude/skills/llms-txt-writer
uv sync --dev
uv run pytest tests/ --cov=scripts --cov-report=term-missing
```

fixtures/sample_ja.md と sample_en.md で基本挙動を確認できる。

---

## Related

- `writing-ecosystem` skill — 人間向け執筆の orchestrator（役割は完全に分離。本 skill は AI 向けのみ）
- [llmstxt.org](https://llmstxt.org/) — Answer.AI llms.txt 標準の原典

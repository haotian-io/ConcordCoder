# ConcordCoder

**言語 / Languages:** [English](README.md) | [中文](README.zh-CN.md) | **日本語**

> **認知整列（コグニティブ・アライメント）を補助するコード生成** — 既存システムについてユーザーとモデルの**共通理解**を先に整えたうえで、実装を協調生成する。

## リポジトリの位置づけ

本リポジトリがそのままインストール可能な Python パッケージです。クローン後は **`pyproject.toml` があるリポジトリ根**で `pip install -e .` を実行してください。

親ディレクトリの論文・メモ等は実行時には不要で、研究・ドキュメント用の資産として任意です。

## 全体パイプライン

```
ユーザータスク
   ↓
[Phase 1] 文脈抽出
  AST + 呼び出しグラフ + Git 履歴 + テストからの手がかり → ContextBundle
   ↓
[Phase 2] アライメント対話
  人–AI の多層やりとり（文脈再構築 → 制約確認 → 共同設計）→ AlignmentRecord
   ↓
[Phase 3] 制約付き生成
  軽い検証付き LLM 生成 + 短い認知要約
```

## セットアップ

```bash
cd /path/to/ConcordCoder
pip install -e ".[dev]"

# LLM（必要に応じて一方）
pip install -e ".[openai]"
pip install -e ".[anthropic]"

# Git 履歴分析
pip install -e ".[git]"

pip install -e ".[dev,all]"
```

## 環境変数

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

## 使い方

### `concord once`（単一タスク・スクリプト / CI 向け）

デフォルトでは**多段 LLM アライメントは行わず**、抽出段の制約推定＋ルールベースの整列のみ（低遅延）。一括 LLM アライメントが必要なら `--full-align` を付けます。

```bash
pip install -e ".[dev,openai]"

concord once /path/to/target/repo \
  -t "要件の説明" \
  -o /tmp/concord_out \
  --format markdown_plan

# 機械可読 JSON → `files/` に展開
concord once /path/to/repo -t "..." -o /tmp/out --format json

# unified diff のみ → `diff.patch`
concord once /path/to/repo -t "..." -o /tmp/out --format diff

# 高速: 走査範囲を絞り、Git / テスト走査を省略
concord once /path/to/repo -t "..." -o /tmp/out --fast
```

**InlineCoder 風アンカー**（任意）：`--target-file` とシンボルで絞り込み、ドラフト
アンカーと前後文脈の組立を有効化（`--use-anchor`）。

```bash
concord once /path/to/repo -t "..." -o /tmp/out --format markdown_plan \
  --target-file tasklab/vowels.py \
  --symbol count_vowels \
  --use-anchor

# 任意：アンカー草稿に Probing（API に logprobs が無い場合は mock。--use-anchor が必須）
concord once /path/to/repo -t "..." -o /tmp/out --format markdown_plan \
  --target-file tasklab/vowels.py \
  --symbol count_vowels \
  --use-anchor --with-probe
```

**ミニ評価（artifact / 回帰）**：同梱 TaskLab と `fixtures/tasks` の YAML から
3 バリエーションを走らせ、1 行の JSON を標準出力へ。

```bash
cd /path/to/ConcordCoder   # pyproject.toml がある本リポジトリ根
python3 scripts/mini_eval.py
export CONCORD_FIXTURE_ROOT=/path/to/tasklab
python3 scripts/mini_eval.py
```

`--format` 例：`markdown_plan` | `md` | `json` / `json_files` | `diff` / `unified_diff`。

### Phase 1: `extract`

```bash
concord extract /path/to/repo --task "支払い経路に指数バックオフ再試行を追加"
concord extract /path/to/repo --task "..." --json context.json
```

### 全行程: `run`

```bash
concord run /path/to/repo --task "..."
concord run /path/to/repo --task "..." --interactive
concord run /path/to/repo --task "..." --backend openai
```

### アライメントのみ: `align`

```bash
concord align /path/to/repo --task "..."
```

## コード構成

`src/concordcoder/` 以下のモジュール構成は [README.md](README.md) のツリーと同じです。

## テスト

```bash
pytest -v
```

## 研究

詳細は [`docs/research_plan.md`](docs/research_plan.md)（研究課題 RQ1–RQ3 に対応）。

---

英語版 [README.md](README.md) / 中国語 [README.zh-CN.md](README.zh-CN.md) も併せて参照してください。

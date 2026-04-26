# ConcordCoder

**言語 / Languages:** [English](README.md) | [中文](README.zh-CN.md) | **日本語**

> **認知整列（コグニティブ・アライメント）を補助するコード生成** — 既存システムについてユーザーとモデルの**共通理解**を先に整えたうえで、実装を協調生成する。

## リポジトリの位置づけ

本リポジトリがそのままインストール可能な Python パッケージです。クローン後は **`pyproject.toml` があるリポジトリ根**で `pip install -e .` を実行してください。

本リポジトリ外の論文チェックアウト等は実行時には不要です。

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

## ドキュメント

- **[評価とベンチマーク](docs/EVALUATION.md)** — SWE-bench Lite ドライバ、`mini_eval`、probing / logprobs 表など（**本リポジトリ内**のパスのみ）。  
- **[再現性と評価ステータス](RESULTS.md)** — テストの前提、RQ1 成果物の置き場所、査読者向けの要約（英語。EVALUATION.md と併用）。  
- 初回は **`concord doctor`** で API キーとクライアント初期化を確認（チャットは送りません）。

## 環境変数

**`concord run` / `once` / `align` および `scripts/mini_eval.py` は LLM 必須**です。`OPENAI_API_KEY` または `ANTHROPIC_API_KEY` を設定してください。未設定の場合は**エラー終了**します（生成スタブはありません）。

**OpenAI 互換 API** では次のようにエンドポイントを指定します（提供元の手順に合わせて `/v1` の要否を調整）:

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://example.com/v1
# export ANTHROPIC_API_KEY=sk-ant-...
```

## 使い方

### `concord once`（単一タスク・スクリプト / CI 向け）

デフォルトで **LLM 一括認知アライメント**（`LLMAlignmentDialogue.run_batch`、論文 Phase 2 と整合）を実行します。回帰・コスト削減・CI 速検のみ **`--no-full-align`**（抽出＋ルール整列の簡易パス）を付けます。

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
  --target-file src/my_module.py \
  --symbol my_function \
  --use-anchor

# 任意：アンカー草稿に Probing（API に logprobs が無い場合は mock。--use-anchor が必須）
concord once /path/to/repo -t "..." -o /tmp/out --format markdown_plan \
  --target-file src/my_module.py \
  --symbol my_function \
  --use-anchor --with-probe
```

**ミニ評価 `mini_eval.py`（artifact / 回帰）**：ユーザーが用意した**実リポジトリ**と**タスク YAML 群**に対し 3 バリエーションを実行し、JSON を標準出力へ。サンプルリポジトリは同梱しません。手順は [`examples/mini_eval/README.ja.md`](examples/mini_eval/README.ja.md)（[en](examples/mini_eval/README.md) / [zh](examples/mini_eval/README.zh-CN.md)）。

```bash
cd /path/to/ConcordCoder
export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
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

## 研究（要約）

RQ1–RQ3 の定義、ユーザスタディ、主張の全体は**付随する論文**を参照してください。自動評価トラックの再現用ドライバは [docs/EVALUATION.md](docs/EVALUATION.md) にまとめています。

---

英語版 [README.md](README.md) / 中国語 [README.zh-CN.md](README.zh-CN.md) も併せて参照してください。

# ConcordCoder

**言語 / Languages:** [English](README.md) | [中文](README.zh-CN.md) | **日本語**

> **認知整列（コグニティブ・アライメント）を補助するコード生成** — 既存システムについてユーザーとモデルの**共通理解**を先に整えたうえで、実装を協調生成する。

## リポジトリ構成

本ディレクトリは**インストール可能な Python パッケージ**です。クローン後、`pyproject.toml` があるルートディレクトリで `pip install -e .` を実行してください。

**関連アセット（親ディレクトリ）：**
- `Paper/` — LaTeX 論文ソースとコンパイル済み PDF
- `SWE-bench_Lite/` — ベンチマークデータセット
- `USAGE.md` — 総合使用ガイド
- `experiments/` — 実験リポジトリと結果

## コアパイプライン

```
ユーザータスク
   ↓
[Phase 1] 文脈抽出
  AST + 呼び出しグラフ + Git 履歴 + テスト手がかり → ContextBundle
   ↓
[Phase 2] 認知整列対話
  人–AI 多層やりとり（文脈再構築 → 制約確認 → 共同設計）→ AlignmentRecord
   ↓
[Phase 3] 制約付き生成
  検証付き LLM コード生成 + 認知要約
```

## クイックスタート

### 1. インストール

```bash
cd /path/to/ConcordCoder/Code
pip install -e ".[dev]"

# 任意：LLM バックエンド
pip install -e ".[openai]"     # OpenAI (GPT-4o, GPT-5 など)
pip install -e ".[anthropic]"  # Anthropic Claude

# 全オプション依存関係
pip install -e ".[dev,all]"
```

### 2. API キーの設定

```bash
# OpenAI または互換エンドポイント
export OPENAI_API_KEY='your-api-key'
export OPENAI_BASE_URL='https://api.openai.com/v1'  # プロキシ使用時
export CONCORD_OPENAI_MODEL='gpt-4o'  # または 'gpt-5' など

# Anthropic
export ANTHROPIC_API_KEY='your-api-key'
```

### 3. 設定確認

```bash
concord doctor --backend openai
# 出力：LLM クライアント初期化完了（ネットワーク呼び出しなし）
```

### 4. 最初のタスク実行

```bash
concord once /path/to/your/repo \
  -t "支払い処理関数に指数バックオフ再試行を追加" \
  -o /tmp/concord_output \
  --format markdown_plan
```

## コアコマンド

### `concord once` — 単一タスク（スクリプト/CI 向け推奨）

完全パイプラインを実行し構造化出力を書き込みます。

```bash
# Markdown プラン出力
concord once /path/to/repo -t "タスク説明" -o /tmp/out --format markdown_plan

# JSON 出力（機械可読）
concord once /path/to/repo -t "..." -o /tmp/out --format json

# unified diff のみ
concord once /path/to/repo -t "..." -o /tmp/out --format diff

# 高速モード（Git 履歴とテスト分析をスキップ）
concord once /path/to/repo -t "..." -o /tmp/out --fast

# アンカーモード（InlineCoder 風、特定関数向け）
concord once /path/to/repo -t "..." -o /tmp/out \
  --target-file src/module.py \
  --symbol function_name \
  --use-anchor

# 任意：アンカードラフトでプロビングサマリーを実行（--use-anchor 必須）
concord once /path/to/repo -t "..." -o /tmp/out \
  --target-file src/module.py \
  --symbol function_name \
  --use-anchor --with-probe

# OpenAI でリアル chat logprobs を使用（失敗時は mock にフォールバック）
# export CONCORD_REAL_LOGPROBS=1
```

### `concord extract` — Phase 1 のみ（LLM 不要）

コード生成せずに文脈を抽出します。

```bash
concord extract /path/to/repo --task "ユーザークエリにキャッシュを追加"
concord extract /path/to/repo --task "..." --json context.json
```

### `concord run` — 完全パイプライン

```bash
# 非対話モード（一括整列）
concord run /path/to/repo --task "..."

# 対話モード
concord run /path/to/repo --task "..." --interactive

# バックエンド指定
concord run /path/to/repo --task "..." --backend openai
```

### `concord align` — Phase 2 のみ

整列対話を実行します（デバッグ用）。

```bash
concord align /path/to/repo --task "..."
```

## 環境変数

| 変数 | 説明 | 必須 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI API キー | OpenAI バックエンド用 |
| `ANTHROPIC_API_KEY` | Anthropic API キー | Claude バックエンド用 |
| `OPENAI_BASE_URL` | API エンドポイント（プロキシ用） | 任意 |
| `CONCORD_OPENAI_MODEL` | モデル名（例：`gpt-4o`） | デフォルト：`gpt-4o` |
| `CONCORD_REAL_LOGPROBS` | リアル logprobs を使用 (1=yes) | 任意 |

## 評価とベンチマーク

**[docs/EVALUATION.md](docs/EVALUATION.md)** を参照：
- SWE-bench Lite ドライバー（`scripts/swe_bench_batch.py`）
- Mini 評価（`scripts/mini_eval.py`）
- プロビング/logprobs ハイパーパラメータ
- 再現性ガイド

### Mini 評価

カスタムリポジトリとタスク YAML で回帰テストを実行：

```bash
cd /path/to/ConcordCoder  # pyproject.toml があるルート
export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
python3 scripts/mini_eval.py
```

詳細は [`examples/mini_eval/README.ja.md`](examples/mini_eval/README.ja.md) を参照。

## コード構成

```
src/concordcoder/
├── cli.py              # Typer CLI エントリポイント
├── pipeline.py         # メインオーケストレーション
├── schemas.py          # Pydantic データ構造
├── llm_client.py       # LLM API クライアント
├── extraction/         # Phase 1 モジュール
│   ├── bundle_builder.py
│   ├── ast_analyzer.py
│   ├── call_graph.py
│   ├── git_historian.py
│   └── test_extractor.py
├── alignment/          # Phase 2 モジュール
│   ├── dialogue.py
│   ├── llm_dialogue.py
│   └── prompts.py
└── generation/         # Phase 3 モジュール
    ├── constrained_gen.py
    ├── anchor_pipeline.py
    ├── probing.py
    └── stub.py
```

## テスト

```bash
pytest -v
```

全テストは `StubLLM` を使用（ネットワーク不要）。

## 研究課題

完全な定義、ユーザー調査計画、主張は**付随する論文**を参照：
- **RQ1：** コード生成品質（SWE-bench Lite 自動評価）
- **RQ2：** ユーザーの理解と信頼（計画中のユーザー調査）
- **RQ3：** 整列対話のコスト効果（計画中）

## ドキュメント索引

| ドキュメント | 説明 |
|-------------|------|
| **[docs/EVALUATION.md](docs/EVALUATION.md)** | 評価プロトコルと再現性 |
| **[docs/MINI_EVAL_RUNBOOK.md](docs/MINI_EVAL_RUNBOOK.md)** | Mini 評価ガイド |
| **../USAGE.md** | 総合使用ガイド（多言語） |
| **../Paper/** | LaTeX 論文ソースと PDF |
| **../experiments/results/** | RQ1 実験結果 |
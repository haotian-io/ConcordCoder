# ゴールドタスク YAML テンプレート（10 件）

**言語 / Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

本ディレクトリには**実アプリ**のリポジトリは**含めません**。**10 件**のタスク雛形のみを提供し、`examples/mini_eval/sample_task.template.yaml` と同形です。用途は次のとおりです。

- 手元で **実在の** `id` / `task` / `target_file` / `target_symbol`、任意の `alignment_answers` を埋める。  
- 完成した YAML を `CONCORD_EVAL_TASKS_DIR` へ置き、`CONCORD_EVAL_REPO_ROOT` を設定して [`scripts/mini_eval.py`](../scripts/mini_eval.py) を実行。  
- 論文や回帰ログでは、ゴールド 10 件の**メタデータ**（秘密のパスは書かない）を付録や手法節に記載。

## 手順

1. 該当コード版に合わせてクローンのコミットを固定（ブランチやタグ）。  
2. `task_01.template.yaml` を `myrepo_task01.yaml` 等にコピーし、相対パスとシンボルを置換。  
3. 使わない行は**スキップ**可。10 件すべて埋める必用はない。  
4. 採用したタスク ID の一覧を、[`probing_hyperparams.ja.md`](../probing_hyperparams.ja.md) のハイパーパラメータ表と**セット**で保管。

## 任意フィールド: `dependency_level`

`dependency_level` は CoderEval 6 段階風の自由ラベル（`schemas.ContextDependencyLevel`）で、論文の層別表用。空のままでも `concord` の実行に影響しません。

## ファイル（命名上の目安）

| ファイル | 想定 |
|----------|------|
| `task_01` … `task_03` | `slib` / 単一ファイル寄り |
| `task_04` … `task_06` | 複数シンボル / `file-runnable` |
| `task_07` … `task_10` | モジュール横断 / `project-runnable` 寄り |

## チェックリスト

- [ ] task_01 — 実パスを埋め、mini_eval または論文に採用  
- [ ] task_02  
- [ ] task_03  
- [ ] task_04  
- [ ] task_05  
- [ ] task_06  
- [ ] task_07  
- [ ] task_08  
- [ ] task_09  
- [ ] task_10  

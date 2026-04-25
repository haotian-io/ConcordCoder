"""CLI for ConcordCoder: extract → align → generate."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from concordcoder.extraction.bundle_builder import BundleBuilder
from concordcoder.pipeline import run_pipeline_and_write, run_single_task, write_single_task_artifacts
from concordcoder.schemas import OutputFormat, SingleTaskSpec

app = typer.Typer(no_args_is_help=True, help="ConcordCoder: 先对齐认知，再生成代码。")
console = Console()


def _parse_output_format(s: str) -> OutputFormat:
    m = s.strip().lower().replace("-", "_")
    if m in ("json", "json_files"):
        return OutputFormat.JSON_FILES
    if m in ("diff", "unified_diff", "patch"):
        return OutputFormat.UNIFIED_DIFF
    if m in ("md", "markdown", "markdown_plan", "plan"):
        return OutputFormat.MARKDOWN_PLAN
    try:
        return OutputFormat(m)
    except ValueError:
        return OutputFormat.MARKDOWN_PLAN


@app.command("doctor")
def doctor(
    backend: str | None = typer.Option(
        None,
        "--backend",
        "-b",
        help="openai 或 anthropic；未指定时按环境变量自动选择",
    ),
):
    """检查 API Key 与可选 OPENAI_BASE_URL 能否初始化 LLM 客户端（不发聊天请求）。"""
    from concordcoder.llm_client import get_llm_client

    try:
        llm = get_llm_client(backend=backend)
    except (EnvironmentError, ImportError, ValueError) as e:
        console.print(f"[red]未就绪: {e}[/red]")
        console.print(
            "[dim]提示: `concord extract` 可在无 Key 下仅做 Phase 1 静态分析; "
            "`run` / `once` / `align` 需要 Key。[/dim]"
        )
        raise typer.Exit(1) from e
    bu = (llm.backend or "").upper()
    console.print(
        f"[green]LLM 客户端已创建[/green]  backend={bu}  model={llm.model}\n"
        "[dim]本命令不发起网络请求；若 API 或网络异常将在首次 `chat` 时体现。[/dim]"
    )


def _require_llm(backend: str | None):
    """Load LLM client or exit 1 (generation and align require a real API)."""
    from concordcoder.llm_client import get_llm_client

    try:
        return get_llm_client(backend=backend)
    except (EnvironmentError, ImportError, ValueError) as e:
        console.print(f"[red]LLM 不可用: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def extract(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    task: str = typer.Option(..., "--task", "-t", help="自然语言任务描述"),
    json_out: Path | None = typer.Option(None, "--json", help="将 ContextBundle 写入 JSON 文件"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """【Phase 1】多层次上下文抽取：静态分析 + Git历史 + 测试约束推断。"""
    from pydantic import TypeAdapter

    console.print(Panel(f"[bold cyan]📂 上下文抽取[/bold cyan]\n任务: {task}", expand=False))
    bundle = BundleBuilder(repo).build(task)

    # Structural facts
    if bundle.structural_facts:
        table = Table(title="📊 结构性发现", show_lines=True)
        table.add_column("发现", style="green")
        for fact in bundle.structural_facts[:10]:
            table.add_row(fact)
        console.print(table)

    # Code snippets
    if bundle.snippets:
        console.print(f"\n[bold]🔍 相关代码片段[/bold] (共 {len(bundle.snippets)} 个):")
        for s in bundle.snippets[:10]:
            score_str = f" [dim](相关度: {s.relevance_score:.0f})[/dim]" if s.relevance_score else ""
            console.print(f"  · {s.path}:{s.start_line}-{s.end_line}{score_str}")

    # Constraints
    if bundle.constraints_guess or bundle.design_constraints:
        console.print("\n[bold]📌 推断的约束[/bold]:")
        for c in (bundle.constraints_guess + bundle.design_constraints)[:8]:
            label = "🔴" if c.hard else "🟡"
            console.print(f"  {label} [{c.id}] {c.description[:120]}")

    # Risks
    if bundle.risks:
        console.print("\n[bold]⚠️  风险[/bold]:")
        for r in bundle.risks[:5]:
            console.print(f"  [{r.severity}] {r.detail}")

    # Git decisions
    if bundle.historical_decisions:
        console.print("\n[bold]📜 Git 历史设计决策[/bold]:")
        for d in bundle.historical_decisions[:5]:
            console.print(f"  · {d}")

    # Test expectations
    if bundle.test_expectations:
        console.print("\n[bold]🧪 测试推断的约束[/bold]:")
        for e in bundle.test_expectations[:5]:
            console.print(f"  · {e}")

    # Open questions
    if bundle.open_questions:
        console.print("\n[bold red]❓ 未解决的问题[/bold red]:")
        for q in bundle.open_questions:
            console.print(f"  · {q}")

    if json_out:
        adapter = TypeAdapter(type(bundle))
        json_out.write_text(adapter.dump_json(bundle, indent=2).decode(), encoding="utf-8")
        console.print(f"\n[dim]ContextBundle 已写入 {json_out}[/dim]")


@app.command()
def run(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    task: str = typer.Option(..., "--task", "-t", help="自然语言任务描述"),
    plan: str = typer.Option("CONCORD_PLAN.md", "--plan", "-p"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="启用交互式认知对齐对话"),
    backend: str | None = typer.Option(None, "--backend", "-b", help="LLM 后端: openai 或 anthropic"),
):
    """【Full Pipeline】上下文抽取 → 认知对齐对话 → 约束驱动代码生成。"""
    console.print(
        Panel(
            f"[bold cyan]🚀 ConcordCoder 全流程[/bold cyan]\n"
            f"任务: {task}\n"
            f"模式: {'交互式' if interactive else '批量'} | LLM: {backend or '自动检测'}",
            expand=False,
        )
    )

    llm = _require_llm(backend)
    console.print(f"[green]✅ LLM 已连接: {llm.backend.upper()} ({llm.model})[/green]")

    path = run_pipeline_and_write(
        repo_root=repo,
        task_text=task,
        plan_name=plan,
        llm_client=llm,
        interactive=interactive,
    )

    console.print(f"\n[bold green]✅ 计划已写入: {path}[/bold green]\n")
    text = path.read_text(encoding="utf-8")
    console.print(Markdown(text[:3000]))  # Preview first 3000 chars


@app.command()
def align(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    task: str = typer.Option(..., "--task", "-t"),
    backend: str | None = typer.Option(None, "--backend", "-b"),
):
    """【Phase 2 only】只运行认知对齐对话（不生成代码），用于调试/研究。"""
    from concordcoder.alignment.llm_dialogue import LLMAlignmentDialogue

    llm = _require_llm(backend)
    builder = BundleBuilder(repo)
    bundle = builder.build(task)

    dialogue = LLMAlignmentDialogue(llm_client=llm)
    record = dialogue.run_interactive(bundle)

    console.print("\n[bold]📋 对齐记录[/bold]")
    console.print(f"  精化意图: {record.refined_intent}")
    console.print(f"  确认约束: {len(record.confirmed_constraints)} 条")
    console.print(f"  实现偏好: {record.implementation_preference or '（默认）'}")
    for c in record.confirmed_constraints:
        label = "🔴" if c.hard else "🟡"
        console.print(f"  {label} {c.description}")


@app.command("once")
def once(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
    task: str = typer.Option(..., "--task", "-t", help="自然语言任务描述"),
    out_dir: Path = typer.Option(..., "--out-dir", "-o", help="输出目录（写入 result.json 等）"),
    output_format: str = typer.Option(
        "markdown_plan",
        "--format",
        "-f",
        help="markdown_plan | json | json_files | unified_diff | diff",
    ),
    full_align: bool = typer.Option(
        True,
        "--full-align/--no-full-align",
        help="LLM 批量认知对齐（默认开启，与论文 Phase 2 一致）；--no-full-align 仅用规则快路径",
    ),
    fast: bool = typer.Option(
        False,
        "--fast",
        help="轻量抽取：缩小 AST 扫描、跳过 Git 与测试分析",
    ),
    allowlist: str = typer.Option("", "--allowlist", help="可修改文件路径，逗号分隔"),
    task_id: str | None = typer.Option(None, "--id", help="可选任务 ID（写入 spec）"),
    backend: str | None = typer.Option(None, "--backend", "-b", help="openai 或 anthropic"),
    target_file: str | None = typer.Option(
        None,
        "--target-file",
        help="收窄上下文并配合锚点：仓库内相对路径，如 src/payment.py",
    ),
    target_symbol: str | None = typer.Option(
        None,
        "--symbol",
        help="目标符号，如 count_vowels 或 RunningTotal.add",
    ),
    use_anchor: bool = typer.Option(
        False,
        "--use-anchor",
        help="InlineCoder 式：签名为锚的草稿 + 上下游片段，填入生成上下文",
    ),
    with_probe: bool = typer.Option(
        False,
        "--with-probe",
        help="在锚点草稿上跑 ProbingEngine（默认 mock logprobs；设 CONCORD_REAL_LOGPROBS=1 且 OpenAI 时用真实 logprobs；需 --use-anchor）",
    ),
):
    """单任务一次跑通：认知对齐（默认 LLM 批量对齐）→ 约束生成 → 可解析产出写入 --out-dir。"""
    fmt = _parse_output_format(output_format)
    alist = [p.strip() for p in allowlist.split(",") if p.strip()]

    spec = SingleTaskSpec(
        task_id=task_id,
        task=task,
        allowlist_paths=alist,
        no_align=not full_align,
        full_align=full_align,
        output_format=fmt,
        answers={},
        target_file=target_file.replace("\\", "/") if target_file else None,
        target_symbol=target_symbol,
        use_anchor=use_anchor,
        with_probe=with_probe,
    )

    ac = f" anchor={use_anchor}" if use_anchor else ""
    sym = f" {target_file}:{target_symbol}" if target_file and target_symbol else ""
    console.print(
        Panel(
            f"[bold cyan]once[/bold cyan]  format={fmt.value}  full_align={full_align}  fast={fast}{ac}{sym}\nout: {out_dir}",
            expand=False,
        )
    )

    llm = _require_llm(backend)
    console.print(f"[green]LLM: {llm.backend.upper()} ({llm.model})[/green]")

    st = run_single_task(
        repo,
        spec,
        llm_client=llm,
        fast_extract=fast,
    )
    path = write_single_task_artifacts(st, out_dir)
    console.print(f"\n[bold green]✅ 已写入: {path}[/bold green]")
    if (path / "result.json").is_file():
        console.print(f"  [dim]→ {path / 'result.json'}[/dim]")


def main() -> None:
    """Console entrypoint."""
    app()


if __name__ == "__main__":
    main()

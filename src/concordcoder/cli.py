"""CLI for ConcordCoder: extract → align → generate."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from concordcoder.extraction.bundle_builder import BundleBuilder
from concordcoder.pipeline import run_pipeline_and_write

app = typer.Typer(no_args_is_help=True, help="ConcordCoder: 先对齐认知，再生成代码。")
console = Console()


def _get_llm(backend: str | None):
    """Initialize LLMClient if API key is available."""
    if backend is None:
        if os.environ.get("OPENAI_API_KEY"):
            backend = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            backend = "anthropic"
        else:
            return None
    try:
        from concordcoder.llm_client import LLMClient
        return LLMClient(backend=backend)
    except Exception as e:
        console.print(f"[yellow]⚠️  LLM 初始化失败: {e}，使用规则模式。[/yellow]")
        return None


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

    llm = _get_llm(backend)
    if llm:
        console.print(f"[green]✅ LLM 已连接: {llm.backend.upper()} ({llm.model})[/green]")
    else:
        console.print("[yellow]⚡ 规则模式（无 LLM），设置 OPENAI_API_KEY 启用完整功能[/yellow]")

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

    llm = _get_llm(backend)
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


def main() -> None:
    """Console entrypoint."""
    app()


if __name__ == "__main__":
    main()

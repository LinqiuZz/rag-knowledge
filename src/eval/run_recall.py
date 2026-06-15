"""RAG 评估 CLI 运行器

用法:
    python -m src.eval.run_recall --test-file eval/test_cases.json --top-k 5
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.config import load_settings
from src.store.vector import VectorStore
from src.store.embedding import EmbeddingManager
from src.eval.recall import load_test_cases, evaluate_batch

console = Console()


@click.command()
@click.option("--test-file", required=True, help="测试用例 JSON 文件路径")
@click.option("--top-k", default=5, help="检索 Top-K")
@click.option("--output", default=None, help="结果输出 JSON 路径")
def main(test_file, top_k, output):
    """运行 RAG 检索质量评估。"""
    settings = load_settings()
    embedder = EmbeddingManager(settings)
    vs = VectorStore(settings)

    console.print(f"[cyan]加载测试用例:[/cyan] {test_file}")
    test_cases = load_test_cases(test_file)
    console.print(f"  共 {len(test_cases)} 条用例")

    console.print(f"[cyan]运行评估...[/cyan] (Top-K={top_k})")
    result = evaluate_batch(test_cases, vs, embedder, top_k=top_k)

    m = result["metrics"]
    panel_text = f"""[bold]评估结果汇总[/bold]

  测试用例数:   {result['total_cases']}
  Top-K:        {result['top_k']}

  Recall@{top_k}:    {m['recall_at_k']:.2%}
  Precision@{top_k}: {m['precision_at_k']:.2%}
  MRR:           {m['mrr']:.2%}
  Hit Rate:      {m['hit_rate']:.2%}"""

    console.print(Panel(panel_text, title="📊 RAG 评估报告", border_style="green"))

    table = Table(title="逐条详情")
    table.add_column("#", style="cyan")
    table.add_column("问题", max_width=40)
    table.add_column("Recall", justify="right")
    table.add_column("MRR", justify="right")
    table.add_column("命中", justify="center")

    for i, d in enumerate(result["details"], 1):
        hit_mark = "\u2713" if d["hit"] else "\u2717"
        table.add_row(
            str(i),
            d["question"][:40],
            f"{d['recall']:.2f}",
            f"{d['mrr']:.2f}",
            hit_mark,
        )

    console.print(table)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        console.print(f"[green]结果已保存到:[/green] {output}")


if __name__ == "__main__":
    main()

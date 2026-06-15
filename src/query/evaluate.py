"""RAG 评估模块 — 检索质量和回答质量评估"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from ..config import Settings
    from ..store.vector import VectorStore
    from ..store.embedding import EmbeddingManager
    from ..llm.base import BaseLLM

console = Console()


@dataclass
class RetrievalMetrics:
    """检索质量指标。"""
    query: str = ""
    top_k: int = 5
    results_count: int = 0
    avg_distance: float = 0.0          # 平均余弦距离（越小越相似）
    min_distance: float = 0.0          # 最佳匹配距离
    max_distance: float = 0.0          # 最差匹配距离
    unique_sources: int = 0            # 唯一来源数
    retrieval_time_ms: float = 0.0     # 检索耗时（毫秒）


@dataclass
class AnswerMetrics:
    """回答质量指标。"""
    query: str = ""
    answer_length: int = 0             # 回答字符数
    citation_count: int = 0            # 引用来源数
    has_citations: bool = False        # 是否有引用
    generation_time_ms: float = 0.0    # 生成耗时（毫秒）
    total_time_ms: float = 0.0         # 端到端耗时（毫秒）


@dataclass
class EvalResult:
    """单次评估结果。"""
    retrieval: RetrievalMetrics = field(default_factory=RetrievalMetrics)
    answer: AnswerMetrics = field(default_factory=AnswerMetrics)


def evaluate_retrieval(
    query: str,
    vector_store: VectorStore,
    embedder: EmbeddingManager,
    top_k: int = 5,
) -> RetrievalMetrics:
    """评估检索质量。"""
    metrics = RetrievalMetrics(query=query, top_k=top_k)

    # 生成查询嵌入
    start = time.perf_counter()
    query_embedding = embedder.embed_query(query)

    # 执行检索
    results = vector_store.search(query_embedding, top_k=top_k)
    metrics.retrieval_time_ms = (time.perf_counter() - start) * 1000

    # 分析结果
    if results and results.get("distances") and results["distances"][0]:
        distances = results["distances"][0]
        metrics.results_count = len(distances)
        metrics.avg_distance = sum(distances) / len(distances)
        metrics.min_distance = min(distances)
        metrics.max_distance = max(distances)

    if results and results.get("metadatas") and results["metadatas"][0]:
        sources = set()
        for meta in results["metadatas"][0]:
            if meta and "source" in meta:
                sources.add(meta["source"])
        metrics.unique_sources = len(sources)

    return metrics


def evaluate_answer(
    query: str,
    answer: str,
    total_time_ms: float,
    generation_time_ms: float,
) -> AnswerMetrics:
    """评估回答质量。"""
    import re

    metrics = AnswerMetrics(
        query=query,
        answer_length=len(answer),
        generation_time_ms=generation_time_ms,
        total_time_ms=total_time_ms,
    )

    # 统计引用
    citations = re.findall(r'\[来源\d+\]|\[\d+\]|\[Source \d+\]', answer)
    metrics.citation_count = len(citations)
    metrics.has_citations = len(citations) > 0

    return metrics


def run_evaluation(
    queries: list[str],
    settings: Settings,
    vector_store: VectorStore,
    embedder: EmbeddingManager,
    llm: BaseLLM,
    top_k: int = 5,
) -> list[EvalResult]:
    """批量运行 RAG 评估。"""
    results = []

    for i, query in enumerate(queries, 1):
        console.print(f"\n[cyan]评估 [{i}/{len(queries)}]:[/cyan] {query}")

        # 评估检索
        retrieval = evaluate_retrieval(query, vector_store, embedder, top_k)

        # 评估 RAG 问答
        start_total = time.perf_counter()

        # 检索上下文
        query_embedding = embedder.embed_query(query)
        search_results = vector_store.search(query_embedding, top_k=top_k)

        # 拼接上下文
        context_parts = []
        if search_results and search_results.get("documents") and search_results["documents"][0]:
            for j, doc in enumerate(search_results["documents"][0]):
                context_parts.append(f"[来源{j+1}] {doc}")
        context = "\n\n".join(context_parts)

        # 生成回答
        system_prompt = "基于以下参考资料回答问题。回答时请引用来源，格式为 [来源N]。\n\n参考资料：\n" + context

        start_gen = time.perf_counter()
        try:
            answer = llm.chat(system_prompt, query)
        except Exception as e:
            answer = f"生成失败: {e}"
        generation_time_ms = (time.perf_counter() - start_gen) * 1000

        total_time_ms = (time.perf_counter() - start_total) * 1000

        # 评估回答
        answer_metrics = evaluate_answer(query, answer, total_time_ms, generation_time_ms)

        result = EvalResult(retrieval=retrieval, answer=answer_metrics)
        results.append(result)

        # 输出简要结果
        console.print(f"  检索: {retrieval.results_count} 结果, 平均距离 {retrieval.avg_distance:.4f}, 耗时 {retrieval.retrieval_time_ms:.1f}ms")
        console.print(f"  回答: {answer_metrics.answer_length} 字, {answer_metrics.citation_count} 个引用, 耗时 {generation_time_ms:.1f}ms")

    return results


def print_eval_summary(results: list[EvalResult]):
    """打印评估汇总表。"""
    if not results:
        console.print("[yellow]无评估结果[/yellow]")
        return

    table = Table(title="RAG 评估汇总", show_lines=True)
    table.add_column("查询", style="cyan", max_width=30)
    table.add_column("检索数", justify="right")
    table.add_column("平均距离", justify="right")
    table.add_column("检索耗时", justify="right")
    table.add_column("回答字数", justify="right")
    table.add_column("引用数", justify="right")
    table.add_column("生成耗时", justify="right")
    table.add_column("总耗时", justify="right")

    for r in results:
        table.add_row(
            r.retrieval.query[:30],
            str(r.retrieval.results_count),
            f"{r.retrieval.avg_distance:.4f}",
            f"{r.retrieval.retrieval_time_ms:.0f}ms",
            str(r.answer.answer_length),
            str(r.answer.citation_count),
            f"{r.answer.generation_time_ms:.0f}ms",
            f"{r.answer.total_time_ms:.0f}ms",
        )

    console.print(table)

    # 汇总统计
    avg_dist = sum(r.retrieval.avg_distance for r in results) / len(results)
    avg_retrieval_ms = sum(r.retrieval.retrieval_time_ms for r in results) / len(results)
    avg_gen_ms = sum(r.answer.generation_time_ms for r in results) / len(results)
    citation_rate = sum(1 for r in results if r.answer.has_citations) / len(results) * 100

    console.print(f"\n[bold]汇总:[/bold]")
    console.print(f"  平均检索距离: {avg_dist:.4f}")
    console.print(f"  平均检索耗时: {avg_retrieval_ms:.1f}ms")
    console.print(f"  平均生成耗时: {avg_gen_ms:.1f}ms")
    console.print(f"  引用覆盖率: {citation_rate:.1f}%")


def export_eval_results(results: list[EvalResult], output_path: str):
    """导出评估结果为 JSON。"""
    data = {
        "summary": {
            "total_queries": len(results),
            "avg_distance": sum(r.retrieval.avg_distance for r in results) / len(results) if results else 0,
            "avg_retrieval_ms": sum(r.retrieval.retrieval_time_ms for r in results) / len(results) if results else 0,
            "avg_generation_ms": sum(r.answer.generation_time_ms for r in results) / len(results) if results else 0,
            "citation_rate": sum(1 for r in results if r.answer.has_citations) / len(results) * 100 if results else 0,
        },
        "results": [asdict(r) for r in results],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    console.print(f"[green]✓ 评估结果已导出:[/green] {output_path}")

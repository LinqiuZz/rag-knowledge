"""RAG 评估模块 — 检索质量量化指标

支持指标:
- Recall@K: 前 K 个结果中命中相关文档的比例
- MRR (Mean Reciprocal Rank): 第一个相关结果的排名倒数
- Precision@K: 前 K 个结果中相关文档的占比

使用方式:
    python -m src.eval.run_recall --test-file eval/test_cases.json --top-k 5
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..store.vector import VectorStore
    from ..store.embedding import EmbeddingManager


@dataclass
class TestCase:
    """单条测试用例。"""
    question: str
    expected_sources: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """单条测试用例的评估结果。"""
    question: str
    recall_at_k: float
    precision_at_k: float
    mrr: float
    hit: bool
    matched_sources: list[str]
    retrieved_sources: list[str]


def evaluate_single(
    test_case: TestCase,
    vector_store: "VectorStore",
    embedder: "EmbeddingManager",
    top_k: int = 5,
) -> EvalResult:
    """评估单条测试用例的检索质量。"""
    from ..query.search import semantic_search

    results = semantic_search(test_case.question, vector_store, embedder, top_k=top_k)
    retrieved_sources = [r.source for r in results]

    expected_set = set(test_case.expected_sources)
    matched = [s for s in retrieved_sources if s in expected_set]

    recall = len(matched) / len(expected_set) if expected_set else 0.0
    precision = len(matched) / top_k

    mrr = 0.0
    for i, src in enumerate(retrieved_sources):
        if src in expected_set:
            mrr = 1.0 / (i + 1)
            break

    return EvalResult(
        question=test_case.question,
        recall_at_k=recall,
        precision_at_k=precision,
        mrr=mrr,
        hit=len(matched) > 0,
        matched_sources=matched,
        retrieved_sources=retrieved_sources,
    )


def evaluate_batch(
    test_cases: list[TestCase],
    vector_store: "VectorStore",
    embedder: "EmbeddingManager",
    top_k: int = 5,
) -> dict:
    """批量评估，返回汇总指标。"""
    results = []
    for tc in test_cases:
        r = evaluate_single(tc, vector_store, embedder, top_k=top_k)
        results.append(r)

    n = len(results)
    if n == 0:
        return {"error": "无测试用例"}

    avg_recall = sum(r.recall_at_k for r in results) / n
    avg_precision = sum(r.precision_at_k for r in results) / n
    avg_mrr = sum(r.mrr for r in results) / n
    hit_rate = sum(1 for r in results if r.hit) / n

    return {
        "total_cases": n,
        "top_k": top_k,
        "metrics": {
            "recall_at_k": round(avg_recall, 4),
            "precision_at_k": round(avg_precision, 4),
            "mrr": round(avg_mrr, 4),
            "hit_rate": round(hit_rate, 4),
        },
        "details": [
            {
                "question": r.question,
                "recall": r.recall_at_k,
                "precision": r.precision_at_k,
                "mrr": r.mrr,
                "hit": r.hit,
                "matched": r.matched_sources,
                "retrieved": r.retrieved_sources,
            }
            for r in results
        ],
    }


def load_test_cases(path: str | Path) -> list[TestCase]:
    """从 JSON 文件加载测试用例。

    JSON 格式:
    [
        {
            "question": "什么是梯度下降？",
            "expected_sources": ["E:/docs/ml_basics.pdf"],
            "expected_keywords": ["梯度", "学习率"]
        },
        ...
    ]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = []
    for item in data:
        cases.append(TestCase(
            question=item["question"],
            expected_sources=item.get("expected_sources", []),
            expected_keywords=item.get("expected_keywords", []),
        ))
    return cases

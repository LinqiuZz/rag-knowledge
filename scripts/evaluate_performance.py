#!/usr/bin/env python3
"""
RAG系统性能评估脚本

本脚本用于评估不同检索策略的性能，包括：
1. 检索准确率
2. 检索召回率
3. 回答质量
4. 响应时间
"""

import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# 确保 src 目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings
from src.store.vector import VectorStore
from src.store.embedding import EmbeddingManager
from src.llm.base import get_llm
from src.query.rag import rag_answer
from src.query.evaluation import rag_evaluate


class RAGEvaluator:
    """RAG系统评估器"""

    def __init__(self):
        """初始化评估器"""
        self.settings = load_settings()
        self.embedder = EmbeddingManager(self.settings)
        self.vector_store = VectorStore(self.settings)
        self.llm = get_llm(self.settings.llm.default, self.settings)

        if not self.llm.is_available():
            raise RuntimeError(f"LLM后端 ({self.settings.llm.default}) 不可用")

    def evaluate_retrieval_strategy(
        self,
        questions: List[str],
        strategy: str = "semantic",
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        评估特定检索策略的性能

        Args:
            questions: 测试问题列表
            strategy: 检索策略 (semantic, hybrid, multi_query)
            top_k: 检索文档数量

        Returns:
            评估结果字典
        """
        results = []
        total_time = 0

        for question in questions:
            start_time = time.time()

            # 根据策略选择参数
            use_hybrid = strategy == "hybrid"
            use_multi_query = strategy == "multi_query"

            # 执行RAG问答
            result = rag_answer(
                question, self.settings, self.vector_store, self.embedder, self.llm,
                top_k=top_k, use_hybrid=use_hybrid, use_multi_query=use_multi_query
            )

            end_time = time.time()
            response_time = end_time - start_time
            total_time += response_time

            # 评估回答质量
            evaluation = rag_evaluate(
                question, result["answer"], result["sources"], result["context"]
            )

            results.append({
                "question": question,
                "answer": result["answer"],
                "sources": result["sources"],
                "response_time": response_time,
                "evaluation": evaluation,
            })

        # 计算平均指标
        avg_response_time = total_time / len(questions) if questions else 0

        # 计算平均评估指标
        avg_metrics = self._calculate_average_metrics(results)

        return {
            "strategy": strategy,
            "questions_count": len(questions),
            "avg_response_time": avg_response_time,
            "avg_metrics": avg_metrics,
            "detailed_results": results,
        }

    def _calculate_average_metrics(self, results: List[Dict]) -> Dict[str, float]:
        """计算平均评估指标"""
        if not results:
            return {}

        # 初始化指标累加器
        metrics_sum = {
            "faithfulness": 0,
            "relevance": 0,
            "completeness": 0,
        }

        # 累加所有评估指标
        for result in results:
            evaluation = result["evaluation"]
            if hasattr(evaluation, 'metrics') and evaluation.metrics:
                generation_metrics = evaluation.metrics.get("generation", {})
                for key in metrics_sum:
                    if key in generation_metrics:
                        metrics_sum[key] += generation_metrics[key]

        # 计算平均值
        count = len(results)
        avg_metrics = {key: value / count for key, value in metrics_sum.items()}

        return avg_metrics

    def compare_strategies(
        self,
        questions: List[str],
        strategies: List[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        比较不同检索策略的性能

        Args:
            questions: 测试问题列表
            strategies: 要比较的策略列表
            top_k: 检索文档数量

        Returns:
            比较结果字典
        """
        if strategies is None:
            strategies = ["semantic", "hybrid", "multi_query"]

        comparison_results = {}

        for strategy in strategies:
            print(f"\n评估策略: {strategy}")
            print("-" * 40)

            result = self.evaluate_retrieval_strategy(questions, strategy, top_k)
            comparison_results[strategy] = result

            # 打印结果摘要
            print(f"平均响应时间: {result['avg_response_time']:.2f}秒")
            print(f"平均评估指标:")
            for metric, value in result['avg_metrics'].items():
                print(f"  {metric}: {value:.3f}")

        return comparison_results

    def generate_report(self, comparison_results: Dict[str, Any]) -> str:
        """
        生成评估报告

        Args:
            comparison_results: 比较结果

        Returns:
            报告字符串
        """
        report = []
        report.append("=" * 60)
        report.append("RAG系统性能评估报告")
        report.append("=" * 60)

        # 概览
        report.append(f"\n评估时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"测试问题数量: {list(comparison_results.values())[0]['questions_count']}")
        report.append(f"检索文档数量: {list(comparison_results.values())[0].get('top_k', 5)}")

        # 策略比较
        report.append("\n" + "=" * 60)
        report.append("策略性能比较")
        report.append("=" * 60)

        # 表头
        report.append(f"\n{'策略':<15} {'响应时间(秒)':<15} {'忠实度':<10} {'相关性':<10} {'完整性':<10}")
        report.append("-" * 60)

        # 数据行
        for strategy, result in comparison_results.items():
            avg_time = result['avg_response_time']
            metrics = result['avg_metrics']
            faithfulness = metrics.get('faithfulness', 0)
            relevance = metrics.get('relevance', 0)
            completeness = metrics.get('completeness', 0)

            report.append(f"{strategy:<15} {avg_time:<15.2f} {faithfulness:<10.3f} {relevance:<10.3f} {completeness:<10.3f}")

        # 推荐策略
        report.append("\n" + "=" * 60)
        report.append("推荐策略")
        report.append("=" * 60)

        # 找出最佳策略
        best_strategy = None
        best_score = 0

        for strategy, result in comparison_results.items():
            metrics = result['avg_metrics']
            # 计算综合得分（可根据需求调整权重）
            score = (
                metrics.get('faithfulness', 0) * 0.4 +
                metrics.get('relevance', 0) * 0.4 +
                metrics.get('completeness', 0) * 0.2
            )

            if score > best_score:
                best_score = score
                best_strategy = strategy

        if best_strategy:
            report.append(f"\n推荐策略: {best_strategy}")
            report.append(f"综合得分: {best_score:.3f}")
            report.append("\n推荐理由:")
            report.append("- 忠实度: 回答是否忠实于检索到的上下文")
            report.append("- 相关性: 回答是否与问题相关")
            report.append("- 完整性: 回答是否完整地回答了问题")

        # 详细结果
        report.append("\n" + "=" * 60)
        report.append("详细评估结果")
        report.append("=" * 60)

        for strategy, result in comparison_results.items():
            report.append(f"\n策略: {strategy}")
            report.append("-" * 40)

            for i, detail in enumerate(result['detailed_results'], 1):
                report.append(f"\n问题 {i}: {detail['question']}")
                report.append(f"响应时间: {detail['response_time']:.2f}秒")
                report.append(f"来源数量: {len(detail['sources'])}")

                if detail['sources']:
                    report.append("主要来源:")
                    for s in detail['sources'][:2]:
                        report.append(f"  - {s['title']} (相关度: {1 - s['score']:.2f})")

        return "\n".join(report)


def main():
    """主函数"""
    print("RAG系统性能评估")
    print("=" * 60)

    try:
        # 创建评估器
        evaluator = RAGEvaluator()

        # 测试问题
        test_questions = [
            "什么是梯度下降？",
            "RAG系统的基本原理是什么？",
            "Python常用代码片段有哪些？",
            "数据库设计的基本原则是什么？",
            "机器学习的主要算法有哪些？",
        ]

        print(f"测试问题数量: {len(test_questions)}")
        print("\n开始评估...")

        # 比较不同策略
        comparison_results = evaluator.compare_strategies(test_questions)

        # 生成报告
        report = evaluator.generate_report(comparison_results)

        # 保存报告
        report_path = Path("evaluation_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\n评估完成！报告已保存到: {report_path}")

        # 打印报告摘要
        print("\n" + "=" * 60)
        print("报告摘要")
        print("=" * 60)

        # 提取关键信息
        lines = report.split("\n")
        for line in lines:
            if "推荐策略:" in line or "综合得分:" in line:
                print(line)

    except Exception as e:
        print(f"\n❌ 评估过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
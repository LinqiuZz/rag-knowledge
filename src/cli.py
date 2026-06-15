"""CLI 入口 — 个人知识库系统"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# 设置环境变量以解决Windows控制台编码问题
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# 确保 src 目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings, Settings
from src.store.vector import VectorStore
from src.store.metadata import MetadataStore
from src.store.embedding import EmbeddingManager
from src.llm.base import get_llm

console = Console()


def _get_components(settings: Settings):
    """初始化所有组件。"""
    embedder = EmbeddingManager(settings)
    vector_store = VectorStore(settings)
    meta_store = MetadataStore(settings)
    llm = get_llm(settings.llm.default, settings)
    return embedder, vector_store, meta_store, llm


@click.group()
@click.option("--config", default=None, help="配置文件路径")
@click.pass_context
def cli(ctx, config):
    """📚 个人知识库系统 — 本地离线，支持 PDF & 网页"""
    ctx.ensure_object(dict)
    ctx.obj["settings"] = load_settings(config)


# ── 摄取 ──────────────────────────────────────────────────

@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.pass_context
def add(ctx, files):
    """导入文件到知识库。支持: PDF, Word, Excel, Markdown, TXT, 代码文件等。
    用法: python run.py add file.pdf file.docx *.py"""
    import glob as glob_mod
    from pathlib import Path

    settings = ctx.obj["settings"]
    embedder, vs, ms, _ = _get_components(settings)

    from src.ingest.pipeline import (
        ingest_pdf, ingest_word, ingest_excel, ingest_text,
        SUPPORTED_EXTENSIONS,
    )

    def _ingest_file(f: str):
        p = Path(f)
        ext = p.suffix.lower()
        file_type = SUPPORTED_EXTENSIONS.get(ext)
        if file_type == 'pdf':
            return ingest_pdf(f, settings, vs, ms, embedder)
        elif file_type == 'word':
            return ingest_word(f, settings, vs, ms, embedder)
        elif file_type == 'excel':
            return ingest_excel(f, settings, vs, ms, embedder)
        elif file_type in ('text', 'code'):
            return ingest_text(f, settings, vs, ms, embedder)
        else:
            raise ValueError(f"不支持的格式: {ext}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS.keys()))}")

    # Expand globs on Windows
    expanded_files = []
    for f in files:
        matches = glob_mod.glob(f)
        if matches:
            expanded_files.extend(matches)
        else:
            expanded_files.append(f)

    for f in expanded_files:
        try:
            result = _ingest_file(f)
            console.print()
        except Exception as e:
            console.print(f"  [red]✗ 失败:[/red] {e}")
            ms.log(str(f), "error", str(e))

    ms.close()


@cli.command()
@click.argument("urls", nargs=-1, required=True)
@click.pass_context
def add_url(ctx, urls):
    """导入网页到知识库。"""
    settings = ctx.obj["settings"]
    embedder, vs, ms, _ = _get_components(settings)

    from src.ingest.pipeline import ingest_webpage

    for url in urls:
        try:
            result = ingest_webpage(url, settings, vs, ms, embedder)
            console.print()
        except Exception as e:
            console.print(f"  [red]✗ 失败:[/red] {e}")
            ms.log(url, "error", str(e))

    ms.close()


# ── 查询 ──────────────────────────────────────────────────


@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.pass_context
def add_text(ctx, files):
    """导入文档/代码/配置文件到知识库。支持: PDF, Word, Excel, Markdown, Python, JS, JSON, YAML 等"""
    import glob as glob_mod
    
    settings = ctx.obj["settings"]
    embedder, vs, ms, _ = _get_components(settings)

    from src.ingest.pipeline import ingest_text

    # Expand globs on Windows
    expanded_files = []
    for f in files:
        matches = glob_mod.glob(f)
        if matches:
            expanded_files.extend(matches)
        else:
            expanded_files.append(f)  # Keep original for error message
    
    for f in expanded_files:
        try:
            result = ingest_text(f, settings, vs, ms, embedder)
            console.print()
        except Exception as e:
            console.print(f"  [red]✗ 失败:[/red] {e}")
            ms.log(str(f), "error", str(e))

    ms.close()

@cli.command()
@click.argument("query")
@click.option("-k", "--top-k", default=5, help="返回结果数量")
@click.pass_context
def search(ctx, query, top_k):
    """语义搜索知识库。"""
    settings = ctx.obj["settings"]
    embedder, vs, _, _ = _get_components(settings)

    from src.query.search import semantic_search

    results = semantic_search(query, vs, embedder, top_k=top_k)

    if not results:
        console.print("[yellow]未找到相关内容。[/yellow]")
        return

    for i, r in enumerate(results, 1):
        console.print(Panel(
            r.text[:300] + ("..." if len(r.text) > 300 else ""),
            title=f"[bold]#{i}[/bold] {r.title} (相似度: {1 - r.score:.2f})",
            subtitle=f"来源: {r.source}",
            border_style="blue",
        ))


@cli.command()
@click.argument("question")
@click.option("-k", "--top-k", default=5, help="检索文档数量")
@click.option("--llm", default=None, help="指定 LLM 后端 (claude|ollama)")
@click.option("--hybrid", is_flag=True, help="使用混合检索（语义+关键词）")
@click.option("--multi-query", is_flag=True, help="使用多查询检索（提高召回率）")
@click.pass_context
def ask(ctx, question, top_k, llm, hybrid, multi_query):
    """RAG 问答 — 基于知识库回答问题。"""
    settings = ctx.obj["settings"]
    if llm:
        settings.llm.default = llm
    embedder, vs, _, llm_inst = _get_components(settings)

    from src.query.rag import rag_answer

    if not llm_inst.is_available():
        console.print(f"[red]LLM 后端 ({settings.llm.default}) 不可用。[/red]")
        if settings.llm.default == "claude":
            console.print("请设置环境变量: export ANTHROPIC_AUTH_TOKEN=***  ")
        else:
            console.print("请确保 Ollama 正在运行: ollama serve")
        return

    # 显示使用的检索策略
    strategy_info = []
    if hybrid:
        strategy_info.append("混合检索")
    if multi_query:
        strategy_info.append("多查询检索")
    if strategy_info:
        console.print(f"[dim]使用策略: {', '.join(strategy_info)}[/dim]")

    with console.status("[bold green]思考中..."):
        result = rag_answer(
            question, settings, vs, embedder, llm_inst, top_k=top_k,
            use_hybrid=hybrid, use_multi_query=multi_query
        )

    console.print(Panel(result["answer"], title="回答", border_style="green"))

    if result["sources"]:
        table = Table(title="引用来源")
        table.add_column("#", style="cyan")
        table.add_column("标题")
        table.add_column("类型")
        table.add_column("相关度", justify="right")
        for s in result["sources"]:
            table.add_row(
                str(s["index"]), s["title"], s["doc_type"],
                f"{1 - s['score']:.2f}",
            )
        console.print(table)


@cli.command()
@click.argument("source")
@click.option("--llm", default=None, help="指定 LLM 后端")
@click.pass_context
def summarize(ctx, source, llm):
    """为已导入的文档生成摘要。"""
    settings = ctx.obj["settings"]
    if llm:
        settings.llm.default = llm
    embedder, vs, ms, llm_inst = _get_components(settings)

    from src.query.summarize import summarize_document

    if not llm_inst.is_available():
        console.print(f"[red]LLM 后端 ({settings.llm.default}) 不可用。[/red]")
        return

    with console.status("[bold green]生成摘要..."):
        summary = summarize_document(source, settings, vs, ms, embedder, llm_inst)

    console.print(Panel(summary, title=f"摘要: {source}", border_style="magenta"))
    ms.close()


# ── 管理 ──────────────────────────────────────────────────

@cli.command()
@click.pass_context
def list(ctx):
    """列出知识库中的所有文档。"""
    settings = ctx.obj["settings"]
    _, vs, ms, _ = _get_components(settings)

    docs = ms.list_documents()
    if not docs:
        console.print("[yellow]知识库为空。使用 `add` 命令导入文档。[/yellow]")
        return

    table = Table(title="知识库文档列表")
    table.add_column("标题", style="cyan")
    table.add_column("类型")
    table.add_column("块数", justify="right")
    table.add_column("字符数", justify="right")
    table.add_column("导入时间")

    for doc in docs:
        created = doc["created_at"]
        if hasattr(created, 'strftime'):
            created = created.strftime("%Y-%m-%d %H:%M:%S")
        else:
            created = str(created)[:19]
        table.add_row(
            doc["title"], doc["doc_type"],
            str(doc["chunk_count"]), str(doc["char_count"]),
            created,
        )

    console.print(table)
    console.print(f"\n向量库总块数: [bold]{vs.count()}[/bold]")
    ms.close()


@cli.command()
@click.argument("source")
@click.confirmation_option(prompt="确认删除该文档及其所有块？")
@click.pass_context
def remove(ctx, source):
    """从知识库删除指定文档。"""
    settings = ctx.obj["settings"]
    _, vs, ms, _ = _get_components(settings)

    count = vs.delete_by_source(source)
    ms.delete_document(source)
    console.print(f"[green]已删除[/green] {count} 个向量块。")
    ms.close()


@cli.command()
@click.pass_context
def info(ctx):
    """显示系统状态和配置信息。"""
    settings = ctx.obj["settings"]
    _, vs, ms, _ = _get_components(settings)

    docs = ms.list_documents()

    panel_text = f"""[bold]配置信息[/bold]

  LLM 后端:     {settings.llm.default}
  Claude 模型:  {settings.llm.claude_model}
  Ollama 模型:  {settings.llm.ollama_model}
  嵌入模型:     {settings.embedding.model_name}
  嵌入设备:     {settings.embedding.device}

[bold]存储信息[/bold]

  文档数量:     {len(docs)}
  向量块总数:   {vs.count()}
  向量库路径:   {settings.chroma_dir}
  MySQL 数据库: {settings.mysql.database}@{settings.mysql.host}:{settings.mysql.port}"""

    console.print(Panel(panel_text, title="知识库系统状态", border_style="blue"))
    ms.close()



@cli.command()
@click.pass_context
def check(ctx):
    """健康检查 — 验证所有组件是否正常工作。"""
    import importlib
    settings = ctx.obj["settings"]
    results = []

    # 1. 检查 Python 版本
    import sys
    v = sys.version_info
    ok = v >= (3, 10)
    results.append(("Python >= 3.10", ok, f"{v.major}.{v.minor}.{v.micro}"))

    # 2. 检查依赖包
    deps = ["chromadb", "pymupdf", "trafilatura", "sentence_transformers",
            "anthropic", "ollama", "click", "rich", "pyyaml"]
    for dep in deps:
        try:
            importlib.import_module(dep)
            results.append((f"依赖: {dep}", True, "已安装"))
        except ImportError:
            results.append((f"依赖: {dep}", False, "未安装"))

    # 3. 检查 MySQL 连接
    try:
        from src.store.metadata import MetadataStore
        ms = MetadataStore(settings)
        ms.close()
        results.append(("MySQL 连接", True, f"{settings.mysql.database}@{settings.mysql.host}:{settings.mysql.port}"))
    except Exception as e:
        results.append(("MySQL 连接", False, str(e)[:80]))

    # 4. 检查嵌入模型
    try:
        from src.store.embedding import EmbeddingManager
        em = EmbeddingManager(settings)
        vec = em.embed_query("测试")
        ok = len(vec) == settings.embedding.dimension
        results.append(("嵌入模型", ok, f"维度={len(vec)}, 设备={settings.embedding.device}"))
    except Exception as e:
        results.append(("嵌入模型", False, str(e)[:80]))

    # 5. 检查 LLM
    from src.llm.base import get_llm
    llm = get_llm(settings.llm.default, settings)
    avail = llm.is_available()
    results.append((f"LLM ({settings.llm.default})", avail, "可用" if avail else "不可用"))

    # 输出结果
    table = Table(title="健康检查")
    table.add_column("组件", style="cyan")
    table.add_column("状态")
    table.add_column("详情")
    for name, ok, detail in results:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, status, detail)
    console.print(table)


# ── 评估 ──────────────────────────────────────────────────

@cli.command()
@click.argument("queries", nargs=-1, required=True)
@click.option("-k", "--top-k", default=5, help="检索文档数量")
@click.option("--export", default=None, help="导出评估结果到 JSON 文件")
@click.pass_context
def evaluate(ctx, queries, top_k, export):
    """RAG 评估：批量测试检索和回答质量。"""
    settings = ctx.obj["settings"]
    embedder, vs, ms, llm = _get_components(settings)

    from src.query.evaluate import run_evaluation, print_eval_summary, export_eval_results

    query_list = [q for q in queries]
    results = run_evaluation(
        query_list, settings, vs, embedder, llm, top_k=top_k
    )
    print_eval_summary(results)

    if export:
        export_eval_results(results, export)

    ms.close()


if __name__ == "__main__":
    cli()

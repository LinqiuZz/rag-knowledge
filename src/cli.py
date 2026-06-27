"""CLI 入口 — 企业级知识库系统 v2.0"""

from __future__ import annotations

import sys
import os
import glob as glob_mod
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bootstrap import bootstrap, AppContext

console = Console()


def _init(ctx) -> AppContext:
    """获取或创建应用上下文（缓存到 Click context）。"""
    app = ctx.obj.get("_app")
    if app is None:
        config = ctx.obj.get("_config_path")
        llm = ctx.obj.get("_llm_backend")
        app = bootstrap(config_path=config, llm_backend=llm)
        ctx.obj["_app"] = app
    return app


# ═══════════════════════════════════════════════════════════════
# CLI 组
# ═══════════════════════════════════════════════════════════════

@click.group()
@click.option("--config", default=None, help="配置文件路径")
@click.option("--llm", default=None, help="指定 LLM 后端 (claude|ollama)")
@click.pass_context
def cli(ctx, config, llm):
    """🧠 企业级 RAG 知识库 — 多格式深度解析 · 语义检索 · 智能问答 · 文档生成"""
    ctx.ensure_object(dict)
    ctx.obj["_config_path"] = config
    ctx.obj["_llm_backend"] = llm


# ═══════════════════════════════════════════════════════════════
# 摄取
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.option("--owner", default=1, help="文档所有者 ID")
@click.pass_context
def add(ctx, files, owner):
    """导入文件到知识库。支持 PDF, Word, Excel, PPT, Markdown, TXT, 图片, 代码等。
    用法: python run.py add file.pdf file.docx *.py"""
    app = _init(ctx)

    from src.ingest.pipeline import ingest_document, SUPPORTED_EXTENSIONS

    expanded = []
    for f in files:
        matches = glob_mod.glob(f)
        expanded.extend(matches if matches else [f])

    for f in expanded:
        ext = Path(f).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            console.print(f"  [red]✗ 不支持的格式:[/red] {ext}")
            continue
        try:
            result = ingest_document(
                f, app.settings, app.vector_store, app.meta_store,
                app.embedder, app.storage, owner_id=owner,
            )
            console.print(f"  [green]✓ {result['title']}[/green] "
                          f"({result['small_chunks']} 子块 + {result['big_chunks']} 父块)")
        except Exception as e:
            console.print(f"  [red]✗ {Path(f).name}:[/red] {e}")

    app.close()


@cli.command()
@click.argument("urls", nargs=-1, required=True)
@click.pass_context
def add_url(ctx, urls):
    """导入网页到知识库。"""
    app = _init(ctx)

    from src.ingest.webpage import extract_webpage
    from src.ingest.chunking import split_text

    for url in urls:
        try:
            doc = extract_webpage(url)
            if not doc["text"]:
                console.print(f"  [yellow]⚠ 未提取到内容: {url}[/yellow]")
                continue

            chunks = split_text(doc["text"], app.settings.chunking.small_size,
                               app.settings.chunking.small_overlap)
            embeddings = app.embedder.embed_documents(chunks)

            import hashlib
            ids = [hashlib.md5(f"{url}_{i}".encode()).hexdigest()[:12] for i in range(len(chunks))]
            metadatas = [
                {"source": url, "doc_type": "webpage", "title": doc["title"], "chunk_idx": i}
                for i in range(len(chunks))
            ]

            app.vector_store.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
            app.meta_store.log(url, "success", f"摄取完成: {len(chunks)} 块")
            console.print(f"  [green]✓ {doc['title']}[/green] ({len(chunks)} 块)")
        except Exception as e:
            console.print(f"  [red]✗ {url}:[/red] {e}")

    app.close()


# ═══════════════════════════════════════════════════════════════
# 查询
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("query")
@click.option("-k", "--top-k", default=5, help="返回结果数量")
@click.option("--hybrid/--no-hybrid", default=False, help="混合检索")
@click.option("--rerank/--no-rerank", default=True, help="重排序")
@click.pass_context
def search(ctx, query, top_k, hybrid, rerank):
    """语义/混合检索知识库。"""
    app = _init(ctx)

    result = app.pipeline.retrieve(
        query=query, embedder=app.embedder, vector_store=app.vector_store,
        meta_store=app.meta_store, use_hybrid=hybrid, use_rerank=rerank,
    )

    if not result.hits:
        console.print("[yellow]未找到相关内容。[/yellow]")
        return

    for i, h in enumerate(result.hits[:top_k], 1):
        location = f"第{h.page_number}页" if h.page_number else f"幻灯片{h.slide_number}" if h.slide_number else ""
        console.print(Panel(
            h.plain_text[:300] + ("..." if len(h.plain_text) > 300 else ""),
            title=f"[bold]#{i}[/bold] {h.title} {location} (综合分: {h.final_score:.2f})",
            subtitle=f"来源: {h.source}  ·  {h.element_type}",
            border_style="blue",
        ))


@cli.command()
@click.argument("question")
@click.option("-k", "--top-k", default=5, help="检索文档数量")
@click.option("--hybrid/--no-hybrid", default=False, help="混合检索")
@click.option("--multi/--no-multi", default=False, help="多查询扩展（旧接口）")
@click.option("--rerank/--no-rerank", default=True, help="重排序")
@click.option("--rewrite/--no-rewrite", default=True, help="查询改写（上下文补全+任务分解+HyDE）")
@click.option("--hyde/--no-hyde", default=True, help="HyDE 语义增强（假设文档嵌入）")
@click.option("--decompose/--no-decompose", default=True, help="任务分解（子查询拆解）")
@click.option("--compress/--no-compress", default=True, help="上下文补全（指代消解）")
@click.option("--few-shot/--no-few-shot", default=True, help="Few-Shot 示例引导")
@click.option("--cot/--no-cot", default=True, help="Chain-of-Thought 分步推理")
@click.pass_context
def ask(ctx, question, top_k, hybrid, multi, rerank,
        rewrite, hyde, decompose, compress, few_shot, cot):
    """RAG 问答 — 基于知识库回答问题。"""
    app = _init(ctx)

    if not app.llm.is_available():
        console.print(f"[red]LLM 后端 ({app.settings.llm.default}) 不可用。[/red]")
        if app.settings.llm.default == "claude":
            console.print("请设置环境变量: export ANTHROPIC_AUTH_TOKEN=***")
        return

    from src.query.rag import rag_answer

    # 显示使用的检索策略
    strategy_info = []
    if hybrid:    strategy_info.append("混合检索")
    if multi:     strategy_info.append("多查询扩展")
    if rewrite:   strategy_info.append("查询改写")
    if hyde:      strategy_info.append("HyDE")
    if decompose: strategy_info.append("任务分解")
    if compress:  strategy_info.append("上下文补全")
    if few_shot:  strategy_info.append("Few-Shot")
    if cot:       strategy_info.append("CoT")
    if strategy_info:
        console.print(f"[dim]策略: {' | '.join(strategy_info)}[/dim]")

    with console.status("[bold green]思考中..."):
        result = rag_answer(
            question, app.settings, app.vector_store, app.embedder, app.llm,
            meta_store=app.meta_store, top_k=top_k,
            use_hybrid=hybrid, use_multi_query=multi, use_rerank=rerank,
            use_rewrite=rewrite, use_hyde=hyde,
            use_decompose=decompose, use_compress=compress,
            pipeline=app.pipeline,
            use_few_shot=few_shot, use_cot=cot,
        )

    console.print(Panel(result["answer"], title="回答", border_style="green"))

    if result["sources"]:
        table = Table(title="引用来源")
        table.add_column("#", style="cyan")
        table.add_column("标题")
        table.add_column("类型")
        table.add_column("相关度", justify="right")
        for s in result["sources"]:
            table.add_row(str(s["index"]), s.get("title", ""),
                          s.get("doc_type", ""), f"{s['score']:.2f}")
        console.print(table)


@cli.command()
@click.argument("source")
@click.pass_context
def summarize(ctx, source):
    """为已导入的文档生成摘要。"""
    app = _init(ctx)

    if not app.llm.is_available():
        console.print(f"[red]LLM ({app.settings.llm.default}) 不可用。[/red]")
        return

    from src.query.summarize import summarize_document

    with console.status("[bold green]生成摘要..."):
        summary = summarize_document(source, app.settings, app.vector_store,
                                     app.meta_store, app.embedder, app.llm)
    console.print(Panel(summary, title=f"摘要: {source}", border_style="magenta"))


# ═══════════════════════════════════════════════════════════════
# 管理
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.pass_context
def list(ctx):
    """列出知识库中的所有文档。"""
    app = _init(ctx)
    docs = app.meta_store.list_documents()

    if not docs:
        console.print("[yellow]知识库为空。使用 `add` 命令导入文档。[/yellow]")
        app.close()
        return

    table = Table(title="知识库文档列表")
    table.add_column("ID", style="dim")
    table.add_column("标题", style="cyan")
    table.add_column("格式")
    table.add_column("状态")
    table.add_column("字符数", justify="right")
    table.add_column("更新时间")

    for doc in docs:
        updated = str(doc.get("updated_at", doc.get("created_at", "")))[:19]
        table.add_row(
            str(doc.get("id", "")),
            doc.get("title", ""),
            doc.get("format", doc.get("doc_type", "")),
            doc.get("status", "active"),
            str(doc.get("char_count", 0)),
            updated,
        )

    console.print(table)
    console.print(f"\n向量库总块数: [bold]{app.vector_store.count()}[/bold]")
    app.close()


@cli.command()
@click.argument("doc_id", type=int)
@click.confirmation_option(prompt="确认删除该文档及其所有块？")
@click.pass_context
def remove(ctx, doc_id):
    """从知识库删除指定文档（需提供文档 ID，用 list 命令查看）。"""
    app = _init(ctx)
    app.meta_store.delete_document(doc_id)
    try:
        app.vector_store.delete_by_filter({"doc_id": doc_id})
    except Exception:
        pass
    console.print(f"[green]已删除[/green] 文档 {doc_id}")
    app.close()


@cli.command()
@click.pass_context
def info(ctx):
    """显示系统状态和配置信息。"""
    app = _init(ctx)
    s = app.settings
    docs = app.meta_store.list_documents()

    panel_text = f"""[bold]配置信息[/bold]

  LLM 后端:        {s.llm.default} ({s.llm.claude_model})
  嵌入模型:        {s.embedding.model_name} ({s.embedding.dimension}维)
  分块策略:        {s.chunking.strategy} (子块{s.chunking.small_size}/父块{s.chunking.big_size})
  向量库:          {s.vector_db.provider} ({s.vector_db.collection_name})

[bold]存储信息[/bold]

  文档数量:        {len(docs)}
  向量块总数:      {app.vector_store.count()}
  元数据库:        PostgreSQL {s.postgres.host}:{s.postgres.port}/{s.postgres.database}
  对象存储:        {'MinIO ' + s.minio.endpoint if app.storage.enabled else '本地文件'}
  消息队列:        {s.mq.provider}"""

    console.print(Panel(panel_text, title="知识库系统状态 v2.0", border_style="blue"))
    app.close()


@cli.command()
@click.pass_context
def check(ctx):
    """健康检查 — 验证所有组件是否正常工作。"""
    import importlib
    app = _init(ctx)
    s = app.settings
    results = []

    # 1. Python 版本
    v = sys.version_info
    results.append(("Python >= 3.10", v >= (3, 10), f"{v.major}.{v.minor}.{v.micro}"))

    # 2. 核心依赖
    deps = ["chromadb", "pymupdf", "sentence_transformers",
            "anthropic", "psycopg2", "click", "rich", "pyyaml",
            "python_docx", "openpyxl", "fastapi"]
    for dep in deps:
        try:
            importlib.import_module(dep)
            results.append((f"依赖: {dep}", True, "已安装"))
        except ImportError:
            results.append((f"依赖: {dep}", False, "未安装（可选）"))

    # 3. 数据库连接
    try:
        app.meta_store._ensure_connected()
        results.append(("PostgreSQL", True, f"{s.postgres.host}:{s.postgres.port}/{s.postgres.database}"))
    except Exception as e:
        results.append(("PostgreSQL", False, str(e)[:80]))

    # 4. 嵌入模型
    try:
        vec = app.embedder.embed_query("测试")
        ok = len(vec) == s.embedding.dimension
        results.append(("嵌入模型", ok, f"维度={len(vec)}, 设备={s.embedding.device}"))
    except Exception as e:
        results.append(("嵌入模型", False, str(e)[:80]))

    # 5. LLM
    avail = app.llm.is_available()
    results.append((f"LLM ({s.llm.default})", avail, "可用" if avail else "不可用"))

    # 6. MinIO
    try:
        ok = app.storage.enabled
        results.append(("MinIO 存储", ok, f"{s.minio.endpoint}" if ok else "本地回退"))
    except Exception:
        results.append(("MinIO 存储", False, "不可用"))

    table = Table(title="健康检查")
    table.add_column("组件", style="cyan")
    table.add_column("状态")
    table.add_column("详情")
    for name, ok, detail in results:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, status, detail)
    console.print(table)

    app.close()


# ═══════════════════════════════════════════════════════════════
# 评估
# ═══════════════════════════════════════════════════════════════

@cli.command()
@click.argument("queries", nargs=-1, required=True)
@click.option("-k", "--top-k", default=5)
@click.option("--export", default=None, help="导出评估结果到 JSON 文件")
@click.pass_context
def evaluate(ctx, queries, top_k, export):
    """RAG 评估：批量测试检索和回答质量。"""
    app = _init(ctx)

    from src.query.evaluate import run_evaluation, print_eval_summary, export_eval_results

    results = run_evaluation(list(queries), app.settings, app.vector_store,
                             app.embedder, app.llm, top_k=top_k)
    print_eval_summary(results)

    if export:
        export_eval_results(results, export)

    app.close()


if __name__ == "__main__":
    cli()

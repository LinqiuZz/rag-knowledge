"""多格式文档解析器"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class DocumentContent:
    """文档内容"""
    title: str
    text: str
    doc_type: str
    page_count: Optional[int] = None
    char_count: int = 0
    metadata: Optional[dict] = None


def parse_document(file_path: str | Path) -> DocumentContent:
    """
    自动识别并解析文档

    支持格式：PDF、Word、Excel、Markdown、TXT、HTML

    Args:
        file_path: 文件路径

    Returns:
        文档内容
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = path.suffix.lower()
    parsers = {
        ".pdf": _parse_pdf,
        ".docx": _parse_word,
        # 注意: .doc 格式不支持，python-docx 只支持 .docx
        ".xlsx": _parse_excel,
        ".xls": _parse_excel,
        ".md": _parse_markdown,
        ".markdown": _parse_markdown,
        ".txt": _parse_text,
        ".html": _parse_html,
        ".htm": _parse_html,
    }

    parser = parsers.get(suffix)
    if parser is None:
        if suffix == ".doc":
            raise ValueError(f"不支持旧版 .doc 格式，请转换为 .docx 格式后重试")
        raise ValueError(f"不支持的文件格式: {suffix}")

    return parser(path)


def _parse_pdf(path: Path) -> DocumentContent:
    """解析 PDF"""
    import fitz

    doc = fitz.open(str(path))
    pages = []
    for page in doc:
        pages.append(page.get_text())

    text = "\n\n".join(pages).strip()
    doc.close()

    return DocumentContent(
        title=path.stem,
        text=text,
        doc_type="pdf",
        page_count=len(pages),
        char_count=len(text),
    )


def _parse_word(path: Path) -> DocumentContent:
    """解析 Word 文档"""
    try:
        from docx import Document
        doc = Document(str(path))

        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text.strip())

        # 提取表格内容
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                if row_text.strip():
                    paragraphs.append(row_text)

        text = "\n\n".join(paragraphs)

        return DocumentContent(
            title=path.stem,
            text=text,
            doc_type="word",
            char_count=len(text),
        )
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")


def _parse_excel(path: Path) -> DocumentContent:
    """解析 Excel 文档"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True)

        content_parts = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            sheet_content = [f"=== Sheet: {sheet_name} ==="]

            for row in ws.iter_rows(values_only=True):
                row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
                if row_text.strip(" |"):
                    sheet_content.append(row_text)

            content_parts.append("\n".join(sheet_content))

        text = "\n\n".join(content_parts)

        return DocumentContent(
            title=path.stem,
            text=text,
            doc_type="excel",
            char_count=len(text),
        )
    except ImportError:
        raise ImportError("请安装 openpyxl: pip install openpyxl")


def _parse_markdown(path: Path) -> DocumentContent:
    """解析 Markdown"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    return DocumentContent(
        title=path.stem,
        text=text,
        doc_type="markdown",
        char_count=len(text),
    )


def _parse_text(path: Path) -> DocumentContent:
    """解析纯文本"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    return DocumentContent(
        title=path.stem,
        text=text,
        doc_type="text",
        char_count=len(text),
    )


def _parse_html(path: Path) -> DocumentContent:
    """解析 HTML"""
    try:
        from bs4 import BeautifulSoup

        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

        soup = BeautifulSoup(html, "html.parser")

        # 移除 script 和 style
        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        return DocumentContent(
            title=path.stem,
            text=text,
            doc_type="html",
            char_count=len(text),
        )
    except ImportError:
        raise ImportError("请安装 beautifulsoup4: pip install beautifulsoup4")

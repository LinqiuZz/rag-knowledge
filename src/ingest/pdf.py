"""PDF 文档解析（支持文字版和扫描版OCR）"""

from __future__ import annotations

import os
from pathlib import Path

# Tesseract路径（Windows默认安装位置）
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_pdf(file_path: str | Path, use_ocr: bool = True) -> dict:
    """
    解析 PDF 文件，返回结构化内容。
    自动检测：如果文字提取为空，尝试OCR识别。

    Args:
        file_path: PDF文件路径
        use_ocr: 是否启用OCR（默认True）

    Returns:
        {
            "title": str,         # 文件名（去扩展名）
            "text": str,          # 全文文本
            "page_count": int,    # 页数
            "char_count": int,    # 字符数
            "ocr_used": bool,     # 是否使用了OCR
        }
    """
    import fitz  # PyMuPDF

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {path}")

    doc = fitz.open(str(path))
    pages = []
    ocr_used = False

    for i, page in enumerate(doc):
        # 先尝试直接提取文字
        text = page.get_text()

        # 如果文字很少，可能是扫描版，尝试OCR
        if use_ocr and len(text.strip()) < 50:
            ocr_text = _ocr_page(page)
            if ocr_text:
                text = ocr_text
                ocr_used = True

        pages.append(text)
        if (i + 1) % 50 == 0:
            print(f"    已处理 {i+1}/{len(doc)} 页")

    text = "\n\n".join(pages).strip()
    title = path.stem

    doc.close()

    return {
        "title": title,
        "text": text,
        "page_count": len(pages),
        "char_count": len(text),
        "ocr_used": ocr_used,
    }


def _ocr_page(page) -> str:
    """对单页PDF进行OCR识别"""
    try:
        import pytesseract
        from PIL import Image
        import io

        # 设置Tesseract路径
        if os.path.exists(TESSERACT_CMD):
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

        # 将PDF页面转为图像
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # OCR识别（中英文）
        text = pytesseract.image_to_string(img, lang='chi_sim+eng', config='--psm 6')
        return text.strip()
    except Exception as e:
        print(f"    OCR识别失败: {e}")
        return ""

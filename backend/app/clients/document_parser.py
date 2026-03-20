from __future__ import annotations

from io import BytesIO
from pathlib import Path


class DocumentParseError(ValueError):
    pass


class ResumeDocumentParser:
    def extract_text(self, file_bytes: bytes, file_name: str, content_type: str = "") -> str:
        suffix = Path(file_name).suffix.lower()
        if not file_bytes:
            raise DocumentParseError("上传的文件为空，无法解析。")

        if suffix in {".txt", ".md", ".json", ".csv"} or content_type.startswith("text/"):
            return self._decode_text(file_bytes)
        if suffix == ".pdf":
            return self._extract_pdf(file_bytes)
        if suffix == ".docx":
            return self._extract_docx(file_bytes)
        if suffix == ".doc":
            raise DocumentParseError("当前仅支持 .docx，不支持旧版 .doc，请先转换后再上传。")

        raise DocumentParseError(f"暂不支持的文件类型: {suffix or content_type or 'unknown'}")

    def _decode_text(self, file_bytes: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
            try:
                text = file_bytes.decode(encoding)
                if text.strip():
                    return text
            except UnicodeDecodeError:
                continue
        raise DocumentParseError("文本文件编码无法识别，请转成 UTF-8 后重试。")

    def _extract_pdf(self, file_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency issue
            raise DocumentParseError("PDF 解析依赖未安装，请安装 pypdf。") from exc

        reader = PdfReader(BytesIO(file_bytes))
        texts = [page.extract_text() or "" for page in reader.pages]
        content = "\n".join(texts).strip()
        if not content:
            raise DocumentParseError("PDF 中未提取到可用文本，可能是扫描件或图片版 PDF。")
        return content

    def _extract_docx(self, file_bytes: bytes) -> str:
        try:
            from docx import Document
        except ImportError as exc:  # pragma: no cover - dependency issue
            raise DocumentParseError("Word 解析依赖未安装，请安装 python-docx。") from exc

        document = Document(BytesIO(file_bytes))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        content = "\n".join(paragraphs).strip()
        if not content:
            raise DocumentParseError("DOCX 中未提取到可用文本。")
        return content
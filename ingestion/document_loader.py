"""
Document Loader — Ingests PDF, DOCX, TXT files into raw text.

Priority extraction order:
1. pdfplumber (best layout-aware extraction)
2. PyMuPDF/fitz (fast fallback)
3. python-docx (for DOCX)
4. Plain text read

Supports batch ingestion of up to 100 resumes per run.
All PII remains local — no cloud calls made here.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DocumentLoader:
    """
    Loads documents from disk and extracts raw text.
    Supports PDF (pdfplumber + PyMuPDF fallback), DOCX, and TXT.
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".text"}
    MAX_BATCH_SIZE = 100  # Per spec: support up to 100 resumes per run

    def load_file(self, file_path: str | Path) -> dict:
        """
        Load a single document file and return its raw text.

        Args:
            file_path: Path to the document file.

        Returns:
            dict with keys: path, name, extension, text, page_count, error
        """
        path = Path(file_path)
        result = {
            "path": str(path),
            "name": path.name,
            "extension": path.suffix.lower(),
            "text": "",
            "page_count": 0,
            "error": None,
        }

        if not path.exists():
            result["error"] = f"File not found: {path}"
            logger.error(result["error"])
            return result

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            result["error"] = f"Unsupported file type: {path.suffix}"
            logger.warning(result["error"])
            return result

        ext = path.suffix.lower()

        if ext == ".pdf":
            result = self._load_pdf(path, result)
        elif ext in {".docx", ".doc"}:
            result = self._load_docx(path, result)
        else:
            result = self._load_text(path, result)

        logger.info(f"Loaded {path.name}: {len(result['text'])} chars, {result['page_count']} pages")
        return result

    def load_bytes(self, content: bytes, filename: str) -> dict:
        """
        Load a document from bytes (e.g., uploaded via web UI/API).

        Args:
            content: Raw bytes of the document.
            filename: Original filename (used to determine type).

        Returns:
            dict with same structure as load_file()
        """
        import tempfile
        ext = Path(filename).suffix.lower()
        suffix = ext if ext in self.SUPPORTED_EXTENSIONS else ".txt"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            result = self.load_file(tmp_path)
            result["name"] = filename  # Restore original name
            result["path"] = filename
            return result
        finally:
            tmp_path.unlink(missing_ok=True)

    def load_batch(self, file_paths: list[str | Path]) -> list[dict]:
        """
        Load a batch of documents (up to MAX_BATCH_SIZE).

        Args:
            file_paths: List of file paths.

        Returns:
            List of result dicts.
        """
        if len(file_paths) > self.MAX_BATCH_SIZE:
            logger.warning(f"Batch size {len(file_paths)} exceeds limit {self.MAX_BATCH_SIZE}. Truncating.")
            file_paths = file_paths[:self.MAX_BATCH_SIZE]

        results = []
        for fp in file_paths:
            result = self.load_file(fp)
            results.append(result)

        logger.info(f"Batch loaded: {len(results)} documents, "
                    f"{sum(1 for r in results if not r['error'])} successful")
        return results

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _load_pdf(self, path: Path, result: dict) -> dict:
        """Extract text from PDF using pdfplumber (primary) or PyMuPDF (fallback)."""
        # Method 1: pdfplumber — best for structured/tabular PDFs
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text.strip())
                result["page_count"] = len(pdf.pages)
                result["text"] = "\n\n".join(pages_text)

            if result["text"].strip():
                logger.debug(f"PDF loaded via pdfplumber: {path.name}")
                return result
        except ImportError:
            logger.debug("pdfplumber not available, trying PyMuPDF...")
        except Exception as e:
            logger.warning(f"pdfplumber failed for {path.name}: {e}. Trying PyMuPDF...")

        # Method 2: PyMuPDF (fitz) fallback
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text())
            result["page_count"] = len(doc)
            result["text"] = "\n\n".join(pages_text)
            doc.close()
            logger.debug(f"PDF loaded via PyMuPDF: {path.name}")
            return result
        except ImportError:
            logger.error("Neither pdfplumber nor PyMuPDF available. Cannot parse PDF.")
            result["error"] = "PDF parser not available. Install pdfplumber or pymupdf."
        except Exception as e:
            logger.error(f"PyMuPDF failed for {path.name}: {e}")
            result["error"] = str(e)

        return result

    def _load_docx(self, path: Path, result: dict) -> dict:
        """Extract text from DOCX using python-docx."""
        try:
            from docx import Document
            doc = Document(str(path))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            # Also extract table content
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        paragraphs.append(row_text)
            result["text"] = "\n".join(paragraphs)
            result["page_count"] = 1  # DOCX doesn't have explicit pages
            logger.debug(f"DOCX loaded via python-docx: {path.name}")
        except ImportError:
            result["error"] = "python-docx not installed. Run: pip install python-docx"
        except Exception as e:
            result["error"] = f"DOCX parse error: {e}"
            logger.error(f"DOCX failed for {path.name}: {e}")
        return result

    def _load_text(self, path: Path, result: dict) -> dict:
        """Load plain text file."""
        try:
            result["text"] = path.read_text(encoding="utf-8", errors="ignore")
            result["page_count"] = 1
        except Exception as e:
            result["error"] = f"Text read error: {e}"
            logger.error(f"TXT failed for {path.name}: {e}")
        return result

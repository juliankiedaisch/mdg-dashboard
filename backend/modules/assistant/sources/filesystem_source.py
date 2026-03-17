# Assistant Module - Sources: Filesystem Connector
"""
Connector for local filesystem directories.
Supports PDF, DOCX, TXT, Markdown, HTML files.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from modules.assistant.sources.base_source import BaseSource, DocumentChunk

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md', '.html', '.htm'}


def read_txt(filepath: str) -> str:
    """Read plain text / markdown file."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def read_html(filepath: str) -> str:
    """Read HTML file and convert to plain text."""
    import re
    from html import unescape
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>|</p>|</div>|</li>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    return text.strip()


def read_pdf(filepath: str) -> str:
    """Read PDF file using PyPDF2 (optional dependency)."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return '\n\n'.join(pages)
    except ImportError:
        logger.warning("PyPDF2 not installed. Skipping PDF: %s", filepath)
        return ''
    except Exception as e:
        logger.error("Failed to read PDF %s: %s", filepath, e)
        return ''


def read_docx(filepath: str) -> str:
    """Read DOCX file using python-docx (optional dependency)."""
    try:
        from docx import Document
        doc = Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n\n'.join(paragraphs)
    except ImportError:
        logger.warning("python-docx not installed. Skipping DOCX: %s", filepath)
        return ''
    except Exception as e:
        logger.error("Failed to read DOCX %s: %s", filepath, e)
        return ''


FILE_READERS = {
    '.txt': read_txt,
    '.md': read_txt,
    '.html': read_html,
    '.htm': read_html,
    '.pdf': read_pdf,
    '.docx': read_docx,
}


class FilesystemSource(BaseSource):
    """Connector for local filesystem directories."""

    def __init__(self, source_config: Dict[str, Any]):
        super().__init__(source_config)
        config = source_config.get('config', {})
        self.directory = config.get('directory', '')
        self.recursive = config.get('recursive', True)
        self.extensions = config.get('extensions', list(SUPPORTED_EXTENSIONS))

    def _scan_files(self, since: Optional[datetime] = None) -> List[str]:
        """Scan directory for supported files, optionally filtered by modification time."""
        files = []
        dir_path = Path(self.directory)
        if not dir_path.exists():
            logger.error(f"Directory not found: {self.directory}")
            return files

        pattern = '**/*' if self.recursive else '*'
        for fp in dir_path.glob(pattern):
            if not fp.is_file():
                continue
            if fp.suffix.lower() not in self.extensions:
                continue
            if since:
                mtime = datetime.fromtimestamp(fp.stat().st_mtime)
                if mtime < since:
                    continue
            files.append(str(fp))

        return sorted(files)

    def fetch_documents(self) -> List[DocumentChunk]:
        """Fetch all documents from the configured directory."""
        documents = []
        files = self._scan_files()

        for filepath in files:
            ext = Path(filepath).suffix.lower()
            reader = FILE_READERS.get(ext)
            if not reader:
                continue

            text = reader(filepath)
            if not text.strip():
                continue

            title = Path(filepath).name
            rel_path = os.path.relpath(filepath, self.directory) if self.directory else filepath

            documents.append(DocumentChunk(
                text=text,
                title=title,
                source='filesystem',
                source_id=self.source_id,
                document_url=f"file://{filepath}",
                permission_tags=['public'],
                source_type='external_document',
                extra_metadata={
                    'file_path': filepath,
                    'relative_path': rel_path,
                    'file_extension': ext,
                    'file_size': os.path.getsize(filepath),
                },
            ))

        logger.info(f"Filesystem: Fetched {len(documents)} documents from '{self.directory}'")
        return documents

    def sync(self, last_sync: Optional[datetime] = None) -> List[DocumentChunk]:
        """Incremental sync: fetch only files modified since last_sync."""
        if last_sync is None:
            return self.fetch_documents()

        documents = []
        files = self._scan_files(since=last_sync)

        for filepath in files:
            ext = Path(filepath).suffix.lower()
            reader = FILE_READERS.get(ext)
            if not reader:
                continue

            text = reader(filepath)
            if not text.strip():
                continue

            title = Path(filepath).name
            rel_path = os.path.relpath(filepath, self.directory) if self.directory else filepath

            documents.append(DocumentChunk(
                text=text,
                title=title,
                source='filesystem',
                source_id=self.source_id,
                document_url=f"file://{filepath}",
                permission_tags=['public'],
                source_type='external_document',
                extra_metadata={
                    'file_path': filepath,
                    'relative_path': rel_path,
                    'file_extension': ext,
                    'file_size': os.path.getsize(filepath),
                },
            ))

        logger.info(f"Filesystem sync: Found {len(documents)} updated files since {last_sync}")
        return documents

    def test_connection(self) -> Dict[str, Any]:
        """Test filesystem access."""
        dir_path = Path(self.directory)
        if not dir_path.exists():
            return {'success': False, 'message': f"Directory not found: {self.directory}"}
        if not dir_path.is_dir():
            return {'success': False, 'message': f"Not a directory: {self.directory}"}

        files = self._scan_files()
        return {'success': True, 'message': f'Directory accessible. {len(files)} supported files found.'}

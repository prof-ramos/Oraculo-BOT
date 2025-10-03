"""
Document processing utilities for RAG system.

Handles text extraction from various document formats and provides
chunking functionality for embedding generation.
"""

import hashlib
import os
from pathlib import Path
from typing import List, Dict, Any
import magic
import tiktoken

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from docx import Document
except ImportError:
    Document = None


class DocumentProcessor:
    """Utility class for document text extraction and preprocessing."""

    def __init__(self):
        """Initialize the document processor."""
        self.supported_extensions = {'.pdf', '.docx', '.doc', '.md', '.txt'}
        self.mime_types = {
            'application/pdf': '.pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/msword': '.doc',
            'text/markdown': '.md',
            'text/plain': '.txt'
        }

    def get_mime_type(self, file_path: Path) -> str:
        """Determine file MIME type using python-magic."""
        try:
            mime = magic.Magic(mime=True)
            return mime.from_file(str(file_path))
        except Exception:
            # Fallback to extension-based detection
            return self._get_mime_from_extension(file_path)

    def _get_mime_from_extension(self, file_path: Path) -> str:
        """Fallback MIME type detection based on file extension."""
        ext = file_path.suffix.lower()
        if ext == '.pdf':
            return 'application/pdf'
        elif ext == '.docx':
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif ext == '.doc':
            return 'application/msword'
        elif ext == '.md':
            return 'text/markdown'
        elif ext == '.txt':
            return 'text/plain'
        else:
            return 'application/octet-stream'

    def load_document(self, file_path: Path) -> str:
        """Universal document loader detecting format and extracting text."""
        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        mime_type = self.get_mime_type(file_path)
        ext = file_path.suffix.lower()

        if mime_type == 'application/pdf' or ext == '.pdf':
            return self._load_pdf(file_path)
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or ext == '.docx':
            return self._load_docx(file_path)
        elif mime_type == 'text/markdown' or ext == '.md':
            return self._load_markdown(file_path)
        elif mime_type == 'text/plain' or ext in ['.txt', '.doc']:
            return self._load_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {mime_type} for {file_path}")

    def _load_pdf(self, file_path: Path) -> str:
        """Extract text from PDF files."""
        if PyPDF2 is None:
            raise ImportError("PyPDF2 is required for PDF processing. Install with: pip install PyPDF2")

        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            raise RuntimeError(f"Error reading PDF {file_path}: {e}")

        return text.strip()

    def _load_docx(self, file_path: Path) -> str:
        """Extract text from DOCX files."""
        if Document is None:
            raise ImportError("python-docx is required for DOCX processing. Install with: pip install python-docx")

        text = ""
        try:
            doc = Document(file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            raise RuntimeError(f"Error reading DOCX {file_path}: {e}")

        return text.strip()

    def _load_markdown(self, file_path: Path) -> str:
        """Load markdown files as plain text."""
        try:
            return file_path.read_text(encoding='utf-8')
        except Exception as e:
            raise RuntimeError(f"Error reading markdown {file_path}: {e}")

    def _load_text(self, file_path: Path) -> str:
        """Load text files."""
        try:
            return file_path.read_text(encoding='utf-8')
        except Exception as e:
            raise RuntimeError(f"Error reading text file {file_path}: {e}")

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks for embedding."""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Find the last complete sentence within the chunk
            if end < len(text):
                # Look for sentence endings
                chunk_text = text[start:end]
                last_sentence_end = max(
                    chunk_text.rfind('. '),
                    chunk_text.rfind('.\n'),
                    chunk_text.rfind('! '),
                    chunk_text.rfind('?\n'),
                    chunk_text.rfind('\n\n')
                )

                if last_sentence_end > chunk_size * 0.7:  # Use at least 70% of chunk_size
                    end = start + last_sentence_end + 1
                elif end < len(text):
                    # If no good sentence boundary found, look for word boundary
                    last_space = chunk_text.rfind(' ')
                    if last_space > chunk_size * 0.8:
                        end = start + last_space

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = max(start + 1, end - overlap)

        return chunks

    def get_document_hash(self, content: str) -> str:
        """Generate SHA256 hash for duplicate detection."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def get_document_metadata(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Extract metadata from document for storage."""
        return {
            'id': self.get_document_hash(content),
            'filename': file_path.name,
            'content_hash': self.get_document_hash(content),
            'file_path': str(file_path),
            'file_size': file_path.stat().st_size,
            'mime_type': self.get_mime_type(file_path),
            'extension': file_path.suffix.lower()
        }

    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        """Count tokens in text using tiktoken."""
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            # Fallback to approximate character-based counting
            return len(text) // 4

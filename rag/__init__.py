"""
RAG (Retrieval-Augmented Generation) module for document processing and vector storage.

This module provides functionality to:
- Extract text from various document formats (PDF, DOCX, Markdown, TXT)
- Generate embeddings using OpenAI
- Store and retrieve embeddings using ChromaDB
- Prevent duplicate document processing through content hashing
"""

from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from .rag_system import RAGSystem

__all__ = ['DocumentProcessor', 'VectorStore', 'RAGSystem']

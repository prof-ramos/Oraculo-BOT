"""
Main RAG system orchestrator.

Coordinates document processing, embedding generation, vector storage,
and retrieval for context augmentation in chat responses.
"""

import asyncio
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import aiofiles
from datetime import datetime

from .document_processor import DocumentProcessor
from .vector_store import VectorStore


class RAGSystem:
    """Coordinates all RAG operations including document processing and retrieval."""

    def __init__(self,
                 openai_api_key: str,
                 chroma_path: str = "./chroma_db",
                 collection_name: str = "legal_documents",
                 max_context_length: int = 3000,
                 similarity_threshold: float = 0.7,
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        """Initialize the RAG system.

        Args:
            openai_api_key: OpenAI API key for embeddings
            chroma_path: Path to persist ChromaDB
            collection_name: Name of the vector collection
            max_context_length: Maximum tokens for retrieved context
            similarity_threshold: Minimum similarity score for retrieval
            chunk_size: Size of text chunks for embedding
            chunk_overlap: Overlap between chunks
        """
        self.config = {
            'openai_api_key': openai_api_key,
            'chroma_path': chroma_path,
            'collection_name': collection_name,
            'max_context_length': max_context_length,
            'similarity_threshold': similarity_threshold,
            'chunk_size': chunk_size,
            'chunk_overlap': chunk_overlap
        }

        # Initialize components
        self.processor = DocumentProcessor()
        self.vector_store = VectorStore(
            collection_name=collection_name,
            persist_directory=chroma_path,
            openai_api_key=openai_api_key
        )

        # Track processed documents to prevent duplicates
        self.processed_hashes: Set[str] = set()

        # Load existing hashes from vector store
        self._load_existing_hashes()

    def _load_existing_hashes(self):
        """Load existing document hashes from vector store."""
        try:
            documents = self.vector_store.list_documents(limit=1000)
            for doc in documents:
                content_hash = doc.get('content_hash')
                if content_hash:
                    self.processed_hashes.add(content_hash)
        except Exception as e:
            print(f"Warning: Could not load existing hashes: {e}")

    async def initialize_store(self) -> bool:
        """Initialize the vector store and ensure it's ready."""
        try:
            # Test the vector store with a simple query
            info = self.vector_store.get_collection_info()
            print(f"Vector store initialized: {info}")
            return True
        except Exception as e:
            print(f"Error initializing vector store: {e}")
            return False

    async def add_document(self, file_path: Path) -> Dict[str, Any]:
        """Process and store a new document if not already embedded.

        Args:
            file_path: Path to the document file

        Returns:
            Dictionary with processing results and metadata
        """
        try:
            # Check if file exists and is readable
            if not file_path.exists():
                return {
                    'success': False,
                    'error': f'File not found: {file_path}',
                    'document_id': None
                }

            # Load and extract text from document
            content = self.processor.load_document(file_path)

            if not content.strip():
                return {
                    'success': False,
                    'error': 'Document contains no extractable text',
                    'document_id': None
                }

            # Generate content hash for duplicate detection
            content_hash = self.processor.get_document_hash(content)

            # Check if already processed
            if content_hash in self.processed_hashes:
                return {
                    'success': False,
                    'error': 'Document already processed (duplicate content)',
                    'document_id': None,
                    'duplicate': True
                }

            # Get document metadata
            metadata = self.processor.get_document_metadata(file_path, content)
            metadata['processed_at'] = datetime.now().isoformat()

            # Split into chunks for embedding
            chunks = self.processor.chunk_text(
                content,
                chunk_size=self.config['chunk_size'],
                overlap=self.config['chunk_overlap']
            )

            # Store each chunk
            stored_ids = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata['chunk_index'] = i
                chunk_metadata['total_chunks'] = len(chunks)
                chunk_metadata['chunk_hash'] = self.processor.get_document_hash(chunk)

                doc_id = await self.vector_store.store_document(chunk, chunk_metadata)
                stored_ids.append(doc_id)

            # Update processed hashes
            self.processed_hashes.add(content_hash)

            return {
                'success': True,
                'document_id': metadata['id'],
                'content_hash': content_hash,
                'chunks_stored': len(stored_ids),
                'total_chunks': len(chunks),
                'metadata': metadata
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'document_id': None
            }

    async def retrieve_context(self, query: str, max_tokens: Optional[int] = None) -> str:
        """Retrieve relevant context for a user query.

        Args:
            query: User query text
            max_tokens: Maximum tokens for context (uses config default if None)

        Returns:
            Formatted context string for RAG augmentation
        """
        if not query.strip():
            return ""

        max_tokens = max_tokens or self.config['max_context_length']

        try:
            # Search for similar documents
            similar_docs = await self.vector_store.search_similar(
                query=query,
                limit=10,  # Get more candidates for better selection
                threshold=self.config['similarity_threshold']
            )

            if not similar_docs:
                return ""

            # Sort by similarity score and select top results
            similar_docs.sort(key=lambda x: x['similarity_score'], reverse=True)

            # Build context within token limit
            context_parts = []
            current_tokens = 0

            for doc in similar_docs:
                content = doc['content']
                doc_tokens = self.processor.count_tokens(content)

                # Check if adding this document would exceed the limit
                if current_tokens + doc_tokens > max_tokens and context_parts:
                    break

                context_parts.append(content)
                current_tokens += doc_tokens

            # Join contexts with clear separation
            if context_parts:
                context = "\n\n---\n\n".join(context_parts)
                return f"Relevant context from legal documents:\n\n{context}"
            else:
                return ""

        except Exception as e:
            print(f"Error retrieving context: {e}")
            return ""

    def is_document_processed(self, content_hash: str) -> bool:
        """Check if a document has already been processed.

        Args:
            content_hash: SHA256 hash of document content

        Returns:
            True if document is already in the system
        """
        return content_hash in self.processed_hashes

    def get_system_info(self) -> Dict[str, Any]:
        """Get information about the RAG system status."""
        try:
            collection_info = self.vector_store.get_collection_info()
            return {
                'config': self.config,
                'processed_documents': len(self.processed_hashes),
                'collection_info': collection_info,
                'supported_formats': list(self.processor.supported_extensions)
            }
        except Exception as e:
            return {
                'error': str(e),
                'processed_documents': len(self.processed_hashes)
            }

    async def cleanup_duplicates(self) -> Dict[str, Any]:
        """Remove duplicate documents based on content hash.

        Returns:
            Dictionary with cleanup results
        """
        try:
            # Get all documents
            all_docs = self.vector_store.list_documents(limit=10000)

            # Group by content hash
            hash_groups = {}
            for doc in all_docs:
                content_hash = doc.get('content_hash')
                if content_hash:
                    if content_hash not in hash_groups:
                        hash_groups[content_hash] = []
                    hash_groups[content_hash].append(doc)

            # Find and remove duplicates (keep only one per hash)
            removed_count = 0
            for content_hash, docs in hash_groups.items():
                if len(docs) > 1:
                    # Keep the first one, remove the rest
                    for doc in docs[1:]:
                        doc_id = doc.get('id')
                        if doc_id:
                            self.vector_store.delete_document(doc_id)
                            removed_count += 1

            return {
                'success': True,
                'duplicates_removed': removed_count,
                'unique_documents': len(hash_groups)
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

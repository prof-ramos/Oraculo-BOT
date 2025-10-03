"""
Vector store implementation using ChromaDB for RAG system.

Provides async methods for storing and retrieving document embeddings
with metadata support and similarity search capabilities.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Callable
import chromadb
from chromadb.config import Settings
from pathlib import Path

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


class VectorStore:
    """Manages ChromaDB collection with async methods for storage, search, and cleanup."""

    def __init__(self,
                 collection_name: str = "legal_documents",
                 persist_directory: str = "./chroma_db",
                 openai_api_key: Optional[str] = None):
        """Initialize the vector store.

        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist the database
            openai_api_key: OpenAI API key for embedding generation
        """
        self.collection_name = collection_name
        self.persist_directory = Path(persist_directory)
        self.openai_api_key = openai_api_key

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except ValueError:
            # Collection doesn't exist, create it
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Legal documents for RAG system"}
            )

        # Initialize OpenAI client for embeddings
        if AsyncOpenAI is not None and self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None

    async def store_document(self,
                           text: str,
                           metadata: Dict[str, Any],
                           embed_func: Optional[Callable] = None) -> str:
        """Store document embeddings in the vector database.

        Args:
            text: Document text content
            metadata: Document metadata dictionary
            embed_func: Optional custom embedding function

        Returns:
            Document ID that was stored
        """
        if not text.strip():
            raise ValueError("Cannot store empty document")

        # Generate embeddings
        if embed_func:
            embedding = await embed_func(text)
        elif self.openai_client:
            embedding = await self._generate_openai_embedding(text)
        else:
            raise ValueError("No embedding function available")

        # Ensure embedding is a list of floats
        if not isinstance(embedding, list):
            embedding = embedding.tolist() if hasattr(embedding, 'tolist') else [float(embedding)]

        # Store in ChromaDB
        doc_id = metadata.get('id', f"doc_{len(self.collection.get()['ids'])}")

        self.collection.add(
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[doc_id]
        )

        return doc_id

    async def search_similar(self,
                          query: str,
                          embed_func: Optional[Callable] = None,
                          limit: int = 5,
                          threshold: float = 0.1) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity.

        Args:
            query: Search query text
            embed_func: Optional custom embedding function
            limit: Maximum number of results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of retrieved contexts with metadata and similarity scores
        """
        if not query.strip():
            return []

        # Generate query embedding
        if embed_func:
            query_embedding = await embed_func(query)
        elif self.openai_client:
            query_embedding = await self._generate_openai_embedding(query)
        else:
            raise ValueError("No embedding function available")

        # Ensure embedding is a list of floats
        if not isinstance(query_embedding, list):
            query_embedding = query_embedding.tolist() if hasattr(query_embedding, 'tolist') else [float(query_embedding)]

        # Search in ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=['documents', 'metadatas', 'distances']
        )

        # Process results
        contexts = []
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            # Convert distance to similarity score (1 - normalized_distance)
            similarity = 1.0 - (distance / 2.0)  # Normalize assuming max distance of 2

            if similarity >= threshold:
                contexts.append({
                    'content': doc,
                    'metadata': metadata,
                    'similarity_score': similarity,
                    'rank': i + 1
                })

        return contexts

    async def _generate_openai_embedding(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI API."""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")

        try:
            response = await self.openai_client.embeddings.create(
                input=text,
                model="text-embedding-3-small"  # More cost-effective model
            )
            return response.data[0].embedding
        except Exception as e:
            raise RuntimeError(f"Error generating OpenAI embedding: {e}")

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the current collection."""
        try:
            count = self.collection.count()
            return {
                'name': self.collection_name,
                'document_count': count,
                'persist_directory': str(self.persist_directory)
            }
        except Exception as e:
            return {
                'name': self.collection_name,
                'error': str(e)
            }

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def delete_by_metadata(self, metadata_filter: Dict[str, Any]) -> int:
        """Delete documents matching metadata filter.

        Args:
            metadata_filter: Metadata key-value pairs to match

        Returns:
            Number of documents deleted
        """
        try:
            # Get documents matching filter
            results = self.collection.get(where=metadata_filter)

            if results['ids']:
                self.collection.delete(ids=results['ids'])
                return len(results['ids'])
            return 0
        except Exception:
            return 0

    def clear_collection(self) -> bool:
        """Clear all documents from the collection."""
        try:
            self.collection.delete(where={})
            return True
        except Exception:
            return False

    def get_documents_by_hash(self, content_hash: str) -> List[Dict[str, Any]]:
        """Get documents by content hash for duplicate checking."""
        try:
            results = self.collection.get(
                where={'content_hash': content_hash},
                include=['metadatas']
            )
            return results.get('metadatas', [])
        except Exception:
            return []

    def list_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent documents in the collection."""
        try:
            results = self.collection.get(limit=limit, include=['metadatas'])
            return results.get('metadatas', [])
        except Exception:
            return []

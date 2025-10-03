# Implementation Plan

[Overview]
Implement Retrieval-Augmented Generation (RAG) system for the Discord chatbot to provide contextually relevant responses based on legal documents.

The RAG implementation will extract text from legal documents (laws, jurisprudence, doctrines) in various formats (PDF, DOCX, DOC, Markdown, TXT), generate embeddings using OpenAI, store them in a Chroma vector database for efficient retrieval, and automatically augment every user query with relevant retrieved context before sending to OpenRouter. The system will prevent redundant embedding computations by maintaining a hash registry of processed documents.

[Types]
Add new type definitions to support RAG document processing and vector storage.

```python
from typing import TypedDict, Optional
from datetime import datetime
from pathlib import Path

class DocumentMetadata(TypedDict):
    id: str
    filename: str
    content_hash: str
    file_path: str
    file_size: int
    created_at: datetime
    mime_type: str
    embedding_count: int

class RetrievedContext(TypedDict):
    content: str
    metadata: DocumentMetadata
    similarity_score: float

class RAGConfig(TypedDict):
    openai_api_key: str
    chroma_path: str
    collection_name: str
    max_context_length: int
    similarity_threshold: float
    chunk_size: int
    chunk_overlap: int
```

[Files]
Create new files for RAG components and modify existing files to integrate retrieval functionality.

**New files to be created:**
- `rag/document_processor.py`: Handles document loading, text extraction, and chunking (functions: load_pdf, load_docx, load_markdown, load_text, chunk_text, get_document_hash)
- `rag/vector_store.py`: Chroma database integration for storing and retrieving embeddings (class VectorStore with methods: store_document, search_similar, get_collection_info, delete_document)
- `rag/rag_system.py`: Main RAG orchestrator coordinating document processing and retrieval (class RAGSystem with methods: add_document, retrieve_context, is_document_processed)
- `rag/__init__.py`: Package initialization for rag module

**Existing files to be modified:**
- `main.py`: Modify OpenRouterChatClient class to integrate RAG retrieval in _prepare_messages method, update environment variable handling for RAG_CONFIG, add RAG system initialization in __init__ and setup_hook
- `pyproject.toml`: Add new dependencies (chromadb, openai, pypdf2, python-docx, python-magic, tiktoken)
- `admin_cog.py`: Add new hybrid command /add_document for administrators to upload legal documents to the RAG system
- `README.md`: Update documentation with RAG configuration instructions and new admin commands

**Configuration file updates:**
- Add new environment variables: OPENAI_API_KEY, RAG_CHROMA_PATH (optional), RAG_MAX_CONTEXT (optional), RAG_SIMILARITY_THRESHOLD (optional)

[Functions]
Implement new functions for RAG document processing, vector storage, and retrieval integration.

**New functions:**
- `rag/document_processor.py`:
  - `load_document(file_path: Path) -> str`: Universal document loader detecting format and extracting text
  - `chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]`: Split text into overlapping chunks
  - `get_document_hash(content: str) -> str`: Generate SHA256 hash for duplicate detection
  - `get_mime_type(file_path: Path) -> str`: Determine file MIME type
- `rag/vector_store.py`:
  - `async store_document(text: str, metadata: DocumentMetadata, embed_func) -> str`: Store document embeddings
  - `async search_similar(query: str, embed_func, limit: int) -> List[RetrievedContext]`: Vector similarity search
- `rag/rag_system.py`:
  - `async add_document(file_path: Path) -> bool`: Process and store new document if not already embedded
  - `async retrieve_context(query: str, max_tokens: int) -> str`: Get formatted context for RAG augmentation
- `admin_cog.py`:
  - `async add_document(ctx: commands.Context, attachment: discord.Attachment)`
- `main.py`:
  - `_build_rag_context(self, user_query: str) -> List[dict[str, str]]`: Generate RAG-augmented messages

**Modified functions:**
- `main.py`:
  - `OpenRouterChatClient.__init__`: Add RAG_SYSTEM instance variable and configuration loading
  - `OpenRouterChatClient._prepare_messages`: Modify to include RAG context before system prompt
  - `OpenRouterChatClient.setup_hook`: Initialize RAG system and ensure vector store is ready
  - `OpenRouterChatClient._env_int` and `_env_float`: Add support for RAG configuration defaults

[Classes]
Add new classes for RAG system components while modifying the main bot for integration.

**New classes:**
- `rag/vector_store.py`:
  - `VectorStore`: Manages ChromaDB collection with async methods for storage, search, and cleanup
    - Key methods: __init__, store_embedding, query_similar, delete_by_metadata
    - Inherits from optional base classes for consistency
- `rag/rag_system.py`:
  - `RAGSystem`: Coordinates all RAG operations including document processing and retrieval
    - Key methods: __init__, initialize_store, process_document, retrieve_augmented_context
- `rag/document_processor.py`:
  - `DocumentProcessor`: Utility class for text extraction and preprocessing
    - Key methods: extract_text, split_into_chunks

**Modified classes:**
- `main.py`:
  - `OpenRouterChatClient`: Add RAG integration methods and state management
    - Modifications: Add rag_system attribute, modify _prepare_messages to include retrieved context, add setup/cleanup for RAG components

[Dependencies]
Add RAG and document processing dependencies while maintaining backward compatibility.

New packages:
- `chromadb==0.4.24`: Vector database for embedding storage and retrieval
- `openai==1.12.0`: OpenAI API client for embedding generation
- `pypdf2==3.0.1`: PDF text extraction
- `python-docx==1.1.0`: Word document processing
- `python-magic==0.4.27`: File type detection
- `tiktoken==0.6.0`: Token counting for context length management
- `aiofiles==23.2.1`: Async file operations for document processing

Version specifications chosen for compatibility with existing stack (aiohttp, discord.py).

[Testing]
Implement comprehensive tests for RAG components and integration points.

Create `test_rag.py` with:
- Unit tests for DocumentProcessor (text extraction, chunking, hashing)
- Unit tests for VectorStore (embedding storage, similarity search)
- Integration tests for RAGSystem (end-to-end document processing and retrieval)
- Tests for admin command /add_document functionality

Existing tests (if any) remain unchanged but test environment should include mock OpenAI API and temporary Chroma instances.

Validation strategies:
- Document uniqueness verification through hash checking
- Embedding quality assessment via similarity thresholds
- Performance testing with varying document sizes and query loads
- Edge case testing for unsupported file formats and corrupted documents

[Implementation Order]
Implement RAG system components in logical dependency order to ensure incremental integration.

1. Update dependencies in pyproject.toml and install new packages
2. Create rag module with DocumentProcessor and VectorStore classes
3. Implement RAGSystem orchestrator with duplicate checking
4. Add environment configuration and OpenAI API integration
5. Modify OpenRouterChatClient to initialize RAG system
6. Update message preparation to include RAG context in every query
7. Add admin command for document uploads
8. Update README and create setup documentation
9. Implement initial tests for all new components
10. Perform integration testing and performance validation

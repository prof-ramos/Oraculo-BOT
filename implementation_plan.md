# Implementation Plan

## [Overview]
The goal is to refactor the Oraculo-BOT Discord chatbot for improved architecture, security, performance, and developer experience, including migration to Nextcord, a dedicated OpenRouter client, RAG decoupling, uv-based dependency management, and quality tooling.

This implementation addresses key issues in the current codebase: tight coupling between bot logic and API calls, use of unmaintained discord.py, synchronous file operations in async contexts, lack of structured logging and error handling, no validation for environment variables, and absence of tests and linting. The refactors will enhance maintainability, reduce errors, and align with best practices for Python Discord bots on macOS ARM with 8GB RAM constraints, preferring lightweight libraries like httpx over aiohttp where possible. The approach involves modularizing components, adding interfaces with Pydantic, implementing retries and timeouts for API calls, and ensuring ARM compatibility by avoiding heavy dependencies.

The changes fit into the existing system by preserving core functionality (chat responses via OpenRouter with optional RAG context, admin moderation commands) while introducing separation of concerns: a reusable OpenRouter client, decoupled RAG service, and standardized error handling. This will improve DX through uv for fast installs, ruff for linting, pytest for unit tests, and pre-commit hooks, without introducing paid services.

## [Types]
Introduce Pydantic models for structured data handling in API requests/responses, environment validation, and error types to ensure type safety and validation.

- **OpenRouterRequest**: Base model for chat completion requests.
  - Fields: model (str, default="openai/gpt-4o-mini"), messages (List[Message]), max_tokens (Optional[int] = 1024), temperature (Optional[float] = 0.7), stream (bool = False), top_p (Optional[float] = None).
  - Validation: messages non-empty, model in allowed list (from env or config), temperature between 0.0 and 2.0.

- **Message**: Dataclass or Pydantic model for chat messages.
  - Fields: role (Literal["system", "user", "assistant"]), content (str).
  - Relationships: Used in OpenRouterRequest.messages; system prompt from env.

- **OpenRouterResponse**: Model for API responses.
  - Fields: choices (List[Choice]), usage (Optional[Usage]).
  - Nested: Choice (message: Message, finish_reason: str), Usage (prompt_tokens: int, completion_tokens: int, total_tokens: int).
  - Validation: Ensure choices non-empty, content present.

- **EnvConfig**: Pydantic settings for environment variables.
  - Fields: DISCORD_TOKEN (str, required), OPENROUTER_API_KEY (str, required), OPENROUTER_BASE_URL (str, default="https://openrouter.ai/api/v1"), LOG_LEVEL (str, default="INFO"), MODEL_DEFAULT (str, default="openai/gpt-4o-mini"), RAG_ENABLED (bool, default=False), OPENAI_API_KEY (Optional[str]).
  - Validation: Fail-fast on startup if required vars missing; use pydantic-settings for loading.

- **Custom Errors**: Custom exceptions inheriting from Exception.
  - OpenRouterError (base), RateLimitError (status 429), AuthError (401/403), TimeoutError, APIError (other HTTP errors).
  - Fields: status_code (Optional[int]), detail (str).

- **RAGContext**: Model for retrieved context.
  - Fields: context (str), sources (List[str]), similarity_scores (List[float]).
  - Validation: similarity_scores > threshold (from config, default 0.7).

These types ensure immutability where possible (dataclasses with frozen=True), support serialization for logging/JSON, and integrate with asyncio/httpx for async contexts.

## [Files]
Create new files for modularity, modify existing for refactors, update configs; no deletions.

- New files:
  - openrouter_client.py (root): Dedicated async client for OpenRouter API using httpx, with retries (tenacity), timeouts, structured logging (logging with JSON formatter), streaming support via SSE. Purpose: Decouple API logic from bot.
  - config.py (root): Pydantic-based env validation and settings loader. Purpose: Centralized config with fail-fast startup.
  - rag/service.py (rag/): Interface for RAG operations, wrapping RAGSystem for dependency injection. Purpose: Decouple RAG from admin_cog and main.py.
  - tests/test_openrouter_client.py (tests/): Unit tests for client with httpx mocks. Purpose: Verify API interactions.
  - tests/test_bot_handlers.py (tests/): Tests for Discord handlers with pytest-asyncio. Purpose: Ensure command/moderation logic.
  - ruff.toml (root): Ruff configuration for linting (extend from pyproject.toml). Purpose: Enforce code style.
  - .pre-commit-config.yaml (root): Pre-commit hooks for ruff, pytest. Purpose: DX enforcement.
  - .env.example (root): Template with all vars (DISCORD_TOKEN, OPENROUTER_API_KEY, etc.). Purpose: Security best practice.
  - docs/architecture.md (docs/): ASCII diagrams of bot flow, RAG integration. Purpose: Documentation.

- Existing files to modify:
  - pyproject.toml: Update dependencies (nextcord ^2.3.0, httpx ^0.27.0, pydantic ^2.5.0, tenacity ^8.3.0, python-dotenv ^1.0.0; remove discord, aiohttp); add dev deps (ruff ^0.5.0, pytest ^8.0.0, pytest-asyncio ^0.23.0, pre-commit ^3.7.0); configure [tool.ruff], [tool.pytest]. Changes: Enable uv sync compatibility.
  - main.py: Migrate to Nextcord (replace discord with nextcord, commands.Bot with nextcord.ext.commands.Bot); inject OpenRouterClient and RAGService; add env validation on startup; refactor _query_openrouter to use client; update intents (message_content=True). Changes: Remove aiohttp session, add async context manager for client.
  - admin_cog.py: Update to Nextcord syntax (nextcord.ext.commands, nextcord.Interaction); inject RAGService for add_document; use client for any API calls if needed. Changes: Decouple RAG access via service.
  - rag/rag_system.py: Minor: Add async methods if needed for service integration; ensure ARM compatibility (chromadb is ok). Changes: Expose via service.
  - moderation_logger.py: Add structured logging (JSON output); make async-safe. Changes: Use logging module with JSON formatter.
  - README.md: Update installation (uv venv, uv pip install -e .), setup (.env from example), run (uv run python -m main), tests (uv run pytest), troubleshooting (rate limits, ARM notes). Changes: Add sections for new tools.

- Configuration updates: pyproject.toml as above; add [tool.uv] for package=false if non-package.

## [Functions]
Introduce new functions for modularity, modify existing for Nextcord migration and decoupling, no removals.

- New functions:
  - openrouter_client.py: async def query_chat(messages: List[Message], model: str = None, stream: bool = False) -> str | AsyncIterator[str]: Core API call with retries (tenacity.retry, wait=exponential, reraise=True), timeout (httpx.Timeout(60.0)), headers (auth, referer from config). Purpose: Handle streaming/non-streaming, errors. Signature: in openrouter_client.py.
  - openrouter_client.py: async def stream_chat(messages: List[Message], model: str = None) -> AsyncIterator[str]: SSE parsing for streaming. Purpose: Real-time responses. Signature: yields content chunks.
  - config.py: def load_config() -> EnvConfig: Load and validate env with pydantic. Purpose: Startup validation. Signature: in config.py.
  - rag/service.py: async def retrieve_context(query: str) -> RAGContext: Wrap RAGSystem.retrieve_context. Purpose: Interface. Signature: in rag/service.py.
  - rag/service.py: async def add_document(file_path: Path) -> Dict[str, Any]: Wrap RAGSystem.add_document. Purpose: Decoupled access. Signature: in rag/service.py.
  - main.py: async def setup_services(bot: Bot) -> None: Initialize client, rag_service, inject to bot. Purpose: DI. Signature: in main.py.

- Modified functions:
  - main.py: _query_openrouter -> remove, replace calls with client.query_chat; _prepare_messages: Add RAG context via service.retrieve_context if enabled. Changes: Async, use Pydantic models.
  - main.py: on_message: Update to Nextcord Interaction if needed, but keep message-based; use client for query. Changes: Better error handling with custom exceptions.
  - admin_cog.py: add_document: Use rag_service.add_document instead of direct RAGSystem. Changes: Inject service in __init__.
  - moderation_logger.py: log_action, warn_user: Add structured logging (logger.info with extras). Changes: JSON output via logging config.

## [Classes]
New classes for clients/services, modify existing for migration and injection.

- New classes:
  - openrouter_client.py: class OpenRouterClient: Async client with httpx.AsyncClient, config injection. Key methods: __aenter__, __aexit__, query_chat, stream_chat. Inheritance: None. Purpose: Reusable API handler.
  - rag/service.py: class RAGService: Wrapper for RAGSystem. Key methods: __init__(rag_system: RAGSystem), retrieve_context, add_document. Inheritance: None. Purpose: Decoupling.
  - config.py: No class, but EnvConfig as Pydantic BaseSettings.

- Modified classes:
  - main.py: OpenRouterChatClient -> rename to OraculoBot (nextcord.ext.commands.Bot subclass). Changes: Intents update (nextcord.Intents), inject client/service in __init__, setup_hook loads extensions/services, on_message uses client.query_chat.
  - admin_cog.py: AdminCog: Update to nextcord.ext.commands.Cog, inject RAGService in __init__(self, bot, rag_service). Changes: Hybrid commands to nextcord.slash_command where appropriate, use service.
  - rag/rag_system.py: RAGSystem: Minor, add async wrappers if needed. Changes: Configurable via service.
  - moderation_logger.py: ModerationLogger: Add logging integration. Changes: Use bot.logger.

No removed classes; migration preserves structure.

## [Dependencies]
Migrate to uv-compatible pyproject.toml; add lightweight, ARM-friendly deps; update versions for stability.

- New packages:
  - nextcord ^2.3.0 (replace discord ^2.3.2): Maintained Discord wrapper.
  - httpx ^0.27.0 (replace aiohttp ^3.9.5): Async HTTP client, better for streaming/timeouts.
  - pydantic ^2.5.0: Type validation/models.
  - tenacity ^8.3.0: Retries for API calls.
  - python-dotenv ^1.0.0: Env loading (though Pydantic handles).
  - Dev: ruff ^0.5.0 (linting), pytest ^8.0.0 + pytest-asyncio ^0.23.0 (testing), pre-commit ^3.7.0 (hooks).

- Version changes:
  - chromadb ^0.4.24 -> keep, but ensure ARM wheels.
  - openai ^1.12.0 -> keep for RAG embeddings.
  - Remove: discord, aiohttp.

- Integration: uv pip install -e . for dev; no heavy libs (e.g., avoid torch); all ARM-compatible via wheels.

## [Testing]
Unit and integration tests with pytest-asyncio for async code; mock httpx/discord; coverage >80%.

- Test files: tests/test_openrouter_client.py (mock httpx, test query_chat/stream_chat, errors/retries); tests/test_bot_handlers.py (mock Nextcord, test on_message, commands); tests/test_rag_service.py (mock RAGSystem, test retrieve/add).
- Existing: None; add pytest.ini for asyncio mode.
- Validation: Mock API responses (success, 429, 401); test env validation (missing vars raise); moderation logging (JSON output); RAG integration (context injection).
- Strategies: Parametrize for models/errors; async tests for streaming; run with uv run pytest -v.

## [Implementation Order]
Implement in phases to avoid breaking changes: deps first, then core refactors, tests last.

1. Update pyproject.toml with new deps (nextcord, httpx, etc.); run uv sync; verify bot runs with Nextcord migration stub.
2. Create config.py and .env.example; add validation in main.py startup; test env loading.
3. Create OpenRouterClient in openrouter_client.py; refactor main.py _query_openrouter to use it; test client standalone.
4. Migrate main.py to Nextcord (intents, Bot subclass); update on_message; test basic bot functionality.
5. Create RAGService; refactor admin_cog.py and main.py to use it; test RAG integration.
6. Update moderation_logger.py with structured logging; add logging config in main.py.
7. Add ruff.toml, .pre-commit-config.yaml; run pre-commit install; lint codebase.
8. Write tests in tests/; run pytest; fix issues.
9. Update README.md and create docs/architecture.md with ASCII flows (bot -> client -> OpenRouter; admin -> service -> RAG).
10. Final: uv lock; test full run (uv run python -m main); validate no regressions.

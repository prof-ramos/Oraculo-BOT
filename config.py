from typing import List, Optional, Literal, Any
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class OpenRouterRequest(BaseModel):
    model: str = Field(default="openai/gpt-4o-mini")
    messages: List[Message]
    max_tokens: Optional[int] = 1024
    temperature: Optional[float] = 0.7
    stream: bool = False
    top_p: Optional[float] = None

    @validator("messages")
    def messages_non_empty(cls, v):
        if not v:
            raise ValueError("messages must be non-empty")
        return v

    @validator("temperature")
    def temperature_range(cls, v):
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v

class Choice(BaseModel):
    message: Message
    finish_reason: str

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class OpenRouterResponse(BaseModel):
    choices: List[Choice]
    usage: Optional[Usage] = None

    @validator("choices")
    def choices_non_empty(cls, v):
        if not v:
            raise ValueError("choices must be non-empty")
        return v

class RAGContext(BaseModel):
    context: str
    sources: List[str]
    similarity_scores: List[float]

    @validator("similarity_scores")
    def scores_above_threshold(cls, v):
        threshold = 0.7  # Default threshold
        if any(score < threshold for score in v):
            raise ValueError(f"similarity_scores must be >= {threshold}")
        return v

class EnvConfig(BaseSettings):
    DISCORD_TOKEN: str
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LOG_LEVEL: str = "INFO"
    MODEL_DEFAULT: str = "openai/gpt-4o-mini"
    RAG_ENABLED: bool = False
    OPENAI_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def load_config() -> EnvConfig:
    """Load and validate environment configuration."""
    return EnvConfig()

# Custom Errors
class OpenRouterError(Exception):
    """Base exception for OpenRouter API errors."""
    pass

class RateLimitError(OpenRouterError):
    """Raised when rate limit is exceeded."""
    def __init__(self, status_code: Optional[int] = None, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Rate limit exceeded (status: {status_code}): {detail}")

class AuthError(OpenRouterError):
    """Raised for authentication errors."""
    def __init__(self, status_code: Optional[int] = None, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Authentication failed (status: {status_code}): {detail}")

class TimeoutError(OpenRouterError):
    """Raised for timeout errors."""
    def __init__(self, detail: str = "Request timed out"):
        super().__init__(detail)

class APIError(OpenRouterError):
    """Raised for other API errors."""
    def __init__(self, status_code: Optional[int] = None, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error (status: {status_code}): {detail}")

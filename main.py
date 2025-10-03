"""Discord chatbot powered by OpenRouter."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from typing import Deque, Dict, Iterable, List

import aiohttp
import discord


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class OpenRouterChatClient(discord.Client):
    """Discord client that relays messages to OpenRouter."""

    def __init__(self, **kwargs):
        intents = kwargs.pop("intents", None)
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True

        super().__init__(intents=intents, **kwargs)

        self._api_key = os.getenv("OPENROUTER_API_KEY")
        if not self._api_key:
            raise RuntimeError("Defina a variável de ambiente OPENROUTER_API_KEY para usar o chatbot.")

        self._api_url = os.getenv(
            "OPENROUTER_API_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        )
        self._model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
        self._system_prompt = os.getenv(
            "OPENROUTER_SYSTEM_PROMPT",
            "Você é um assistente útil que responde de forma clara e objetiva.",
        )
        self._timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT", "60"))
        self._max_turns = _env_int("OPENROUTER_MAX_TURNS", 6)

        self._session: aiohttp.ClientSession | None = None
        self._history: Dict[int, Deque[dict[str, str]]] = {}
        self._locks: Dict[int, asyncio.Lock] = {}
        self._allowed_mentions = discord.AllowedMentions.none()

        self._base_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        referer = os.getenv("OPENROUTER_REFERER")
        if referer:
            self._base_headers["HTTP-Referer"] = referer
        title = os.getenv("OPENROUTER_TITLE")
        if title:
            self._base_headers["X-Title"] = title

    async def setup_hook(self) -> None:
        await super().setup_hook()
        await self._ensure_session()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        await super().close()

    async def on_ready(self) -> None:
        assert self.user is not None
        logger.info("Autenticado como %s", self.user)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.author == self.user:
            return

        if not self._should_reply(message):
            return

        content = self._clean_content(message)
        channel_id = message.channel.id
        conversation = self._history.setdefault(
            channel_id,
            deque(maxlen=self._max_turns * 2),
        )
        lock = self._locks.setdefault(channel_id, asyncio.Lock())

        async with lock:
            payload_messages = self._prepare_messages(conversation, content)
            try:
                async with message.channel.typing():
                    reply_text = await self._query_openrouter(payload_messages)
            except (asyncio.TimeoutError, aiohttp.ClientError, RuntimeError) as exc:
                logger.exception("Erro ao consultar o OpenRouter")
                await message.reply(
                    "Desculpe, estou com dificuldades para falar com o OpenRouter agora.",
                    mention_author=False,
                )
                return

            conversation.extend(
                (
                    {"role": "user", "content": content},
                    {"role": "assistant", "content": reply_text},
                )
            )
            await self._send_reply(message, reply_text)

    def _should_reply(self, message: discord.Message) -> bool:
        if isinstance(message.channel, discord.DMChannel):
            return True

        if self.user and self.user in message.mentions:
            return True

        reference = message.reference
        if reference and reference.resolved:
            resolved = reference.resolved
            author = getattr(resolved, "author", None)
            if author and self.user and author.id == self.user.id:
                return True

        return False

    def _clean_content(self, message: discord.Message) -> str:
        content = message.content or ""
        if self.user:
            mention_variants = (
                f"<@{self.user.id}>",
                f"<@!{self.user.id}>",
            )
            for variant in mention_variants:
                content = content.replace(variant, "")

        content = content.strip()
        if not content and message.attachments:
            filenames = ", ".join(attachment.filename for attachment in message.attachments)
            content = f"[O usuário enviou anexos: {filenames}]"

        if not content:
            content = "[O usuário não enviou texto.]"

        return content

    def _prepare_messages(
        self,
        conversation: Deque[dict[str, str]],
        user_message: str,
    ) -> List[dict[str, str]]:
        messages: List[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(conversation)
        messages.append({"role": "user", "content": user_message})
        return messages

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _query_openrouter(self, messages: Iterable[dict[str, str]]) -> str:
        session = await self._ensure_session()
        payload = {
            "model": self._model,
            "messages": list(messages),
        }

        async with session.post(
            self._api_url,
            headers=self._base_headers,
            json=payload,
        ) as response:
            if response.status == 429:
                retry_after = response.headers.get("Retry-After", "60")
                raise RuntimeError(
                    f"Rate limit atingido. Tente novamente após {retry_after} segundos."
                )
            if response.status in (401, 403):
                raise RuntimeError(
                    "Falha de autenticação. Verifique OPENROUTER_API_KEY."
                )
            if response.status >= 500:
                raise RuntimeError(
                    f"Erro do servidor OpenRouter ({response.status}). Tente novamente mais tarde."
                )
            if response.status != 200:
                detail = await response.text()
                raise RuntimeError(
                    f"OpenRouter retornou o status {response.status}: {detail}",
                )

            data = await response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Resposta do OpenRouter não contém choices.")

        message = choices[0].get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise RuntimeError("Resposta do OpenRouter veio vazia.")
        return content

    async def _send_reply(self, message: discord.Message, reply_text: str) -> None:
        chunks = self._split_message(reply_text)
        for index, chunk in enumerate(chunks):
            if index == 0:
                await message.reply(chunk, mention_author=False)
            else:
                await message.channel.send(
                    chunk,
                    reference=message.to_reference(),
                    allowed_mentions=self._allowed_mentions,
                )

    @staticmethod
    def _split_message(text: str, limit: int = 2000) -> List[str]:
        if len(text) <= limit:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + limit)
            if end < len(text):
                split_at = text.rfind("\n", start, end)
                if split_at == -1:
                    split_at = text.rfind(" ", start, end)
                if split_at != -1 and split_at > start:
                    end = split_at + 1

            raw_chunk = text[start:end]
            chunk = raw_chunk.strip()
            chunks.append(chunk if chunk else raw_chunk)
            start = end

        return [chunk for chunk in chunks if chunk.strip()]


def _run() -> None:
    intents = discord.Intents.default()
    intents.message_content = True
    client = OpenRouterChatClient(intents=intents)

    token = os.getenv("TOKEN") or ""
    if not token:
        raise RuntimeError("Defina a variável de ambiente TOKEN com o token do bot do Discord.")

    try:
        client.run(token)  # type: ignore[no-untyped-call]
    except discord.HTTPException as error:
        if error.status == 429:
            logger.error(
                "O Discord rejeitou a conexão por excesso de requisições. Veja sugestões em %s",
                "https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests",
            )
        raise


if __name__ == "__main__":
    _run()

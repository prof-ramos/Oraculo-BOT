import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import aiofiles
import aiofiles.os


class ModerationLogger:
    """Handles logging of moderation actions and user warnings."""

    def __init__(self, log_file: str = "moderation_log.json", warn_file: str = "warns.json"):
        self.log_file = log_file
        self.warn_file = warn_file
        self._lock = asyncio.Lock()
        self._warn_lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

    async def log_action(self, action: dict) -> None:
        """Log a moderation action to the log file."""
        async with self._lock:
            try:
                logs = []
                if await aiofiles.os.path.exists(self.log_file):
                    async with aiofiles.open(self.log_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        logs = json.loads(content) if content.strip() else []

                logs.append(action)

                async with aiofiles.open(self.log_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(logs, indent=2, ensure_ascii=False))
            except (OSError, json.JSONDecodeError) as e:
                self.logger.error("Failed to log action", exc_info=True)

    async def warn_user(self, user_id: int, reason: str, moderator: str) -> int:
        """Add a warning to a user and return the new warning count."""
        async with self._warn_lock:
            try:
                warns = {}
                if await aiofiles.os.path.exists(self.warn_file):
                    async with aiofiles.open(self.warn_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        warns = json.loads(content) if content.strip() else {}

                if str(user_id) not in warns:
                    warns[str(user_id)] = []

                warns[str(user_id)].append({
                    "reason": reason,
                    "moderator": moderator,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                async with aiofiles.open(self.warn_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(warns, indent=2, ensure_ascii=False))

                return len(warns[str(user_id)])
            except (OSError, json.JSONDecodeError) as e:
                self.logger.error("Failed to warn user", exc_info=True)
                return 0

    async def get_warns(self, user_id: int) -> list:
        """Get the list of warnings for a user."""
        async with self._warn_lock:
            try:
                if not await aiofiles.os.path.exists(self.warn_file):
                    return []

                async with aiofiles.open(self.warn_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    warns = json.loads(content) if content.strip() else {}

                return warns.get(str(user_id), [])
            except (OSError, json.JSONDecodeError):
                self.logger.error("Failed to get warnings for user", exc_info=True)
                return []

    async def clear_warns(self, user_id: int) -> bool:
        """Clear all warnings for a user."""
        async with self._warn_lock:
            try:
                if not await aiofiles.os.path.exists(self.warn_file):
                    return True

                async with aiofiles.open(self.warn_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    warns = json.loads(content) if content.strip() else {}

                if str(user_id) in warns:
                    del warns[str(user_id)]

                    async with aiofiles.open(self.warn_file, "w", encoding="utf-8") as f:
                        await f.write(json.dumps(warns, indent=2, ensure_ascii=False))

                return True
            except (OSError, json.JSONDecodeError):
                self.logger.error("Failed to clear warnings for user", exc_info=True)
                return False

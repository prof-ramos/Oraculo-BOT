import asyncio
import json
import os
from datetime import datetime
from pathlib import Path


class ModerationLogger:
    """Handles logging of moderation actions and user warnings."""

    def __init__(self, log_file: str = "moderation_log.json", warn_file: str = "warns.json"):
        self.log_file = log_file
        self.warn_file = warn_file
        self._lock = asyncio.Lock()
        self._warn_lock = asyncio.Lock()

    async def log_action(self, action: dict) -> None:
        """Log a moderation action to the log file."""
        async with self._lock:
            try:
                logs = []
                if os.path.exists(self.log_file):
                    with open(self.log_file, "r", encoding="utf-8") as f:
                        logs = json.load(f)

                logs.append(action)

                with open(self.log_file, "w", encoding="utf-8") as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
            except (OSError, json.JSONDecodeError, json.JSONEncodeError) as e:
                print(f"Failed to log action: {e}")

    async def warn_user(self, user_id: int, reason: str, moderator: str) -> int:
        """Add a warning to a user and return the new warning count."""
        async with self._warn_lock:
            try:
                warns = {}
                if os.path.exists(self.warn_file):
                    with open(self.warn_file, "r", encoding="utf-8") as f:
                        warns = json.load(f)

                if str(user_id) not in warns:
                    warns[str(user_id)] = []

                warns[str(user_id)].append({
                    "reason": reason,
                    "moderator": moderator,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                with open(self.warn_file, "w", encoding="utf-8") as f:
                    json.dump(warns, f, indent=2, ensure_ascii=False)

                return len(warns[str(user_id)])
            except (OSError, json.JSONDecodeError, json.JSONEncodeError) as e:
                print(f"Failed to warn user: {e}")
                return 0

    async def get_warns(self, user_id: int) -> list:
        """Get the list of warnings for a user."""
        async with self._warn_lock:
            try:
                if not os.path.exists(self.warn_file):
                    return []

                with open(self.warn_file, "r", encoding="utf-8") as f:
                    warns = json.load(f)

                return warns.get(str(user_id), [])
            except (OSError, json.JSONDecodeError):
                return []

    async def clear_warns(self, user_id: int) -> bool:
        """Clear all warnings for a user."""
        async with self._warn_lock:
            try:
                if not os.path.exists(self.warn_file):
                    return True

                with open(self.warn_file, "r", encoding="utf-8") as f:
                    warns = json.load(f)

                if str(user_id) in warns:
                    del warns[str(user_id)]

                    with open(self.warn_file, "w", encoding="utf-8") as f:
                        json.dump(warns, f, indent=2, ensure_ascii=False)

                return True
            except (OSError, json.JSONDecodeError, json.JSONEncodeError):
                return False

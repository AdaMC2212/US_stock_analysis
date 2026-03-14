from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BotMessage:
    platform: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    content: Optional[str] = None

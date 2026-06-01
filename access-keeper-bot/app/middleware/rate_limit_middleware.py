"""Middleware for rate limiting to prevent DoS attacks."""

import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware to implement rate limiting per user."""

    def __init__(self):
        # Store last request time per user
        self.user_last_request: Dict[int, float] = defaultdict(float)
        # Store request count per user in current window
        self.user_request_count: Dict[int, int] = defaultdict(int)
        # Window start time per user
        self.user_window_start: Dict[int, float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Any],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """Check rate limits before processing."""
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        elif hasattr(event, 'from_user'):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        telegram_user_id = user.id
        current_time = time.time()
        rate_limit_seconds = settings.rate_limit_seconds

        # Initialize window if first request
        if self.user_window_start[telegram_user_id] == 0:
            self.user_window_start[telegram_user_id] = current_time
            self.user_request_count[telegram_user_id] = 0

        window_start = self.user_window_start[telegram_user_id]
        
        # Check if we're in a new window
        if current_time - window_start >= rate_limit_seconds:
            # Reset window
            self.user_window_start[telegram_user_id] = current_time
            self.user_request_count[telegram_user_id] = 0

        # Check rate limit
        if self.user_request_count[telegram_user_id] >= 10:  # Max 10 requests per window
            time_remaining = rate_limit_seconds - (current_time - window_start)
            logger.warning(
                f"Rate limit exceeded for user {telegram_user_id}. "
                f"Wait {time_remaining:.1f} seconds."
            )
            
            if isinstance(event, Message):
                await event.answer(
                    f"⚠️ Слишком много запросов.\n\n"
                    f"Пожалуйста, подождите {time_remaining:.1f} секунд перед следующим запросом."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Слишком много запросов. Подождите немного.",
                    show_alert=True
                )
            
            return None

        # Update counters
        self.user_last_request[telegram_user_id] = current_time
        self.user_request_count[telegram_user_id] += 1

        return await handler(event, data)

    def reset_user_limits(self, telegram_user_id: int):
        """Reset rate limits for a specific user."""
        self.user_last_request[telegram_user_id] = 0
        self.user_request_count[telegram_user_id] = 0
        self.user_window_start[telegram_user_id] = 0

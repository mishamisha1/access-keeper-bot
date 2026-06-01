"""Middleware for user authentication and authorization."""

import logging
from typing import Any, Callable, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update

from app.config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware to check if user is allowed to use the bot."""

    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Any],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """Check if user is authorized."""
        # Get user from update
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        elif hasattr(event, 'from_user'):
            user = event.from_user
        
        if not user:
            logger.warning("Received update without user information")
            return None
        
        telegram_user_id = user.id
        
        # Check if user is in allowed list
        if telegram_user_id not in settings.allowed_telegram_user_ids:
            logger.warning(
                f"Unauthorized access attempt from user ID: {telegram_user_id}"
            )
            
            # Send denial message if it's a message or callback
            if isinstance(event, Message):
                await event.answer(
                    "❌ Доступ запрещён.\n\n"
                    "Ваш Telegram ID не находится в списке разрешённых пользователей.\n"
                    "Обратитесь к администратору для получения доступа."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ Доступ запрещён.",
                    show_alert=True
                )
            
            return None
        
        # User is authorized, proceed with handler
        data['telegram_user'] = user
        return await handler(event, data)

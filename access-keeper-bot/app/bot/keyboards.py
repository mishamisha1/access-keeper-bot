"""Клавиатуры для Telegram бота."""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура бота."""
    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                KeyboardButton(text="📊 Создать матрицу"),
                KeyboardButton(text="➕ Добавить доступ"),
            ],
            [
                KeyboardButton(text="📁 Импорт из файла"),
                KeyboardButton(text="📑 Мои таблицы"),
            ],
            [
                KeyboardButton(text="⏰ Истекающие доступы"),
                KeyboardButton(text="⚠️ Просроченные"),
            ],
            [
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="❓ Помощь"),
            ],
        ],
    )
    return keyboard


def get_access_action_keyboard(
    spreadsheet_id: str, sheet_name: str, row_number: int
) -> InlineKeyboardMarkup:
    """Клавиатура действий с доступом."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Продлить",
                    callback_data=f"extend_{spreadsheet_id}_{sheet_name}_{row_number}",
                ),
                InlineKeyboardButton(
                    text="❌ Отозвать",
                    callback_data=f"revoke_{spreadsheet_id}_{sheet_name}_{row_number}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Открыть таблицу",
                    url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                ),
            ],
        ]
    )
    return keyboard


def get_confirm_keyboard(action: str, data: str = "") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, создать", callback_data=f"confirm_{action}_{data}"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_{action}_{data}"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_{action}_{data}"),
            ],
        ]
    )
    return keyboard


def get_yes_no_keyboard(callback_prefix: str, data: str = "") -> InlineKeyboardMarkup:
    """Клавиатура Да/Нет."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"{callback_prefix}_yes_{data}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"{callback_prefix}_no_{data}"),
            ],
        ]
    )
    return keyboard


def get_sheet_list_keyboard(sheets: list) -> InlineKeyboardMarkup:
    """Клавиатура со списком таблиц."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=sheet["title"],
                    callback_data=f"select_sheet_{sheet['spreadsheet_id']}",
                )
            ]
            for sheet in sheets
        ]
    )
    return keyboard


def get_template_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с шаблонами матриц."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Простая матрица",
                    callback_data="template_simple",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Расширенная матрица",
                    callback_data="template_extended",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 По ролям",
                    callback_data="template_role",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Ревью доступов",
                    callback_data="template_review",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 PCI DSS / ISO",
                    callback_data="template_pci",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Временные доступы",
                    callback_data="template_temporary",
                ),
            ],
        ]
    )
    return keyboard


def get_due_access_keyboard(
    spreadsheet_id: str, sheet_name: str, row_number: int
) -> InlineKeyboardMarkup:
    """Клавиатура для истекающих доступов."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏳ Продлить",
                    callback_data=f"extend_{spreadsheet_id}_{sheet_name}_{row_number}",
                ),
                InlineKeyboardButton(
                    text="🚫 Отозвать",
                    callback_data=f"revoke_{spreadsheet_id}_{sheet_name}_{row_number}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Таблица",
                    url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                ),
            ],
        ]
    )
    return keyboard


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отмены."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ],
        ]
    )
    return keyboard

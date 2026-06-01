"""
Клавиатуры для Telegram бота.
Соответствует требованиям ISO 27001 A.9.4 (управление доступом).
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    keyboard = [
        [
            KeyboardButton(text="📊 Создать матрицу"),
            KeyboardButton(text="➕ Добавить доступ"),
        ],
        [
            KeyboardButton(text="📁 Импорт из файла"),
            KeyboardButton(text="📋 Мои таблицы"),
        ],
        [
            KeyboardButton(text="⏰ Истекающие доступы"),
            KeyboardButton(text="⚠️ Просроченные"),
        ],
        [
            KeyboardButton(text="⚙️ Настройки"),
            KeyboardButton(text="❓ Помощь"),
        ],
    ]
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def get_access_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения создания доступа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, создать", callback_data="access_confirm"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data="access_edit"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="access_cancel"),
            ],
        ]
    )


def get_matrix_template_keyboard(templates: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура выбора шаблона матрицы."""
    buttons = [
        [InlineKeyboardButton(text=t["name"], callback_data=f"template_{t['key']}")]
        for t in templates
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_sheet_selection_keyboard(sheets: list[dict], action_prefix: str = "sheet") -> InlineKeyboardMarkup:
    """Клавиатура выбора вкладки таблицы."""
    buttons = [
        [InlineKeyboardButton(text=sheet["title"], callback_data=f"{action_prefix}_{sheet['sheet_id']}")]
        for sheet in sheets
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_saved_sheets_keyboard(saved_sheets: list[dict]) -> InlineKeyboardMarkup:
    """Клавиатура сохраненных таблиц."""
    buttons = [
        [
            InlineKeyboardButton(text=sheet["title"], callback_data=f"open_sheet_{sheet['id']}"),
        ]
        for sheet in saved_sheets
    ]
    
    if saved_sheets:
        buttons.append([
            InlineKeyboardButton(text="➕ Привязать новую таблицу", callback_data="bind_new_sheet"),
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_revoke_action_keyboard(record_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий при отзыве доступа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔴 Отозвать", callback_data=f"revoke_confirm_{record_id}"),
            ],
            [
                InlineKeyboardButton(text="📅 Продлить", callback_data=f"extend_access_{record_id}"),
                InlineKeyboardButton(text="📋 Открыть таблицу", callback_data="open_sheet"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
            ],
        ]
    )


def get_extend_options_keyboard(record_id: int) -> InlineKeyboardMarkup:
    """Клавиатура вариантов продления."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+1 неделя", callback_data=f"extend_7d_{record_id}"),
                InlineKeyboardButton(text="+2 недели", callback_data=f"extend_14d_{record_id}"),
            ],
            [
                InlineKeyboardButton(text="+1 месяц", callback_data=f"extend_30d_{record_id}"),
            ],
            [
                InlineKeyboardButton(text="📅 Выбрать дату", callback_data=f"extend_custom_{record_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
            ],
        ]
    )


def get_due_access_keyboard(days: int = 7) -> InlineKeyboardMarkup:
    """Клавиатура для истекающих доступов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Продлить", callback_data="bulk_extend"),
                InlineKeyboardButton(text="🔴 Отозвать", callback_data="bulk_revoke"),
            ],
            [
                InlineKeyboardButton(text="📋 Открыть таблицу", callback_data="open_sheet"),
            ],
        ]
    )


def get_overdue_access_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для просроченных доступов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔴 Срочно отозвать", callback_data="urgent_revoke"),
            ],
            [
                InlineKeyboardButton(text="📅 Продлить", callback_data="bulk_extend"),
                InlineKeyboardButton(text="📋 Открыть таблицу", callback_data="open_sheet"),
            ],
        ]
    )


def get_import_preview_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура предпросмотра импорта."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Импорт", callback_data="import_confirm"),
                InlineKeyboardButton(text="✏️ Изменить маппинг", callback_data="import_edit_mapping"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="import_cancel"),
            ],
        ]
    )


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура настроек."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🕐 Время событий", callback_data="settings_event_time"),
                InlineKeyboardButton(text="🔔 Напоминания", callback_data="settings_reminders"),
            ],
            [
                InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="settings_timezone"),
            ],
            [
                InlineKeyboardButton(text="📊 Таблица по умолчанию", callback_data="settings_default_sheet"),
            ],
            [
                InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data="settings_reset"),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"),
            ],
        ]
    )


def get_calendar_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура настроек календаря."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏰ Время напоминаний", callback_data="cal_reminder_time"),
                InlineKeyboardButton(text="📅 Дни напоминаний", callback_data="cal_reminder_days"),
            ],
            [
                InlineKeyboardButton(text="🗓️ Календарь", callback_data="cal_select"),
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="settings"),
            ],
        ]
    )


def get_yes_no_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """Универсальная клавиатура Да/Нет."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=yes_callback),
                InlineKeyboardButton(text="❌ Нет", callback_data=no_callback),
            ],
        ]
    )


def get_back_keyboard(back_callback: str = "main_menu") -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой Назад."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback),
            ],
        ]
    )


def get_templates_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора шаблона для создания матрицы."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ Простая матрица", callback_data="template_simple"),
            ],
            [
                InlineKeyboardButton(text="2️⃣ Расширенная матрица", callback_data="template_extended"),
            ],
            [
                InlineKeyboardButton(text="3️⃣ По ролям", callback_data="template_role"),
            ],
            [
                InlineKeyboardButton(text="4️⃣ Ревью доступов", callback_data="template_review"),
            ],
            [
                InlineKeyboardButton(text="5️⃣ PCI DSS / ISO", callback_data="template_pci_iso"),
            ],
            [
                InlineKeyboardButton(text="6️⃣ Временные доступы", callback_data="template_temporary"),
            ],
        ]
    )


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Создать матрицу")],
            [KeyboardButton(text="➕ Добавить доступ")],
            [KeyboardButton(text="📁 Импорт из файла")],
            [KeyboardButton(text="📋 Мои таблицы")],
            [KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, создать", callback_data="confirm_create"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
            ],
        ]
    )


def get_import_preview_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура предпросмотра импорта."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Импорт", callback_data="confirm_import"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
            ],
        ]
    )


def get_revoke_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отзыва доступа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔴 Отозвать", callback_data="confirm_revoke"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
            ],
        ]
    )


def get_extend_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура продления доступа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Продлить", callback_data="confirm_extend"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
            ],
        ]
    )


def get_access_due_keyboard(sheet_url: str) -> InlineKeyboardMarkup:
    """Клавиатура для истекающих доступов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Открыть таблицу", url=sheet_url),
            ],
        ]
    )


def get_sheet_selection_keyboard(sheets: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора вкладки таблицы."""
    buttons = [
        [InlineKeyboardButton(text=sheet["title"], callback_data=f"sheet_{sheet['id']}")]
        for sheet in sheets
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

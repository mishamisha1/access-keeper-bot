"""
FSM состояния для бота.
Определяет состояния для диалогов с пользователем.
"""

from aiogram.fsm.state import State, StatesGroup


class AccessStates(StatesGroup):
    """Состояния для добавления доступа."""
    
    waiting_for_full_name = State()  # Ожидание ФИО
    waiting_for_system = State()  # Ожидание системы
    waiting_for_role = State()  # Ожидание роли
    waiting_for_duration = State()  # Ожидание срока доступа
    waiting_for_reason = State()  # Ожидание основания
    waiting_for_confirmation = State()  # Ожидание подтверждения
    waiting_for_comment = State()  # Ожидание комментария
    
    # Quick access flow
    confirming_creation = State()  # Подтверждение создания из /access
    
    # Revoke flow
    searching_for_revoke = State()  # Поиск для отзыва
    confirming_revoke = State()  # Подтверждение отзыва
    
    # Extend flow
    searching_for_extend = State()  # Поиск для продления
    entering_extend_duration = State()  # Ввод срока продления
    confirming_extend = State()  # Подтверждение продления
    
    # Settings
    setting_reminder_days = State()  # Настройка напоминаний


class MatrixStates(StatesGroup):
    """Состояния для создания матрицы."""
    
    choosing_template = State()  # Выбор шаблона
    entering_title = State()  # Ввод названия таблицы
    confirming_creation = State()  # Подтверждение создания


class ImportStates(StatesGroup):
    """Состояния для импорта файлов."""
    
    waiting_for_file = State()  # Ожидание файла
    selecting_sheet = State()  # Выбор вкладки
    confirming_mapping = State()  # Подтверждение маппинга
    reviewing_preview = State()  # Просмотр данных перед записью


class RevokeStates(StatesGroup):
    """Состояния для отзыва доступа."""
    
    searching_access = State()  # Поиск доступа
    confirming_revoke = State()  # Подтверждение отзыва
    entering_revoke_comment = State()  # Комментарий к отзыву


class ExtendStates(StatesGroup):
    """Состояния для продления доступа."""
    
    searching_access = State()  # Поиск доступа
    entering_new_duration = State()  # Новый срок
    confirming_extend = State()  # Подтверждение продления


class BindSheetStates(StatesGroup):
    """Состояния для привязки таблицы."""
    
    waiting_for_link = State()  # Ожидание ссылки
    selecting_default_sheet = State()  # Выбор вкладки по умолчанию


class SettingsStates(StatesGroup):
    """Состояния для настроек."""
    
    editing_timezone = State()  # Редактирование timezone
    editing_event_time = State()  # Редактирование времени события
    editing_reminders = State()  # Редактирование напоминаний

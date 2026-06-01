"""FSM состояния для бота."""

from aiogram.fsm.state import State, StatesGroup


class AccessStates(StatesGroup):
    """Состояния для добавления доступа."""
    waiting_for_full_name = State()
    waiting_for_system = State()
    waiting_for_role = State()
    waiting_for_duration = State()
    waiting_for_reason = State()
    waiting_for_ticket = State()
    waiting_for_confirmation = State()
    waiting_for_edit = State()


class MatrixStates(StatesGroup):
    """Состояния для создания матрицы."""
    waiting_for_template = State()
    waiting_for_matrix_name = State()
    waiting_for_sheet_name = State()


class ImportStates(StatesGroup):
    """Состояния для импорта файла."""
    waiting_for_file = State()
    waiting_for_sheet_selection = State()
    waiting_for_mapping = State()
    waiting_for_import_confirm = State()


class RevokeStates(StatesGroup):
    """Состояния для отзыва доступа."""
    waiting_for_search_query = State()
    waiting_for_revoke_confirm = State()
    waiting_for_revoke_comment = State()


class ExtendStates(StatesGroup):
    """Состояния для продления доступа."""
    waiting_for_extend_query = State()
    waiting_for_new_date = State()
    waiting_for_extend_confirm = State()


class BindSheetStates(StatesGroup):
    """Состояния для привязки таблицы."""
    waiting_for_sheet_link = State()
    waiting_for_sheet_name = State()

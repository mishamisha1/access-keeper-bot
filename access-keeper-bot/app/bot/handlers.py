"""Telegram bot handlers for Access Keeper."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Document,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Message,
)

from app.bot.keyboards import (
    get_access_due_keyboard,
    get_confirmation_keyboard,
    get_extend_keyboard,
    get_import_preview_keyboard,
    get_main_keyboard,
    get_revoke_keyboard,
    get_sheet_selection_keyboard,
    get_templates_keyboard,
)
from app.bot.states import AccessStates, ImportStates, MatrixStates
from app.config import settings
from app.db.database import Database
from app.google.auth import get_authorized_user
from app.google.calendar import CalendarService
from app.google.sheets import SheetsService
from app.parsers.file_parser import parse_file
from app.parsers.mapper import ColumnMapper
from app.parsers.text_parser import TextParser
from app.security.audit_logger import AuditLogger
from app.security.privileged_access import PrivilegedAccessChecker
from app.services.access_service import AccessService
from app.services.date_service import DateService
from app.services.normalization import NormalizationService
from app.templates.matrix_templates import get_template_columns

logger = logging.getLogger(__name__)

router = Router()
db = Database(settings.DB_PATH)
text_parser = TextParser()
date_service = DateService()
normalizer = NormalizationService()
column_mapper = ColumnMapper()
privileged_checker = PrivilegedAccessChecker()
audit_logger = AuditLogger(db)


# ==================== START & HELP ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён. Вы не авторизованы для использования этого бота.")
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        return
    
    # Register user in DB
    db.add_user(user_id, message.from_user.username or str(user_id))
    
    welcome_text = (
        "👋 **Добро пожаловать в Access Keeper Bot!**\n\n"
        "Я помогу вам управлять матрицами доступов, выдавать временные права "
        "и автоматически создавать напоминания в Google Calendar.\n\n"
        "**Возможности:**\n"
        "• Создание матриц доступа в Google Sheets\n"
        "• Быстрое добавление временных доступов из текста\n"
        "• Импорт данных из Excel, CSV, DOCX, PDF\n"
        "• Автоматические напоминания об отзыве доступов\n"
        "• Ревью и продление доступов\n"
        "• Аудит всех изменений\n\n"
        "**Начните с команд:**\n"
        "/new_matrix — Создать новую матрицу\n"
        "/access — Быстро добавить доступ из текста\n"
        "/import_file — Импортировать данные из файла\n"
        "/my_sheets — Мои сохранённые таблицы\n"
        "/help — Справка по всем командам"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    help_text = (
        "📚 **Справка по командам бота**\n\n"
        "**Основные команды:**\n"
        "/start — Запуск бота\n"
        "/help — Эта справка\n\n"
        "**Управление матрицами:**\n"
        "/new_matrix — Создать новую Google Sheets таблицу\n"
        "/bind_sheet — Привязать существующую таблицу\n"
        "/my_sheets — Показать сохранённые таблицы\n"
        "/templates — Показать шаблоны матриц\n\n"
        "**Добавление доступов:**\n"
        "/access <текст> — Быстро добавить доступ из текста\n"
        "Пример: `/access Иванов Иван, доступ на 2 недели, основание: проект X`\n\n"
        "/grant_access — Пошаговое добавление доступа\n"
        "/import_file — Импорт из Excel/CSV/DOCX/PDF\n\n"
        "**Управление доступами:**\n"
        "/revoke_access — Отозвать доступ\n"
        "/extend_access — Продлить доступ\n"
        "/access_due — Истекающие доступы (7 дней)\n"
        "/access_overdue — Просроченные доступы\n\n"
        "**Настройки:**\n"
        "/settings — Настройки бота\n"
        "/calendar_settings — Настройки календаря"
    )
    
    await message.answer(help_text, parse_mode="Markdown")


# ==================== MATRIX CREATION ====================

@router.message(Command("new_matrix"))
async def cmd_new_matrix(message: Message, state: FSMContext):
    """Handle /new_matrix command."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    await state.set_state(MatrixStates.selecting_template)
    
    await message.answer(
        "📊 **Выберите шаблон матрицы доступа:**\n\n"
        "1️⃣ Простая матрица — базовые поля\n"
        "2️⃣ Расширенная матрица — все поля + ревью\n"
        "3️⃣ Матрица по ролям — роли vs модули\n"
        "4️⃣ Ревью доступов — для аудита\n"
        "5️⃣ PCI DSS / ISO — соответствие стандартам\n"
        "6️⃣ Временные доступы — с календарём",
        reply_markup=get_templates_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("template_"))
async def callback_template_selected(callback: CallbackQuery, state: FSMContext):
    """Handle template selection."""
    template_id = callback.data.replace("template_", "")
    
    template_map = {
        "simple": "Простая матрица доступа",
        "extended": "Расширенная матрица доступа",
        "role": "Матрица по ролям",
        "review": "Ревью доступов",
        "pci_iso": "PCI DSS / ISO access review",
        "temporary": "Временные доступы"
    }
    
    template_name = template_map.get(template_id, "Неизвестный шаблон")
    
    await state.update_data(template_id=template_id)
    await state.set_state(MatrixStates.entering_title)
    
    await callback.message.edit_text(
        f"✅ Выбран шаблон: **{template_name}**\n\n"
        "Введите название для новой таблицы (например: 'Матрица доступов Q2 2026'):",
        parse_mode="Markdown"
    )


@router.message(MatrixStates.entering_title)
async def handle_matrix_title(message: Message, state: FSMContext):
    """Handle matrix title entry."""
    title = message.text.strip()
    data = await state.get_data()
    template_id = data.get("template_id")
    
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не выбран. Начните заново /new_matrix")
        return
    
    await message.answer("⏳ Создаю таблицу в Google Sheets...")
    
    try:
        # Get authorized Google user
        creds = get_authorized_user()
        if not creds:
            await message.answer(
                "❌ Ошибка авторизации Google.\n"
                "Запустите: `python -m app.google_auth_setup`"
            )
            return
        
        sheets_service = SheetsService(creds)
        
        # Get template columns
        columns = get_template_columns(template_id)
        
        # Create spreadsheet
        spreadsheet_id, spreadsheet_url = sheets_service.create_spreadsheet(
            title=title,
            columns=columns,
            template_id=template_id
        )
        
        # Save to DB
        db.add_saved_sheet(
            telegram_user_id=message.from_user.id,
            spreadsheet_id=spreadsheet_id,
            spreadsheet_url=spreadsheet_url,
            title=title,
            default_sheet_name="Доступы"
        )
        
        # Log audit
        audit_logger.log_action(
            action="CREATED_MATRIX",
            telegram_user_id=message.from_user.id,
            telegram_username=message.from_user.username,
            spreadsheet_id=spreadsheet_id,
            details={"template": template_id, "title": title}
        )
        
        await message.answer(
            f"✅ **Таблица создана!**\n\n"
            f"📊 Название: {title}\n"
            f"🔗 Ссылка: {spreadsheet_url}\n\n"
            "Таблица содержит:\n"
            "• Вкладку с колонками шаблона\n"
            "• Вкладку 'История изменений'\n"
            "• Вкладку 'README' с инструкцией\n\n"
            "Теперь вы можете добавлять доступы через /access или /import_file",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Failed to create matrix: {e}")
        await message.answer(f"❌ Ошибка создания таблицы: {str(e)}")


# ==================== QUICK ACCESS COMMAND ====================

@router.message(Command("access"))
async def cmd_access(message: Message, state: FSMContext):
    """Handle /access command with text parsing."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    # Extract text after /access
    text = message.text.replace("/access", "", 1).strip()
    
    if not text:
        await message.answer(
            "❌ Укажите данные доступа после команды.\n\n"
            "**Пример:**\n"
            "`/access Саксонов Михаил, доступ на 2 недели, основание: совместная работа`"
        )
        return
    
    await message.answer("⏳ Анализирую запрос...")
    
    try:
        # Parse text
        parsed = text_parser.parse(text)
        
        if not parsed.get("full_name"):
            await message.answer(
                "❌ Не удалось распознать ФИО пользователя.\n"
                "Пожалуйста, укажите фамилию и имя явно."
            )
            return
        
        # Calculate dates
        granted_at = datetime.now()
        valid_until = date_service.calculate_end_date(
            parsed.get("duration", "1 день"),
            granted_at
        )
        
        # Build preview
        preview_text = (
            "📋 **Предварительный просмотр:**\n\n"
            f"👤 **Пользователь:** {parsed.get('full_name', 'Не указано')}\n"
            f"🔐 **Логин:** {parsed.get('login', 'Не указано')}\n"
            f"📧 **Email:** {parsed.get('email', 'Не указано')}\n"
            f"💻 **Система:** {parsed.get('system', 'Не указано')}\n"
            f"🎭 **Роль:** {parsed.get('role', 'Не указано')}\n"
            f"📊 **Уровень доступа:** {parsed.get('access_level', 'Не указано')}\n"
            f"⏱️ **Срок доступа:** {parsed.get('duration', 'Не указано')}\n"
            f"📅 **Дата выдачи:** {granted_at.strftime('%Y-%m-%d')}\n"
            f"📅 **Дата окончания:** {valid_until.strftime('%Y-%m-%d %H:%M')}\n"
            f"📝 **Основание:** {parsed.get('justification', 'Не указано')}\n"
            f"🎫 **Заявка:** {parsed.get('ticket_number', 'Не указано')}\n"
            f"✅ **Действие:** Забрать доступ\n"
        )
        
        # Check privileged access
        if normalizer.is_privileged_role(parsed.get("role", "")):
            preview_text += "\n⚠️ **ВНИМАНИЕ:** Обнаружен привилегированный доступ!\n"
        
        preview_text += "\nСоздать запись в Google Sheets и событие в Calendar?"
        
        await state.update_data(
            parsed_data=parsed,
            granted_at=granted_at.isoformat(),
            valid_until=valid_until.isoformat()
        )
        await state.set_state(AccessStates.confirming_creation)
        
        await message.answer(
            preview_text,
            reply_markup=get_confirmation_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Failed to parse access request: {e}")
        await message.answer(f"❌ Ошибка обработки запроса: {str(e)}")


@router.callback_query(F.data == "confirm_create")
async def callback_confirm_create(callback: CallbackQuery, state: FSMContext):
    """Confirm access creation."""
    data = await state.get_data()
    parsed = data.get("parsed_data", {})
    granted_at_str = data.get("granted_at")
    valid_until_str = data.get("valid_until")
    
    granted_at = datetime.fromisoformat(granted_at_str) if granted_at_str else datetime.now()
    valid_until = datetime.fromisoformat(valid_until_str) if valid_until_str else datetime.now() + timedelta(days=14)
    
    await callback.message.edit_text("⏳ Создаю запись...")
    
    try:
        # Get default sheet
        default_sheet = db.get_default_sheet(callback.from_user.id)
        
        if not default_sheet:
            await callback.message.answer(
                "❌ Таблица по умолчанию не настроена.\n"
                "Используйте /new_matrix для создания или /bind_sheet для привязки."
            )
            return
        
        # Get Google credentials
        creds = get_authorized_user()
        if not creds:
            await callback.message.answer("❌ Ошибка авторизации Google.")
            return
        
        sheets_service = SheetsService(creds)
        calendar_service = CalendarService(creds)
        
        # Prepare record
        record = {
            "full_name": parsed.get("full_name", ""),
            "login": parsed.get("login", ""),
            "email": parsed.get("email", ""),
            "system": parsed.get("system", "Не указано"),
            "role": parsed.get("role", "Не указано"),
            "access_level": parsed.get("access_level", "Не указано"),
            "justification": parsed.get("justification", "Не указано"),
            "ticket_number": parsed.get("ticket_number", ""),
            "granted_at": granted_at.strftime("%Y-%m-%d"),
            "valid_until": valid_until.strftime("%Y-%m-%d %H:%M"),
            "status": "Временный",
            "added_by": callback.from_user.username or str(callback.from_user.id),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        # Normalize
        normalized = normalizer.normalize_record(record, granted_at)
        
        # Add to sheet
        row_num = sheets_service.append_row(
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            values=normalized
        )
        
        # Create calendar event
        event_summary = f"[Access Review] Забрать доступ: {normalized['full_name']}"
        if normalized.get("system") and normalized.get("role"):
            event_summary += f" — {normalized['system']} — {normalized['role']}"
        
        event_description = (
            f"Пользователь: {normalized['full_name']}\n"
            f"Логин: {normalized.get('login', 'Не указано')}\n"
            f"Система: {normalized.get('system', 'Не указано')}\n"
            f"Роль: {normalized.get('role', 'Не указано')}\n"
            f"Основание: {normalized.get('justification', 'Не указано')}\n"
            f"Дата выдачи: {normalized['granted_at']}\n"
            f"Дата окончания: {normalized['valid_until']}\n"
            f"Действие: Забрать доступ\n"
            f"Таблица: {default_sheet['spreadsheet_url']}"
        )
        
        event_id, event_link = calendar_service.create_event(
            summary=event_summary,
            description=event_description,
            start_datetime=valid_until,
            timezone=settings.TIMEZONE,
            reminders=[1440, 0]  # 1 day and 0 minutes before
        )
        
        # Update sheet with event ID
        if event_id:
            sheets_service.update_cell(
                spreadsheet_id=default_sheet["spreadsheet_id"],
                sheet_name=default_sheet["default_sheet_name"],
                row=row_num,
                col="Calendar Event ID",
                value=event_id
            )
        
        # Log audit
        audit_logger.log_action(
            action="CREATED_ACCESS",
            telegram_user_id=callback.from_user.id,
            telegram_username=callback.from_user.username,
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            row_number=row_num,
            calendar_event_id=event_id,
            full_name=normalized["full_name"],
            system=normalized.get("system", ""),
            role=normalized.get("role", ""),
            valid_until=normalized["valid_until"],
            status="Временный"
        )
        
        await callback.message.answer(
            f"✅ **Доступ создан!**\n\n"
            f"📊 Запись добавлена в строку {row_num}\n"
            f"🔗 Таблица: {default_sheet['spreadsheet_url']}\n"
            f"📅 Событие календаря создано\n"
            f"⏰ Напоминание: за 1 день и в момент события",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Failed to create access: {e}")
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "cancel_action")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel current action."""
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")


# ==================== FILE IMPORT ====================

@router.message(Command("import_file"))
async def cmd_import_file(message: Message, state: FSMContext):
    """Handle /import_file command."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    await state.set_state(ImportStates.waiting_for_file)
    
    await message.answer(
        "📎 **Отправьте файл для импорта**\n\n"
        "Поддерживаемые форматы:\n"
        "• Excel (.xlsx, .xls)\n"
        "• CSV (.csv)\n"
        "• Текст (.txt)\n"
        "• Word (.docx)\n"
        "• PDF (.pdf)\n\n"
        "Или отправьте /cancel для отмены.",
        parse_mode="Markdown"
    )


@router.message(ImportStates.waiting_for_file, F.document)
async def handle_file_import(message: Message, state: FSMContext):
    """Handle uploaded file."""
    document: Document = message.document
    
    # Check file size (max 10MB)
    if document.file_size > 10 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой (макс. 10MB)")
        return
    
    await message.answer("⏳ Скачиваю и анализирую файл...")
    
    try:
        # Download file
        file = await message.bot.get_file(document.file_id)
        file_path = Path(f"/tmp/import_{document.file_unique_id}_{document.file_name}")
        await message.bot.download_file(file.file_path, file_path)
        
        # Parse file
        result = parse_file(file_path)
        
        if result.row_count == 0:
            await message.answer("❌ Файл пуст или не содержит данных.")
            file_path.unlink(missing_ok=True)
            return
        
        # Map columns
        mapping = column_mapper.map_columns(result.headers)
        
        # Build preview
        preview = (
            f"📊 **Анализ файла:**\n\n"
            f"📁 Тип: {result.file_type}\n"
            f"📈 Строк: {result.row_count}\n"
            f"📝 Колонок: {len(result.headers)}\n\n"
            f"**Распознанные колонки:**\n"
        )
        
        unmapped = []
        for orig, mapped in mapping.items():
            preview += f"• {orig} → {mapped}\n"
        
        for header in result.headers:
            if header not in mapping:
                unmapped.append(header)
        
        if unmapped:
            preview += f"\n⚠️ **Не распознаны:** {', '.join(unmapped[:5])}"
            if len(unmapped) > 5:
                preview += f" и ещё {len(unmapped) - 5}"
        
        await state.update_data(
            file_path=str(file_path),
            headers=result.headers,
            rows=result.rows,
            mapping=mapping,
            row_count=result.row_count
        )
        await state.set_state(ImportStates.confirming_import)
        
        await message.answer(
            preview + "\n\nПродолжить импорт?",
            reply_markup=get_import_preview_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Failed to import file: {e}")
        await message.answer(f"❌ Ошибка импорта: {str(e)}")


@router.callback_query(F.data == "confirm_import")
async def callback_confirm_import(callback: CallbackQuery, state: FSMContext):
    """Confirm file import."""
    data = await state.get_data()
    file_path = data.get("file_path")
    rows = data.get("rows", [])
    mapping = data.get("mapping", {})
    
    await callback.message.edit_text("⏳ Импортирую данные...")
    
    try:
        # Get default sheet
        default_sheet = db.get_default_sheet(callback.from_user.id)
        
        if not default_sheet:
            await callback.message.answer(
                "❌ Таблица по умолчанию не настроена.\n"
                "Используйте /new_matrix или /bind_sheet."
            )
            return
        
        # Get Google credentials
        creds = get_authorized_user()
        if not creds:
            await callback.message.answer("❌ Ошибка авторизации Google.")
            return
        
        sheets_service = SheetsService(creds)
        
        # Transform rows according to mapping
        transformed_rows = []
        for row in rows:
            transformed = {}
            for orig_col, std_field in mapping.items():
                if orig_col in row:
                    transformed[std_field] = row[orig_col]
            
            # Normalize
            normalized = normalizer.normalize_record(transformed)
            transformed_rows.append(normalized)
        
        # Batch add to sheet
        added_count = sheets_service.append_rows(
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            rows=transformed_rows
        )
        
        # Log audit
        audit_logger.log_action(
            action="IMPORTED_FILE",
            telegram_user_id=callback.from_user.id,
            telegram_username=callback.from_user.username,
            spreadsheet_id=default_sheet["spreadsheet_id"],
            details={"rows_imported": added_count, "file": file_path}
        )
        
        await callback.message.answer(
            f"✅ **Импорт завершён!**\n\n"
            f"📊 Добавлено строк: {added_count}\n"
            f"🔗 Таблица: {default_sheet['spreadsheet_url']}",
            parse_mode="Markdown"
        )
        
        # Cleanup
        Path(file_path).unlink(missing_ok=True)
        await state.clear()
        
    except Exception as e:
        logger.error(f"Failed to confirm import: {e}")
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


# ==================== MY SHEETS ====================

@router.message(Command("my_sheets"))
async def cmd_my_sheets(message: Message):
    """Show saved sheets."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    sheets = db.get_saved_sheets(user_id)
    
    if not sheets:
        await message.answer(
            "📭 У вас пока нет сохранённых таблиц.\n\n"
            "Используйте /new_matrix для создания или /bind_sheet для привязки."
        )
        return
    
    text = "📊 **Ваши таблицы:**\n\n"
    
    for i, sheet in enumerate(sheets, 1):
        is_default = "📌 " if sheet.get("is_default") else ""
        text += f"{is_default}{i}. **{sheet['title']}**\n"
        text += f"   🔗 {sheet['spreadsheet_url']}\n"
        text += f"   📑 Вкладка: {sheet['default_sheet_name']}\n\n"
    
    await message.answer(text, parse_mode="Markdown")


# ==================== ACCESS DUE/OVERDUE ====================

@router.message(Command("access_due"))
async def cmd_access_due(message: Message):
    """Show soon expiring accesses."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    default_sheet = db.get_default_sheet(user_id)
    
    if not default_sheet:
        await message.answer("❌ Таблица по умолчанию не настроена.")
        return
    
    await message.answer("⏳ Проверяю истекающие доступы...")
    
    try:
        creds = get_authorized_user()
        if not creds:
            await message.answer("❌ Ошибка авторизации Google.")
            return
        
        sheets_service = SheetsService(creds)
        
        # Get rows expiring in next 7 days
        due_date = datetime.now() + timedelta(days=7)
        
        rows = sheets_service.get_expiring_accesses(
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            until_date=due_date
        )
        
        if not rows:
            await message.answer("✅ Нет доступов, истекающих в ближайшие 7 дней.")
            return
        
        text = f"⏰ **Доступы, истекающие до {due_date.strftime('%d.%m.%Y')}:**\n\n"
        
        for row in rows[:10]:  # Show max 10
            text += f"• {row.get('full_name', 'N/A')} — {row.get('system', 'N/A')}\n"
            text += f"  Срок: {row.get('valid_until', 'N/A')}\n"
            text += f"  Строка: {row.get('row_number', 'N/A')}\n\n"
        
        if len(rows) > 10:
            text += f"... и ещё {len(rows) - 10}\n"
        
        await message.answer(
            text,
            reply_markup=get_access_due_keyboard(default_sheet["spreadsheet_url"]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Failed to check due accesses: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(Command("access_overdue"))
async def cmd_access_overdue(message: Message):
    """Show overdue accesses."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    default_sheet = db.get_default_sheet(user_id)
    
    if not default_sheet:
        await message.answer("❌ Таблица по умолчанию не настроена.")
        return
    
    await message.answer("⏳ Проверяю просроченные доступы...")
    
    try:
        creds = get_authorized_user()
        if not creds:
            await message.answer("❌ Ошибка авторизации Google.")
            return
        
        sheets_service = SheetsService(creds)
        
        rows = sheets_service.get_overdue_accesses(
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"]
        )
        
        if not rows:
            await message.answer("✅ Нет просроченных доступов.")
            return
        
        text = "🚨 **Просроченные доступы:**\n\n"
        
        for row in rows[:10]:
            text += f"• {row.get('full_name', 'N/A')} — {row.get('system', 'N/A')}\n"
            text += f"  Истёк: {row.get('valid_until', 'N/A')}\n"
            text += f"  Строка: {row.get('row_number', 'N/A')}\n\n"
        
        if len(rows) > 10:
            text += f"... и ещё {len(rows) - 10}\n"
        
        await message.answer(
            text,
            reply_markup=get_access_due_keyboard(default_sheet["spreadsheet_url"]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Failed to check overdue accesses: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


# ==================== REVOKE ACCESS ====================

@router.message(Command("revoke_access"))
async def cmd_revoke_access(message: Message, state: FSMContext):
    """Start access revocation process."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    await state.set_state(AccessStates.searching_for_revoke)
    
    await message.answer(
        "🔍 **Поиск доступа для отзыва**\n\n"
        "Введите:\n"
        "• ФИО пользователя\n"
        "• Логин\n"
        "• Систему\n"
        "• Номер заявки\n"
        "• Или номер строки\n\n"
        "/cancel — отмена"
    )


@router.message(AccessStates.searching_for_revoke)
async def handle_revoke_search(message: Message, state: FSMContext):
    """Search for access to revoke."""
    search_query = message.text.strip()
    
    await message.answer(f"⏳ Поиск по запросу: {search_query}...")
    
    try:
        default_sheet = db.get_default_sheet(message.from_user.id)
        
        if not default_sheet:
            await message.answer("❌ Таблица по умолчанию не настроена.")
            return
        
        creds = get_authorized_user()
        if not creds:
            await message.answer("❌ Ошибка авторизации Google.")
            return
        
        sheets_service = SheetsService(creds)
        
        # Search
        results = sheets_service.search_accesses(
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            query=search_query
        )
        
        if not results:
            await message.answer("❌ Ничего не найдено.")
            return
        
        if len(results) > 1:
            # Multiple results - show list
            text = f"Найдено {len(results)} записей:\n\n"
            for i, row in enumerate(results[:5], 1):
                text += f"{i}. {row.get('full_name', 'N/A')} — {row.get('system', 'N/A')}\n"
            
            if len(results) > 5:
                text += f"... и ещё {len(results) - 5}"
            
            await message.answer(text)
            return
        
        # Single result - show preview
        row = results[0]
        
        preview = (
            f"📋 **Найдена запись:**\n\n"
            f"👤 Пользователь: {row.get('full_name', 'N/A')}\n"
            f"🔐 Логин: {row.get('login', 'N/A')}\n"
            f"💻 Система: {row.get('system', 'N/A')}\n"
            f"🎭 Роль: {row.get('role', 'N/A')}\n"
            f"📅 До: {row.get('valid_until', 'N/A')}\n"
            f"📊 Статус: {row.get('status', 'N/A')}\n"
            f"📑 Строка: {row.get('row_number', 'N/A')}\n\n"
            "Отозвать этот доступ?"
        )
        
        await state.update_data(revoke_row=row)
        await state.set_state(AccessStates.confirming_revoke)
        
        await message.answer(
            preview,
            reply_markup=get_revoke_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Failed to search for revoke: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "confirm_revoke")
async def callback_confirm_revoke(callback: CallbackQuery, state: FSMContext):
    """Confirm access revocation."""
    data = await state.get_data()
    row = data.get("revoke_row", {})
    
    await callback.message.edit_text("⏳ Отзываю доступ...")
    
    try:
        default_sheet = db.get_default_sheet(callback.from_user.id)
        creds = get_authorized_user()
        
        if not creds or not default_sheet:
            await callback.message.answer("❌ Ошибка конфигурации.")
            return
        
        sheets_service = SheetsService(creds)
        calendar_service = CalendarService(creds)
        
        row_num = row.get("row_number")
        
        # Update status
        sheets_service.update_cell(
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            row=row_num,
            col="Статус доступа",
            value="Отозван"
        )
        
        # Update calendar event if exists
        event_id = row.get("calendar_event_id")
        if event_id:
            calendar_service.update_event_title(
                event_id=event_id,
                new_title=f"[DONE] Доступ отозван: {row.get('full_name', 'N/A')}"
            )
        
        # Log audit
        audit_logger.log_action(
            action="REVOKED_ACCESS",
            telegram_user_id=callback.from_user.id,
            telegram_username=callback.from_user.username,
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            row_number=row_num,
            full_name=row.get("full_name", ""),
            system=row.get("system", ""),
            old_status=row.get("status", ""),
            new_status="Отозван"
        )
        
        await callback.message.answer(
            f"✅ Доступ отозван!\n\n"
            f"Пользователь: {row.get('full_name', 'N/A')}\n"
            f"Система: {row.get('system', 'N/A')}\n"
            f"Статус изменён на: **Отозван**",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Failed to revoke access: {e}")
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


# ==================== EXTEND ACCESS ====================

@router.message(Command("extend_access"))
async def cmd_extend_access(message: Message, state: FSMContext):
    """Start access extension process."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    await state.set_state(AccessStates.searching_for_extend)
    
    await message.answer(
        "🔍 **Поиск доступа для продления**\n\n"
        "Введите ФИО, логин или номер строки:\n\n"
        "/cancel — отмена"
    )


@router.message(AccessStates.searching_for_extend)
async def handle_extend_search(message: Message, state: FSMContext):
    """Search for access to extend."""
    search_query = message.text.strip()
    
    await message.answer(f"⏳ Поиск: {search_query}...")
    
    try:
        default_sheet = db.get_default_sheet(message.from_user.id)
        
        if not default_sheet:
            await message.answer("❌ Таблица не настроена.")
            return
        
        creds = get_authorized_user()
        if not creds:
            await message.answer("❌ Ошибка авторизации Google.")
            return
        
        sheets_service = SheetsService(creds)
        
        results = sheets_service.search_accesses(
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            query=search_query
        )
        
        if not results:
            await message.answer("❌ Ничего не найдено.")
            return
        
        row = results[0]
        
        preview = (
            f"📋 **Найдена запись:**\n\n"
            f"👤 {row.get('full_name', 'N/A')} — {row.get('system', 'N/A')}\n"
            f"📅 Текущий срок: {row.get('valid_until', 'N/A')}\n"
            f"📑 Строка: {row.get('row_number', 'N/A')}\n\n"
            "На сколько продлить?\n"
            "Примеры: 'на неделю', 'на 2 недели', 'до 15.07.2026'"
        )
        
        await state.update_data(extend_row=row)
        await state.set_state(AccessStates.entering_extend_duration)
        
        await message.answer(preview, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Failed to search for extend: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(AccessStates.entering_extend_duration)
async def handle_extend_duration(message: Message, state: FSMContext):
    """Handle extension duration input."""
    duration_text = message.text.strip()
    data = await state.get_data()
    row = data.get("extend_row", {})
    
    try:
        current_until = row.get("valid_until", "")
        
        # Parse current date
        try:
            current_date = datetime.strptime(current_until.split()[0], "%Y-%m-%d")
        except:
            current_date = datetime.now()
        
        # Calculate new date
        new_date = date_service.calculate_end_date(duration_text, current_date)
        
        preview = (
            f"📅 **Продление доступа**\n\n"
            f"👤 {row.get('full_name', 'N/A')}\n"
            f"📅 Было: {current_until}\n"
            f"📅 Станет: {new_date.strftime('%Y-%m-%d %H:%M')}\n\n"
            "Продлить?"
        )
        
        await state.update_data(new_valid_until=new_date.isoformat())
        await state.set_state(AccessStates.confirming_extend)
        
        await message.answer(
            preview,
            reply_markup=get_confirmation_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Failed to calculate extension: {e}")
        await message.answer(f"❌ Ошибка расчёта даты: {str(e)}")


@router.callback_query(F.data == "confirm_create")  # Reuse confirm button
async def callback_confirm_extend(callback: CallbackQuery, state: FSMContext):
    """Confirm access extension."""
    data = await state.get_data()
    
    # Check if this is extend confirmation
    if "new_valid_until" not in data:
        return  # Not extend flow
    
    row = data.get("extend_row", {})
    new_until_str = data.get("new_valid_until")
    new_until = datetime.fromisoformat(new_until_str)
    
    await callback.message.edit_text("⏳ Продлеваю доступ...")
    
    try:
        default_sheet = db.get_default_sheet(callback.from_user.id)
        creds = get_authorized_user()
        
        if not creds or not default_sheet:
            await callback.message.answer("❌ Ошибка конфигурации.")
            return
        
        sheets_service = SheetsService(creds)
        calendar_service = CalendarService(creds)
        
        row_num = row.get("row_number")
        old_until = row.get("valid_until", "")
        
        # Update sheet
        sheets_service.update_cell(
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            row=row_num,
            col="Дата окончания",
            value=new_until.strftime("%Y-%m-%d %H:%M")
        )
        
        # Update calendar event
        event_id = row.get("calendar_event_id")
        if event_id:
            calendar_service.reschedule_event(
                event_id=event_id,
                new_datetime=new_until
            )
        
        # Log audit
        audit_logger.log_action(
            action="EXTENDED_ACCESS",
            telegram_user_id=callback.from_user.id,
            telegram_username=callback.from_user.username,
            spreadsheet_id=default_sheet["spreadsheet_id"],
            sheet_name=default_sheet["default_sheet_name"],
            row_number=row_num,
            full_name=row.get("full_name", ""),
            old_valid_until=old_until,
            new_valid_until=new_until.strftime("%Y-%m-%d %H:%M")
        )
        
        await callback.message.answer(
            f"✅ Доступ продлен!\n\n"
            f"Новый срок: **{new_until.strftime('%d.%m.%Y %H:%M')}**",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Failed to extend access: {e}")
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


# ==================== SETTINGS ====================

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Show bot settings."""
    user_id = message.from_user.id
    
    if user_id not in settings.ALLOWED_TELEGRAM_USER_IDS:
        await message.answer("❌ Доступ запрещён.")
        return
    
    user_settings = db.get_user_settings(user_id)
    
    text = "⚙️ **Настройки бота:**\n\n"
    
    if user_settings:
        text += f"🕒 Часовой пояс: {user_settings.get('timezone', 'Asia/Almaty')}\n"
        text += f"⏰ Время событий: {user_settings.get('event_hour', 9):02d}:{user_settings.get('event_minute', 0):02d}\n"
        text += f"📅 Напоминания: за {user_settings.get('reminder_days', '1,0')} дн.\n"
    else:
        text += "Настройки по умолчанию.\n"
    
    text += "\nДля изменения используйте /calendar_settings"
    
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("calendar_settings"))
async def cmd_calendar_settings(message: Message, state: FSMContext):
    """Calendar settings."""
    await state.set_state(AccessStates.setting_reminder_days)
    
    await message.answer(
        "📅 **Настройка напоминаний**\n\n"
        "Через сколько дней до события напоминать?\n"
        "Примеры: '1,0' (за день и в день), '7,3,1,0'\n\n"
        "/cancel — отмена"
    )


# ==================== CANCEL HANDLER ====================

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current operation."""
    current_state = await state.get_state()
    
    if current_state:
        await state.clear()
        await message.answer("❌ Действие отменено.")
    else:
        await message.answer("Нет активных операций.")

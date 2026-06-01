"""
Сервис управления доступами.
Основной бизнес-логика для создания, отзыва и продления доступов.
Соответствует требованиям ISO 27001 A.9.4 (управление доступом).
"""

from datetime import datetime, timedelta
from typing import Optional, Any, Dict, List
import re

from app.logging_config import get_logger
from app.config import config
from app.db.database import db
from app.google.auth import google_auth
from app.google.sheets import sheets_service
from app.google.calendar import calendar_service
from app.services.date_service import date_service
from app.templates.matrix_templates import matrix_templates

logger = get_logger(__name__)


# Привилегированные роли (ISO 27001 A.9.2.3)
PRIVILEGED_ROLE_PATTERNS = [
    r'admin', r'administrator', r'root', r'superuser', r'owner',
    r'privileged', r'domain\s*admin', r'global\s*admin', r'security\s*admin',
    r'sysadmin', r'backup\s*admin', r'database\s*admin', r'network\s*admin',
    r'power\s*user', r'full\s*access', r'sudo', r'elevated'
]


class AccessService:
    """Сервис для управления жизненным циклом доступов."""
    
    def __init__(self):
        self.sheets = sheets_service
        self.calendar = calendar_service
        self.date_service = date_service
    
    @staticmethod
    def detect_privileged_access(role: str, access_level: str = "") -> bool:
        """
        Определяет, является ли доступ привилегированным.
        Соответствует ISO 27001 A.9.2.3 (Управление привилегиями).
        
        Args:
            role: Роль пользователя
            access_level: Уровень доступа
            
        Returns:
            True если доступ привилегированный
        """
        if not role and not access_level:
            return False
        
        text_to_check = f"{role} {access_level}".lower()
        
        for pattern in PRIVILEGED_ROLE_PATTERNS:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                logger.info(f"Обнаружен привилегированный доступ по паттерну '{pattern}'")
                return True
        
        return False
    
    @staticmethod
    def normalize_status(status: str) -> str:
        """
        Нормализация статусов доступа.
        Соответствует ISO 27001 A.12.4 (Логирование и мониторинг).
        """
        if not status:
            return "Не указан"
        
        status_lower = status.lower().strip()
        
        # Активные статусы
        if status_lower in ['active', 'enabled', 'активен', 'активный', 'да', 'yes', 'true']:
            return "Активен"
        
        # Отключенные
        if status_lower in ['disabled', 'отключен', 'нет', 'no', 'false', 'inactive']:
            return "Отключен"
        
        # На ревью
        if status_lower in ['review', 'на проверке', 'ревью', 'pending review', 'на ревью']:
            return "На ревью"
        
        # Временный
        if status_lower in ['temporary', 'временный', 'temp', 'врем']:
            return "Временный"
        
        # Отозван
        if status_lower in ['revoked', 'отозван', 'отменен', 'cancelled']:
            return "Отозван"
        
        # Просрочен
        if status_lower in ['overdue', 'просрочен', 'expired', 'истек']:
            return "Просрочен"
        
        # По умолчанию
        return status.strip().title()
    
    async def create_access_from_parsed(
        self,
        telegram_user_id: int,
        username: str,
        parsed_data: dict,
        spreadsheet_id: Optional[str] = None,
        sheet_name: Optional[str] = None,
    ) -> dict:
        """
        Создание доступа из распарсенных данных.
        
        Args:
            telegram_user_id: ID пользователя Telegram
            username: Имя пользователя
            parsed_data: Распарсенные данные запроса
            spreadsheet_id: ID таблицы (по умолчанию из настроек)
            sheet_name: Название вкладки (по умолчанию из настроек)
            
        Returns:
            Результат операции с ссылками
        """
        # Получаем настройки пользователя
        settings = db.get_settings(telegram_user_id)
        
        # Определяем таблицу
        if not spreadsheet_id:
            spreadsheet_id = settings.default_spreadsheet_id if settings else None
        
        if not spreadsheet_id:
            # Создаем новую таблицу по умолчанию
            logger.info("Создание новой таблицы по умолчанию")
            result = self.sheets.create_spreadsheet(
                title=f"Access Matrix - {username}",
                template_name="temporary_access",
            )
            spreadsheet_id = result["spreadsheet_id"]
            sheet_name = result["sheet_name"]
            
            # Сохраняем таблицу
            db.save_sheet(
                telegram_user_id=telegram_user_id,
                spreadsheet_id=spreadsheet_id,
                spreadsheet_url=result["spreadsheet_url"],
                title=result["title"],
                default_sheet_name=sheet_name,
            )
            
            # Обновляем настройки
            db.upsert_settings(
                telegram_user_id=telegram_user_id,
                default_spreadsheet_id=spreadsheet_id,
                default_sheet_name=sheet_name,
            )
        elif not sheet_name:
            sheet_name = settings.default_sheet_name if settings else "Временные доступы"
        
        # Формируем данные для записи
        record_data = self._prepare_record_data(parsed_data, username)
        
        # Получаем маппинг колонок для шаблона temporary_access
        template = matrix_templates.get_template("temporary_access")
        column_mapping = self._get_column_mapping_for_template(template)
        
        # Добавляем запись в таблицу
        row_number = self.sheets.append_access_record(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            record_data=record_data,
            column_mapping=column_mapping,
        )
        
        # Создаем событие календаря если есть дата окончания
        calendar_event_id = None
        calendar_event_link = None
        
        if parsed_data.get("end_date"):
            try:
                end_date = date_service.parse_absolute_date(parsed_data["end_date"])
                if not end_date:
                    end_date = date_service.get_now() + timedelta(days=1)
                
                event_result = self.calendar.create_access_review_event(
                    full_name=parsed_data.get("full_name", ""),
                    system=parsed_data.get("system", ""),
                    role=parsed_data.get("role", ""),
                    end_date=end_date,
                    access_data=parsed_data,
                    spreadsheet_url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                    sheet_name=sheet_name,
                    row_number=row_number,
                )
                
                calendar_event_id = event_result["event_id"]
                calendar_event_link = event_result["event_link"]
                
                # Обновляем ячейки с Calendar Event ID
                self._update_calendar_info_in_sheet(
                    spreadsheet_id,
                    sheet_name,
                    row_number,
                    calendar_event_id,
                    calendar_event_link,
                )
                
            except Exception as e:
                logger.error(f"Ошибка создания события календаря: {e}")
                # Обновляем статус на ошибку
                self.sheets.update_cell(
                    spreadsheet_id,
                    sheet_name,
                    row_number,
                    column_mapping.get("status", 15),
                    "Ошибка создания события",
                )
        
        # Сохраняем запись в локальную БД
        created_record = db.save_created_record(
            telegram_user_id=telegram_user_id,
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            row_number=row_number,
            full_name=parsed_data.get("full_name", ""),
            system=parsed_data.get("system", ""),
            role=parsed_data.get("role", ""),
            valid_until=parsed_data.get("end_date", ""),
            status="Активен",
            calendar_event_id=calendar_event_id,
            calendar_event_link=calendar_event_link,
        )
        
        # Записываем в историю
        db.log_access_history(
            telegram_user_id=telegram_user_id,
            username=username,
            action="CREATED_ACCESS",
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            row_number=row_number,
            full_name=parsed_data.get("full_name", ""),
            login=parsed_data.get("login", ""),
            system=parsed_data.get("system", ""),
            new_role=parsed_data.get("role", ""),
            new_valid_until=parsed_data.get("end_date", ""),
            new_status="Активен",
            comment=parsed_data.get("reason", ""),
        )
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
            "sheet_name": sheet_name,
            "row_number": row_number,
            "calendar_event_id": calendar_event_id,
            "calendar_link": calendar_event_link,
            "record_id": created_record.id,
        }
    
    def _prepare_record_data(self, parsed_data: dict, username: str) -> dict:
        """Подготовка данных для записи в таблицу."""
        now = date_service.get_now()
        
        return {
            "full_name": parsed_data.get("full_name", ""),
            "login": parsed_data.get("login", ""),
            "email": parsed_data.get("email", ""),
            "system": parsed_data.get("system", ""),
            "role": parsed_data.get("role", ""),
            "access_level": parsed_data.get("access_level", ""),
            "reason": parsed_data.get("reason", ""),
            "ticket_number": parsed_data.get("ticket_number", ""),
            "granted_date": parsed_data.get("granted_date") or date_service.format_datetime(now),
            "duration": parsed_data.get("duration_text", ""),
            "end_date": parsed_data.get("end_date", ""),
            "reminder_time": f"{config.DEFAULT_EVENT_HOUR}:{config.DEFAULT_EVENT_MINUTE:02d}",
            "action": parsed_data.get("action_after_expiry", "Забрать доступ"),
            "status": "Активен",
            "review_status": "Не начато",
            "owner": "",
            "security_contact": "",
            "added_by": username,
            "created_at": date_service.format_datetime(now),
            "comment": parsed_data.get("comment", ""),
        }
    
    def _get_column_mapping_for_template(self, template: dict) -> dict[str, int]:
        """Получение маппинга колонок для шаблона."""
        columns = template["columns"]
        mapping = {}
        
        # Маппинг полей к колонкам шаблона temporary_access
        field_to_col = {
            "row_number": 0,
            "full_name": 1,
            "login": 2,
            "email": 3,
            "system": 4,
            "role": 5,
            "access_level": 6,
            "reason": 7,
            "ticket_number": 8,
            "granted_date": 9,
            "duration": 10,
            "end_date": 11,
            "reminder_time": 12,
            "action": 13,
            "status": 14,
            "review_status": 15,
            "owner": 16,
            "security_contact": 17,
            "calendar_event_id": 18,
            "calendar_event_link": 19,
            "google_sheets_row": 20,
            "added_by": 21,
            "created_at": 22,
            "comment": 23,
        }
        
        return {k: v for k, v in field_to_col.items() if v < len(columns)}
    
    def _update_calendar_info_in_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        calendar_event_id: str,
        calendar_event_link: str,
    ):
        """Обновление информации о календаре в таблице."""
        try:
            # Находим индексы колонок
            headers = self.sheets.get_sheet_headers(spreadsheet_id, sheet_name)
            
            col_event_id = None
            col_event_link = None
            
            for i, header in enumerate(headers):
                if "Calendar Event ID" in header or "Event ID" in header:
                    col_event_id = i
                elif "Calendar Event Link" in header or "Event Link" in header:
                    col_event_link = i
            
            # Обновляем ячейки
            if col_event_id is not None:
                self.sheets.update_cell(
                    spreadsheet_id,
                    sheet_name,
                    row_number,
                    col_event_id,
                    calendar_event_id,
                )
            
            if col_event_link is not None:
                self.sheets.update_cell(
                    spreadsheet_id,
                    sheet_name,
                    row_number,
                    col_event_link,
                    calendar_event_link,
                )
                
        except Exception as e:
            logger.warning(f"Не удалось обновить информацию о календаре: {e}")


# Глобальный экземпляр сервиса
access_service = AccessService()

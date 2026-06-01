"""Сервис для управления доступами."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.db.models import AccessRecord, ParsedAccessRequest
from app.db.database import Database
from app.google.sheets import GoogleSheetsService
from app.google.calendar import GoogleCalendarService
from app.services.date_service import DateService
from app.config import (
    DEFAULT_SPREADSHEET_ID,
    DEFAULT_SHEET_NAME,
    DEFAULT_CALENDAR_ID,
    DEFAULT_REMINDER_DAYS,
    DEFAULT_ACCESS_ACTION,
    TIMEZONE,
)

logger = logging.getLogger(__name__)


class AccessService:
    """Сервис для управления записями о доступе."""

    def __init__(self, db: Database):
        self.db = db
        self.sheets_service = GoogleSheetsService()
        self.calendar_service = GoogleCalendarService()
        self.date_service = DateService()

    def create_access_record(
        self,
        telegram_user_id: int,
        record: AccessRecord,
        spreadsheet_id: Optional[str] = None,
        sheet_name: Optional[str] = None,
        add_to_calendar: bool = True,
    ) -> Tuple[bool, str, Optional[int], Optional[str]]:
        """
        Создаёт запись о доступе в Google Sheets и событие в Calendar.

        Возвращает: (успех, сообщение, номер_строки, event_id)
        """
        # Получаем таблицу по умолчанию или указанную
        if not spreadsheet_id:
            settings = self.db.get_settings(telegram_user_id)
            spreadsheet_id = settings.get("default_spreadsheet_id") or DEFAULT_SPREADSHEET_ID

        if not spreadsheet_id:
            return False, "❌ Таблица не указана. Используйте /bind_sheet для привязки таблицы.", None, None

        if not sheet_name:
            settings = self.db.get_settings(telegram_user_id)
            sheet_name = settings.get("default_sheet_name") or DEFAULT_SHEET_NAME

        try:
            # Проверяем существование таблицы
            spreadsheet = self.sheets_service.get_spreadsheet(spreadsheet_id)
            if not spreadsheet:
                return False, f"❌ Таблица {spreadsheet_id} не найдена или нет доступа.", None, None

            # Проверяем существование вкладки
            sheet_names = self.sheets_service.get_sheet_names(spreadsheet_id)
            if sheet_name not in sheet_names:
                # Создаём новую вкладку с заголовками
                headers = self._get_default_headers()
                self.sheets_service.create_sheet(spreadsheet_id, sheet_name, headers)
                logger.info("Создана новая вкладка: %s", sheet_name)

            # Получаем заголовки
            headers = self.sheets_service.get_headers(spreadsheet_id, sheet_name)
            if not headers:
                return False, f"❌ Не удалось получить заголовки вкладки {sheet_name}.", None, None

            # Маппим поля записи на колонки
            row_data = self._map_record_to_row(record, headers)

            # Добавляем строку
            row_number = self.sheets_service.append_rows(
                spreadsheet_id, sheet_name, [row_data]
            )

            if not row_number:
                return False, "❌ Не удалось добавить строку в таблицу.", None, None

            # Создаём событие в календаре если указана дата окончания
            event_id = None
            event_link = None
            if add_to_calendar and record.valid_until:
                event_result = self._create_calendar_event(record, spreadsheet_id, sheet_name, row_number)
                if event_result:
                    event_id = event_result.get("id")
                    event_link = self.calendar_service.get_event_link(event_id)

                    # Обновляем строку с Calendar Event ID и Link
                    self._update_calendar_fields(
                        spreadsheet_id, sheet_name, row_number, event_id, event_link
                    )

            # Сохраняем информацию о созданной записи
            self.db.save_created_record(
                telegram_user_id=telegram_user_id,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                row_number=row_number,
                calendar_event_id=event_id,
                calendar_event_link=event_link,
                full_name=record.full_name,
                system=record.system or "",
                role=record.role or "",
                valid_until=self.date_service.format_date(record.valid_until) if record.valid_until else "",
                status=record.status,
            )

            # Добавляем запись в историю
            self._add_history_entry(
                spreadsheet_id, sheet_name, "CREATED_ACCESS", telegram_user_id, record
            )

            spreadsheet_url = self.sheets_service.get_spreadsheet_url(spreadsheet_id)
            message = (
                f"✅ Запись успешно создана!\n\n"
                f"📊 Таблица: {spreadsheet_url}\n"
                f"📑 Вкладка: {sheet_name}\n"
                f"📍 Строка: {row_number}"
            )

            if event_id:
                message += f"\n📅 Событие в календаре создано"

            return True, message, row_number, event_id

        except Exception as e:
            logger.exception("Ошибка создания записи о доступе: %s", e)
            return False, f"❌ Ошибка: {str(e)}", None, None

    def _get_default_headers(self) -> List[str]:
        """Возвращает заголовки по умолчанию для временных доступов."""
        return [
            "№", "ФИО", "Логин", "Email", "Система", "Роль", "Уровень доступа",
            "Основание выдачи", "Номер заявки", "Дата выдачи", "Срок доступа",
            "Дата окончания", "Время напоминания", "Действие", "Статус доступа",
            "Статус ревью", "Владелец системы", "Ответственный ИБ",
            "Calendar Event ID", "Calendar Event Link", "Google Sheets Row",
            "Кем добавлено", "Дата создания записи", "Комментарий"
        ]

    def _map_record_to_row(self, record: AccessRecord, headers: List[str]) -> List[str]:
        """Маппит объект записи на строку таблицы."""
        row = [""] * len(headers)

        field_map = {
            "№": lambda: "",  # Будет автозаполнено Google Sheets или вручную
            "ФИО": record.full_name,
            "Логин": record.login or "",
            "Email": record.email or "",
            "Система": record.system or "",
            "Роль": record.role or "",
            "Уровень доступа": record.access_level or "",
            "Основание выдачи": record.reason or "",
            "Номер заявки": record.ticket_number or "",
            "Дата выдачи": self.date_service.format_date(record.granted_at) if record.granted_at else "",
            "Срок доступа": self._calculate_duration(record.granted_at, record.valid_until),
            "Дата окончания": self.date_service.format_date(record.valid_until) if record.valid_until else "",
            "Время напоминания": f"{record.granted_at.hour:02d}:{record.granted_at.minute:02d}" if record.granted_at else "09:00",
            "Действие": DEFAULT_ACCESS_ACTION,
            "Статус доступа": record.status,
            "Статус ревью": record.review_status or "",
            "Владелец системы": record.system_owner or "",
            "Ответственный ИБ": record.security_owner or "",
            "Calendar Event ID": record.calendar_event_id or "",
            "Calendar Event Link": record.calendar_event_link or "",
            "Google Sheets Row": str(record.row_number) if record.row_number else "",
            "Кем добавлено": record.added_by or "",
            "Дата создания записи": self.date_service.format_datetime(record.created_at) if record.created_at else "",
            "Комментарий": record.comment or "",
        }

        for i, header in enumerate(headers):
            header_clean = header.strip().lower()
            for key, value in field_map.items():
                if key.lower() == header_clean:
                    row[i] = str(value) if value is not None else ""
                    break

        return row

    def _calculate_duration(self, start: Optional[datetime], end: Optional[datetime]) -> str:
        """Вычисляет длительность доступа в днях."""
        if not start or not end:
            return ""

        delta = end - start
        days = delta.days

        if days == 1:
            return "1 день"
        elif 2 <= days <= 4:
            return f"{days} дня"
        elif 5 <= days <= 21:
            weeks = days // 7
            remaining_days = days % 7
            if weeks == 1 and remaining_days == 0:
                return "1 неделя"
            elif weeks == 1:
                return f"1 неделя {remaining_days} дня"
            elif remaining_days == 0:
                return f"{weeks} недель"
            else:
                return f"{weeks} недель {remaining_days} дней"
        elif days >= 30:
            months = days // 30
            return f"{months} мес." if months == 1 else f"{months} месяцев"
        else:
            return f"{days} дней"

    def _create_calendar_event(
        self,
        record: AccessRecord,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
    ) -> Optional[Dict[str, Any]]:
        """Создаёт событие в Google Calendar."""
        if not record.valid_until:
            return None

        # Формируем название события
        if record.system and record.role:
            summary = f"[Access Review] Забрать доступ: {record.full_name} — {record.system} — {record.role}"
        else:
            summary = f"[Access Review] Забрать доступ: {record.full_name}"

        # Формируем описание
        spreadsheet_url = self.sheets_service.get_spreadsheet_url(spreadsheet_id)
        description = (
            f"Пользователь: {record.full_name}\n"
            f"Логин: {record.login or 'Не указано'}\n"
            f"Email: {record.email or 'Не указано'}\n"
            f"Система: {record.system or 'Не указано'}\n"
            f"Роль: {record.role or 'Не указано'}\n"
            f"Уровень доступа: {record.access_level or 'Не указано'}\n"
            f"Основание: {record.reason or 'Не указано'}\n"
            f"Номер заявки: {record.ticket_number or 'Не указано'}\n"
            f"Дата выдачи: {self.date_service.format_date(record.granted_at) if record.granted_at else 'Не указано'}\n"
            f"Дата окончания: {self.date_service.format_date(record.valid_until)}\n"
            f"Действие: Забрать доступ\n"
            f"\n"
            f"Google Sheets: {spreadsheet_url}\n"
            f"Вкладка: {sheet_name}\n"
            f"Строка: {row_number}\n"
            f"Владелец системы: {record.system_owner or 'Не указано'}\n"
            f"Ответственный ИБ: {record.security_owner or 'Не указано'}\n"
            f"Комментарий: {record.comment or ''}"
        )

        # Получаем настройки напоминаний
        settings = self.db.get_settings(0)  # Настройки по умолчанию
        reminder_days_str = settings.get("reminder_days", "1,0")
        reminder_days = [int(d.strip()) for d in reminder_days_str.split(",") if d.strip()]

        return self.calendar_service.create_event(
            summary=summary,
            start_datetime=record.valid_until,
            description=description,
            calendar_id=DEFAULT_CALENDAR_ID,
            reminder_days=reminder_days,
        )

    def _update_calendar_fields(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        event_id: str,
        event_link: str,
    ) -> None:
        """Обновляет поля Calendar Event ID и Link в таблице."""
        headers = self.sheets_service.get_headers(spreadsheet_id, sheet_name)

        event_id_col = None
        event_link_col = None

        for i, header in enumerate(headers):
            if "calendar event id" in header.lower():
                event_id_col = chr(ord("A") + i)
            elif "calendar event link" in header.lower():
                event_link_col = chr(ord("A") + i)

        updates = []
        if event_id_col:
            updates.append([event_id])
        if event_link_col:
            updates.append([event_link])

        if updates:
            range_name = f"{sheet_name}!{event_id_col or 'T'}{row_number}"
            self.sheets_service.update_range(spreadsheet_id, range_name, [updates[0]])

    def _add_history_entry(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        action: str,
        telegram_user_id: int,
        record: AccessRecord,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Добавляет запись в историю изменений."""
        # Получаем или создаём вкладку истории
        history_sheet_name = "История изменений"
        sheet_names = self.sheets_service.get_sheet_names(spreadsheet_id)

        if history_sheet_name not in sheet_names:
            history_headers = [
                "Дата и время", "Действие", "Telegram User ID", "Telegram Username",
                "ФИО", "Логин", "Система", "Старая роль", "Новая роль",
                "Старая дата окончания", "Новая дата окончания",
                "Старый статус", "Новый статус", "Комментарий"
            ]
            self.sheets_service.create_sheet(spreadsheet_id, history_sheet_name, history_headers)

        now = self.date_service.get_now()
        history_row = [
            self.date_service.format_datetime(now),
            action,
            str(telegram_user_id),
            "",  # Username нужно получать отдельно
            record.full_name,
            record.login or "",
            record.system or "",
            old_values.get("role", "") if old_values else "",
            record.role or "",
            self.date_service.format_date(old_values["valid_until"]) if old_values and old_values.get("valid_until") else "",
            self.date_service.format_date(record.valid_until) if record.valid_until else "",
            old_values.get("status", "") if old_values else "",
            record.status,
            record.comment or "",
        ]

        self.sheets_service.append_rows(spreadsheet_id, history_sheet_name, [history_row])

    def revoke_access(
        self,
        telegram_user_id: int,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        comment: str = "",
        update_calendar: bool = True,
    ) -> Tuple[bool, str]:
        """Отмечает доступ как отозванный."""
        try:
            headers = self.sheets_service.get_headers(spreadsheet_id, sheet_name)
            
            # Находим индексы нужных колонок
            status_col = None
            review_col = None
            comment_col = None
            event_id_col = None

            for i, header in enumerate(headers):
                header_lower = header.lower()
                if "статус доступа" in header_lower or "status" in header_lower:
                    status_col = chr(ord("A") + i)
                elif "статус ревью" in header_lower:
                    review_col = chr(ord("A") + i)
                elif "комментарий" in header_lower:
                    comment_col = chr(ord("A") + i)
                elif "calendar event id" in header_lower:
                    event_id_col = chr(ord("A") + i)

            # Обновляем статус
            now = self.date_service.get_now()
            updates = []

            if status_col:
                updates.append((f"{status_col}{row_number}", "Отозван"))
            if review_col:
                updates.append((f"{review_col}{row_number}", "Выполнено"))
            if comment_col:
                updates.append((f"{comment_col}{row_number}", f"{comment} (отозвано {now.strftime('%Y-%m-%d')})"))

            for range_name, value in updates:
                self.sheets_service.update_range(spreadsheet_id, range_name, [[value]])

            # Обновляем событие в календаре
            if update_calendar and event_id_col:
                event_id_range = f"{sheet_name}!{event_id_col}{row_number}"
                event_id_result = self.sheets_service.get_range(spreadsheet_id, event_id_range)
                if event_id_result and event_id_result[0]:
                    event_id = event_id_result[0][0]
                    if event_id:
                        self.calendar_service.update_event(
                            event_id=event_id,
                            summary=f"[DONE] Доступ отозван",
                        )

            # Добавляем запись в историю
            # Для простоты создаём новую запись AccessRecord
            record = AccessRecord(full_name="Не указано", status="Отозван", comment=comment)
            self._add_history_entry(
                spreadsheet_id, sheet_name, "REVOKED_ACCESS", telegram_user_id, record
            )

            return True, "✅ Доступ отмечен как отозванный"

        except Exception as e:
            logger.exception("Ошибка отзыва доступа: %s", e)
            return False, f"❌ Ошибка: {str(e)}"

    def extend_access(
        self,
        telegram_user_id: int,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        new_end_date: datetime,
        comment: str = "",
    ) -> Tuple[bool, str]:
        """Продлевает срок доступа."""
        try:
            headers = self.sheets_service.get_headers(spreadsheet_id, sheet_name)

            # Находим колонку даты окончания
            end_date_col = None
            event_id_col = None

            for i, header in enumerate(headers):
                header_lower = header.lower()
                if "дата окончания" in header_lower or "valid until" in header_lower:
                    end_date_col = chr(ord("A") + i)
                elif "calendar event id" in header_lower:
                    event_id_col = chr(ord("A") + i)

            if not end_date_col:
                return False, "❌ Не найдена колонка 'Дата окончания'"

            # Обновляем дату
            new_date_str = self.date_service.format_date(new_end_date)
            self.sheets_service.update_range(
                spreadsheet_id, f"{sheet_name}!{end_date_col}{row_number}", [[new_date_str]]
            )

            # Обновляем событие в календаре
            if event_id_col:
                event_id_range = f"{sheet_name}!{event_id_col}{row_number}"
                event_id_result = self.sheets_service.get_range(spreadsheet_id, event_id_range)
                if event_id_result and event_id_result[0]:
                    event_id = event_id_result[0][0]
                    if event_id:
                        self.calendar_service.update_event(
                            event_id=event_id,
                            start_datetime=new_end_date,
                        )

            # Добавляем запись в историю
            record = AccessRecord(
                full_name="Не указано",
                valid_until=new_end_date,
                status="Продлён",
                comment=comment,
            )
            self._add_history_entry(
                spreadsheet_id, sheet_name, "EXTENDED_ACCESS", telegram_user_id, record
            )

            return True, f"✅ Доступ продлён до {new_date_str}"

        except Exception as e:
            logger.exception("Ошибка продления доступа: %s", e)
            return False, f"❌ Ошибка: {str(e)}"

    def get_due_accesses(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        days_ahead: int = 7,
    ) -> List[Dict[str, Any]]:
        """Получает доступы, которые истекают в ближайшие N дней."""
        try:
            headers = self.sheets_service.get_headers(spreadsheet_id, sheet_name)
            if not headers:
                return []

            # Находим колонки
            fullname_col = None
            end_date_col = None
            status_col = None
            system_col = None

            for i, header in enumerate(headers):
                header_lower = header.lower()
                if "фио" in header_lower or "пользователь" in header_lower:
                    fullname_col = i
                elif "дата окончания" in header_lower or "valid until" in header_lower:
                    end_date_col = i
                elif "статус" in header_lower and "ревью" not in header_lower:
                    status_col = i
                elif "система" in header_lower:
                    system_col = i

            if end_date_col is None:
                return []

            # Получаем все данные
            data = self.sheets_service.get_range(spreadsheet_id, f"{sheet_name}!A:Z")
            if not data or len(data) < 2:
                return []

            due_accesses = []
            now = self.date_service.get_now()
            cutoff_date = now + timedelta(days=days_ahead)

            for row_idx, row in enumerate(data[1:], start=2):  # Пропускаем заголовок
                if end_date_col >= len(row) or not row[end_date_col]:
                    continue

                # Парсим дату окончания
                end_date_str = row[end_date_col]
                end_date = dateparser.parse(end_date_str, languages=["ru"])
                if not end_date:
                    continue

                # Проверяем, попадает ли в диапазон
                if now <= end_date <= cutoff_date:
                    # Проверяем статус (не должен быть "Отозван")
                    status = row[status_col] if status_col and status_col < len(row) else ""
                    if "отозван" in status.lower():
                        continue

                    due_accesses.append({
                        "row_number": row_idx,
                        "full_name": row[fullname_col] if fullname_col and fullname_col < len(row) else "Не указано",
                        "system": row[system_col] if system_col and system_col < len(row) else "Не указано",
                        "valid_until": end_date,
                        "status": status,
                    })

            return sorted(due_accesses, key=lambda x: x["valid_until"])

        except Exception as e:
            logger.exception("Ошибка получения истекающих доступов: %s", e)
            return []

    def get_overdue_accesses(
        self,
        spreadsheet_id: str,
        sheet_name: str,
    ) -> List[Dict[str, Any]]:
        """Получает просроченные доступы."""
        try:
            headers = self.sheets_service.get_headers(spreadsheet_id, sheet_name)
            if not headers:
                return []

            # Находим колонки (аналогично get_due_accesses)
            fullname_col = None
            end_date_col = None
            status_col = None
            system_col = None

            for i, header in enumerate(headers):
                header_lower = header.lower()
                if "фио" in header_lower or "пользователь" in header_lower:
                    fullname_col = i
                elif "дата окончания" in header_lower or "valid until" in header_lower:
                    end_date_col = i
                elif "статус" in header_lower and "ревью" not in header_lower:
                    status_col = i
                elif "система" in header_lower:
                    system_col = i

            if end_date_col is None:
                return []

            # Получаем все данные
            data = self.sheets_service.get_range(spreadsheet_id, f"{sheet_name}!A:Z")
            if not data or len(data) < 2:
                return []

            overdue_accesses = []
            now = self.date_service.get_now()

            for row_idx, row in enumerate(data[1:], start=2):
                if end_date_col >= len(row) or not row[end_date_col]:
                    continue

                end_date_str = row[end_date_col]
                end_date = dateparser.parse(end_date_str, languages=["ru"])
                if not end_date:
                    continue

                # Проверяем, просрочена ли дата
                if end_date < now:
                    status = row[status_col] if status_col and status_col < len(row) else ""
                    if "отозван" in status.lower():
                        continue

                    overdue_accesses.append({
                        "row_number": row_idx,
                        "full_name": row[fullname_col] if fullname_col and fullname_col < len(row) else "Не указано",
                        "system": row[system_col] if system_col and system_col < len(row) else "Не указано",
                        "valid_until": end_date,
                        "status": status,
                    })

            return sorted(overdue_accesses, key=lambda x: x["valid_until"])

        except Exception as e:
            logger.exception("Ошибка получения просроченных доступов: %s", e)
            return []


# Импортируем здесь чтобы избежать циклических импортов
from datetime import timedelta
import dateparser

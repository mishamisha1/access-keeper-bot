"""
Google Calendar API сервис.
Соответствует требованиям ISO 27001 A.12.3 (резервное копирование) и A.12.4 (мониторинг).
Создает события с напоминаниями для отзыва временных доступов.
"""

from datetime import datetime, timedelta
from typing import Optional, Any

from app.logging_config import get_logger
from app.google.auth import google_auth
from app.config import config

logger = get_logger(__name__)


class GoogleCalendarService:
    """Сервис для работы с Google Calendar API."""
    
    def __init__(self):
        self.service = None
    
    def _ensure_service(self):
        """Проверка и получение сервиса."""
        if self.service is None:
            self.service = google_auth.calendar_service
        return self.service
    
    def create_event(
        self,
        summary: str,
        start_datetime: datetime,
        end_datetime: datetime | None = None,
        description: str = "",
        attendees: list[str] | None = None,
        reminder_days: list[int] | None = None,
        calendar_id: str = "primary",
    ) -> dict:
        """
        Создание события в Google Calendar.
        
        Args:
            summary: Название события
            start_datetime: Дата и время начала
            end_datetime: Дата и время окончания (по умолчанию + 30 минут)
            description: Описание события
            attendees: Список email участников
            reminder_days: Дни для напоминаний (например [1, 0] - за 1 день и в день)
            calendar_id: ID календаря
            
        Returns:
            Информация о созданном событии
        """
        service = self._ensure_service()
        
        if end_datetime is None:
            end_datetime = start_datetime + timedelta(minutes=30)
        
        # Формируем напоминания
        reminders = []
        if reminder_days is None:
            reminder_days = config.DEFAULT_REMINDER_DAYS
        
        for days in reminder_days:
            if days == 0:
                # Напоминание в день события (утром)
                reminders.append({
                    "method": "popup",
                    "minutes": 9 * 60,  # 9 часов = 540 минут
                })
            else:
                reminders.append({
                    "method": "popup",
                    "minutes": days * 24 * 60,  # Дни в минуты
                })
        
        event_body = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": config.TIMEZONE,
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": config.TIMEZONE,
            },
            "reminders": {
                "useDefault": False,
                "overrides": reminders,
            },
        }
        
        # Добавляем участников если указаны
        if attendees:
            event_body["attendees"] = [
                {"email": email} for email in attendees
            ]
        
        try:
            event = service.events().insert(
                calendarId=calendar_id,
                body=event_body,
                sendNotifications=True,
            ).execute()
            
            logger.info(f"Создано событие календаря: {event['id']}")
            
            return {
                "event_id": event["id"],
                "event_link": event.get("htmlLink", ""),
                "summary": event["summary"],
                "start": event["start"]["dateTime"],
                "end": event["end"]["dateTime"],
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания события календаря: {e}")
            raise
    
    def update_event(
        self,
        event_id: str,
        summary: str | None = None,
        description: str | None = None,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
        calendar_id: str = "primary",
    ) -> dict:
        """
        Обновление существующего события.
        
        Args:
            event_id: ID события
            summary: Новое название
            description: Новое описание
            start_datetime: Новая дата начала
            end_datetime: Новая дата окончания
            calendar_id: ID календаря
            
        Returns:
            Информация об обновленном событии
        """
        service = self._ensure_service()
        
        # Получаем текущее событие
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()
        
        # Обновляем поля
        if summary:
            event["summary"] = summary
        if description:
            event["description"] = description
        if start_datetime:
            event["start"]["dateTime"] = start_datetime.isoformat()
        if end_datetime:
            event["end"]["dateTime"] = end_datetime.isoformat()
        
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
        ).execute()
        
        logger.info(f"Обновлено событие календаря: {event_id}")
        
        return {
            "event_id": updated_event["id"],
            "event_link": updated_event.get("htmlLink", ""),
            "summary": updated_event["summary"],
        }
    
    def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> bool:
        """
        Удаление события из календаря.
        
        Args:
            event_id: ID события
            calendar_id: ID календаря
            
        Returns:
            True если успешно
        """
        service = self._ensure_service()
        
        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
            ).execute()
            
            logger.info(f"Удалено событие календаря: {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления события: {e}")
            return False
    
    def mark_event_done(
        self,
        event_id: str,
        original_summary: str,
        calendar_id: str = "primary",
    ) -> dict:
        """
        Пометка события как выполненного (добавление префикса [DONE]).
        
        Args:
            event_id: ID события
            original_summary: Оригинальное название
            calendar_id: ID календаря
            
        Returns:
            Информация об обновленном событии
        """
        new_summary = f"[DONE] {original_summary}"
        
        return self.update_event(
            event_id=event_id,
            summary=new_summary,
            calendar_id=calendar_id,
        )
    
    def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict | None:
        """
        Получение информации о событии.
        
        Args:
            event_id: ID события
            calendar_id: ID календаря
            
        Returns:
            Информация о событии или None
        """
        service = self._ensure_service()
        
        try:
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id,
            ).execute()
            
            return {
                "event_id": event["id"],
                "summary": event["summary"],
                "description": event.get("description", ""),
                "start": event["start"]["dateTime"],
                "end": event["end"]["dateTime"],
                "location": event.get("location", ""),
                "attendees": event.get("attendees", []),
                "html_link": event.get("htmlLink", ""),
            }
            
        except Exception as e:
            logger.warning(f"Событие не найдено или ошибка: {e}")
            return None
    
    def create_access_review_event(
        self,
        full_name: str,
        system: str,
        role: str,
        end_date: datetime,
        access_data: dict,
        spreadsheet_url: str = "",
        sheet_name: str = "",
        row_number: int = 0,
        reminder_days: list[int] | None = None,
        calendar_id: str = "primary",
    ) -> dict:
        """
        Создание специального события для ревью доступа.
        
        Args:
            full_name: ФИО пользователя
            system: Система
            role: Роль
            end_date: Дата окончания доступа
            access_data: Дополнительные данные доступа
            spreadsheet_url: Ссылка на Google Sheets
            sheet_name: Название вкладки
            row_number: Номер строки
            reminder_days: Дни напоминаний
            calendar_id: ID календаря
            
        Returns:
            Информация о созданном событии
        """
        # Формируем название
        if system and role:
            summary = f"[Access Review] Забрать доступ: {full_name} — {system} — {role}"
        else:
            summary = f"[Access Review] Забрать доступ: {full_name}"
        
        # Формируем описание
        description_lines = [
            "🔐 Доступ требует отзыва/проверки",
            "",
            f"👤 Пользователь: {full_name}",
            f"🖥️ Система: {system or 'Не указано'}",
            f"🎭 Роль: {role or 'Не указано'}",
            "",
            "📋 Детали:",
            f"• Логин: {access_data.get('login', 'Не указано')}",
            f"• Email: {access_data.get('email', 'Не указано')}",
            f"• Уровень доступа: {access_data.get('access_level', 'Не указано')}",
            f"• Основание: {access_data.get('reason', 'Не указано')}",
            f"• Номер заявки: {access_data.get('ticket_number', 'Не указано')}",
            "",
            "📅 Даты:",
            f"• Дата выдачи: {access_data.get('granted_date', 'Не указано')}",
            f"• Дата окончания: {access_data.get('end_date', 'Не указано')}",
            "",
            "✅ Действие: Забрать доступ",
            "",
            "🔗 Ссылки:",
            f"• Таблица: {spreadsheet_url or 'Не доступно'}",
            f"• Вкладка: {sheet_name or 'Не указано'}",
            f"• Строка: {row_number or 'Не указано'}",
            "",
            f"Владелец системы: {access_data.get('owner', 'Не указано')}",
            f"Ответственный ИБ: {access_data.get('security_contact', 'Не указано')}",
            f"Комментарий: {access_data.get('comment', '')}",
        ]
        
        description = "\n".join(description_lines)
        
        # Время события (09:00 по умолчанию)
        start_dt = end_date.replace(
            hour=config.DEFAULT_EVENT_HOUR,
            minute=config.DEFAULT_EVENT_MINUTE,
            second=0,
            microsecond=0,
        )
        
        # Событие длится 1 час
        end_dt = start_dt + timedelta(hours=1)
        
        return self.create_event(
            summary=summary,
            start_datetime=start_dt,
            end_datetime=end_dt,
            description=description,
            reminder_days=reminder_days,
            calendar_id=calendar_id,
        )


# Глобальный экземпляр
calendar_service = GoogleCalendarService()

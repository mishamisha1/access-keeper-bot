"""Работа с Google Calendar API."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from app.google.auth import get_google_auth

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Сервис для работы с Google Calendar."""
    
    def __init__(self):
        self.auth = get_google_auth()
    
    def _get_service(self) -> Optional[Resource]:
        """Получает сервис Google Calendar."""
        return self.auth.get_calendar_service()
    
    def create_event(
        self,
        summary: str,
        start_datetime: datetime,
        description: str = "",
        calendar_id: str = "primary",
        reminder_days: List[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Создаёт событие в календаре."""
        service = self._get_service()
        if not service:
            return None
        
        if reminder_days is None:
            reminder_days = [1, 0]  # За 1 день и в день события
        
        try:
            event = {
                "summary": summary,
                "description": description,
                "start": {
                    "dateTime": start_datetime.isoformat(),
                    "timeZone": "Asia/Almaty"
                },
                "end": {
                    "dateTime": (
                        start_datetime.replace(hour=start_datetime.hour + 1)
                    ).isoformat(),
                    "timeZone": "Asia/Almaty"
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": days * 24 * 60}
                        for days in reminder_days
                    ]
                }
            }
            
            result = service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            logger.info("Создано событие: %s", result["id"])
            return result
        except HttpError as e:
            logger.error("Ошибка создания события: %s", e)
            return None
    
    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start_datetime: Optional[datetime] = None,
        calendar_id: str = "primary"
    ) -> Optional[Dict[str, Any]]:
        """Обновляет событие в календаре."""
        service = self._get_service()
        if not service:
            return None
        
        try:
            # Получаем текущее событие
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Обновляем поля
            if summary:
                event["summary"] = summary
            if description:
                event["description"] = description
            if start_datetime:
                event["start"]["dateTime"] = start_datetime.isoformat()
                event["end"]["dateTime"] = (
                    start_datetime.replace(hour=start_datetime.hour + 1)
                ).isoformat()
            
            result = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info("Обновлено событие: %s", event_id)
            return result
        except HttpError as e:
            logger.error("Ошибка обновления события: %s", e)
            return None
    
    def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary"
    ) -> bool:
        """Удаляет событие из календаря."""
        service = self._get_service()
        if not service:
            return False
        
        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info("Удалено событие: %s", event_id)
            return True
        except HttpError as e:
            logger.error("Ошибка удаления события: %s", e)
            return False
    
    def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary"
    ) -> Optional[Dict[str, Any]]:
        """Получает информацию о событии."""
        service = self._get_service()
        if not service:
            return None
        
        try:
            result = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return result
        except HttpError as e:
            logger.error("Ошибка получения события: %s", e)
            return None
    
    def get_event_link(self, event_id: str, calendar_id: str = "primary") -> str:
        """Получает ссылку на событие."""
        return (
            f"https://calendar.google.com/calendar/event?eid={event_id}"
        )
    
    def list_events(
        self,
        time_min: datetime,
        time_max: datetime,
        calendar_id: str = "primary"
    ) -> List[Dict[str, Any]]:
        """Получает список событий за период."""
        service = self._get_service()
        if not service:
            return []
        
        try:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat() + "Z",
                timeMax=time_max.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            return events_result.get("items", [])
        except HttpError as e:
            logger.error("Ошибка получения списка событий: %s", e)
            return []

"""Сервис для работы с датами и временем."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
import re

import dateparser
from dateutil.relativedelta import relativedelta
import pytz

from app.config import TIMEZONE, DEFAULT_EVENT_HOUR, DEFAULT_EVENT_MINUTE

logger = logging.getLogger(__name__)


class DateService:
    """Сервис для парсинга и обработки дат."""
    
    def __init__(self, timezone: str = TIMEZONE):
        self.timezone = pytz.timezone(timezone)
        self.default_hour = DEFAULT_EVENT_HOUR
        self.default_minute = DEFAULT_EVENT_MINUTE
    
    def get_now(self) -> datetime:
        """Получает текущее время в настроенной таймзоне."""
        return datetime.now(self.timezone)
    
    def parse_duration(self, text: str) -> Optional[int]:
        """
        Парсит длительность из текста.
        
        Примеры:
        - "на 1 день" -> 1
        - "на 2 недели" -> 14
        - "на месяц" -> 30 (приблизительно)
        - "на 3 месяца" -> 90
        
        Возвращает количество дней или None.
        """
        text = text.lower().strip()
        
        # Паттерны для дней
        day_patterns = [
            r"на\s+(\d+)\s+дн",
            r"(\d+)\s+дн",
            r"на\s+(\d+)\s+день",
            r"(\d+)\s+день",
        ]
        
        for pattern in day_patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        
        # Паттерны для недель
        week_patterns = [
            r"на\s+(\d+)\s+нед",
            r"(\d+)\s+нед",
            r"на\s+(\d+)\s+недел",
            r"(\d+)\s+недел",
            r"на\s+неделю",
            r"недел",
        ]
        
        for pattern in week_patterns:
            match = re.search(pattern, text)
            if match:
                num = int(match.group(1)) if match.lastindex else 1
                return num * 7
        
        # Паттерны для месяцев
        month_patterns = [
            r"на\s+(\d+)\s+мес",
            r"(\d+)\s+мес",
            r"на\s+(\d+)\s+месяц",
            r"(\d+)\s+месяц",
            r"на\s+месяц",
            r"месяц",
        ]
        
        for pattern in month_patterns:
            match = re.search(pattern, text)
            if match:
                num = int(match.group(1)) if match.lastindex else 1
                return num * 30  # Приблизительно
        
        return None
    
    def parse_date_until(self, text: str) -> Optional[datetime]:
        """
        Парсит дату окончания из текста.
        
        Примеры:
        - "до завтра" -> завтра
        - "до пятницы" -> ближайшая пятница
        - "до конца недели" -> воскресенье
        - "до 15.07.2026" -> 15 июля 2026
        - "до 15 июля" -> 15 июля текущего года
        """
        text = text.lower().strip()
        now = self.get_now()
        
        # "до завтра"
        if "до завтра" in text or "до завтрашнего" in text:
            return self._set_time(now + timedelta(days=1))
        
        # "до конца недели"
        if "до конца недели" in text or "до конца текущей недели" in text:
            days_until_sunday = 6 - now.weekday()
            if days_until_sunday == 0:
                days_until_sunday = 7
            return self._set_time(now + timedelta(days=days_until_sunday))
        
        # "до пятницы" и другие дни недели
        weekdays = {
            "понедельник": 0,
            "вторник": 1,
            "среда": 2,
            "четверг": 3,
            "пятница": 4,
            "суббота": 5,
            "воскресенье": 6
        }
        
        for day_name, weekday_num in weekdays.items():
            if f"до {day_name}" in text:
                days_until = weekday_num - now.weekday()
                if days_until <= 0:
                    days_until += 7
                return self._set_time(now + timedelta(days=days_until))
        
        # "до конца месяца"
        if "до конца месяца" in text:
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            return self._set_time(next_month - timedelta(days=1))
        
        # Конкретная дата через dateparser
        # Ищем паттерны типа "до 15.07.2026", "до 15 июля", "до 2026-07-15"
        date_match = re.search(r"до\s+(\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{2,4})", text)
        if date_match:
            parsed = dateparser.parse(date_match.group(1), languages=["ru"])
            if parsed:
                return self._set_time(parsed)
        
        # Ищем дату без "до"
        parsed = dateparser.parse(text, languages=["ru"])
        if parsed:
            return self._set_time(parsed)
        
        return None
    
    def _set_time(self, dt: datetime) -> datetime:
        """Устанавливает время по умолчанию."""
        if isinstance(dt, datetime):
            return dt.replace(
                hour=self.default_hour,
                minute=self.default_minute,
                second=0,
                microsecond=0
            )
        return dt
    
    def calculate_end_date(
        self,
        start_date: Optional[datetime] = None,
        duration_days: Optional[int] = None,
        end_date: Optional[datetime] = None
    ) -> datetime:
        """
        Вычисляет дату окончания.
        
        Если указана duration_days, прибавляет её к start_date.
        Если указана end_date, возвращает её.
        По умолчанию использует текущую дату + duration_days.
        """
        if start_date is None:
            start_date = self.get_now()
        
        if end_date:
            return end_date
        
        if duration_days:
            return start_date + timedelta(days=duration_days)
        
        # По умолчанию 14 дней (2 недели)
        return start_date + timedelta(days=14)
    
    def parse_relative_date(self, text: str) -> Tuple[Optional[datetime], Optional[int]]:
        """
        Парсит относительную дату из текста.
        
        Возвращает кортеж (дата_окончания, длительность_в_днях).
        """
        # Сначала пробуем найти конкретную дату
        end_date = self.parse_date_until(text)
        if end_date:
            return end_date, None
        
        # Затем пробуем найти длительность
        duration = self.parse_duration(text)
        if duration:
            end_date = self.calculate_end_date(duration_days=duration)
            return end_date, duration
        
        return None, None
    
    def format_date(self, dt: datetime, format_str: str = "%Y-%m-%d") -> str:
        """Форматирует дату в строку."""
        return dt.strftime(format_str)
    
    def format_datetime(self, dt: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """Форматирует дату и время в строку."""
        return dt.strftime(format_str)
    
    def is_overdue(self, end_date: datetime) -> bool:
        """Проверяет, просрочена ли дата."""
        return self.get_now() > end_date
    
    def days_until(self, end_date: datetime) -> int:
        """Возвращает количество дней до даты."""
        delta = end_date - self.get_now()
        return delta.days

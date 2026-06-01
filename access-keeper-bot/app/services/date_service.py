"""
Сервис работы с датами и временем.
Соответствует требованиям ISO 27001 A.12.3.1 (резервное копирование) и A.12.4 (логирование).
Обрабатывает все форматы дат, временные зоны и относительные сроки.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
import re

import dateparser
from dateutil.relativedelta import relativedelta
from pytz import timezone, UnknownTimeZoneError

from app.config import config
from app.logging_config import get_logger

logger = get_logger(__name__)


class DateService:
    """
    Сервис для парсинга, нормализации и форматирования дат.
    Поддерживает русские и английские форматы, относительные сроки.
    """
    
    # Синонимы для дней недели на русском
    WEEKDAYS_RU = {
        "понедельник": 0,
        "пн": 0,
        "вторник": 1,
        "вт": 1,
        "среда": 2,
        "ср": 2,
        "четверг": 3,
        "чт": 3,
        "пятница": 4,
        "пт": 4,
        "суббота": 5,
        "сб": 5,
        "воскресенье": 6,
        "вс": 6,
    }
    
    # Паттерны для извлечения сроков
    DURATION_PATTERNS = [
        # "на X дней/дней"
        (r"на\s+(\d+)\s*дн[ейья]?", "days"),
        # "на X недель/недели"
        (r"на\s+(\d+)\s*нед[ельли]?", "weeks"),
        # "на X месяцев/месяц"
        (r"на\s+(\d+)\s*мес[яев]?ц?", "months"),
        # "на неделю"
        (r"на\s+неделю", "1_week"),
        # "на месяц"
        (r"на\s+месяц", "1_month"),
        # "на год"
        (r"на\s+год", "1_year"),
        # "до завтра"
        (r"до\s+завтра", "tomorrow"),
        # "до пятницы" и т.д.
        (r"до\s+(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье|пн|вт|ср|чт|пт|сб|вс)", "weekday"),
        # "до конца недели"
        (r"до\s+конца\s+недели", "end_of_week"),
        # "до конца месяца"
        (r"до\s+конца\s+месяца", "end_of_month"),
    ]
    
    def __init__(self, tz_name: str | None = None):
        """
        Инициализация сервиса дат.
        
        Args:
            tz_name: Название временной зоны (по умолчанию из config)
        """
        self.tz_name = tz_name or config.TIMEZONE
        try:
            self.timezone = timezone(self.tz_name)
        except UnknownTimeZoneError:
            logger.warning(f"Неизвестная временная зона {self.tz_name}, используем UTC")
            self.timezone = timezone("UTC")
            self.tz_name = "UTC"
    
    def get_now(self) -> datetime:
        """Получение текущего времени в настроенной временной зоне."""
        return datetime.now(self.timezone)
    
    def parse_relative_date(self, text: str) -> Optional[datetime]:
        """
        Парсинг относительных сроков из текста.
        
        Примеры:
        - "на 2 недели" -> сегодня + 14 дней
        - "на месяц" -> сегодня + 1 месяц
        - "до завтра" -> завтра
        - "до пятницы" -> ближайшая пятница
        - "до конца недели" -> воскресенье текущей недели
        
        Args:
            text: Текст со сроком
            
        Returns:
            datetime окончания или None если не найдено
        """
        text_lower = text.lower().strip()
        now = self.get_now()
        
        for pattern, duration_type in self.DURATION_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                if duration_type == "days":
                    days = int(match.group(1))
                    return now.replace(
                        hour=config.DEFAULT_EVENT_HOUR,
                        minute=config.DEFAULT_EVENT_MINUTE,
                        second=0,
                        microsecond=0
                    ) + timedelta(days=days)
                
                elif duration_type == "weeks":
                    weeks = int(match.group(1))
                    return now.replace(
                        hour=config.DEFAULT_EVENT_HOUR,
                        minute=config.DEFAULT_EVENT_MINUTE,
                        second=0,
                        microsecond=0
                    ) + timedelta(weeks=weeks)
                
                elif duration_type == "months":
                    months = int(match.group(1))
                    return (now + relativedelta(months=months)).replace(
                        hour=config.DEFAULT_EVENT_HOUR,
                        minute=config.DEFAULT_EVENT_MINUTE,
                        second=0,
                        microsecond=0
                    )
                
                elif duration_type == "1_week":
                    return now.replace(
                        hour=config.DEFAULT_EVENT_HOUR,
                        minute=config.DEFAULT_EVENT_MINUTE,
                        second=0,
                        microsecond=0
                    ) + timedelta(weeks=1)
                
                elif duration_type == "1_month":
                    return (now + relativedelta(months=1)).replace(
                        hour=config.DEFAULT_EVENT_HOUR,
                        minute=config.DEFAULT_EVENT_MINUTE,
                        second=0,
                        microsecond=0
                    )
                
                elif duration_type == "1_year":
                    return (now + relativedelta(years=1)).replace(
                        hour=config.DEFAULT_EVENT_HOUR,
                        minute=config.DEFAULT_EVENT_MINUTE,
                        second=0,
                        microsecond=0
                    )
                
                elif duration_type == "tomorrow":
                    tomorrow = now + timedelta(days=1)
                    return tomorrow.replace(
                        hour=config.DEFAULT_EVENT_HOUR,
                        minute=config.DEFAULT_EVENT_MINUTE,
                        second=0,
                        microsecond=0
                    )
                
                elif duration_type == "weekday":
                    weekday_name = match.group(1)
                    target_weekday = self.WEEKDAYS_RU.get(weekday_name)
                    if target_weekday is not None:
                        # Найти ближайший будущий день недели
                        days_ahead = target_weekday - now.weekday()
                        if days_ahead <= 0:  # Если уже прошел в этой неделе
                            days_ahead += 7
                        target_date = now + timedelta(days=days_ahead)
                        return target_date.replace(
                            hour=config.DEFAULT_EVENT_HOUR,
                            minute=config.DEFAULT_EVENT_MINUTE,
                            second=0,
                            microsecond=0
                        )
                
                elif duration_type == "end_of_week":
                    # До конца недели (воскресенье)
                    days_ahead = 6 - now.weekday()  # Воскресенье = 6
                    if days_ahead < 0:
                        days_ahead += 7
                    end_of_week = now + timedelta(days=days_ahead)
                    return end_of_week.replace(
                        hour=23,  # Конец дня
                        minute=59,
                        second=0,
                        microsecond=0
                    )
                
                elif duration_type == "end_of_month":
                    # До конца месяца
                    if now.month == 12:
                        end_of_month = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        end_of_month = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
                    return end_of_month.replace(
                        hour=23,
                        minute=59,
                        second=0,
                        microsecond=0
                    )
        
        return None
    
    def parse_absolute_date(self, text: str) -> Optional[datetime]:
        """
        Парсинг абсолютных дат из текста.
        
        Поддерживаемые форматы:
        - 15.07.2026
        - 2026-07-15
        - 15 июля
        - 15 июля 2026
        - July 15, 2026
        - 2026-07-15 14:30
        
        Args:
            text: Текст с датой
            
        Returns:
            datetime или None
        """
        # Используем dateparser для автоматического определения формата
        result = dateparser.parse(
            text,
            languages=["ru", "en"],
            settings={
                "TIMEZONE": self.tz_name,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
            }
        )
        
        if result:
            # Устанавливаем время по умолчанию если не указано
            if result.hour == 0 and result.minute == 0:
                result = result.replace(
                    hour=config.DEFAULT_EVENT_HOUR,
                    minute=config.DEFAULT_EVENT_MINUTE,
                )
            return result
        
        return None
    
    def parse_date_from_text(self, text: str) -> Optional[datetime]:
        """
        Универсальный парсер дат из текста.
        Сначала пытается найти относительный срок, затем абсолютную дату.
        
        Args:
            text: Текст с датой
            
        Returns:
            datetime или None
        """
        # Сначала пробуем относительные сроки
        relative_date = self.parse_relative_date(text)
        if relative_date:
            return relative_date
        
        # Затем пробуем абсолютные даты
        absolute_date = self.parse_absolute_date(text)
        if absolute_date:
            return absolute_date
        
        return None
    
    def calculate_end_date(
        self,
        start_date: datetime | None = None,
        duration_text: str | None = None,
        explicit_end_date: datetime | None = None,
    ) -> datetime:
        """
        Расчет даты окончания доступа.
        
        Args:
            start_date: Дата начала (по умолчанию сегодня)
            duration_text: Текст с длительностью ("на 2 недели", "до пятницы")
            explicit_end_date: Явно указанная дата окончания
            
        Returns:
            datetime окончания
        """
        if explicit_end_date:
            return explicit_end_date
        
        start = start_date or self.get_now()
        
        if duration_text:
            # Пробуем распарсить длительность из текста
            end_date = self.parse_date_from_text(duration_text)
            if end_date:
                return end_date
        
        # По умолчанию + 1 день если ничего не найдено
        return start.replace(
            hour=config.DEFAULT_EVENT_HOUR,
            minute=config.DEFAULT_EVENT_MINUTE,
            second=0,
            microsecond=0
        ) + timedelta(days=1)
    
    def format_datetime(self, dt: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """
        Форматирование datetime в строку.
        
        Args:
            dt: datetime для форматирования
            format_str: формат строки
            
        Returns:
            Отформатированная строка
        """
        # Конвертируем в нашу временную зону если нужно
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        else:
            dt = dt.astimezone(self.timezone)
        
        return dt.strftime(format_str)
    
    def format_date(self, dt: datetime, format_str: str = "%Y-%m-%d") -> str:
        """Форматирование только даты."""
        return self.format_datetime(dt, format_str)
    
    def is_overdue(self, end_date: datetime) -> bool:
        """
        Проверка, просрочена ли дата.
        
        Args:
            end_date: Дата окончания
            
        Returns:
            True если дата прошла
        """
        now = self.get_now()
        
        # Конвертируем в одну временную зону для сравнения
        if end_date.tzinfo is None:
            end_date = self.timezone.localize(end_date)
        else:
            end_date = end_date.astimezone(self.timezone)
        
        return now > end_date
    
    def days_until(self, end_date: datetime) -> int:
        """
        Количество дней до даты окончания.
        
        Args:
            end_date: Дата окончания
            
        Returns:
            Количество дней (отрицательное если дата прошла)
        """
        now = self.get_now()
        
        if end_date.tzinfo is None:
            end_date = self.timezone.localize(end_date)
        else:
            end_date = end_date.astimezone(self.timezone)
        
        delta = end_date - now
        return delta.days
    
    def create_event_datetime(
        self,
        date: datetime,
        hour: int | None = None,
        minute: int | None = None,
    ) -> datetime:
        """
        Создание datetime для события календаря.
        
        Args:
            date: Базовая дата
            hour: Час (по умолчанию из config)
            minute: Минута (по умолчанию из config)
            
        Returns:
            datetime для события
        """
        result = date.replace(
            hour=hour if hour is not None else config.DEFAULT_EVENT_HOUR,
            minute=minute if minute is not None else config.DEFAULT_EVENT_MINUTE,
            second=0,
            microsecond=0,
        )
        
        if result.tzinfo is None:
            result = self.timezone.localize(result)
        
        return result
    
    def parse_reminder_days(self, reminder_str: str) -> list[int]:
        """
        Парсинг строки с днями напоминаний.
        
        Args:
            reminder_str: Строка вида "1,0" или "7,3,0"
            
        Returns:
            Список дней для напоминаний
        """
        try:
            return [int(d.strip()) for d in reminder_str.split(",") if d.strip()]
        except ValueError:
            logger.warning(f"Некорректный формат напоминаний: {reminder_str}")
            return config.DEFAULT_REMINDER_DAYS


# Глобальный экземпляр сервиса
date_service = DateService()

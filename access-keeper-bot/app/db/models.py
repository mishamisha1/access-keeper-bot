"""
Модели данных для SQLite базы данных.
Соответствует требованиям ISO 27001 A.8.2 (управление информацией).
"""

import sqlite3
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """Модель пользователя Telegram."""
    id: Optional[int]
    telegram_user_id: int
    username: str
    created_at: datetime
    
    @classmethod
    def from_row(cls, row: tuple) -> "User":
        return cls(
            id=row[0],
            telegram_user_id=row[1],
            username=row[2],
            created_at=datetime.fromisoformat(row[3]) if row[3] else datetime.now(timezone.utc),
        )


@dataclass
class SavedSheet:
    """Модель сохраненной Google Sheets таблицы."""
    id: Optional[int]
    telegram_user_id: int
    spreadsheet_id: str
    spreadsheet_url: str
    title: str
    default_sheet_name: str
    created_at: datetime
    
    @classmethod
    def from_row(cls, row: tuple) -> "SavedSheet":
        return cls(
            id=row[0],
            telegram_user_id=row[1],
            spreadsheet_id=row[2],
            spreadsheet_url=row[3],
            title=row[4],
            default_sheet_name=row[5],
            created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(timezone.utc),
        )


@dataclass
class Settings:
    """Модель настроек пользователя."""
    id: Optional[int]
    telegram_user_id: int
    default_spreadsheet_id: Optional[str]
    default_sheet_name: str
    default_calendar_id: str
    timezone: str
    event_hour: int
    event_minute: int
    reminder_days: str  # CSV формат: "1,0"
    
    @classmethod
    def from_row(cls, row: tuple) -> "Settings":
        return cls(
            id=row[0],
            telegram_user_id=row[1],
            default_spreadsheet_id=row[2],
            default_sheet_name=row[3],
            default_calendar_id=row[4],
            timezone=row[5],
            event_hour=row[6],
            event_minute=row[7],
            reminder_days=row[8],
        )


@dataclass
class CreatedRecord:
    """Модель созданной записи доступа."""
    id: Optional[int]
    telegram_user_id: int
    spreadsheet_id: str
    sheet_name: str
    row_number: int
    calendar_event_id: Optional[str]
    calendar_event_link: Optional[str]
    full_name: str
    system: str
    role: str
    valid_until: str
    status: str
    created_at: datetime
    
    @classmethod
    def from_row(cls, row: tuple) -> "CreatedRecord":
        return cls(
            id=row[0],
            telegram_user_id=row[1],
            spreadsheet_id=row[2],
            sheet_name=row[3],
            row_number=row[4],
            calendar_event_id=row[5],
            calendar_event_link=row[6],
            full_name=row[7],
            system=row[8],
            role=row[9],
            valid_until=row[10],
            status=row[11],
            created_at=datetime.fromisoformat(row[12]) if row[12] else datetime.now(timezone.utc),
        )


@dataclass
class AccessHistoryEntry:
    """Модель записи истории изменений доступов."""
    id: Optional[int]
    telegram_user_id: int
    username: str
    action: str  # CREATED_ACCESS, EXTENDED_ACCESS, REVOKED_ACCESS, etc.
    spreadsheet_id: str
    sheet_name: str
    row_number: int
    full_name: str
    login: str
    system: str
    old_role: Optional[str]
    new_role: Optional[str]
    old_valid_until: Optional[str]
    new_valid_until: Optional[str]
    old_status: Optional[str]
    new_status: Optional[str]
    comment: str
    created_at: datetime
    
    @classmethod
    def from_row(cls, row: tuple) -> "AccessHistoryEntry":
        return cls(
            id=row[0],
            telegram_user_id=row[1],
            username=row[2],
            action=row[3],
            spreadsheet_id=row[4],
            sheet_name=row[5],
            row_number=row[6],
            full_name=row[7],
            login=row[8],
            system=row[9],
            old_role=row[10],
            new_role=row[11],
            old_valid_until=row[12],
            new_valid_until=row[13],
            old_status=row[14],
            new_status=row[15],
            comment=row[16],
            created_at=datetime.fromisoformat(row[17]) if row[17] else datetime.now(timezone.utc),
        )

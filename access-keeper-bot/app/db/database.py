"""
База данных SQLite для хранения настроек, истории и метаданных.
Соответствует требованиям ISO 27001 A.8.2 (управление информацией) и A.10.1.1 (шифрование).
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager

from app.config import config
from app.logging_config import get_logger
from app.db.models import (
    User,
    SavedSheet,
    Settings,
    CreatedRecord,
    AccessHistoryEntry,
)

logger = get_logger(__name__)


class Database:
    """
    Класс для работы с SQLite базой данных.
    Обеспечивает безопасное хранение настроек и истории действий.
    """
    
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or config.DB_PATH
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для безопасного подключения к БД."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка транзакции БД: {e}")
            raise
        finally:
            conn.close()
    
    def _init_database(self) -> None:
        """Инициализация таблиц базы данных."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица сохраненных таблиц
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_sheets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL,
                    spreadsheet_id TEXT NOT NULL,
                    spreadsheet_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    default_sheet_name TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_user_id) REFERENCES users(telegram_user_id)
                )
            """)
            
            # Таблица настроек
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER UNIQUE NOT NULL,
                    default_spreadsheet_id TEXT,
                    default_sheet_name TEXT NOT NULL DEFAULT 'Временные доступы',
                    default_calendar_id TEXT NOT NULL DEFAULT 'primary',
                    timezone TEXT NOT NULL DEFAULT 'Asia/Almaty',
                    event_hour INTEGER NOT NULL DEFAULT 9,
                    event_minute INTEGER NOT NULL DEFAULT 0,
                    reminder_days TEXT NOT NULL DEFAULT '1,0',
                    FOREIGN KEY (telegram_user_id) REFERENCES users(telegram_user_id)
                )
            """)
            
            # Таблица созданных записей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS created_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL,
                    spreadsheet_id TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    calendar_event_id TEXT,
                    calendar_event_link TEXT,
                    full_name TEXT NOT NULL,
                    system TEXT NOT NULL,
                    role TEXT NOT NULL,
                    valid_until TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Активен',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_user_id) REFERENCES users(telegram_user_id)
                )
            """)
            
            # Таблица истории изменений доступов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    spreadsheet_id TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    full_name TEXT NOT NULL,
                    login TEXT,
                    system TEXT,
                    old_role TEXT,
                    new_role TEXT,
                    old_valid_until TEXT,
                    new_valid_until TEXT,
                    old_status TEXT,
                    new_status TEXT,
                    comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_user_id) REFERENCES users(telegram_user_id)
                )
            """)
            
            # Индексы для производительности
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_telegram_id 
                ON users(telegram_user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_saved_sheets_telegram_id 
                ON saved_sheets(telegram_user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_records_telegram_id 
                ON created_records(telegram_user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_access_history_telegram_id 
                ON access_history(telegram_user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_access_history_action 
                ON access_history(action)
            """)
            
            logger.info("База данных инициализирована")
    
    # ==================== Пользователи ====================
    
    def upsert_user(self, telegram_user_id: int, username: str) -> User:
        """Создание или обновление пользователя."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (telegram_user_id, username, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    username = excluded.username
                RETURNING *
            """, (telegram_user_id, username, datetime.now(timezone.utc).isoformat()))
            
            row = cursor.fetchone()
            return User.from_row(tuple(row))
    
    def get_user(self, telegram_user_id: int) -> Optional[User]:
        """Получение пользователя по ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE telegram_user_id = ?",
                (telegram_user_id,)
            )
            row = cursor.fetchone()
            return User.from_row(tuple(row)) if row else None
    
    # ==================== Сохраненные таблицы ====================
    
    def save_sheet(
        self,
        telegram_user_id: int,
        spreadsheet_id: str,
        spreadsheet_url: str,
        title: str,
        default_sheet_name: str,
    ) -> SavedSheet:
        """Сохранение информации о таблице."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO saved_sheets 
                    (telegram_user_id, spreadsheet_id, spreadsheet_url, title, default_sheet_name)
                VALUES (?, ?, ?, ?, ?)
                RETURNING *
            """, (
                telegram_user_id,
                spreadsheet_id,
                spreadsheet_url,
                title,
                default_sheet_name,
            ))
            
            row = cursor.fetchone()
            return SavedSheet.from_row(tuple(row))
    
    def get_saved_sheets(self, telegram_user_id: int) -> list[SavedSheet]:
        """Получение всех сохраненных таблиц пользователя."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM saved_sheets WHERE telegram_user_id = ? ORDER BY created_at DESC",
                (telegram_user_id,)
            )
            return [SavedSheet.from_row(tuple(row)) for row in cursor.fetchall()]
    
    def delete_saved_sheet(self, telegram_user_id: int, sheet_id: int) -> bool:
        """Удаление сохраненной таблицы."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM saved_sheets WHERE id = ? AND telegram_user_id = ?",
                (sheet_id, telegram_user_id)
            )
            return cursor.rowcount > 0
    
    # ==================== Настройки ====================
    
    def upsert_settings(
        self,
        telegram_user_id: int,
        default_spreadsheet_id: Optional[str] = None,
        default_sheet_name: str = "Временные доступы",
        default_calendar_id: str = "primary",
        timezone_str: str = "Asia/Almaty",
        event_hour: int = 9,
        event_minute: int = 0,
        reminder_days: str = "1,0",
    ) -> Settings:
        """Создание или обновление настроек пользователя."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO settings 
                    (telegram_user_id, default_spreadsheet_id, default_sheet_name, 
                     default_calendar_id, timezone, event_hour, event_minute, reminder_days)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    default_spreadsheet_id = excluded.default_spreadsheet_id,
                    default_sheet_name = excluded.default_sheet_name,
                    default_calendar_id = excluded.default_calendar_id,
                    timezone = excluded.timezone,
                    event_hour = excluded.event_hour,
                    event_minute = excluded.event_minute,
                    reminder_days = excluded.reminder_days
                RETURNING *
            """, (
                telegram_user_id,
                default_spreadsheet_id,
                default_sheet_name,
                default_calendar_id,
                timezone_str,
                event_hour,
                event_minute,
                reminder_days,
            ))
            
            row = cursor.fetchone()
            return Settings.from_row(tuple(row))
    
    def get_settings(self, telegram_user_id: int) -> Optional[Settings]:
        """Получение настроек пользователя."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM settings WHERE telegram_user_id = ?",
                (telegram_user_id,)
            )
            row = cursor.fetchone()
            return Settings.from_row(tuple(row)) if row else None
    
    # ==================== Созданные записи ====================
    
    def save_created_record(
        self,
        telegram_user_id: int,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        full_name: str,
        system: str,
        role: str,
        valid_until: str,
        status: str = "Активен",
        calendar_event_id: Optional[str] = None,
        calendar_event_link: Optional[str] = None,
    ) -> CreatedRecord:
        """Сохранение информации о созданной записи доступа."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO created_records 
                    (telegram_user_id, spreadsheet_id, sheet_name, row_number,
                     calendar_event_id, calendar_event_link, full_name, system,
                     role, valid_until, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING *
            """, (
                telegram_user_id,
                spreadsheet_id,
                sheet_name,
                row_number,
                calendar_event_id,
                calendar_event_link,
                full_name,
                system,
                role,
                valid_until,
                status,
            ))
            
            row = cursor.fetchone()
            return CreatedRecord.from_row(tuple(row))
    
    def get_created_records(
        self, 
        telegram_user_id: int, 
        limit: int = 50
    ) -> list[CreatedRecord]:
        """Получение последних созданных записей."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM created_records 
                   WHERE telegram_user_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT ?""",
                (telegram_user_id, limit)
            )
            return [CreatedRecord.from_row(tuple(row)) for row in cursor.fetchall()]
    
    def update_record_calendar_info(
        self,
        record_id: int,
        calendar_event_id: str,
        calendar_event_link: str,
    ) -> bool:
        """Обновление информации о событии календаря."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE created_records 
                   SET calendar_event_id = ?, calendar_event_link = ?
                   WHERE id = ?""",
                (calendar_event_id, calendar_event_link, record_id)
            )
            return cursor.rowcount > 0
    
    # ==================== История изменений ====================
    
    def log_access_history(
        self,
        telegram_user_id: int,
        username: str,
        action: str,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        full_name: str,
        login: str = "",
        system: str = "",
        old_role: Optional[str] = None,
        new_role: Optional[str] = None,
        old_valid_until: Optional[str] = None,
        new_valid_until: Optional[str] = None,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        comment: str = "",
    ) -> AccessHistoryEntry:
        """Запись события в историю изменений доступов."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO access_history 
                    (telegram_user_id, username, action, spreadsheet_id, sheet_name,
                     row_number, full_name, login, system, old_role, new_role,
                     old_valid_until, new_valid_until, old_status, new_status, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING *
            """, (
                telegram_user_id,
                username,
                action,
                spreadsheet_id,
                sheet_name,
                row_number,
                full_name,
                login,
                system,
                old_role,
                new_role,
                old_valid_until,
                new_valid_until,
                old_status,
                new_status,
                comment,
            ))
            
            row = cursor.fetchone()
            entry = AccessHistoryEntry.from_row(tuple(row))
            logger.info(f"Запись в историю: {action} для {full_name}")
            return entry
    
    def get_access_history(
        self,
        telegram_user_id: int,
        action_filter: Optional[str] = None,
        limit: int = 100,
    ) -> list[AccessHistoryEntry]:
        """Получение истории изменений."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if action_filter:
                cursor.execute(
                    """SELECT * FROM access_history 
                       WHERE telegram_user_id = ? AND action = ?
                       ORDER BY created_at DESC 
                       LIMIT ?""",
                    (telegram_user_id, action_filter, limit)
                )
            else:
                cursor.execute(
                    """SELECT * FROM access_history 
                       WHERE telegram_user_id = ?
                       ORDER BY created_at DESC 
                       LIMIT ?""",
                    (telegram_user_id, limit)
                )
            
            return [AccessHistoryEntry.from_row(tuple(row)) for row in cursor.fetchall()]


# Глобальный экземпляр базы данных
db = Database()

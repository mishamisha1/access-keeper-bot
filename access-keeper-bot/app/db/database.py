"""База данных SQLite."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    """Класс для работы с SQLite базой данных."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Создаёт подключение к базе данных."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """Инициализирует таблицы базы данных."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица сохранённых таблиц
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                spreadsheet_id TEXT NOT NULL,
                spreadsheet_url TEXT,
                title TEXT,
                default_sheet_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_user_id) REFERENCES users(telegram_user_id)
            )
        """)
        
        # Таблица настроек
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER UNIQUE NOT NULL,
                default_spreadsheet_id TEXT,
                default_sheet_name TEXT DEFAULT 'Временные доступы',
                default_calendar_id TEXT DEFAULT 'primary',
                timezone TEXT DEFAULT 'Asia/Almaty',
                event_hour INTEGER DEFAULT 9,
                event_minute INTEGER DEFAULT 0,
                reminder_days TEXT DEFAULT '1,0',
                FOREIGN KEY (telegram_user_id) REFERENCES users(telegram_user_id)
            )
        """)
        
        # Талица созданных записей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS created_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                spreadsheet_id TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                row_number INTEGER,
                calendar_event_id TEXT,
                calendar_event_link TEXT,
                full_name TEXT,
                system TEXT,
                role TEXT,
                valid_until TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_user_id) REFERENCES users(telegram_user_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_user(self, telegram_user_id: int, username: Optional[str] = None) -> None:
        """Добавляет пользователя в базу данных."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (telegram_user_id, username) VALUES (?, ?)",
            (telegram_user_id, username)
        )
        conn.commit()
        conn.close()
    
    def get_user(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """Получает пользователя из базы данных."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE telegram_user_id = ?",
            (telegram_user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def save_sheet(
        self,
        telegram_user_id: int,
        spreadsheet_id: str,
        spreadsheet_url: str,
        title: str,
        default_sheet_name: Optional[str] = None
    ) -> int:
        """Сохраняет информацию о таблице."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO saved_sheets 
            (telegram_user_id, spreadsheet_id, spreadsheet_url, title, default_sheet_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            (telegram_user_id, spreadsheet_id, spreadsheet_url, title, default_sheet_name)
        )
        conn.commit()
        last_id = cursor.lastrowid
        conn.close()
        return last_id
    
    def get_saved_sheets(self, telegram_user_id: int) -> List[Dict[str, Any]]:
        """Получает список сохранённых таблиц пользователя."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM saved_sheets WHERE telegram_user_id = ? ORDER BY created_at DESC",
            (telegram_user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_default_sheet(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """Получает таблицу по умолчанию для пользователя."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ss.* FROM saved_sheets ss
            JOIN settings s ON ss.spreadsheet_id = s.default_spreadsheet_id
            WHERE s.telegram_user_id = ?
            """,
            (telegram_user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def save_settings(
        self,
        telegram_user_id: int,
        default_spreadsheet_id: Optional[str] = None,
        default_sheet_name: Optional[str] = None,
        default_calendar_id: Optional[str] = None,
        timezone: Optional[str] = None,
        event_hour: Optional[int] = None,
        event_minute: Optional[int] = None,
        reminder_days: Optional[str] = None
    ) -> None:
        """Сохраняет настройки пользователя."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Получаем текущие настройки
        cursor.execute(
            "SELECT * FROM settings WHERE telegram_user_id = ?",
            (telegram_user_id,)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующие настройки
            updates = []
            values = []
            
            if default_spreadsheet_id is not None:
                updates.append("default_spreadsheet_id = ?")
                values.append(default_spreadsheet_id)
            if default_sheet_name is not None:
                updates.append("default_sheet_name = ?")
                values.append(default_sheet_name)
            if default_calendar_id is not None:
                updates.append("default_calendar_id = ?")
                values.append(default_calendar_id)
            if timezone is not None:
                updates.append("timezone = ?")
                values.append(timezone)
            if event_hour is not None:
                updates.append("event_hour = ?")
                values.append(event_hour)
            if event_minute is not None:
                updates.append("event_minute = ?")
                values.append(event_minute)
            if reminder_days is not None:
                updates.append("reminder_days = ?")
                values.append(reminder_days)
            
            if updates:
                values.append(telegram_user_id)
                query = f"UPDATE settings SET {', '.join(updates)} WHERE telegram_user_id = ?"
                cursor.execute(query, values)
        else:
            # Создаём новые настройки
            cursor.execute(
                """
                INSERT INTO settings 
                (telegram_user_id, default_spreadsheet_id, default_sheet_name, 
                 default_calendar_id, timezone, event_hour, event_minute, reminder_days)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_user_id,
                    default_spreadsheet_id,
                    default_sheet_name or "Временные доступы",
                    default_calendar_id or "primary",
                    timezone or "Asia/Almaty",
                    event_hour or 9,
                    event_minute or 0,
                    reminder_days or "1,0"
                )
            )
        
        conn.commit()
        conn.close()
    
    def get_settings(self, telegram_user_id: int) -> Dict[str, Any]:
        """Получает настройки пользователя."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM settings WHERE telegram_user_id = ?",
            (telegram_user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        
        # Возвращаем настройки по умолчанию
        return {
            "telegram_user_id": telegram_user_id,
            "default_spreadsheet_id": None,
            "default_sheet_name": "Временные доступы",
            "default_calendar_id": "primary",
            "timezone": "Asia/Almaty",
            "event_hour": 9,
            "event_minute": 0,
            "reminder_days": "1,0"
        }
    
    def save_created_record(
        self,
        telegram_user_id: int,
        spreadsheet_id: str,
        sheet_name: str,
        row_number: int,
        calendar_event_id: Optional[str],
        calendar_event_link: Optional[str],
        full_name: str,
        system: Optional[str],
        role: Optional[str],
        valid_until: str,
        status: str
    ) -> int:
        """Сохраняет информацию о созданной записи."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO created_records 
            (telegram_user_id, spreadsheet_id, sheet_name, row_number,
             calendar_event_id, calendar_event_link, full_name, system, role,
             valid_until, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_user_id, spreadsheet_id, sheet_name, row_number,
                calendar_event_id, calendar_event_link, full_name, system, role,
                valid_until, status
            )
        )
        conn.commit()
        last_id = cursor.lastrowid
        conn.close()
        return last_id
    
    def get_created_records(
        self,
        telegram_user_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получает список созданных записей."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM created_records 
            WHERE telegram_user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (telegram_user_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

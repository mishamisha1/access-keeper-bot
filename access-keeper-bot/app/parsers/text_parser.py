"""Парсер текста для извлечения данных о доступе."""

import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from rapidfuzz import fuzz, process

from app.db.models import ParsedAccessRequest
from app.services.date_service import DateService

logger = logging.getLogger(__name__)


class TextParser:
    """Парсер свободного текста для извлечения данных о доступе."""
    
    # Синонимы для полей
    FIELD_SYNONYMS = {
        "full_name": [
            "фио", "фамилия", "имя", "отчество", "пользователь", 
            "сотрудник", "user", "employee", "full name", "name",
            "кто", "кому"
        ],
        "login": [
            "логин", "login", "username", "user name", "уз", 
            "учетная запись", "account", "account name", "ник",
            "юзернейм"
        ],
        "email": [
            "email", "mail", "почта", "e-mail", "эмэйл", "адрес"
        ],
        "system": [
            "система", "system", "application", "app", 
            "информационная система", "ис", "сервис", "service",
            "программа", "продукт"
        ],
        "role": [
            "роль", "role", "group", "ad group", "security group",
            "permission group", "должность", "позиция", "права"
        ],
        "access_level": [
            "access", "permission", "права", "уровень доступа",
            "access level", "rights", "доступ"
        ],
        "reason": [
            "reason", "основание", "business justification",
            "justification", "причина", "цель", "зачем", "для чего"
        ],
        "ticket_number": [
            "ticket", "request", "заявка", "номер заявки",
            "inc", "req", "sr", "номер", "тикет"
        ]
    }
    
    # Привилегированные роли
    PRIVILEGED_ROLES = [
        "admin", "administrator", "root", "superuser", "owner",
        "privileged", "domain admin", "global admin", "security admin",
        "админ", "администратор", "суперюзер"
    ]
    
    def __init__(self):
        self.date_service = DateService()
    
    def parse(self, text: str) -> ParsedAccessRequest:
        """
        Парсит текст и извлекает данные о доступе.
        
        Примеры:
        - "Саксонов Михаил, доступ на 2 недели, основание: совместная работа"
        - "Иванов Иван доступ на 3 дня в Jira, причина: временная задача"
        """
        request = ParsedAccessRequest(raw_text=text)
        text_lower = text.lower()
        
        # Извлекаем ФИО
        request.full_name = self._extract_full_name(text)
        
        # Извлекаем логин
        request.login = self._extract_login(text)
        
        # Извлекаем email
        request.email = self._extract_email(text)
        
        # Извлекаем систему
        request.system = self._extract_system(text)
        
        # Извлекаем роль
        request.role = self._extract_role(text)
        
        # Извлекаем уровень доступа
        request.access_level = self._extract_access_level(text)
        
        # Извлекаем основание
        request.reason = self._extract_reason(text)
        
        # Извлекаем номер заявки
        request.ticket_number = self._extract_ticket_number(text)
        
        # Извлекаем дату окончания и длительность
        end_date, duration = self.date_service.parse_relative_date(text)
        request.valid_until = end_date
        request.duration_days = duration
        
        # Дата выдачи - сегодня
        request.granted_at = self.date_service.get_now()
        
        # Время события по умолчанию
        request.event_time = f"{self.date_service.default_hour:02d}:{self.date_service.default_minute:02d}:00"
        
        # Действие по умолчанию
        request.action = "Забрать доступ"
        
        # Определяем недостающие поля
        request.missing_fields = self._get_missing_fields(request)
        
        # Вычисляем уверенность парсинга
        request.confidence = self._calculate_confidence(request)
        
        return request
    
    def _extract_full_name(self, text: str) -> Optional[str]:
        """Извлекает ФИО из текста."""
        # Паттерн: имя фамилия (два слова с заглавной буквы в начале)
        pattern = r"^([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        
        # Ищем после ключевых слов
        for synonym in self.FIELD_SYNONYMS["full_name"]:
            pattern = rf"{synonym}[:\s]+([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_login(self, text: str) -> Optional[str]:
        """Извлекает логин из текста."""
        # Паттерн: логин@ или login: или username:
        patterns = [
            r"логин[:\s]+([a-zA-Z0-9_\.@-]+)",
            r"login[:\s]+([a-zA-Z0-9_\.@-]+)",
            r"username[:\s]+([a-zA-Z0-9_\.@-]+)",
            r"@\s*([a-zA-Z0-9_\.@-]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Извлекает email из текста."""
        pattern = r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_system(self, text: str) -> Optional[str]:
        """Извлекает название системы из текста."""
        # Ищем после ключевых слов
        for synonym in self.FIELD_SYNONYMS["system"]:
            pattern = rf"(?:в|на|для)?\s*{synonym}[:\s]+([^\s,\.]+)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                system = match.group(1).strip()
                # Исключаем слова-паразиты
                if system.lower() not in ["доступ", "на", "в", "для"]:
                    return system
        
        # Ищем известные системы
        known_systems = [
            "jira", "confluence", "splunk", "gitlab", "github",
            "bitbucket", "jenkins", "kubernetes", "docker", "aws",
            "azure", "gcp", "1c", "sap", "oracle", "active directory",
            "ad", "ldap", "vpn", "citrix", "rds", "ssh"
        ]
        
        for system in known_systems:
            if system in text.lower():
                return system.title()
        
        return None
    
    def _extract_role(self, text: str) -> Optional[str]:
        """Извлекает роль из текста."""
        # Ищем после ключевых слов
        for synonym in self.FIELD_SYNONYMS["role"]:
            pattern = rf"{synonym}[:\s]+([^\s,\.]+)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                role = match.group(1).strip()
                if role.lower() not in ["доступ", "на", "в", "для"]:
                    return role
        
        # Ищем паттерны типа "read-only", "admin", "developer"
        patterns = [
            r"([a-z]+-only)",
            r"([a-z]+admin)",
            r"(developer)",
            r"(manager)",
            r"(analyst)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(1)
        
        return None
    
    def _extract_access_level(self, text: str) -> Optional[str]:
        """Извлекает уровень доступа."""
        levels = {
            "read": "Чтение",
            "write": "Запись",
            "modify": "Изменение",
            "delete": "Удаление",
            "admin": "Администратор",
            "full": "Полный",
            "readonly": "Только чтение",
            "read-only": "Только чтение",
        }
        
        for key, value in levels.items():
            if key in text.lower():
                return value
        
        return None
    
    def _extract_reason(self, text: str) -> Optional[str]:
        """Извлекает основание/причину."""
        for synonym in self.FIELD_SYNONYMS["reason"]:
            pattern = rf"{synonym}[:\s]+(.+?)(?:,|$)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_ticket_number(self, text: str) -> Optional[str]:
        """Извлекает номер заявки."""
        # Паттерны: INC-12345, REQ-123, SR12345
        patterns = [
            r"(INC[-\s]?\d+)",
            r"(REQ[-\s]?\d+)",
            r"(SR[-\s]?\d+)",
            r"(TICKET[-\s]?\d+)",
            r"(ЗАЯВК[АЕ][-\s]?\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper().replace(" ", "-")
        
        return None
    
    def _get_missing_fields(self, request: ParsedAccessRequest) -> List[str]:
        """Определяет недостающие обязательные поля."""
        missing = []
        
        if not request.full_name:
            missing.append("full_name")
        
        if not request.valid_until:
            missing.append("valid_until")
        
        return missing
    
    def _calculate_confidence(self, request: ParsedAccessRequest) -> float:
        """Вычисляет уверенность парсинга."""
        total_fields = 8  # full_name, login, email, system, role, reason, ticket, valid_until
        filled_fields = sum([
            bool(request.full_name),
            bool(request.login),
            bool(request.email),
            bool(request.system),
            bool(request.role),
            bool(request.reason),
            bool(request.ticket_number),
            bool(request.valid_until),
        ])
        
        return filled_fields / total_fields
    
    def is_privileged_role(self, role: str) -> bool:
        """Проверяет, является ли роль привилегированной."""
        if not role:
            return False
        
        role_lower = role.lower()
        return any(priv in role_lower for priv in self.PRIVILEGED_ROLES)

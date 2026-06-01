"""
Парсер свободного текста для извлечения данных о доступах.
Соответствует требованиям ISO 27001 A.8.2 (управление информацией).
Использует NLP-подход для понимания человеческих формулировок.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from rapidfuzz import fuzz, process

from app.logging_config import get_logger
from app.services.date_service import date_service

logger = get_logger(__name__)


@dataclass
class ParsedAccessRequest:
    """Результат парсинга запроса на доступ."""
    
    full_name: str = ""
    login: str = ""
    email: str = ""
    system: str = ""
    role: str = ""
    access_level: str = ""
    duration_text: str = ""
    reason: str = ""
    ticket_number: str = ""
    granted_date: Optional[str] = None
    end_date: Optional[str] = None
    action_after_expiry: str = "Забрать доступ"
    
    # Дополнительные поля
    department: str = ""
    owner: str = ""
    security_contact: str = ""
    comment: str = ""
    
    # Флаги валидности
    is_valid: bool = False
    missing_fields: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    
    def to_dict(self) -> dict:
        """Конвертация в словарь."""
        return {
            "full_name": self.full_name,
            "login": self.login,
            "email": self.email,
            "system": self.system,
            "role": self.role,
            "access_level": self.access_level,
            "duration_text": self.duration_text,
            "reason": self.reason,
            "ticket_number": self.ticket_number,
            "granted_date": self.granted_date,
            "end_date": self.end_date,
            "action_after_expiry": self.action_after_expiry,
            "department": self.department,
            "owner": self.owner,
            "security_contact": self.security_contact,
            "comment": self.comment,
        }
    
    def get_preview_text(self) -> str:
        """Текст для preview пользователю."""
        lines = [
            "📋 *Распознанные данные:*",
            f"• *Пользователь:* {self.full_name or 'Не указано'}",
            f"• *Логин:* {self.login or 'Не указано'}",
            f"• *Email:* {self.email or 'Не указано'}",
            f"• *Система:* {self.system or 'Не указано'}",
            f"• *Роль:* {self.role or 'Не указано'}",
            f"• *Уровень доступа:* {self.access_level or 'Не указано'}",
            f"• *Срок доступа:* {self.duration_text or 'Не указано'}",
            f"• *Дата выдачи:* {self.granted_date or 'Сегодня'}",
            f"• *Дата окончания:* {self.end_date or 'Не рассчитана'}",
            f"• *Основание:* {self.reason or 'Не указано'}",
            f"• *Номер заявки:* {self.ticket_number or 'Не указано'}",
            f"• *Действие:* {self.action_after_expiry}",
        ]
        
        if self.missing_fields:
            lines.append(f"\n⚠️ *Не хватает:* {', '.join(self.missing_fields)}")
        
        return "\n".join(lines)


class TextParser:
    """
    Парсер свободного текста для извлечения данных о доступах.
    Поддерживает русские и английские формулировки.
    """
    
    # Паттерны для извлечения ФИО
    NAME_PATTERNS = [
        # "Саксонов Михаил"
        r"([А-Я][а-я]+\s+[А-Я][а-я]+)",
        # "Иванов Иван Иванович"
        r"([А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+)",
        # Английские имена "John Doe"
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)",
    ]
    
    # Паттерны для систем
    SYSTEM_KEYWORDS = [
        "jira", "confluence", "splunk", "gitlab", "github",
        "bitbucket", "jenkins", "kubernetes", "docker",
        "aws", "azure", "gcp", "1c", "sap", "oracle",
        "active directory", "ad", "ldap", "vpn",
        "почта", "email", "exchange", "outlook",
        "crm", "erp", "itsm", "servicedesk",
    ]
    
    # Паттерны для ролей
    ROLE_KEYWORDS = [
        "admin", "administrator", "root", "superuser",
        "developer", "dev", "разработчик",
        "manager", "менеджер", "руководитель",
        "analyst", "аналитик",
        "viewer", "reader", "читатель", "read-only",
        "editor", "редактор",
        "owner", "владелец",
        "user", "пользователь",
        "guest", "гость",
        "auditor", "аудитор",
        "security", "безопасность",
    ]
    
    # Синонимы для полей
    FIELD_SYNONYMS = {
        "full_name": ["фио", "фамилия", "имя", "пользователь", "сотрудник", "name", "user", "employee"],
        "login": ["логин", "username", "учетная запись", "уз", "account", "uid"],
        "email": ["email", "почта", "e-mail", "mail", "электронная почта"],
        "system": ["система", "system", "application", "app", "сервис", "ис", "программа"],
        "role": ["роль", "role", "group", "должность", "позиция", "position"],
        "access_level": ["доступ", "уровень", "level", "права", "rights", "permission"],
        "reason": ["основание", "причина", "reason", "justification", "зачем", "для чего"],
        "ticket": ["заявка", "номер", "ticket", "request", "inc", "req", "sr", "task"],
        "duration": ["срок", "длительность", "на сколько", "до когда", "duration", "period"],
    }
    
    def __init__(self):
        """Инициализация парсера."""
        pass
    
    def parse(self, text: str) -> ParsedAccessRequest:
        """
        Основной метод парсинга текста.
        
        Args:
            text: Исходный текст запроса
            
        Returns:
            ParsedAccessRequest с извлеченными данными
        """
        result = ParsedAccessRequest()
        text_lower = text.lower()
        
        # Извлекаем ФИО
        result.full_name = self._extract_name(text)
        
        # Извлекаем логин (может быть в формате @username или login)
        result.login = self._extract_login(text)
        
        # Извлекаем email
        result.email = self._extract_email(text)
        
        # Извлекаем систему
        result.system = self._extract_system(text)
        
        # Извлекаем роль
        result.role = self._extract_role(text)
        
        # Извлекаем уровень доступа
        result.access_level = self._extract_access_level(text)
        
        # Извлекаем срок доступа
        duration_info = self._extract_duration(text)
        result.duration_text = duration_info.get("text", "")
        result.end_date = duration_info.get("end_date")
        
        # Извлекаем основание
        result.reason = self._extract_reason(text)
        
        # Извлекаем номер заявки
        result.ticket_number = self._extract_ticket(text)
        
        # Определяем действие после окончания срока
        result.action_after_expiry = self._extract_action(text)
        
        # Валидация результата
        self._validate_result(result)
        
        # Расчет confidence score
        result.confidence_score = self._calculate_confidence(result)
        
        return result
    
    def _extract_name(self, text: str) -> str:
        """Извлечение ФИО из текста."""
        for pattern in self.NAME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                # Проверка что это не часть другого слова
                if len(name) >= 5:
                    return name.title()
        return ""
    
    def _extract_login(self, text: str) -> str:
        """Извлечение логина из текста."""
        # Паттерн @username
        match = re.search(r"@(\w+)", text)
        if match:
            return match.group(1)
        
        # Паттерн "логин: xxx" или "login: xxx"
        match = re.search(r"(?:логин|login|username)[:\s]+(\w+)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return ""
    
    def _extract_email(self, text: str) -> str:
        """Извлечение email из текста."""
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        if match:
            return match.group(0)
        return ""
    
    def _extract_system(self, text: str) -> str:
        """Извлечение названия системы из текста."""
        text_lower = text.lower()
        
        # Поиск по ключевым словам
        found_systems = []
        for keyword in self.SYSTEM_KEYWORDS:
            if keyword in text_lower:
                found_systems.append(keyword)
        
        if found_systems:
            # Возвращаем первое найденное или объединяем
            return found_systems[0].title()
        
        # Паттерн "в системе XXX" или "в XXX"
        match = re.search(r"(?:в\s+(?:системе\s+)?)([A-Z][A-Za-z0-9\-\.]+)", text)
        if match:
            system = match.group(1)
            if len(system) <= 20:  # Защита от ложных срабатываний
                return system
        
        return ""
    
    def _extract_role(self, text: str) -> str:
        """Извлечение роли из текста."""
        text_lower = text.lower()
        
        # Поиск по ключевым словам
        found_roles = []
        for keyword in self.ROLE_KEYWORDS:
            if re.search(rf"\b{keyword}\b", text_lower):
                found_roles.append(keyword)
        
        if found_roles:
            return found_roles[0].title()
        
        # Паттерн "роль: XXX" или "как XXX"
        match = re.search(r"(?:роль|как)\s*[:\s]?\s*([A-Za-zА-Яа-я\-]+)", text, re.IGNORECASE)
        if match:
            role = match.group(1)
            if role.lower() not in ["на", "для", "с", "и"]:
                return role.title()
        
        return ""
    
    def _extract_access_level(self, text: str) -> str:
        """Извлечение уровня доступа."""
        text_lower = text.lower()
        
        levels = {
            "read-only": "Чтение",
            "read only": "Чтение",
            "только чтение": "Чтение",
            "чтение": "Чтение",
            "запись": "Запись",
            "write": "Запись",
            "изменение": "Изменение",
            "modify": "Изменение",
            "удаление": "Удаление",
            "delete": "Удаление",
            "admin": "Администратор",
            "administrator": "Администратор",
            "полный": "Полный",
            "full": "Полный",
        }
        
        for key, value in levels.items():
            if key in text_lower:
                return value
        
        return ""
    
    def _extract_duration(self, text: str) -> dict:
        """Извлечение срока доступа."""
        result = {"text": "", "end_date": None}
        
        # Используем date_service для парсинга
        end_date = date_service.parse_date_from_text(text)
        
        if end_date:
            # Попытка найти текст с длительностью
            patterns = [
                r"на\s+\d+\s*(дн[ейья]?|нед[ельли]?|мес[яев]?ц?)",
                r"на\s+(неделю|месяц|год)",
                r"до\s+(завтра|пятницы|понедельника|конца\s+(недели|месяца))",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    result["text"] = match.group(0)
                    break
            
            if not result["text"]:
                result["text"] = "указан в тексте"
            
            result["end_date"] = date_service.format_datetime(end_date)
        
        return result
    
    def _extract_reason(self, text: str) -> str:
        """Извлечение основания/причины."""
        # Паттерны для основания
        patterns = [
            r"(?:основание|причина|reason|justification)[:\s]+(.+?)(?:,|$)",
            r"(?:для\s+чего|зачем)[:\s]+(.+?)(?:,|$)",
            r"(?:совместная\s+работа|временная\s+задача|проект|аудит|проверка)[^,\.]*",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                reason = match.group(1).strip() if len(match.groups()) > 0 else match.group(0)
                return reason.strip().rstrip(",.")
        
        return ""
    
    def _extract_ticket(self, text: str) -> str:
        """Извлечение номера заявки."""
        # Паттерны для номеров заявок: INC-12345, REQ-123, SR123, DEV-123
        patterns = [
            r"\b(INC|REQ|SR|TASK|DEV|OPS|SEC|IT)[\-]?(\d+)\b",
            r"\bзаявка\s*[:\s]?\s*(\d+)",
            r"\bномер\s*[:\s]?\s*(\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) > 1:
                    return f"{match.group(1).upper()}-{match.group(2)}"
                else:
                    return match.group(1)
        
        return ""
    
    def _extract_action(self, text: str) -> str:
        """Извлечение действия после окончания срока."""
        text_lower = text.lower()
        
        actions = {
            "забрать": "Забрать доступ",
            "отозвать": "Отозвать доступ",
            "продлить": "Продлить автоматически",
            "пересмотреть": "Пересмотреть доступ",
            "уведомить": "Уведомить владельца",
        }
        
        for key, value in actions.items():
            if key in text_lower:
                return value
        
        return "Забрать доступ"  # По умолчанию
    
    def _validate_result(self, result: ParsedAccessRequest) -> None:
        """Валидация результата парсинга."""
        missing = []
        
        if not result.full_name:
            missing.append("ФИО пользователя")
        
        if not result.end_date:
            missing.append("Срок доступа")
        
        # Основание не обязательно, но желательно
        # if not result.reason:
        #     missing.append("Основание доступа")
        
        result.missing_fields = missing
        result.is_valid = len(missing) == 0
    
    def _calculate_confidence(self, result: ParsedAccessRequest) -> float:
        """
        Расчет уверенности парсинга (0-100%).
        
        Учитывает:
        - Наличие обязательных полей
        - Количество заполненных полей
        - Качество извлечения (длина строк)
        """
        score = 0.0
        max_score = 100.0
        
        # Обязательные поля (60% веса)
        if result.full_name:
            score += 30
        if result.end_date:
            score += 30
        
        # Дополнительные поля (40% веса)
        filled_optional = sum([
            bool(result.login),
            bool(result.email),
            bool(result.system),
            bool(result.role),
            bool(result.reason),
        ])
        score += (filled_optional / 5) * 40
        
        # Бонус за качество извлечения
        if len(result.full_name) > 10:
            score += 10
        if len(result.reason) > 10:
            score += 10
        
        return min(score, max_score)


# Глобальный экземпляр парсера
text_parser = TextParser()

"""Модели данных."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class AccessRecord:
    """Запись о доступе."""
    full_name: str
    login: Optional[str] = None
    email: Optional[str] = None
    system: Optional[str] = None
    role: Optional[str] = None
    access_level: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    employee_id: Optional[str] = None
    manager: Optional[str] = None
    
    # Права доступа
    read_permission: bool = False
    write_permission: bool = False
    modify_permission: bool = False
    delete_permission: bool = False
    admin_permission: bool = False
    privileged_access: bool = False
    
    # Основание и заявки
    reason: Optional[str] = None
    ticket_number: Optional[str] = None
    
    # Даты
    granted_at: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    last_review: Optional[datetime] = None
    next_review: Optional[datetime] = None
    
    # Статусы
    status: str = "Активен"
    review_status: Optional[str] = None
    next_action: Optional[str] = None
    
    # Владелец и ответственный
    system_owner: Optional[str] = None
    security_owner: Optional[str] = None
    
    # Calendar
    calendar_event_id: Optional[str] = None
    calendar_event_link: Optional[str] = None
    
    # Дополнительно
    row_number: Optional[int] = None
    added_by: Optional[str] = None
    created_at: Optional[datetime] = None
    comment: Optional[str] = None
    
    # Для ревью
    confirmed_by_owner: Optional[bool] = None
    keep_access: Optional[bool] = None
    revoke_access: Optional[bool] = None
    revoke_reason: Optional[str] = None
    
    # Для PCI DSS / ISO
    system_criticality: Optional[str] = None
    last_login_date: Optional[datetime] = None
    corrective_action: Optional[str] = None
    action_owner: Optional[str] = None
    deadline: Optional[datetime] = None
    result: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует запись в словарь."""
        return {
            "full_name": self.full_name,
            "login": self.login,
            "email": self.email,
            "system": self.system,
            "role": self.role,
            "access_level": self.access_level,
            "department": self.department,
            "position": self.position,
            "employee_id": self.employee_id,
            "manager": self.manager,
            "read_permission": "Да" if self.read_permission else "Нет",
            "write_permission": "Да" if self.write_permission else "Нет",
            "modify_permission": "Да" if self.modify_permission else "Нет",
            "delete_permission": "Да" if self.delete_permission else "Нет",
            "admin_permission": "Да" if self.admin_permission else "Нет",
            "privileged_access": "Да" if self.privileged_access else "Нет",
            "reason": self.reason,
            "ticket_number": self.ticket_number,
            "granted_at": self.granted_at.strftime("%Y-%m-%d") if self.granted_at else None,
            "valid_until": self.valid_until.strftime("%Y-%m-%d") if self.valid_until else None,
            "last_review": self.last_review.strftime("%Y-%m-%d") if self.last_review else None,
            "next_review": self.next_review.strftime("%Y-%m-%d") if self.next_review else None,
            "status": self.status,
            "review_status": self.review_status,
            "next_action": self.next_action,
            "system_owner": self.system_owner,
            "security_owner": self.security_owner,
            "calendar_event_id": self.calendar_event_id,
            "calendar_event_link": self.calendar_event_link,
            "row_number": self.row_number,
            "added_by": self.added_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
            "comment": self.comment,
            "confirmed_by_owner": "Да" if self.confirmed_by_owner else "Нет" if self.confirmed_by_owner is not None else None,
            "keep_access": "Да" if self.keep_access else "Нет" if self.keep_access is not None else None,
            "revoke_access": "Да" if self.revoke_access else "Нет" if self.revoke_access is not None else None,
            "revoke_reason": self.revoke_reason,
            "system_criticality": self.system_criticality,
            "last_login_date": self.last_login_date.strftime("%Y-%m-%d") if self.last_login_date else None,
            "corrective_action": self.corrective_action,
            "action_owner": self.action_owner,
            "deadline": self.deadline.strftime("%Y-%m-%d") if self.deadline else None,
            "result": self.result,
        }


@dataclass
class ParsedAccessRequest:
    """Результат парсинга запроса на доступ."""
    full_name: Optional[str] = None
    login: Optional[str] = None
    email: Optional[str] = None
    system: Optional[str] = None
    role: Optional[str] = None
    access_level: Optional[str] = None
    reason: Optional[str] = None
    ticket_number: Optional[str] = None
    duration_days: Optional[int] = None
    valid_until: Optional[datetime] = None
    granted_at: Optional[datetime] = None
    event_time: Optional[str] = None
    action: Optional[str] = None
    raw_text: str = ""
    confidence: float = 0.0
    missing_fields: List[str] = field(default_factory=list)
    
    def is_complete(self) -> bool:
        """Проверяет, хватает ли данных для создания записи."""
        required = ["full_name", "valid_until"]
        return all(getattr(self, field) for field in required)


@dataclass
class ColumnMapping:
    """Маппинг колонок."""
    source_column: str
    target_column: str
    confidence: float
    column_type: str  # тип целевой колонки

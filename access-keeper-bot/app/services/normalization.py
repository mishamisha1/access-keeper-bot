"""Data normalization service for access records."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.date_service import DateService


class NormalizationService:
    """Normalize and validate access data."""
    
    # Status mappings
    STATUS_MAPPINGS = {
        'active': 'Активен',
        'enabled': 'Активен',
        'активен': 'Активен',
        'активный': 'Активен',
        'да': 'Активен',
        'yes': 'Активен',
        'true': 'Активен',
        
        'disabled': 'Отключен',
        'отключен': 'Отключен',
        'нет': 'Отключен',
        'no': 'Отключен',
        'false': 'Отключен',
        
        'review': 'На ревью',
        'на проверке': 'На ревью',
        'ревью': 'На ревью',
        'pending review': 'На ревью',
        'на ревью': 'На ревью',
        
        'temporary': 'Временный',
        'временный': 'Временный',
        'temp': 'Временный',
        
        'revoked': 'Отозван',
        'отозван': 'Отозван',
        'cancelled': 'Отозван',
        'отменен': 'Отозван',
        
        'overdue': 'Просрочен',
        'просрочен': 'Просрочен',
        'expired': 'Просрочен',
        'истек': 'Просрочен',
        
        'error': 'Ошибка',
        'ошибка': 'Ошибка',
        'failed': 'Ошибка',
    }
    
    # Privileged role patterns
    PRIVILEGED_PATTERNS = [
        r'admin',
        r'administrator',
        r'root',
        r'superuser',
        r'owner',
        r'privileged',
        r'domain\s*admin',
        r'global\s*admin',
        r'security\s*admin',
        r'sysadmin',
        r'system\s*admin',
        r'database\s*admin',
        r'db\s*admin',
        r'network\s*admin',
        r'infrastructure\s*admin',
        r'cloud\s*admin',
        r'aws\s*admin',
        r'azure\s*admin',
        r'gcp\s*admin',
        r'full\s*access',
        r'unrestricted',
        r'elevated',
        r'power\s*user',
        r'sudo',
        r'backup\s*admin',
        r'recovery\s*admin',
        r'emergency',
        r'break\s*glass',
        r'break-glass',
        r'breakglass',
    ]
    
    def __init__(self):
        self.date_service = DateService()
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.PRIVILEGED_PATTERNS]
    
    def normalize_status(self, status: Optional[str]) -> str:
        """Normalize status value to standard Russian format."""
        if not status:
            return 'Активен'
        
        status_lower = str(status).lower().strip()
        
        # Direct mapping
        if status_lower in self.STATUS_MAPPINGS:
            return self.STATUS_MAPPINGS[status_lower]
        
        # Check partial matches
        for key, value in self.STATUS_MAPPINGS.items():
            if key in status_lower:
                return value
        
        # Default
        return 'Активен'
    
    def normalize_full_name(self, name: Optional[str]) -> str:
        """Normalize full name (capitalize properly)."""
        if not name:
            return ''
        
        name = str(name).strip()
        
        # Remove extra spaces
        name = re.sub(r'\s+', ' ', name)
        
        # Capitalize each part
        parts = name.split(' ')
        normalized_parts = []
        for part in parts:
            if part:
                normalized_parts.append(part.capitalize())
        
        return ' '.join(normalized_parts)
    
    def normalize_email(self, email: Optional[str]) -> str:
        """Normalize email address."""
        if not email:
            return ''
        
        email = str(email).strip().lower()
        
        # Basic email validation
        if '@' in email and '.' in email:
            return email
        
        return ''
    
    def normalize_login(self, login: Optional[str]) -> str:
        """Normalize login/username."""
        if not login:
            return ''
        
        return str(login).strip().lower()
    
    def is_privileged_role(self, role: Optional[str]) -> bool:
        """Check if role is privileged."""
        if not role:
            return False
        
        role_lower = str(role).lower()
        
        for pattern in self._compiled_patterns:
            if pattern.search(role_lower):
                return True
        
        return False
    
    def normalize_date(self, date_value: Optional[str], 
                      reference_date: Optional[datetime] = None) -> Optional[str]:
        """Normalize date to ISO format."""
        if not date_value:
            return None
        
        try:
            parsed_date = self.date_service.parse_date(str(date_value), reference_date)
            if parsed_date:
                return parsed_date.strftime('%Y-%m-%d')
        except Exception:
            pass
        
        return None
    
    def normalize_record(self, record: Dict[str, Any], 
                        reference_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Normalize a complete access record.
        
        Args:
            record: Raw record dictionary
            reference_date: Reference date for relative date parsing
            
        Returns:
            Normalized record dictionary
        """
        normalized = {}
        
        # Map common field variations
        field_mappings = {
            'full_name': ['full_name', 'fio', 'name', 'user', 'employee', 'фио', 'пользователь'],
            'login': ['login', 'username', 'account', 'логин', 'учетная запись'],
            'email': ['email', 'mail', 'почта', 'e-mail'],
            'system': ['system', 'application', 'app', 'система', 'сервис'],
            'role': ['role', 'group', 'должность', 'роль'],
            'access_level': ['access_level', 'access', 'permission', 'права', 'уровень доступа'],
            'department': ['department', 'подразделение', 'отдел'],
            'owner': ['owner', 'владелец', 'system_owner'],
            'status': ['status', 'статус'],
            'granted_at': ['granted_at', 'date_granted', 'дата выдачи', 'start_date'],
            'valid_until': ['valid_until', 'date_until', 'дата окончания', 'end_date', 'deadline'],
            'ticket_number': ['ticket_number', 'ticket', 'request', 'заявка', 'inc'],
            'justification': ['justification', 'reason', 'основание', 'причина'],
        }
        
        for standard_field, variations in field_mappings.items():
            value = None
            for variation in variations:
                if variation in record:
                    value = record[variation]
                    break
            
            if value is not None:
                # Apply field-specific normalization
                if standard_field == 'full_name':
                    normalized[standard_field] = self.normalize_full_name(value)
                elif standard_field == 'email':
                    normalized[standard_field] = self.normalize_email(value)
                elif standard_field == 'login':
                    normalized[standard_field] = self.normalize_login(value)
                elif standard_field == 'status':
                    normalized[standard_field] = self.normalize_status(value)
                elif standard_field in ['granted_at', 'valid_until']:
                    normalized[standard_field] = self.normalize_date(value, reference_date)
                else:
                    normalized[standard_field] = str(value).strip()
        
        # Add privileged flag
        if 'role' in normalized:
            normalized['is_privileged'] = self.is_privileged_role(normalized['role'])
        
        # Set defaults for missing required fields
        if 'status' not in normalized:
            normalized['status'] = 'Активен'
        if 'granted_at' not in normalized and reference_date:
            normalized['granted_at'] = reference_date.strftime('%Y-%m-%d')
        
        return normalized
    
    def validate_record(self, record: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate a normalized record.
        
        Args:
            record: Normalized record dictionary
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Required fields
        required_fields = ['full_name', 'login', 'system', 'role']
        
        for field in required_fields:
            if not record.get(field):
                errors.append(f"Отсутствует обязательное поле: {field}")
        
        # Email format validation
        if record.get('email') and '@' not in record['email']:
            errors.append("Некорректный формат email")
        
        # Date validation
        granted_at = record.get('granted_at')
        valid_until = record.get('valid_until')
        
        if granted_at and valid_until:
            try:
                granted = datetime.fromisoformat(granted_at)
                until = datetime.fromisoformat(valid_until)
                
                if until < granted:
                    errors.append("Дата окончания раньше даты выдачи")
            except ValueError:
                errors.append("Некорректный формат даты")
        
        # Privileged access requires justification
        if record.get('is_privileged') and not record.get('justification'):
            errors.append("Привилегированный доступ требует обоснования")
        
        return len(errors) == 0, errors

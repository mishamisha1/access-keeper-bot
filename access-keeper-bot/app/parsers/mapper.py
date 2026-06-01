"""Intelligent column mapping using fuzzy matching."""

import logging
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


# Column synonyms for intelligent mapping
COLUMN_SYNONYMS = {
    'full_name': [
        'фио', 'фамилия', 'имя', 'отчество', 'пользователь', 'сотрудник',
        'user', 'employee', 'full name', 'name', 'fullname', 'worker'
    ],
    'login': [
        'логин', 'login', 'username', 'user name', 'учетная запись', 'уз',
        'account', 'account name', 'uid', 'user id', 'id пользователя'
    ],
    'email': [
        'email', 'mail', 'почта', 'e-mail', 'electronic mail', 'адрес почты'
    ],
    'system': [
        'система', 'system', 'application', 'app', 'информационная система',
        'ис', 'сервис', 'service', 'программа', 'software'
    ],
    'role': [
        'роль', 'role', 'group', 'ad group', 'security group', 'permission group',
        'группа', 'должность', 'position', 'title'
    ],
    'access_level': [
        'access', 'permission', 'права', 'уровень доступа', 'access level',
        'rights', 'privileges', 'полномочия', 'доступ'
    ],
    'department': [
        'department', 'подразделение', 'отдел', 'unit', 'департамент',
        'division', 'team', 'команда'
    ],
    'owner': [
        'owner', 'владелец', 'system owner', 'app owner', 'ответственный',
        'владелец системы', 'manager'
    ],
    'status': [
        'status', 'статус', 'state', 'состояние', 'active status', 'access status'
    ],
    'granted_at': [
        'granted at', 'дата выдачи', 'start date', 'valid from', 'дата начала',
        'issue date', 'created at', 'дата создания'
    ],
    'valid_until': [
        'until', 'valid until', 'deadline', 'дата окончания', 'срок действия',
        'valid to', 'end date', 'expiry date', 'expiration', 'дата истечения'
    ],
    'ticket_number': [
        'ticket', 'request', 'заявка', 'номер заявки', 'inc', 'req', 'sr',
        'incident', 'change request', 'номер запроса'
    ],
    'justification': [
        'reason', 'основание', 'business justification', 'justification',
        'причина', 'purpose', 'цель', 'обоснование', 'comment', 'комментарий'
    ],
    'calendar_event_id': [
        'calendar event id', 'event id', 'google calendar id', 'календарь id',
        'meeting id', 'reminder id'
    ],
    'calendar_event_link': [
        'calendar event link', 'event link', 'google calendar link',
        'ссылка на календарь', 'meeting link'
    ],
    'row_number': [
        'row number', 'row', 'строка', 'номер строки', '#'
    ],
    'added_by': [
        'added by', 'created by', 'кем добавлено', 'автор', 'operator'
    ],
    'review_status': [
        'review status', 'статус ревью', 'review state', 'подтверждение',
        'approval status'
    ]
}


class ColumnMapper:
    """Map file columns to standard field names using fuzzy matching."""
    
    def __init__(self, confidence_threshold: int = 70):
        """
        Initialize mapper.
        
        Args:
            confidence_threshold: Minimum confidence score (0-100) for auto-mapping
        """
        self.confidence_threshold = confidence_threshold
        self._build_search_index()
    
    def _build_search_index(self):
        """Build search index for all synonyms."""
        self.synonym_to_field = {}
        self.field_choices = []
        
        for field_name, synonyms in COLUMN_SYNONYMS.items():
            self.field_choices.append(field_name)
            for synonym in synonyms:
                self.synonym_to_field[synonym.lower().strip()] = field_name
    
    def map_column(self, column_name: str) -> Tuple[Optional[str], int]:
        """
        Map a column name to standard field name.
        
        Args:
            column_name: Original column name
            
        Returns:
            Tuple of (mapped_field_name, confidence_score)
        """
        if not column_name:
            return None, 0
        
        col_lower = column_name.lower().strip()
        
        # Direct match
        if col_lower in self.synonym_to_field:
            return self.synonym_to_field[col_lower], 100
        
        # Check with underscores replaced by spaces
        col_normalized = col_lower.replace('_', ' ').replace('-', ' ')
        if col_normalized in self.synonym_to_field:
            return self.synonym_to_field[col_normalized], 95
        
        # Fuzzy match against all field names
        best_match = process.extractOne(
            col_lower,
            self.field_choices,
            scorer=fuzz.partial_ratio
        )
        
        if best_match and best_match[1] >= self.confidence_threshold:
            logger.debug(
                f"Mapped '{column_name}' -> '{best_match[0]}' "
                f"(confidence: {best_match[1]})"
            )
            return best_match[0], best_match[1]
        
        # No confident match
        logger.debug(f"No confident match for column: {column_name}")
        return None, 0
    
    def map_columns(self, columns: List[str]) -> Dict[str, str]:
        """
        Map multiple columns to standard field names.
        
        Args:
            columns: List of original column names
            
        Returns:
            Dictionary mapping original names to standard names
        """
        mapping = {}
        unmapped = []
        
        for col in columns:
            mapped_field, confidence = self.map_column(col)
            
            if mapped_field:
                # Only add if we haven't mapped this field yet
                if mapped_field not in mapping.values():
                    mapping[col] = mapped_field
                else:
                    # Duplicate mapping - keep the one with higher confidence
                    unmapped.append((col, mapped_field, confidence))
            else:
                unmapped.append((col, None, 0))
        
        if unmapped:
            logger.warning(
                f"Unmapped or duplicate columns: {[u[0] for u in unmapped]}"
            )
        
        return mapping
    
    def get_suggested_mapping(self, column_name: str) -> List[Tuple[str, int]]:
        """
        Get suggested mappings for a column with scores.
        
        Args:
            column_name: Original column name
            
        Returns:
            List of (field_name, confidence_score) tuples
        """
        suggestions = process.extract(
            column_name.lower(),
            self.field_choices,
            scorer=fuzz.partial_ratio,
            limit=5
        )
        return [(s[0], s[1]) for s in suggestions]
    
    def get_required_fields(self) -> List[str]:
        """Get list of required standard fields."""
        return [
            'full_name',
            'login',
            'email',
            'system',
            'role',
            'access_level',
            'granted_at',
            'valid_until',
            'status'
        ]
    
    def get_optional_fields(self) -> List[str]:
        """Get list of optional standard fields."""
        return [
            'department',
            'owner',
            'ticket_number',
            'justification',
            'calendar_event_id',
            'calendar_event_link',
            'row_number',
            'added_by',
            'review_status'
        ]

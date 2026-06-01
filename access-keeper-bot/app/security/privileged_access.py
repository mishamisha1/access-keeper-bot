"""Privileged access detection and control."""

import re
from dataclasses import dataclass
from typing import List, Optional, Set


@dataclass
class PrivilegeLevel:
    """Represents a privilege level."""
    name: str
    is_privileged: bool
    requires_approval: bool
    description: str


class PrivilegedAccessChecker:
    """Check and classify privileged access roles."""

    # Privileged role patterns (case-insensitive)
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
        r'emergency\s*access',
        r'emergency',
        r'break\s*glass',
        r'break-glass',
        r'breakglass',
    ]

    # Pre-compiled regex patterns for performance
    _compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in PRIVILEGED_PATTERNS]

    # Standard privilege levels
    PRIVILEGE_LEVELS = {
        'read_only': PrivilegeLevel(
            name='Только чтение',
            is_privileged=False,
            requires_approval=False,
            description='Доступ только на чтение данных'
        ),
        'standard': PrivilegeLevel(
            name='Стандартный',
            is_privileged=False,
            requires_approval=False,
            description='Стандартные права доступа для выполнения рабочих задач'
        ),
        'elevated': PrivilegeLevel(
            name='Повышенный',
            is_privileged=True,
            requires_approval=True,
            description='Повышенные права доступа, требующие обоснования'
        ),
        'administrative': PrivilegeLevel(
            name='Административный',
            is_privileged=True,
            requires_approval=True,
            description='Административные права с полным контролем системы'
        ),
        'emergency': PrivilegeLevel(
            name='Экстренный',
            is_privileged=True,
            requires_approval=True,
            description='Экстренный доступ (break-glass), требует немедленного ревью'
        ),
    }

    def __init__(self):
        self._custom_privileged_roles: Set[str] = set()
        self._require_approval_for_all_temporary = True

    def is_privileged_role(self, role: Optional[str]) -> bool:
        """
        Check if a role is considered privileged.
        
        Args:
            role: Role name or description
            
        Returns:
            True if the role is privileged, False otherwise
        """
        if not role:
            return False
        
        role_lower = role.lower().strip()
        
        # Check custom privileged roles first
        if role_lower in self._custom_privileged_roles:
            return True
        
        # Check against patterns
        for pattern in self._compiled_patterns:
            if pattern.search(role_lower):
                return True
        
        return False

    def get_privilege_level(self, role: Optional[str], 
                           access_type: Optional[str] = None) -> PrivilegeLevel:
        """
        Determine the privilege level for a role.
        
        Args:
            role: Role name or description
            access_type: Additional access type information
            
        Returns:
            PrivilegeLevel object
        """
        if not role:
            return self.PRIVILEGE_LEVELS['standard']
        
        role_lower = role.lower().strip()
        
        # Check for read-only
        if any(keyword in role_lower for keyword in ['read-only', 'readonly', 'read only', 'viewer', 'guest']):
            return self.PRIVILEGE_LEVELS['read_only']
        
        # Check for emergency/break-glass
        if any(keyword in role_lower for keyword in ['emergency', 'break-glass', 'break glass', 'urgent']):
            return self.PRIVILEGE_LEVELS['emergency']
        
        # Check if privileged
        if self.is_privileged_role(role):
            # Distinguish between elevated and administrative
            if any(keyword in role_lower for keyword in ['admin', 'superuser', 'root', 'owner']):
                return self.PRIVILEGE_LEVELS['administrative']
            else:
                return self.PRIVILEGE_LEVELS['elevated']
        
        return self.PRIVILEGE_LEVELS['standard']

    def add_custom_privileged_role(self, role: str):
        """Add a custom role to the privileged list."""
        self._custom_privileged_roles.add(role.lower().strip())

    def remove_custom_privileged_role(self, role: str):
        """Remove a custom role from the privileged list."""
        self._custom_privileged_roles.discard(role.lower().strip())

    def get_privileged_roles(self) -> Set[str]:
        """Get all custom privileged roles."""
        return self._custom_privileged_roles.copy()

    def requires_approval(self, role: Optional[str], is_temporary: bool = False) -> bool:
        """
        Check if access requires approval.
        
        Args:
            role: Role name or description
            is_temporary: Whether this is temporary access
            
        Returns:
            True if approval is required, False otherwise
        """
        # All temporary access requires approval per ISO 27001
        if is_temporary and self._require_approval_for_all_temporary:
            return True
        
        # Privileged roles always require approval
        if self.is_privileged_role(role):
            return True
        
        return False

    def validate_access_request(self, role: Optional[str], 
                               is_temporary: bool,
                               justification: Optional[str]) -> tuple[bool, List[str]]:
        """
        Validate an access request against security policies.
        
        Args:
            role: Role name or description
            is_temporary: Whether this is temporary access
            justification: Business justification for access
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check for privileged access without justification
        if self.is_privileged_role(role):
            if not justification or len(justification.strip()) < 10:
                issues.append(
                    "Привилегированный доступ требует подробного обоснования (минимум 10 символов)"
                )
        
        # Check temporary access duration
        if is_temporary:
            if not justification or len(justification.strip()) < 5:
                issues.append(
                    "Временный доступ требует указания причины предоставления"
                )
        
        # Check for emergency access
        if self.get_privilege_level(role).name == self.PRIVILEGE_LEVELS['emergency'].name:
            issues.append(
                "⚠️ ЭКСТРЕННЫЙ ДОСТУП: Требуется немедленное уведомление руководителя ИБ"
            )
        
        return len(issues) == 0, issues

    def set_require_approval_for_temporary(self, required: bool):
        """Configure whether all temporary access requires approval."""
        self._require_approval_for_all_temporary = required

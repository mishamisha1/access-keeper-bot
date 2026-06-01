"""
Шаблоны Google Sheets матриц доступа.
Соответствует требованиям ISO 27001 A.9.4 (управление доступом).
Содержит 6 предустановленных шаблонов для различных сценариев.
"""

from typing import TypedDict


class TemplateDict(TypedDict):
    """Тип для шаблона."""
    name: str
    sheet_name: str
    description: str
    columns: list[str]


class MatrixTemplates:
    """Класс управления шаблонами матриц доступа."""
    
    TEMPLATES: dict[str, TemplateDict] = {
        "simple_matrix": {
            "name": "Простая матрица доступа",
            "sheet_name": "Матрица доступов",
            "description": "Базовая матрица для учета доступов пользователей",
            "columns": [
                "№", "ФИО", "Логин", "Email", "Должность", "Подразделение",
                "Система", "Роль", "Уровень доступа", "Основание выдачи",
                "Номер заявки", "Дата выдачи", "Дата окончания",
                "Владелец системы", "Ответственный ИБ", "Статус доступа",
                "Комментарий"
            ],
        },
        
        "extended_matrix": {
            "name": "Расширенная матрица доступа",
            "sheet_name": "Расширенная матрица",
            "description": "Детальная матрица с правами и ревью",
            "columns": [
                "№", "ФИО", "Логин", "Email", "Табельный номер", "Должность",
                "Подразделение", "Руководитель", "Система", "Модуль", "Роль",
                "Права: чтение", "Права: запись", "Права: изменение",
                "Права: удаление", "Админские права", "Привилегированный доступ",
                "Основание доступа", "Номер заявки", "Дата выдачи", "Дата окончания",
                "Владелец системы", "Ответственный ИБ", "Последнее ревью",
                "Статус ревью", "Следующее действие", "Calendar Event ID",
                "Calendar Event Link", "Комментарий"
            ],
        },
        
        "role_matrix": {
            "name": "Матрица по ролям",
            "sheet_name": "Ролевая матрица",
            "description": "Матрица соответствия ролей и модулей системы",
            "columns": [
                "№", "Роль", "Модуль 1", "Модуль 2", "Модуль 3", "Модуль 4",
                "Модуль 5", "Модуль 6", "Модуль 7", "Модуль 8",
                "Описание роли", "Уровень привилегий", "Требования к безопасности"
            ],
        },
        
        "review_matrix": {
            "name": "Ревью доступов",
            "sheet_name": "Ревью доступов",
            "description": "Таблица для проведения регулярного ревью доступов",
            "columns": [
                "№", "Система", "Пользователь", "Логин", "Email", "Роль",
                "Владелец доступа", "Подтверждено владельцем", "Оставить доступ",
                "Отозвать доступ", "Причина", "Дата ревью", "Следующее ревью",
                "Статус", "Комментарий"
            ],
        },
        
        "pci_iso_matrix": {
            "name": "PCI DSS / ISO Access Review",
            "sheet_name": "PCI ISO Review",
            "description": "Матрица для compliance проверок PCI DSS и ISO 27001",
            "columns": [
                "№", "Система", "Критичность системы", "Пользователь",
                "Учетная запись", "Email", "Привилегированный доступ",
                "Бизнес-основание", "Владелец системы", "Дата последнего входа",
                "Дата выдачи доступа", "Дата окончания доступа",
                "Дата последнего пересмотра", "Результат пересмотра",
                "Корректирующее действие", "Ответственный", "Deadline",
                "Status", "Calendar Event ID", "Calendar Event Link"
            ],
        },
        
        "temporary_access": {
            "name": "Временные доступы",
            "sheet_name": "Временные доступы",
            "description": "Управление временными доступами с автоматическим отзывом",
            "columns": [
                "№", "ФИО", "Логин", "Email", "Система", "Роль",
                "Уровень доступа", "Основание выдачи", "Номер заявки",
                "Дата выдачи", "Срок доступа", "Дата окончания",
                "Время напоминания", "Действие", "Статус доступа",
                "Статус ревью", "Владелец системы", "Ответственный ИБ",
                "Calendar Event ID", "Calendar Event Link", "Google Sheets Row",
                "Кем добавлено", "Дата создания записи", "Комментарий"
            ],
        },
    }
    
    # Статусы для dropdown
    STATUS_VALUES = [
        "Активен",
        "Временный",
        "На ревью",
        "Ожидает отзыва",
        "Отозван",
        "Продлён",
        "Просрочен",
        "Ошибка",
    ]
    
    # Статусы ревью
    REVIEW_STATUS_VALUES = [
        "Не начато",
        "В процессе",
        "Выполнено",
        "Требует действий",
        "Отклонено",
    ]
    
    # Уровни доступа
    ACCESS_LEVEL_VALUES = [
        "Нет доступа",
        "Чтение",
        "Запись",
        "Изменение",
        "Удаление",
        "Админ",
        "Полный",
    ]
    
    def get_template(self, template_name: str) -> TemplateDict:
        """
        Получение шаблона по имени.
        
        Args:
            template_name: Имя шаблона
            
        Returns:
            Словарь шаблона
            
        Raises:
            ValueError: Если шаблон не найден
        """
        if template_name not in self.TEMPLATES:
            available = ", ".join(self.TEMPLATES.keys())
            raise ValueError(
                f"Шаблон '{template_name}' не найден. Доступные: {available}"
            )
        
        return self.TEMPLATES[template_name]
    
    def list_templates(self) -> list[dict]:
        """Получение списка всех шаблонов."""
        return [
            {
                "key": key,
                "name": template["name"],
                "sheet_name": template["sheet_name"],
                "description": template["description"],
                "column_count": len(template["columns"]),
            }
            for key, template in self.TEMPLATES.items()
        ]
    
    def get_column_mapping(
        self,
        template_name: str,
        external_headers: list[str],
    ) -> dict[str, int]:
        """
        Интеллектуальный маппинг колонок внешнего файла к шаблону.
        Использует fuzzy matching для сопоставления.
        
        Args:
            template_name: Имя шаблона
            external_headers: Заголовки внешнего файла
            
        Returns:
            Маппинг {field_name: column_index}
        """
        from rapidfuzz import fuzz, process
        
        template = self.get_template(template_name)
        columns = template["columns"]
        
        # Синонимы для полей
        field_synonyms = {
            "full_name": ["фио", "фамилия", "имя", "пользователь", "сотрудник", 
                         "name", "user", "employee", "full name"],
            "login": ["логин", "username", "учетная запись", "уз", "account", 
                     "uid", "user name", "account name"],
            "email": ["email", "почта", "e-mail", "mail", "электронная почта"],
            "system": ["система", "system", "application", "app", "сервис", 
                      "ис", "программа", "service"],
            "role": ["роль", "role", "group", "должность", "позиция", 
                    "position", "ad group", "security group"],
            "access_level": ["доступ", "уровень", "level", "права", "rights", 
                           "permission", "access level", "access"],
            "department": ["подразделение", "отдел", "department", "unit", "департамент"],
            "owner": ["владелец", "owner", "system owner", "app owner", 
                     "владелец системы"],
            "status": ["статус", "status", "state", "состояние"],
            "granted_date": ["дата выдачи", "granted at", "start date", 
                           "valid from", "дата начала"],
            "end_date": ["дата окончания", "until", "valid until", "deadline", 
                        "срок действия", "valid to", "end date", "expiry"],
            "ticket_number": ["ticket", "request", "заявка", "номер заявки", 
                            "inc", "req", "sr", "task", "номер"],
            "reason": ["reason", "основание", "business justification", 
                      "justification", "причина", "basis"],
            "calendar_event_id": ["calendar event id", "event id", 
                                 "google calendar id", "календарь id"],
            "calendar_event_link": ["calendar event link", "event link", 
                                   "google calendar link", "ссылка календарь"],
        }
        
        mapping = {}
        
        for field_name, synonyms in field_synonyms.items():
            best_match = None
            best_score = 0
            
            for header in external_headers:
                # Прямое совпадение
                if header.lower().strip() == field_name.lower():
                    best_match = header
                    best_score = 100
                    break
                
                # Совпадение с синонимами
                for synonym in synonyms:
                    score = fuzz.ratio(header.lower(), synonym.lower())
                    if score > best_score and score >= 70:
                        best_score = score
                        best_match = header
            
            if best_match:
                # Находим индекс колонки в шаблоне
                try:
                    col_index = columns.index(best_match)
                    mapping[field_name] = col_index
                except ValueError:
                    # Если точного совпадения нет, ищем похожее
                    for i, col in enumerate(columns):
                        score = fuzz.ratio(col.lower(), best_match.lower())
                        if score >= 70:
                            mapping[field_name] = i
                            break
        
        return mapping
    
    def get_required_fields(self, template_name: str) -> list[str]:
        """Получение списка обязательных полей для шаблона."""
        required_map = {
            "temporary_access": [
                "full_name",
                "system",
                "granted_date",
                "end_date",
                "status",
            ],
            "simple_matrix": [
                "full_name",
                "system",
                "role",
            ],
            "extended_matrix": [
                "full_name",
                "system",
                "role",
            ],
            "review_matrix": [
                "system",
                "full_name",
                "role",
            ],
            "pci_iso_matrix": [
                "system",
                "full_name",
            ],
            "role_matrix": [
                "role",
            ],
        }
        
        return required_map.get(template_name, [])


# Глобальный экземпляр
matrix_templates = MatrixTemplates()

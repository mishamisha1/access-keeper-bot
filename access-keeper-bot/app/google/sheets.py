"""
Google Sheets API сервис.
Соответствует требованиям ISO 27001 A.8.2 (управление информацией) и A.12.3 (резервное копирование).
Создает, читает и обновляет таблицы с правильным форматированием.
"""

from typing import Optional, Any
from datetime import datetime

from app.logging_config import get_logger
from app.google.auth import google_auth
from app.templates.matrix_templates import MatrixTemplates

logger = get_logger(__name__)


class GoogleSheetsService:
    """Сервис для работы с Google Sheets API."""
    
    def __init__(self):
        self.service = None
        self.templates = MatrixTemplates()
    
    def _ensure_service(self):
        """Проверка и получение сервиса."""
        if self.service is None:
            self.service = google_auth.sheets_service
        return self.service
    
    def create_spreadsheet(
        self,
        title: str,
        template_name: str = "temporary_access",
    ) -> dict:
        """
        Создание новой Google Sheets таблицы с шаблоном.
        
        Args:
            title: Название таблицы
            template_name: Название шаблона
            
        Returns:
            Информация о созданной таблице
        """
        service = self._ensure_service()
        template = self.templates.get_template(template_name)
        
        # Создаем таблицу
        spreadsheet_body = {
            "properties": {
                "title": title,
                "locale": "ru_RU",
                "timeZone": "Asia/Almaty",
            },
            "sheets": [
                {
                    "properties": {
                        "title": template["sheet_name"],
                        "gridProperties": {
                            "rowCount": 1000,
                            "columnCount": len(template["columns"]) + 5,
                        },
                    }
                }
            ],
        }
        
        response = service.spreadsheets().create(body=spreadsheet_body).execute()
        spreadsheet_id = response["spreadsheetId"]
        spreadsheet_url = response["spreadsheetUrl"]
        
        logger.info(f"Создана таблица {title} (ID: {spreadsheet_id})")
        
        # Применяем форматирование
        self._apply_formatting(spreadsheet_id, template)
        
        # Создаем дополнительные вкладки
        self._create_additional_sheets(spreadsheet_id, template)
        
        # Добавляем заголовки
        self._add_headers(spreadsheet_id, template["sheet_name"], template["columns"])
        
        return {
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": spreadsheet_url,
            "title": title,
            "sheet_name": template["sheet_name"],
        }
    
    def _apply_formatting(self, spreadsheet_id: str, template: dict):
        """Применение форматирования к таблице."""
        service = self._ensure_service()
        
        requests = [
            # Жирный шрифт для заголовков
            {
                "repeatCell": {
                    "range": {
                        "sheetId": 0,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                        }
                    },
                    "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor",
                }
            },
            # Закрепление первой строки
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": 0,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # Автоширина колонок
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": 0,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": len(template["columns"]),
                    }
                }
            },
            # Перенос текста
            {
                "repeatCell": {
                    "range": {
                        "sheetId": 0,
                        "startRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "wrapStrategy": "WRAP",
                            "verticalAlignment": "TOP",
                        }
                    },
                    "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment",
                }
            },
        ]
        
        # Добавляем фильтры
        requests.append({
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": 0,
                        "startRowIndex": 0,
                        "endColumnIndex": len(template["columns"]),
                    }
                }
            }
        })
        
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            ).execute()
            logger.debug("Форматирование применено")
        except Exception as e:
            logger.warning(f"Ошибка при форматировании: {e}")
    
    def _create_additional_sheets(self, spreadsheet_id: str, template: dict):
        """Создание дополнительных вкладок (README, История)."""
        service = self._ensure_service()
        
        # Вкладка README
        readme_body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": "README",
                            "gridProperties": {"rowCount": 50, "columnCount": 5},
                        }
                    }
                }
            ]
        }
        
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=readme_body,
            ).execute()
            
            # Добавляем контент в README
            readme_content = [
                ["📖 Access Keeper Bot - Инструкция"],
                [""],
                ["Назначение таблицы:"],
                [template.get("description", "Управление временными доступами")],
                [""],
                ["Как работает бот:"],
                ["1. Команда /access создает запись в этой таблице"],
                ["2. Автоматически создается событие в Google Calendar"],
                ["3. Calendar Event ID сохраняется в колонке"],
                [""],
                ["Статусы доступов:"],
                ["- Активен: доступ действителен"],
                ["- Временный: доступ на ограниченный срок"],
                ["- На ревью: требуется проверка"],
                ["- Отозван: доступ отменен"],
                ["- Просрочен: срок истек"],
                [""],
                ["Команды бота:"],
                ["/access - добавить доступ"],
                ["/revoke_access - отозвать доступ"],
                ["/extend_access - продлить доступ"],
                ["/access_due - истекающие доступы"],
                ["/access_overdue - просроченные доступы"],
            ]
            
            self._append_rows(
                spreadsheet_id,
                "README",
                readme_content,
            )
            
        except Exception as e:
            logger.warning(f"Ошибка создания README: {e}")
        
        # Вкладка История изменений
        history_body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": "История изменений",
                            "gridProperties": {"rowCount": 1000, "columnCount": 15},
                        }
                    }
                }
            ]
        }
        
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=history_body,
            ).execute()
            
            # Заголовки истории
            history_headers = [
                "Дата и время", "Действие", "Telegram User", "Username",
                "ФИО", "Логин", "Система", "Старая роль", "Новая роль",
                "Старая дата окончания", "Новая дата окончания",
                "Старый статус", "Новый статус", "Комментарий"
            ]
            
            self._append_rows(
                spreadsheet_id,
                "История изменений",
                [history_headers],
            )
            
        except Exception as e:
            logger.warning(f"Ошибка создания вкладки истории: {e}")
    
    def _add_headers(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        columns: list[str],
    ):
        """Добавление заголовков в таблицу."""
        self._append_rows(spreadsheet_id, sheet_name, [columns])
    
    def _append_rows(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ):
        """Добавление строк в таблицу."""
        service = self._ensure_service()
        
        body = {
            "values": rows,
        }
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z",
            valueInputOption=value_input_option,
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
    
    def append_access_record(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        record_data: dict,
        column_mapping: dict[str, int],
    ) -> int:
        """
        Добавление записи о доступе в таблицу.
        
        Args:
            spreadsheet_id: ID таблицы
            sheet_name: Название вкладки
            record_data: Данные записи
            column_mapping: Маппинг колонок {field_name: column_index}
            
        Returns:
            Номер добавленной строки
        """
        # Получаем текущее количество строк для определения номера новой
        service = self._ensure_service()
        
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:A",
        ).execute()
        
        values = result.get("values", [])
        row_number = len(values) + 1  # +1 так как строки нумеруются с 1
        
        # Формируем строку данных согласно маппингу
        max_col = max(column_mapping.values()) if column_mapping else 20
        row = [""] * (max_col + 1)
        
        for field_name, col_index in column_mapping.items():
            value = record_data.get(field_name, "")
            if col_index < len(row):
                row[col_index] = value
        
        # Добавляем номер строки в первую колонку
        row[0] = row_number
        
        self._append_rows(spreadsheet_id, sheet_name, [row])
        
        logger.info(f"Добавлена запись в строку {row_number}")
        return row_number
    
    def get_sheet_headers(
        self,
        spreadsheet_id: str,
        sheet_name: str,
    ) -> list[str]:
        """Получение заголовков таблицы."""
        service = self._ensure_service()
        
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!1:1",
        ).execute()
        
        return result.get("values", [[]])[0] if result.get("values") else []
    
    def get_sheet_list(self, spreadsheet_id: str) -> list[dict]:
        """Получение списка вкладок в таблице."""
        service = self._ensure_service()
        
        result = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
        ).execute()
        
        sheets = result.get("sheets", [])
        return [
            {
                "sheet_id": sheet["properties"]["sheetId"],
                "title": sheet["properties"]["title"],
                "row_count": sheet["properties"]["gridProperties"]["rowCount"],
                "column_count": sheet["properties"]["gridProperties"]["columnCount"],
            }
            for sheet in sheets
        ]
    
    def update_cell(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        row: int,
        col: int,
        value: Any,
    ):
        """Обновление одной ячейки."""
        service = self._ensure_service()
        
        body = {
            "values": [[value]],
        }
        
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!{chr(65 + col)}{row}",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()
    
    def update_row(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        row: int,
        values: list[Any],
    ):
        """Обновление всей строки."""
        service = self._ensure_service()
        
        body = {
            "values": [values],
        }
        
        # Преобразуем номер строки в диапазон
        start_col = "A"
        end_col = chr(65 + len(values) - 1) if len(values) <= 26 else "Z"
        
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!{start_col}{row}:{end_col}{row}",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()
    
    def add_dropdown(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        column_letter: str,
        values: list[str],
        start_row: int = 2,
    ):
        """Добавление dropdown списка в колонку."""
        service = self._ensure_service()
        
        # Получаем sheet_id
        sheets = self.get_sheet_list(spreadsheet_id)
        sheet_id = None
        for sheet in sheets:
            if sheet["title"] == sheet_name:
                sheet_id = sheet["sheet_id"]
                break
        
        if sheet_id is None:
            logger.error(f"Вкладка {sheet_name} не найдена")
            return
        
        requests = [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row - 1,
                        "startColumnIndex": ord(column_letter.upper()) - 65,
                        "endColumnIndex": ord(column_letter.upper()) - 64,
                    },
                    "rule": {
                        "condition": {
                            "type": "ONE_OF_LIST",
                            "values": [{"userEnteredValue": v} for v in values],
                        },
                        "showCustomUi": True,
                    },
                }
            }
        ]
        
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            ).execute()
        except Exception as e:
            logger.warning(f"Ошибка добавления dropdown: {e}")


# Глобальный экземпляр
sheets_service = GoogleSheetsService()

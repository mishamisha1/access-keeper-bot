"""Работа с Google Sheets API."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from app.google.auth import get_google_auth

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Сервис для работы с Google Sheets."""
    
    def __init__(self):
        self.auth = get_google_auth()
    
    def _get_service(self) -> Optional[Resource]:
        """Получает сервис Google Sheets."""
        return self.auth.get_sheets_service()
    
    def create_spreadsheet(self, title: str) -> Optional[Dict[str, Any]]:
        """Создаёт новую Google Sheets таблицу."""
        service = self._get_service()
        if not service:
            return None
        
        try:
            spreadsheet = {
                "properties": {
                    "title": title
                }
            }
            
            result = service.spreadsheets().create(body=spreadsheet).execute()
            logger.info("Создана таблица: %s", result["spreadsheetId"])
            return result
        except HttpError as e:
            logger.error("Ошибка создания таблицы: %s", e)
            return None
    
    def get_spreadsheet(self, spreadsheet_id: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о таблице."""
        service = self._get_service()
        if not service:
            return None
        
        try:
            result = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            return result
        except HttpError as e:
            logger.error("Ошибка получения таблицы: %s", e)
            return None
    
    def get_sheet_names(self, spreadsheet_id: str) -> List[str]:
        """Получает список названий вкладок в таблице."""
        spreadsheet = self.get_spreadsheet(spreadsheet_id)
        if not spreadsheet:
            return []
        
        return [
            sheet["properties"]["title"]
            for sheet in spreadsheet.get("sheets", [])
        ]
    
    def create_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        headers: List[str]
    ) -> Optional[int]:
        """Создаёт новую вкладку с заголовками."""
        service = self._get_service()
        if not service:
            return None
        
        try:
            # Создаём новую вкладку
            requests = [
                {
                    "addSheet": {
                        "properties": {
                            "title": sheet_name
                        }
                    }
                }
            ]
            
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests}
            ).execute()
            
            sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
            
            # Записываем заголовки
            if headers:
                self.update_range(
                    spreadsheet_id,
                    f"{sheet_name}!A1",
                    [headers]
                )
            
            # Форматируем заголовки
            self._format_header_row(service, spreadsheet_id, sheet_name)
            
            logger.info("Создана вкладка: %s", sheet_name)
            return sheet_id
        except HttpError as e:
            logger.error("Ошибка создания вкладки: %s", e)
            return None
    
    def _format_header_row(
        self,
        service: Resource,
        spreadsheet_id: str,
        sheet_name: str
    ) -> None:
        """Форматирует строку заголовков."""
        try:
            requests = [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": self._get_sheet_id(service, spreadsheet_id, sheet_name),
                            "startRowIndex": 0,
                            "endRowIndex": 1
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
                            }
                        },
                        "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor"
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": self._get_sheet_id(service, spreadsheet_id, sheet_name),
                            "gridProperties": {
                                "frozenRowCount": 1
                            }
                        },
                        "fields": "gridProperties.frozenRowCount"
                    }
                }
            ]
            
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests}
            ).execute()
        except HttpError as e:
            logger.warning("Ошибка форматирования заголовков: %s", e)
    
    def _get_sheet_id(
        self,
        service: Resource,
        spreadsheet_id: str,
        sheet_name: str
    ) -> int:
        """Получает ID вкладки по названию."""
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()
        
        for sheet in spreadsheet.get("sheets", []):
            if sheet["properties"]["title"] == sheet_name:
                return sheet["properties"]["sheetId"]
        
        raise ValueError(f"Вкладка {sheet_name} не найдена")
    
    def update_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]]
    ) -> bool:
        """Обновляет диапазон ячеек."""
        service = self._get_service()
        if not service:
            return False
        
        try:
            body = {
                "values": values
            }
            
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            
            return True
        except HttpError as e:
            logger.error("Ошибка обновления диапазона: %s", e)
            return False
    
    def append_rows(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: List[List[Any]]
    ) -> Optional[int]:
        """Добавляет строки в конец таблицы."""
        service = self._get_service()
        if not service:
            return None
        
        try:
            range_name = f"{sheet_name}!A:Z"
            
            body = {
                "values": rows
            }
            
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            
            # Возвращаем номер первой добавленной строки
            updated_range = result.get("updates", {}).get("updatedRange", "")
            if updated_range:
                # Парсим номер строки из формата "Sheet!A2"
                row_num = int(updated_range.split("!")[1][1:])
                return row_num
            
            return None
        except HttpError as e:
            logger.error("Ошибка добавления строк: %s", e)
            return None
    
    def get_range(
        self,
        spreadsheet_id: str,
        range_name: str
    ) -> List[List[Any]]:
        """Получает данные из диапазона."""
        service = self._get_service()
        if not service:
            return []
        
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            return result.get("values", [])
        except HttpError as e:
            logger.error("Ошибка получения данных: %s", e)
            return []
    
    def get_headers(
        self,
        spreadsheet_id: str,
        sheet_name: str
    ) -> List[str]:
        """Получает заголовки вкладки."""
        values = self.get_range(spreadsheet_id, f"{sheet_name}!1:1")
        if values and values[0]:
            return [str(h).strip() for h in values[0]]
        return []
    
    def add_dropdown(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        column_letter: str,
        values: List[str]
    ) -> bool:
        """Добавляет выпадающий список в колонку."""
        service = self._get_service()
        if not service:
            return False
        
        try:
            sheet_id = self._get_sheet_id(service, spreadsheet_id, sheet_name)
            
            requests = [
                {
                    "setDataValidation": {
                        "range": {
                            "sheetId": sheet_id,
                            "startColumnIndex": ord(column_letter.upper()) - ord("A"),
                            "endColumnIndex": ord(column_letter.upper()) - ord("A") + 1,
                            "startRowIndex": 1  # Пропускаем заголовок
                        },
                        "rule": {
                            "condition": {
                                "type": "ONE_OF_LIST",
                                "values": [{"userEnteredValue": v} for v in values]
                            },
                            "showCustomUi": True
                        }
                    }
                }
            ]
            
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests}
            ).execute()
            
            return True
        except HttpError as e:
            logger.error("Ошибка добавления dropdown: %s", e)
            return False
    
    def add_conditional_formatting(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        column_letter: str,
        rules: List[Dict[str, Any]]
    ) -> bool:
        """Добавляет условное форматирование."""
        service = self._get_service()
        if not service:
            return False
        
        try:
            sheet_id = self._get_sheet_id(service, spreadsheet_id, sheet_name)
            
            requests = []
            for rule in rules:
                requests.append({
                    "addConditionalFormatRule": {
                        "rule": {
                            "ranges": [{
                                "sheetId": sheet_id,
                                "startColumnIndex": ord(column_letter.upper()) - ord("A"),
                                "endColumnIndex": ord(column_letter.upper()) - ord("A") + 1,
                                "startRowIndex": 1
                            }],
                            "booleanRule": rule["condition"]
                        },
                        "index": rule.get("index", 0)
                    }
                })
            
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests}
            ).execute()
            
            return True
        except HttpError as e:
            logger.error("Ошибка добавления условного форматирования: %s", e)
            return False
    
    def auto_resize_columns(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        num_columns: int
    ) -> bool:
        """Автоматически изменяет ширину колонок."""
        service = self._get_service()
        if not service:
            return False
        
        try:
            sheet_id = self._get_sheet_id(service, spreadsheet_id, sheet_name)
            
            requests = [
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": num_columns
                        }
                    }
                }
            ]
            
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests}
            ).execute()
            
            return True
        except HttpError as e:
            logger.error("Ошибка изменения размера колонок: %s", e)
            return False
    
    def get_spreadsheet_url(self, spreadsheet_id: str) -> str:
        """Получает URL таблицы."""
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

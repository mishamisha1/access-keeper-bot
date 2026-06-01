"""
Парсер Excel файлов (.xlsx, .xls).
Использует pandas для чтения и нормализации данных.
Соответствует ISO 27001 A.12.4 (Логирование).
"""

import logging
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ExcelParser:
    """Парсер для Excel файлов."""

    def __init__(self):
        self.supported_extensions = ['.xlsx', '.xls']

    def parse(self, file_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Парсит Excel файл.
        
        Args:
            file_path: Путь к файлу
            sheet_name: Имя листа (None = первый лист)
            
        Returns:
            Dict с headers, rows и errors
        """
        try:
            logger.info(f"Чтение Excel файла: {file_path}, лист: {sheet_name or 'первый'}")
            
            # Определяем двигатель в зависимости от расширения
            ext = Path(file_path).suffix.lower()
            engine = 'openpyxl' if ext == '.xlsx' else 'xlrd'
            
            # Читаем Excel
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine)
            else:
                # Читаем первый лист
                excel_file = pd.ExcelFile(file_path, engine=engine)
                sheet_name = excel_file.sheet_names[0]
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
            
            # Очищаем данные
            df = self._clean_dataframe(df)
            
            # Преобразуем в список списков
            headers = [str(col).strip() for col in df.columns.tolist()]
            rows = df.values.tolist()
            
            # Обрабатываем NaN значения
            cleaned_rows = []
            for row in rows:
                cleaned_row = []
                for cell in row:
                    if pd.isna(cell):
                        cleaned_row.append('')
                    elif isinstance(cell, (pd.Timestamp,)):
                        # Форматируем даты
                        cleaned_row.append(cell.strftime('%Y-%m-%d'))
                    else:
                        cleaned_row.append(str(cell).strip())
                cleaned_rows.append(cleaned_row)
            
            # Фильтруем пустые строки
            non_empty_rows = [
                row for row in cleaned_rows 
                if any(cell != '' for cell in row)
            ]
            
            result = {
                'headers': headers,
                'rows': non_empty_rows,
                'sheet_name': sheet_name,
                'total_rows': len(non_empty_rows),
                'errors': []
            }
            
            logger.info(f"Успешно распарсен Excel: {result['total_rows']} строк")
            return result
            
        except Exception as e:
            error_msg = f"Ошибка при чтении Excel: {str(e)}"
            logger.error(error_msg)
            return {
                'headers': [],
                'rows': [],
                'errors': [error_msg]
            }

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Очистка DataFrame от лишних столбцов и строк."""
        # Удаляем полностью пустые столбцы
        df = df.dropna(axis=1, how='all')
        
        # Удаляем полностью пустые строки
        df = df.dropna(axis=0, how='all')
        
        # Заменяем пустые ячейки на пустые строки
        df = df.fillna('')
        
        # Нормализуем заголовки (убираем лишние пробелы)
        df.columns = [str(col).strip() for col in df.columns]
        
        return df

    def get_sheet_names(self, file_path: str) -> List[str]:
        """Возвращает список листов в Excel файле."""
        try:
            excel_file = pd.ExcelFile(file_path, engine='openpyxl')
            return excel_file.sheet_names
        except Exception as e:
            logger.error(f"Ошибка получения списка листов: {str(e)}")
            return []

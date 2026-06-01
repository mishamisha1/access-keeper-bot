"""
Парсер CSV файлов.
Поддерживает различные кодировки и разделители.
Соответствует ISO 27001 A.12.4 (Логирование).
"""

import logging
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CSVParser:
    """Парсер для CSV файлов."""

    def __init__(self):
        self.supported_extensions = ['.csv']
        self.encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'latin1', 'iso-8859-1']
        self.separators = [',', ';', '\t', '|', ':']

    def parse(self, file_path: str, encoding: Optional[str] = None, 
              separator: Optional[str] = None) -> Dict[str, Any]:
        """
        Парсит CSV файл с авто-определением кодировки и разделителя.
        
        Args:
            file_path: Путь к файлу
            encoding: Кодировка (None = авто-определение)
            separator: Разделитель (None = авто-определение)
            
        Returns:
            Dict с headers, rows и errors
        """
        try:
            logger.info(f"Чтение CSV файла: {file_path}")
            
            # Авто-определение кодировки
            if not encoding:
                encoding = self._detect_encoding(file_path)
            
            # Авто-определение разделителя
            if not separator:
                separator = self._detect_separator(file_path, encoding)
            
            logger.info(f"CSV: кодировка={encoding}, разделитель={repr(separator)}")
            
            # Читаем CSV
            df = pd.read_csv(
                file_path,
                sep=separator,
                encoding=encoding,
                on_bad_lines='warn',
                skipinitialspace=True
            )
            
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
                'detected_encoding': encoding,
                'detected_separator': separator,
                'total_rows': len(non_empty_rows),
                'errors': []
            }
            
            logger.info(f"Успешно распарсен CSV: {result['total_rows']} строк")
            return result
            
        except Exception as e:
            error_msg = f"Ошибка при чтении CSV: {str(e)}"
            logger.error(error_msg)
            return {
                'headers': [],
                'rows': [],
                'errors': [error_msg]
            }

    def _detect_encoding(self, file_path: str) -> str:
        """Определяет кодировку файла методом перебора."""
        for encoding in self.encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1024)  # Читаем первые 1KB
                return encoding
            except (UnicodeDecodeError, LookupError):
                continue
        
        # По умолчанию UTF-8
        return 'utf-8'

    def _detect_separator(self, file_path: str, encoding: str) -> str:
        """Определяет разделитель по первым строкам файла."""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                first_lines = [f.readline() for _ in range(5)]
            
            # Считаем количество разделителей в каждой строке
            separator_counts = {}
            for sep in self.separators:
                counts = [line.count(sep) for line in first_lines]
                # Разделитель должен встречаться одинаковое количество раз в строках
                if len(set(counts)) == 1 and counts[0] > 0:
                    separator_counts[sep] = counts[0]
            
            if separator_counts:
                # Возвращаем разделитель с максимальным количеством вхождений
                return max(separator_counts, key=separator_counts.get)
            
            # По умолчанию запятая
            return ','
            
        except Exception as e:
            logger.warning(f"Не удалось определить разделитель: {str(e)}")
            return ','

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Очистка DataFrame."""
        # Удаляем полностью пустые столбцы
        df = df.dropna(axis=1, how='all')
        
        # Удаляем полностью пустые строки
        df = df.dropna(axis=0, how='all')
        
        # Заменяем пустые ячейки на пустые строки
        df = df.fillna('')
        
        # Нормализуем заголовки
        df.columns = [str(col).strip() for col in df.columns]
        
        return df

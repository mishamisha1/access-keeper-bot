"""
Парсер PDF файлов.
Использует pdfplumber для извлечения текста и таблиц.
Соответствует ISO 27001 A.12.4 (Логирование).
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import pdfplumber

logger = logging.getLogger(__name__)


class PDFParser:
    """Парсер для PDF файлов."""

    def __init__(self):
        self.supported_extensions = ['.pdf']

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Парсит PDF файл.
        Извлекает таблицы и текст.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Dict с headers, rows и errors
        """
        try:
            logger.info(f"Чтение PDF файла: {file_path}")
            
            # Пробуем извлечь таблицы
            tables_data = self._extract_tables(file_path)
            
            if tables_data:
                # Если есть таблицы, используем первую непустую
                for table_data in tables_data:
                    if table_data['rows']:
                        logger.info(f"Найдена таблица в PDF: {table_data['row_count']} строк")
                        return {
                            'headers': table_data['headers'],
                            'rows': table_data['rows'],
                            'source_type': 'table',
                            'page': table_data.get('page', 1),
                            'total_rows': table_data['row_count'],
                            'errors': []
                        }
            
            # Если таблиц нет, извлекаем текст
            text_data = self._extract_text(file_path)
            
            if text_data['lines']:
                logger.info(f"Извлечен текст из PDF: {len(text_data['lines'])} строк")
                return {
                    'headers': ['Текст'],
                    'rows': [[line] for line in text_data['lines']],
                    'source_type': 'text',
                    'total_rows': len(text_data['lines']),
                    'errors': text_data.get('warnings', [])
                }
            
            # PDF пуст или содержит только изображения
            return {
                'headers': [],
                'rows': [],
                'source_type': 'empty',
                'total_rows': 0,
                'errors': [
                    'PDF не содержит извлекаемого текста или таблиц. '
                    'Возможно, это сканированный документ. Используйте OCR.'
                ]
            }
            
        except Exception as e:
            error_msg = f"Ошибка при чтении PDF: {str(e)}"
            logger.error(error_msg)
            return {
                'headers': [],
                'rows': [],
                'errors': [error_msg]
            }

    def _extract_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """Извлекает все таблицы из PDF."""
        tables_data = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    tables = page.extract_tables()
                    
                    for table_idx, table in enumerate(tables):
                        if not table:
                            continue
                        
                        # Преобразуем таблицу в наш формат
                        parsed_table = self._parse_table(table, page_num)
                        if parsed_table and parsed_table['rows']:
                            tables_data.append(parsed_table)
                            
        except Exception as e:
            logger.warning(f"Ошибка при извлечении таблиц из PDF: {str(e)}")
        
        return tables_data

    def _parse_table(self, table: List[List[Any]], page_num: int) -> Optional[Dict[str, Any]]:
        """Парсит одну таблицу из pdfplumber."""
        try:
            # Очищаем данные таблицы
            cleaned_rows = []
            for row in table:
                cleaned_row = []
                for cell in row:
                    if cell is None:
                        cleaned_row.append('')
                    else:
                        # Заменяем переносы строк на пробелы
                        text = str(cell).replace('\n', ' ').strip()
                        cleaned_row.append(text)
                
                # Пропускаем полностью пустые строки
                if any(cell != '' for cell in cleaned_row):
                    cleaned_rows.append(cleaned_row)
            
            if not cleaned_rows:
                return None
            
            # Первая строка - заголовки
            headers = cleaned_rows[0] if cleaned_rows else []
            data_rows = cleaned_rows[1:] if len(cleaned_rows) > 1 else []
            
            return {
                'headers': headers,
                'rows': data_rows,
                'page': page_num,
                'row_count': len(data_rows)
            }
            
        except Exception as e:
            logger.warning(f"Ошибка при парсинге таблицы PDF: {str(e)}")
            return None

    def _extract_text(self, file_path: str) -> Dict[str, Any]:
        """Извлекает текст из PDF построчно."""
        lines = []
        warnings = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        # Разбиваем на строки
                        page_lines = text.split('\n')
                        for line in page_lines:
                            cleaned_line = line.strip()
                            if cleaned_line:
                                lines.append(cleaned_line)
                                
        except Exception as e:
            warnings.append(f"Ошибка при извлечении текста: {str(e)}")
        
        # Предупреждение если документ большой
        if len(lines) > 1000:
            warnings.append(f"Большой PDF: {len(lines)} строк.")
        
        return {
            'lines': lines,
            'warnings': warnings
        }

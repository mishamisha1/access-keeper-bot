"""
Универсальный парсер файлов для импорта матриц доступа.
Поддерживает: Excel (.xlsx, .xls), CSV, TXT, DOCX, PDF.
Интегрирует rapidfuzz для интеллектуального маппинга колонок.
Соответствует ISO 27001 A.12.4 (Логирование и мониторинг).
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# Парсеры специфичных форматов
from .excel_parser import ExcelParser
from .csv_parser import CSVParser
from .docx_parser import DocxParser
from .pdf_parser import PDFParser
from .mapper import ColumnMapper

logger = logging.getLogger(__name__)


class FileParser:
    """
    Универсальный интерфейс для парсинга файлов различных форматов.
    Автоматически определяет тип файла и выбирает соответствующий парсер.
    """

    SUPPORTED_EXTENSIONS = {
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.csv': 'csv',
        '.txt': 'text',
        '.docx': 'docx',
        '.pdf': 'pdf'
    }

    def __init__(self):
        self.mapper = ColumnMapper()
        self.parsers = {
            'excel': ExcelParser(),
            'csv': CSVParser(),
            'docx': DocxParser(),
            'pdf': PDFParser()
        }

    def detect_file_type(self, file_path: str) -> Optional[str]:
        """Определяет тип файла по расширению."""
        ext = Path(file_path).suffix.lower()
        return self.SUPPORTED_EXTENSIONS.get(ext)

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Парсит файл и возвращает структурированные данные.
        
        Returns:
            Dict с ключами:
            - 'headers': список заголовков
            - 'rows': список строк данных
            - 'mapped_data': данные с примененным маппингом
            - 'mapping_confidence': уверенность маппинга
            - 'errors': список ошибок
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        file_type = self.detect_file_type(str(file_path))
        
        if not file_type:
            raise ValueError(f"Неподдерживаемый формат файла: {file_path_obj.suffix}")

        logger.info(f"Парсинг файла: {file_path}, тип: {file_type}")

        try:
            if file_type == 'text':
                # Текстовые файлы обрабатываем как CSV или свободный текст
                data = self._parse_text_file(file_path)
            else:
                parser = self.parsers[file_type]
                data = parser.parse(str(file_path))

            # Применяем интеллектуальный маппинг
            mapped_result = self.mapper.map_columns(data)
            
            result = {
                'original_headers': data.get('headers', []),
                'headers': mapped_result['mapped_headers'],
                'rows': data.get('rows', []),
                'mapped_data': mapped_result['mapped_rows'],
                'mapping_confidence': mapped_result['confidence'],
                'mapping_details': mapped_result['details'],
                'row_count': len(data.get('rows', [])),
                'errors': data.get('errors', []),
                'warnings': mapped_result.get('warnings', [])
            }

            logger.info(f"Успешно распарсен файл: {result['row_count']} строк, "
                       f"уверенность маппинга: {result['mapping_confidence']:.2f}")
            
            return result

        except Exception as e:
            logger.error(f"Ошибка при парсинге файла {file_path}: {str(e)}")
            raise

    def _parse_text_file(self, file_path: str) -> Dict[str, Any]:
        """Парсинг текстовых файлов (CSV-like или свободный текст)."""
        import pandas as pd
        
        try:
            # Пробуем прочитать как CSV с разными разделителями
            for sep in [',', ';', '\t', '|']:
                try:
                    df = pd.read_csv(file_path, sep=sep, encoding='utf-8')
                    return {
                        'headers': list(df.columns),
                        'rows': df.values.tolist(),
                        'errors': []
                    }
                except:
                    continue
            
            # Если не CSV, читаем как простой текст
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                return {'headers': [], 'rows': [], 'errors': ['Пустой файл']}
            
            headers = [h.strip() for h in lines[0].split(',')]
            rows = []
            for line in lines[1:]:
                if line.strip():
                    rows.append([cell.strip() for cell in line.split(',')])
            
            return {
                'headers': headers,
                'rows': rows,
                'errors': []
            }
            
        except Exception as e:
            return {
                'headers': [],
                'rows': [],
                'errors': [f"Ошибка чтения текста: {str(e)}"]
            }

    def get_mapping_preview(self, file_path: str) -> Dict[str, Any]:
        """Возвращает превью маппинга для подтверждения пользователем."""
        parsed_data = self.parse_file(file_path)
        
        preview = {
            'total_rows': parsed_data['row_count'],
            'columns_found': len(parsed_data['headers']),
            'mapped_columns': {
                orig: mapped 
                for orig, mapped in zip(
                    parsed_data['original_headers'], 
                    parsed_data['headers']
                )
                if orig != mapped
            },
            'confidence_score': parsed_data['mapping_confidence'],
            'sample_rows': parsed_data['mapped_data'][:3],  # Первые 3 строки
            'warnings': parsed_data.get('warnings', [])
        }
        
        # Проверка на отсутствие критических колонок
        critical_cols = ['full_name', 'login', 'system', 'status']
        mapped_headers = parsed_data['headers']
        missing_critical = [
            col for col in critical_cols 
            if col not in mapped_headers
        ]
        
        if missing_critical:
            preview['warnings'].append(
                f"Отсутствуют критические колонки: {', '.join(missing_critical)}"
            )
        
        return preview

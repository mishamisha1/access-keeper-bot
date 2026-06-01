"""File parser interface and factory."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ParseResult:
    """Result of parsing a file."""
    
    def __init__(self, 
                 headers: List[str],
                 rows: List[Dict[str, Any]],
                 row_count: int,
                 file_type: str,
                 warnings: Optional[List[str]] = None):
        self.headers = headers
        self.rows = rows
        self.row_count = row_count
        self.file_type = file_type
        self.warnings = warnings or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'headers': self.headers,
            'rows': self.rows,
            'row_count': self.row_count,
            'file_type': self.file_type,
            'warnings': self.warnings
        }


class BaseFileParser(ABC):
    """Abstract base class for file parsers."""
    
    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse the file and return structured data."""
        pass
    
    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file."""
        pass


class ExcelParser(BaseFileParser):
    """Parser for Excel files (.xlsx, .xls)."""
    
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in ['.xlsx', '.xls']
    
    def parse(self, file_path: Path) -> ParseResult:
        """Parse Excel file using pandas."""
        warnings = []
        
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            if len(sheet_names) > 1:
                warnings.append(f"Файл содержит {len(sheet_names)} листов. Используется первый лист: {sheet_names[0]}")
            
            # Read first sheet
            df = pd.read_excel(excel_file, sheet_name=sheet_names[0])
            
            # Clean data
            df = df.dropna(how='all')  # Remove completely empty rows
            df = df.fillna('')  # Replace NaN with empty string
            
            # Convert to list of dicts
            rows = df.to_dict('records')
            headers = [str(col) for col in df.columns]
            
            logger.info(f"Parsed Excel file {file_path}: {len(rows)} rows, {len(headers)} columns")
            
            return ParseResult(
                headers=headers,
                rows=rows,
                row_count=len(rows),
                file_type='excel',
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Failed to parse Excel file {file_path}: {e}")
            raise ValueError(f"Не удалось прочитать Excel файл: {str(e)}")


class CSVParser(BaseFileParser):
    """Parser for CSV files."""
    
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.csv'
    
    def parse(self, file_path: Path) -> ParseResult:
        """Parse CSV file with encoding detection."""
        warnings = []
        
        # Try different encodings
        encodings = ['utf-8', 'cp1251', 'latin1', 'utf-8-sig']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                logger.debug(f"Successfully parsed CSV with encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise ValueError("Не удалось определить кодировку CSV файла")
        
        # Clean data
        df = df.dropna(how='all')
        df = df.fillna('')
        
        rows = df.to_dict('records')
        headers = [str(col) for col in df.columns]
        
        logger.info(f"Parsed CSV file {file_path}: {len(rows)} rows")
        
        return ParseResult(
            headers=headers,
            rows=rows,
            row_count=len(rows),
            file_type='csv',
            warnings=warnings
        )


class TextParser(BaseFileParser):
    """Parser for plain text files."""
    
    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.txt'
    
    def parse(self, file_path: Path) -> ParseResult:
        """Parse text file, trying to detect structure."""
        warnings = []
        rows = []
        headers = []
        
        encodings = ['utf-8', 'cp1251', 'latin1']
        content = None
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if not content:
            raise ValueError("Не удалось прочитать текстовый файл")
        
        lines = content.strip().split('\n')
        
        if not lines:
            return ParseResult(headers=[], rows=[], row_count=0, file_type='txt')
        
        # Try to detect if it's CSV-like (has delimiters)
        delimiters = [',', ';', '\t', '|']
        detected_delimiter = None
        
        first_line = lines[0]
        for delim in delimiters:
            if delim in first_line:
                detected_delimiter = delim
                break
        
        if detected_delimiter:
            # Parse as delimited text
            headers = [h.strip() for h in lines[0].split(detected_delimiter)]
            
            for line in lines[1:]:
                if line.strip():
                    values = [v.strip() for v in line.split(detected_delimiter)]
                    if len(values) == len(headers):
                        row = dict(zip(headers, values))
                        rows.append(row)
                    else:
                        warnings.append(f"Строка с неправильным количеством полей: {line[:50]}")
        else:
            # Free-form text - each line is a record
            headers = ['text']
            for line in lines:
                if line.strip():
                    rows.append({'text': line.strip()})
            warnings.append("Текстовый файл не имеет структурированного формата")
        
        logger.info(f"Parsed TXT file {file_path}: {len(rows)} rows")
        
        return ParseResult(
            headers=headers,
            rows=rows,
            row_count=len(rows),
            file_type='txt',
            warnings=warnings
        )


def get_parser_for_file(file_path: Path) -> BaseFileParser:
    """Get appropriate parser for file type."""
    parsers = [ExcelParser(), CSVParser(), TextParser()]
    
    for parser in parsers:
        if parser.can_parse(file_path):
            return parser
    
    raise ValueError(f"Неподдерживаемый тип файла: {file_path.suffix}")


def parse_file(file_path: Path) -> ParseResult:
    """Parse file using appropriate parser."""
    parser = get_parser_for_file(file_path)
    return parser.parse(file_path)

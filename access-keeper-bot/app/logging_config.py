"""
Настройка логирования приложения.
Соответствует требованиям ISO 27001 A.12.4 (логирование и мониторинг).
Не логирует чувствительные данные (токены, пароли, ключи).
"""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.config import config


def setup_logging() -> logging.Logger:
    """
    Настройка системы логирования с защитой от утечки чувствительных данных.
    
    Соответствует:
    - ISO 27001 A.12.4.1 (события логирования)
    - ISO 27001 A.12.4.2 (защита журналов логов)
    """
    
    # Создаем logger
    logger = logging.getLogger("access_keeper_bot")
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Форматтер с маскировкой чувствительных данных
    class SecureFormatter(logging.Formatter):
        """Форматтер, который маскирует чувствительные данные в логах."""
        
        SENSITIVE_PATTERNS = [
            "bot_token",
            "token",
            "secret",
            "password",
            "key",
            "authorization",
        ]
        
        def format(self, record: logging.LogRecord) -> str:
            original_msg = record.getMessage()
            
            # Маскируем потенциально чувствительные данные
            masked_msg = original_msg
            for pattern in self.SENSITIVE_PATTERNS:
                if pattern.lower() in original_msg.lower():
                    masked_msg = f"[SENSITIVE DATA REDACTED] (содержит {pattern})"
                    break
            
            record.msg = masked_msg
            return super().format(record)
    
    formatter = SecureFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler с ротацией
    log_file = config.LOG_FILE
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Запрет propagation для избежания дублирования
    logger.propagate = False
    
    return logger


# Глобальный logger
logger = setup_logging()


def get_logger(name: str = "access_keeper_bot") -> logging.Logger:
    """Получение logger по имени."""
    if name == "access_keeper_bot":
        return logger
    return logging.getLogger(name)

"""
Google OAuth 2.0 авторизация.
Соответствует требованиям ISO 27001 A.9.4 (управление доступом) и A.10.1.1 (криптография).
Использует OAuth 2.0 flow с refresh token для долгосрочного доступа.
"""

import os
import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.config import config
from app.logging_config import get_logger

logger = get_logger(__name__)


class GoogleAuth:
    """
    Класс для управления OAuth 2.0 авторизацией Google.
    Поддерживает Sheets, Drive и Calendar API.
    """
    
    def __init__(
        self,
        client_secret_path: Path | None = None,
        token_path: Path | None = None,
        scopes: list[str] | None = None,
    ):
        """
        Инициализация OAuth клиента.
        
        Args:
            client_secret_path: Путь к client_secret.json
            token_path: Путь для сохранения token.json
            scopes: Список OAuth scopes
        """
        self.client_secret_path = client_secret_path or config.GOOGLE_CLIENT_SECRET_PATH
        self.token_path = token_path or config.GOOGLE_TOKEN_PATH
        self.scopes = scopes or config.SCOPES
        self._credentials: Optional[Credentials] = None
        self._services = {}
    
    @property
    def credentials(self) -> Optional[Credentials]:
        """Получение текущих учетных данных."""
        return self._credentials
    
    def load_credentials(self) -> bool:
        """
        Загрузка сохраненных учетных данных из token.json.
        
        Returns:
            True если успешно загружены, False если нужно авторизоваться
        """
        if not self.token_path.exists():
            logger.info("Token файл не найден, требуется авторизация")
            return False
        
        try:
            with open(self.token_path, "r", encoding="utf-8") as f:
                token_data = json.load(f)
            
            self._credentials = Credentials.from_authorized_user_info(
                token_data, 
                self.scopes
            )
            
            # Проверка валидности токена
            if self._credentials.expired and self._credentials.refresh_token:
                logger.info("Токен истек, пытаемся обновить...")
                try:
                    self._credentials.refresh(Request())
                    self._save_credentials()
                    logger.info("Токен успешно обновлен")
                    return True
                except Exception as e:
                    logger.error(f"Не удалось обновить токен: {e}")
                    self._credentials = None
                    return False
            
            logger.info("Учетные данные загружены успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки учетных данных: {e}")
            self._credentials = None
            return False
    
    def _save_credentials(self) -> None:
        """Сохранение учетных данных в token.json."""
        if not self._credentials:
            return
        
        # Создаем директорию если не существует
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        
        token_data = {
            "token": self._credentials.token,
            "refresh_token": self._credentials.refresh_token,
            "token_uri": self._credentials.token_uri,
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "scopes": self._credentials.scopes,
        }
        
        with open(self.token_path, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)
        
        # Устанавливаем безопасные права на файл (только владелец)
        try:
            os.chmod(self.token_path, 0o600)
        except Exception as e:
            logger.warning(f"Не удалось установить права на файл токена: {e}")
        
        logger.info(f"Учетные данные сохранены в {self.token_path}")
    
    def get_authorization_url(self) -> str:
        """
        Получение URL для авторизации.
        
        Returns:
            URL для перехода пользователя
        """
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"Файл client_secret.json не найден по пути: {self.client_secret_path}"
            )
        
        flow = InstalledAppFlow.from_client_secrets_file(
            self.client_secret_path,
            self.scopes,
        )
        
        # Генерируем URL без автоматического открытия браузера
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        
        return authorization_url
    
    def authenticate_from_code(self, auth_code: str) -> bool:
        """
        Аутентификация по коду авторизации.
        
        Args:
            auth_code: Код авторизации от Google
            
        Returns:
            True если успешно
        """
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"Файл client_secret.json не найден по пути: {self.client_secret_path}"
            )
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secret_path,
                self.scopes,
            )
            
            # ВInstalledAppFlow есть метод fetch_token для обмена кода на токен
            # Но нам нужно использовать более низкоуровневый подход
            from google.oauth2 import _client as oauth2_client
            from google.auth.transport import _http_client
            
            # Используем стандартный flow с redirect_uri
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            flow.fetch_token(code=auth_code)
            
            self._credentials = flow.credentials
            self._save_credentials()
            
            logger.info("Аутентификация успешна")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка аутентификации: {e}")
            return False
    
    def authenticate_interactive(self) -> bool:
        """
        Интерактивная аутентификация через браузер.
        Используется при первом запуске.
        
        Returns:
            True если успешно
        """
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"Файл client_secret.json не найден по пути: {self.client_secret_path}"
            )
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secret_path,
                self.scopes,
            )
            
            # Запускаем локальный сервер для получения callback
            self._credentials = flow.run_local_server(
                port=0,
                open_browser=True,
                prompt="consent",
            )
            
            self._save_credentials()
            logger.info("Интерактивная аутентификация успешна")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка интерактивной аутентификации: {e}")
            return False
    
    def ensure_authenticated(self) -> bool:
        """
        Проверка и обеспечение аутентификации.
        
        Returns:
            True если аутентифицирован
        """
        if self._credentials and self._credentials.valid:
            return True
        
        if self.load_credentials():
            return True
        
        return False
    
    def get_service(self, service_name: str, version: str = "v4"):
        """
        Получение клиента Google API.
        
        Args:
            service_name: Название сервиса ("sheets", "calendar", "drive")
            version: Версия API
            
        Returns:
            Клиент сервиса
        """
        if not self.ensure_authenticated():
            raise RuntimeError("Требуется авторизация в Google")
        
        cache_key = f"{service_name}_{version}"
        if cache_key in self._services:
            return self._services[cache_key]
        
        service_map = {
            "sheets": ("sheets", "v4"),
            "calendar": ("calendar", "v3"),
            "drive": ("drive", "v3"),
        }
        
        if service_name not in service_map:
            raise ValueError(f"Неизвестный сервис: {service_name}")
        
        api_name, api_version = service_map[service_name]
        service = build(api_name, api_version, credentials=self._credentials)
        self._services[cache_key] = service
        
        return service
    
    @property
    def sheets_service(self):
        """Сервис Google Sheets."""
        return self.get_service("sheets")
    
    @property
    def calendar_service(self):
        """Сервис Google Calendar."""
        return self.get_service("calendar")
    
    @property
    def drive_service(self):
        """Сервис Google Drive."""
        return self.get_service("drive")
    
    def revoke_access(self) -> bool:
        """
        Отзыв доступа и удаление токена.
        
        Returns:
            True если успешно
        """
        try:
            if self.token_path.exists():
                self.token_path.unlink()
                logger.info("Токен удален")
            
            self._credentials = None
            self._services.clear()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка отзыва доступа: {e}")
            return False


# Глобальный экземпляр
google_auth = GoogleAuth()


def get_authorized_user():
    """
    Получить авторизованные учетные данные.
    
    Returns:
        Credentials объект или None если не авторизован
    """
    if google_auth.ensure_authenticated():
        return google_auth.credentials
    return None


def get_sheets_service():
    """Получить сервис Google Sheets."""
    return google_auth.sheets_service


def get_calendar_service():
    """Получить сервис Google Calendar."""
    return google_auth.calendar_service


def get_drive_service():
    """Получить сервис Google Drive."""
    return google_auth.drive_service

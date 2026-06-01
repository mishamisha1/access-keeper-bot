"""Авторизация в Google API через OAuth 2.0."""

import os
import logging
from typing import Optional, List
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource

from app.config import GOOGLE_SCOPES, GOOGLE_CLIENT_SECRET_PATH, GOOGLE_TOKEN_PATH

logger = logging.getLogger(__name__)


class GoogleAuth:
    """Класс для авторизации в Google API."""
    
    def __init__(self, token_path: str = GOOGLE_TOKEN_PATH):
        self.token_path = token_path
        self.creds: Optional[Credentials] = None
        self._load_credentials()
    
    def _load_credentials(self) -> None:
        """Загружает сохранённые учётные данные."""
        if os.path.exists(self.token_path):
            try:
                self.creds = Credentials.from_authorized_user_file(
                    self.token_path, GOOGLE_SCOPES
                )
                logger.info("Учётные данные загружены из %s", self.token_path)
            except Exception as e:
                logger.error("Ошибка загрузки учётных данных: %s", e)
                self.creds = None
    
    def is_authenticated(self) -> bool:
        """Проверяет, авторизован ли пользователь."""
        if not self.creds:
            return False
        
        # Проверяем, не истёк ли токен
        if self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._save_credentials()
                logger.info("Токен обновлён")
                return True
            except Exception as e:
                logger.error("Ошибка обновления токена: %s", e)
                return False
        
        return self.creds.valid
    
    def get_authorization_url(self) -> str:
        """Получает URL для авторизации."""
        if not os.path.exists(GOOGLE_CLIENT_SECRET_PATH):
            raise FileNotFoundError(
                f"Файл client_secret.json не найден по пути: {GOOGLE_CLIENT_SECRET_PATH}\n"
                "Скачайте его из Google Cloud Console и поместите в корень проекта."
            )
        
        flow = InstalledAppFlow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRET_PATH, GOOGLE_SCOPES
        )
        
        # Получаем URL для авторизации
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        
        # Сохраняем flow для дальнейшего использования
        self._flow = flow
        
        return auth_url
    
    def authenticate_from_code(self, code: str) -> bool:
        """Авторизуется по коду из консоли."""
        if not hasattr(self, "_flow"):
            logger.error("Flow не инициализирован. Сначала вызовите get_authorization_url()")
            return False
        
        try:
            self.creds = self._flow.fetch_token(code=code)
            self._save_credentials()
            logger.info("Авторизация успешна")
            return True
        except Exception as e:
            logger.error("Ошибка авторизации: %s", e)
            return False
    
    def authenticate_interactive(self) -> bool:
        """Интерактивная авторизация через браузер (для локальной разработки)."""
        if not os.path.exists(GOOGLE_CLIENT_SECRET_PATH):
            raise FileNotFoundError(
                f"Файл client_secret.json не найден по пути: {GOOGLE_CLIENT_SECRET_PATH}"
            )
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRET_PATH, GOOGLE_SCOPES
            )
            
            # Запускаем локальный сервер для получения кода
            self.creds = flow.run_local_server(port=0)
            self._save_credentials()
            logger.info("Интерактивная авторизация успешна")
            return True
        except Exception as e:
            logger.error("Ошибка интерактивной авторизации: %s", e)
            return False
    
    def _save_credentials(self) -> None:
        """Сохраняет учётные данные в файл."""
        if self.creds:
            token_dir = Path(self.token_path).parent
            token_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.token_path, "w", encoding="utf-8") as f:
                f.write(self.creds.to_json())
            logger.info("Учётные данные сохранены в %s", self.token_path)
    
    def get_service(self, service_name: str, version: str) -> Optional[Resource]:
        """Получает клиент для Google API сервиса."""
        if not self.is_authenticated():
            logger.error("Необходима авторизация")
            return None
        
        try:
            service = build(service_name, version, credentials=self.creds)
            return service
        except Exception as e:
            logger.error("Ошибка создания сервиса %s: %s", service_name, e)
            return None
    
    def get_sheets_service(self) -> Optional[Resource]:
        """Получает клиент Google Sheets API."""
        return self.get_service("sheets", "v4")
    
    def get_drive_service(self) -> Optional[Resource]:
        """Получает клиент Google Drive API."""
        return self.get_service("drive", "v3")
    
    def get_calendar_service(self) -> Optional[Resource]:
        """Получает клиент Google Calendar API."""
        return self.get_service("calendar", "v3")
    
    def revoke_credentials(self) -> None:
        """Отзывает учётные данные."""
        if os.path.exists(self.token_path):
            os.remove(self.token_path)
            logger.info("Учётные данные отозваны")
        self.creds = None


# Глобальный экземпляр для использования в приложении
_google_auth: Optional[GoogleAuth] = None


def get_google_auth() -> GoogleAuth:
    """Получает экземпляр GoogleAuth."""
    global _google_auth
    if _google_auth is None:
        _google_auth = GoogleAuth()
    return _google_auth


def check_google_auth() -> bool:
    """Проверяет авторизацию в Google."""
    auth = get_google_auth()
    return auth.is_authenticated()

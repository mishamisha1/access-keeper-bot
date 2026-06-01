#!/usr/bin/env python3
"""
Скрипт для первоначальной настройки Google OAuth.
Запускается один раз для получения токена доступа.

Использование:
    python -m app.google_auth_setup
"""

import sys
from pathlib import Path

# Добавляем корень проекта в path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.config import config
from app.logging_config import logger
from app.google.auth import google_auth


def main():
    """Основная функция настройки OAuth."""
    print("=" * 60)
    print("Access Keeper Bot - Настройка Google OAuth")
    print("=" * 60)
    
    # Проверка наличия client_secret.json
    if not config.GOOGLE_CLIENT_SECRET_PATH.exists():
        print(f"\n❌ Ошибка: Файл client_secret.json не найден!")
        print(f"   Путь: {config.GOOGLE_CLIENT_SECRET_PATH}")
        print("\n📋 Инструкция:")
        print("1. Перейдите в Google Cloud Console: https://console.cloud.google.com/")
        print("2. Создайте проект или выберите существующий")
        print("3. Включите API:")
        print("   - Google Sheets API")
        print("   - Google Calendar API")
        print("   - Google Drive API")
        print("4. Создайте учетные данные (OAuth 2.0 Client ID)")
        print("5. Скачайте файл client_secret.json")
        print(f"6. Поместите файл в: {config.GOOGLE_CLIENT_SECRET_PATH}")
        print("\nПосле этого запустите скрипт снова.")
        return 1
    
    print(f"\n✅ Файл client_secret.json найден")
    print(f"   Путь: {config.GOOGLE_CLIENT_SECRET_PATH}")
    
    # Проверяем есть ли уже токен
    if config.GOOGLE_TOKEN_PATH.exists():
        print(f"\n⚠️  Токен уже существует: {config.GOOGLE_TOKEN_PATH}")
        print("Хотите переавторизоваться?")
        print("1 - Да, получить новый токен")
        print("2 - Нет, использовать существующий")
        print("3 - Удалить существующий токен и выйти")
        
        choice = input("\nВаш выбор (1/2/3): ").strip()
        
        if choice == "3":
            config.GOOGLE_TOKEN_PATH.unlink()
            print("Токен удален.")
            return 0
        elif choice == "2":
            print("Используем существующий токен.")
            if google_auth.ensure_authenticated():
                print("\n✅ Авторизация успешна!")
                return 0
            else:
                print("\n❌ Существующий токен недействителен.")
        # Если choice == "1", продолжаем с авторизацией
    
    print("\n" + "=" * 60)
    print("Авторизация в Google")
    print("=" * 60)
    
    print("\n📋 Шаги авторизации:")
    print("1. Откройте URL ниже в браузере")
    print("2. Войдите в свой Google аккаунт")
    print("3. Предоставьте доступ к API")
    print("4. Скопируйте код авторизации")
    print("5. Вставьте код в поле ввода")
    
    try:
        auth_url = google_auth.get_authorization_url()
        print(f"\n🔗 URL для авторизации:\n{auth_url}\n")
        
        auth_code = input("Введите код авторизации: ").strip()
        
        if not auth_code:
            print("❌ Код авторизации не введен.")
            return 1
        
        print("\n⏳ Обработка кода...")
        
        if google_auth.authenticate_from_code(auth_code):
            print("\n" + "=" * 60)
            print("✅ Авторизация успешна!")
            print("=" * 60)
            
            # Проверяем работу API
            print("\n🧪 Проверка подключения к API...")
            
            try:
                sheets_service = google_auth.sheets_service
                print("✅ Google Sheets API доступен")
            except Exception as e:
                print(f"❌ Google Sheets API: {e}")
            
            try:
                calendar_service = google_auth.calendar_service
                print("✅ Google Calendar API доступен")
            except Exception as e:
                print(f"❌ Google Calendar API: {e}")
            
            try:
                drive_service = google_auth.drive_service
                print("✅ Google Drive API доступен")
            except Exception as e:
                print(f"❌ Google Drive API: {e}")
            
            print(f"\n💾 Токен сохранен в: {config.GOOGLE_TOKEN_PATH}")
            print("\nТеперь вы можете запустить бота:")
            print("  python -m app.main")
            
            return 0
            
        else:
            print("\n❌ Ошибка авторизации. Попробуйте еще раз.")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n❌ Процесс прерван пользователем.")
        return 1
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        logger.exception("Ошибка при настройке OAuth")
        return 1


if __name__ == "__main__":
    sys.exit(main())

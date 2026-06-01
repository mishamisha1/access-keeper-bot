"""Скрипт для интерактивной авторизации Google."""

import sys
from app.google.auth import get_google_auth


def main():
    """Запускает интерактивную авторизацию Google."""
    print("🔐 Авторизация в Google API\n")
    
    auth = get_google_auth()
    
    if auth.is_authenticated():
        print("✅ Вы уже авторизованы!")
        return
    
    try:
        print("1. Откройте следующую ссылку в браузере:\n")
        auth_url = auth.get_authorization_url()
        print(auth_url)
        print("\n2. Разрешите доступ к вашему Google аккаунту")
        print("3. Скопируйте код из браузера и вставьте его ниже:\n")
        
        code = input("Код авторизации: ").strip()
        
        if not code:
            print("❌ Код не введён")
            sys.exit(1)
        
        if auth.authenticate_from_code(code):
            print("\n✅ Авторизация успешна!")
            print("Токен сохранён в token.json")
        else:
            print("\n❌ Ошибка авторизации")
            sys.exit(1)
            
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("\nПоложите client_secret.json в корень проекта")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

# Access Keeper Bot

Telegram-бот для автоматизации матриц доступа, выдачи временных доступов, заполнения Google Sheets и создания напоминаний в Google Calendar.

## 📋 Описание

Бот помогает ИБ-специалистам управлять матрицами доступа:
- Создавать Google Sheets таблицы под матрицы доступа
- Добавлять временные доступы из текста
- Импортировать данные из файлов (Excel, CSV, DOCX, PDF)
- Создавать события в Google Calendar с напоминаниями
- Отслеживать истекающие и просроченные доступы
- Продлевать и отзывать доступы

## 🔧 Установка

### 1. Создание Telegram-бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Придумайте имя и username для бота
4. Скопируйте полученный токен

### 2. Узнайте свой Telegram User ID

1. Откройте бота [@userinfobot](https://t.me/userinfobot)
2. Нажмите Start
3. Скопируйте ваш User ID (число)

### 3. Настройка Google API

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите API:
   - Google Sheets API
   - Google Drive API
   - Google Calendar API
4. Создайте OAuth 2.0 Client ID:
   - Перейдите в "APIs & Services" → "Credentials"
   - Нажмите "Create Credentials" → "OAuth client ID"
   - Выберите "Desktop app"
   - Скачайте файл `client_secret.json`
5. Положите `client_secret.json` в корень проекта

### 4. Настройка переменных окружения

```bash
cp .env.example .env
```

Заполните `.env`:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_botfather
ALLOWED_TELEGRAM_USER_IDS=ваш_user_id

GOOGLE_CLIENT_SECRET_PATH=client_secret.json
GOOGLE_TOKEN_PATH=token.json

DB_PATH=data/access_keeper.db

DEFAULT_SPREADSHEET_ID=
DEFAULT_SHEET_NAME=Временные доступы
DEFAULT_CALENDAR_ID=primary

TIMEZONE=Asia/Almaty
DEFAULT_EVENT_HOUR=9
DEFAULT_EVENT_MINUTE=0
DEFAULT_REMINDER_DAYS=1,0
DEFAULT_ACCESS_ACTION=Забрать доступ

RATE_LIMIT_SECONDS=3
```

## 🚀 Запуск

### Локальный запуск

```bash
# Создаём виртуальное окружение
python -m venv .venv

# Активируем
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Первая авторизация Google (интерактивная)
python -m app.google_auth_setup

# Запускаем бота
python -m app.main
```

### Запуск через Docker

```bash
# Копируем .env.example в .env и заполняем
cp .env.example .env

# Кладём client_secret.json в корень проекта

# Запускаем
docker-compose up --build
```

## 📖 Использование

### Основные команды

- `/start` - Запустить бота
- `/help` - Показать справку
- `/access <текст>` - Быстро добавить временный доступ
- `/new_matrix` - Создать новую матрицу
- `/grant_access` - Пошаговое добавление доступа
- `/revoke_access` - Отозвать доступ
- `/extend_access` - Продлить доступ
- `/access_due` - Показать истекающие доступы
- `/access_overdue` - Показать просроченные доступы
- `/import_file` - Импорт из файла
- `/bind_sheet` - Привязать таблицу
- `/my_sheets` - Мои таблицы
- `/settings` - Настройки

### Примеры использования /access

```
/access Саксонов Михаил, доступ на 2 недели, основание: совместная работа с разработчиками

/access Иванов Иван, Jira read-only на 3 дня, причина: задача DEV-123

/access Петров Петр, Splunk admin на месяц, основание INC-12345

/access Сидорова Анна, доступ до пятницы, причина: аудит логов
```

### Первый запуск и авторизация

При первом запуске нужно авторизоваться в Google:

```bash
python -m app.google_auth_setup
```

Бот выдаст ссылку. Откройте её в браузере, разрешите доступ, скопируйте код и вставьте в консоль.

Токен сохранится в `data/token.json`.

## 📁 Структура проекта

```
access-keeper-bot/
├── app/
│   ├── main.py              # Точка входа
│   ├── config.py            # Конфигурация
│   ├── logging_config.py    # Логирование
│   ├── bot/
│   │   ├── handlers.py      # Обработчики команд
│   │   ├── keyboards.py     # Клавиатуры
│   │   └── states.py        # FSM состояния
│   ├── google/
│   │   ├── auth.py          # OAuth авторизация
│   │   ├── sheets.py        # Google Sheets API
│   │   └── calendar.py      # Google Calendar API
│   ├── parsers/
│   │   ├── text_parser.py   # Парсер текста
│   │   └── file_parser.py   # Парсер файлов
│   ├── services/
│   │   ├── access_service.py # Сервис доступов
│   │   └── date_service.py   # Сервис дат
│   ├── templates/           # Шаблоны матриц
│   └── db/
│       ├── database.py      # SQLite БД
│       └── models.py        # Модели данных
├── data/                    # Данные (токены, БД)
├── requirements.txt         # Зависимости
├── Dockerfile              # Docker образ
├── docker-compose.yml      # Docker Compose
├── .env.example            # Шаблон переменных
└── README.md               # Этот файл
```

## 🔒 Безопасность

- `client_secret.json` и `token.json` не хранятся в репозитории
- `.env` файл в `.gitignore`
- Доступ только для разрешённых Telegram User IDs
- Rate limiting для защиты от спама

## ⚠️ Частые ошибки

### "Google не авторизован"
Запустите `python -m app.google_auth_setup` для авторизации.

### "Таблица не найдена"
Используйте `/bind_sheet` для привязки таблицы.

### "Доступ запрещён"
Проверьте `ALLOWED_TELEGRAM_USER_IDS` в `.env`.

### Ошибки Google API
Проверьте, что включены нужные API в Google Cloud Console.

## 📝 Лицензия

MIT

# Access Keeper Bot - Инструкция для Kali Linux Purple

Эта инструкция предназначена специально для запуска бота **Access Keeper** на операционной системе **Kali Linux Purple**.

## 📋 Предварительные требования

- Установленная ОС Kali Linux Purple
- Учетная запись Google с включенными API
- Учетная запись Telegram и созданный бот
- root-права (или доступ к sudo)

---

## 🚀 Этап 1: Подготовка системы

Откройте терминал и выполните следующие команды для обновления системы и установки необходимых зависимостей:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install git python3 python3-pip python3-venv libxml2-dev libxslt1-dev python3-lxml -y
```

Создайте директорию для проекта:
```bash
mkdir -p ~/access-keeper-bot
cd ~/access-keeper-bot
```

Клонируйте репозиторий:
```bash
git clone https://github.com/mishamisha1/access-keeper-bot.git .
```

---

## 🔑 Этап 2: Настройка Google Cloud Console

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/).
2. Создайте новый проект (например, `access-keeper`).
3. В разделе **APIs & Services > Library** найдите и включите:
   - **Google Sheets API**
   - **Google Drive API**
   - **Google Calendar API**
4. Перейдите в **APIs & Services > OAuth consent screen**:
   - Выберите **External**.
   - Заполните название приложения и email.
   - В разделе **Test users** добавьте свой Gmail.
5. Перейдите в **APIs & Services > Credentials**:
   - Нажмите **Create Credentials > OAuth client ID**.
   - Тип приложения: **Desktop app**.
   - Скачайте файл `client_secret.json`.
6. Сохраните файл `client_secret.json` в папку `~/Downloads`.

---

## ⚙️ Этап 3: Настройка окружения проекта

Переместите файл секретов в папку проекта:
```bash
mv ~/Downloads/client_secret.json ~/access-keeper-bot/
```

Создайте виртуальное окружение Python:
```bash
python3 -m venv venv
source venv/bin/activate
```

Установите зависимости:
```bash
pip install -r requirements.txt
```

Скопируйте шаблон переменных окружения:
```bash
cp .env.example .env
```

Отредактируйте файл `.env`:
```bash
nano .env
```

Заполните следующими данными:
```ini
TELEGRAM_BOT_TOKEN=ваш_токен_бота
ALLOWED_TELEGRAM_USER_IDS=432938586

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
*Замените `ваш_токен_бота` на токен, полученный от @BotFather.*

---

## 🔐 Этап 4: Первая авторизация в Google

Запустите скрипт авторизации:
```bash
python -m app.google_auth_setup
```

1. В терминале появится ссылка. Скопируйте её и откройте в браузере.
2. Войдите в свой Google-аккаунт.
3. Разрешите доступ приложению.
4. Скопируйте код подтверждения и вставьте его в терминал.
5. Файл `token.json` будет сохранен автоматически.

---

## ▶️ Этап 5: Тестовый запуск

Запустите бота в ручном режиме для проверки:
```bash
python -m app.main
```

Если бот запустился без ошибок, нажмите `Ctrl+C` для остановки и перейдите к настройке автозапуска.

---

## 🔄 Этап 6: Настройка автозапуска (Systemd)

Создайте файл сервиса:
```bash
sudo nano /etc/systemd/system/access-keeper.service
```

Вставьте следующее содержимое (замените `kali` на ваше имя пользователя, если оно отличается):
```ini
[Unit]
Description=Access Keeper Telegram Bot
After=network.target

[Service]
User=kali
Group=kali
WorkingDirectory=/home/kali/access-keeper-bot
ExecStart=/home/kali/access-keeper-bot/venv/bin/python -m app.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Сохраните файл (`Ctrl+O`, `Enter`) и выйдите (`Ctrl+X`).

Активируйте и запустите сервис:
```bash
sudo systemctl daemon-reload
sudo systemctl enable access-keeper
sudo systemctl start access-keeper
```

Проверьте статус:
```bash
sudo systemctl status access-keeper
```

Просмотр логов в реальном времени:
```bash
sudo journalctl -u access-keeper -f
```

---

## ✅ Проверка работы

1. Откройте Telegram и найдите своего бота.
2. Нажмите `/start`.
3. Вы должны увидеть главное меню с кнопками.
4. Попробуйте создать матрицу или добавить доступ через `/access`.

---

## 🛠 Решение проблем

**Бот не запускается:**
- Проверьте логи: `sudo journalctl -u access-keeper -n 50`
- Убедитесь, что `client_secret.json` и `token.json` находятся в папке проекта.
- Проверьте правильность токена в `.env`.

**Ошибка авторизации Google:**
- Убедитесь, что ваш email добавлен в **Test users** в Google Cloud Console.
- Удалите `token.json` и пройдите авторизацию заново.

**Ошибки импорта файлов:**
- Убедитесь, что установлены все системные библиотеки: `sudo apt install libxml2-dev libxslt1-dev`.

---

## 📞 Контакты

При возникновении проблем обратитесь к документации в основном файле `README.md` или создайте Issue в репозитории.

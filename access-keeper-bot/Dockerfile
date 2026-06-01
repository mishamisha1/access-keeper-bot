"""Dockerfile для Access Keeper Bot."""

FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаём директорию для данных
RUN mkdir -p /app/data

# Устанавливаем переменную окружения по умолчанию
ENV PYTHONPATH=/app
ENV TZ=Asia/Almaty

# Команда запуска
CMD ["python", "-m", "app.main"]

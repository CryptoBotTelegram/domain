
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 aiuser && \
    chown -R aiuser:aiuser /app

USER aiuser

# Запускаем микросервис
CMD ["python", "main.py"]
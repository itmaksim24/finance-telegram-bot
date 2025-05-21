# 1. Базовый образ с Python
FROM python:3.12-slim

# 2. Рабочая директория
WORKDIR /app

# 3. Скопировать зависимости и установить их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Скопировать весь код в контейнер
COPY . .

# 5. Указать порт (Cloud Run передаёт его в $PORT)
ENV PORT 8080

# 6. Запуск приложения
CMD ["python", "bot.py"]

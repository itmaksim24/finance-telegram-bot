# Dockerfile

# 1. Базовый образ с Python 3.12
FROM python:3.12-slim

# 2. Работаем в /app
WORKDIR /app

# 3. Копируем только файл с зависимостями и ставим их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Копируем весь остальной код
COPY . .

# 5. Указываем порт (Cloud Run слушает этот порт)
ENV PORT 8080
EXPOSE 8080

# 6. Запускаем бота
CMD ["python", "bot.py"]

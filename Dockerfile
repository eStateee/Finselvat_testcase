FROM python:3.10-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала копируем только requirements для лучшего кэширования слоёв
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY app/ ./app/
COPY examples/ ./examples/

# Создаём директорию для БД
RUN mkdir -p /data

# Путь к БД через переменную окружения (монтируется volume на /data)
ENV DB_PATH=/data/app.db

# Непривилегированный пользователь
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app /data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

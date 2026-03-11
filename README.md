# REST API для межведомственного обмена

---

## Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Язык      | Python 3.10+ |
| Фреймворк | FastAPI |
| Валидация | Pydantic v2 |
| БД        | SQLite (файл `data/app.db`) |
| Сервер    | Uvicorn |
| Тесты     | pytest + httpx |
| Контейнер | Docker |

---

## Структура проекта

```
.
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI-приложение, роуты, lifespan
│   ├── schemas.py       # Pydantic-модели (SignedApiData, Transaction, Message, …)
│   ├── crypto.py        # Каноническая сериализация, хэш SHA-256, эмуляция подписи
│   ├── storage.py       # Работа с SQLite-репозиторием
│   └── fixtures/
│       └── guarantee_201_payload.json   # Payload seed-транзакции 201
├── examples/
│   ├── outgoing_search_2024.json        # Тело запроса /outgoing за 2024 год
│   ├── incoming_202_valid.json          # Валидная транзакция 202
│   ├── incoming_203_valid.json          # Валидная транзакция 203
│   └── incoming_202_bad_hash.json       # Транзакция с неверным Hash (→ 400)
├── tests/
│   ├── test_crypto.py   # Unit-тесты: канонизация, хэш, подпись
│   └── test_api.py      # Интеграционные тесты через TestClient
├── data/                # SQLite БД (создаётся автоматически, в .gitignore)
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── generate_examples.py # Скрипт регенерации примеров
```

---


## API Эндпоинты

### GET `/api/health`
Проверка работоспособности сервиса.

**Ответ:** `200 OK` `OK`

---

### POST `/api/messages/outgoing`
Выдаёт транзакции для SYSTEM_A за указанный период.

**Тело запроса:** `SignedApiData`, где `Data = base64(JSON(SearchRequest))`

```json
// SearchRequest
{
  "StartDate": "2024-01-01T00:00:00Z",
  "EndDate": "2024-12-31T23:59:59Z",
  "Limit": 100,
  "Offset": 0
}
```

**Ограничения:** `Limit > 0` и `Limit <= 1000`, иначе `400`.

**Ответ 200:** `SignedApiData`, где `Data = base64(JSON(TransactionsData))`

---

### POST `/api/messages/incoming`
Принимает транзакции от SYSTEM_A (типы 202, 203, 215), сохраняет в БД, генерирует квитки 215.

**Тело запроса:** `SignedApiData`, где `Data = base64(JSON(TransactionsData))`

**Валидация каждой транзакции:**
- `TransactionType == 9`
- `Sign` не пустой
- `Hash` совпадает с пересчитанным
- `SenderBranch == "SYSTEM_A"`, `ReceiverBranch == "SYSTEM_B"`
- `InfoMessageType` in `[202, 203, 215]`
- Наличие `BankGuaranteeHash` в payload (для 202/203)

**Ответ 200:** `SignedApiData` с квитками 215 (пустой массив, если транзакции уже были в БД).

---

### Формат ошибок

```json
{ "error": "Human readable message" }
```

HTTP коды: `400` — ошибка валидации/хэша, `500` — внутренняя ошибка сервера.

---

## Локальный запуск

**Требования:** Python 3.10+

```bash
# 1. Создать и активировать виртуальное окружение
python -m venv venv

# Windows:
venv\Scripts\activate.bat

# Linux/macOS:
source venv/bin/activate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Запустить сервер (авто-перезагрузка при изменении кода)
uvicorn app.main:app --reload
```

Сервис будет доступен на `http://localhost:8000`.

При первом запуске автоматически создаётся `data/app.db` и добавляется seed-транзакция типа 201 (выдача гарантии).

> **Сброс БД:** удалите файл `data/app.db` и перезапустите сервис.

---

## Запуск через Docker

```bash
# Сборка образа
docker build -t system-b-api .

# Запуск с постоянным хранилищем БД
docker run -d \
  --name system-b \
  -p 8000:8000 \
  -v system-b-data:/data \
  system-b-api

# Проверка здоровья
docker exec system-b curl -s http://localhost:8000/api/health

# Просмотр логов
docker logs -f system-b

# Остановка
docker stop system-b && docker rm system-b
```

> Данные БД хранятся в Docker volume `system-b-data` и переживают перезапуск контейнера.

---


## Тесты

```bash
# Все тесты (unit + интеграционные)
pytest -v

# Только unit-тесты модуля crypto
pytest tests/test_crypto.py -v

# Только интеграционные тесты API
pytest tests/test_api.py -v

# С выводом покрытия
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

Интеграционные тесты используют изолированную in-memory SQLite БД (`DB_PATH=:memory:`), не затрагивая данные разработки.

---

## Примеры curl-запросов

> **Windows PowerShell:** используйте `curl.exe` (встроенный) и передавайте данные через `@examples/...` чтобы избежать проблем с кавычками.

### 1. Health-check

```bash
# Linux/macOS
curl -i http://localhost:8000/api/health

# Windows PowerShell
curl.exe -i http://localhost:8000/api/health
```

Ожидаемый ответ: `200 OK` и тело `OK`.

---

### 2. Запрос исходящих (outgoing) — транзакции за 2024 год

```bash
# Linux/macOS
curl -s -X POST http://localhost:8000/api/messages/outgoing \
  -H "Content-Type: application/json" \
  -d @examples/outgoing_search_2024.json

# Windows PowerShell
curl.exe -s -X POST http://localhost:8000/api/messages/outgoing `
  -H "Content-Type: application/json" `
  -d @examples/outgoing_search_2024.json
```

Ожидаемый ответ: `200` JSON с полями `Data`, `Sign`, `SignerCert`. Внутри `Data` (после base64-decode) — `TransactionsData` с `Count >= 1` (seed-транзакция 201).

---

### 3. Приём входящих (incoming) — валидная транзакция 202

```bash
# Linux/macOS
curl -s -X POST http://localhost:8000/api/messages/incoming \
  -H "Content-Type: application/json" \
  -d @examples/incoming_202_valid.json

# Windows PowerShell
curl.exe -s -X POST http://localhost:8000/api/messages/incoming `
  -H "Content-Type: application/json" `
  -d @examples/incoming_202_valid.json
```

Ожидаемый ответ: `200` JSON с `SignedApiData`, внутри `Data` — `TransactionsData` содержит сгенерированный квиток 215.

---

### 4. Приём входящих — транзакция с неверным Hash (ошибка 400)

```bash
# Linux/macOS
curl -i -X POST http://localhost:8000/api/messages/incoming \
  -H "Content-Type: application/json" \
  -d @examples/incoming_202_bad_hash.json

# Windows PowerShell
curl.exe -i -X POST http://localhost:8000/api/messages/incoming `
  -H "Content-Type: application/json" `
  -d @examples/incoming_202_bad_hash.json
```

Ожидаемый ответ: `400 Bad Request` и `{"error": "Invalid Hash in Transaction"}`.

---

### 5. End-to-end: квиток появляется в outgoing

```bash
# Сначала отправьте 202 (шаг 3), затем снова запросите outgoing:
# Linux/macOS
curl -s -X POST http://localhost:8000/api/messages/outgoing \
  -H "Content-Type: application/json" \
  -d @examples/outgoing_search_2024.json

# Windows PowerShell
curl.exe -s -X POST http://localhost:8000/api/messages/outgoing `
  -H "Content-Type: application/json" `
  -d @examples/outgoing_search_2024.json
```

В `Count` должно быть не менее 2: seed-транзакция 201 и сгенерированный квиток 215.

---

### 6. Регенерация example-файлов

Если примеры устарели или нужны свежие (например после смены ChainGuid):

```bash
# Активируйте venv, затем:
python generate_examples.py
```

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DB_PATH`  | `data/app.db` | Путь к файлу SQLite. Используйте `:memory:` для тестов. |

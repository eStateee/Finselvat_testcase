# Система Б (Эмуляция реестра)

Реализация REST API сервиса "Системы Б" для приёма и выдачи транзакций межведомственного обмена. Поддерживает алгоритмы хеширования и канонической сериализации.

## Запуск без Docker (локально)
1. Установите виртуальное окружение и зависимости (Python 3.10+):
```bash
python -m venv venv

# В Windows:
venv\Scripts\activate.bat
# В Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```
2. Поднимите сервер:
```bash
uvicorn app.main:app --reload
```
Доступно на `http://localhost:8000`

## Запуск через Docker
```bash
docker build -t system_b_api .
docker run -p 8000:8000 system_b_api
```

---

## Примеры вызовов API (через curl)
*Примечание: в Windows лучше использовать встроенный `curl.exe` и подставлять данные из файлов через символ `@` (`@examples/...`), чтобы избежать проблем с кавычками PowerShell.*

### 1. Health-check
```bash
curl -i http://localhost:8000/api/health
```

### 2. Запрос исходящих данных (Outgoing)
Запрос списка транзакций, адресованных SYSTEM_A за 2024 год:
```bash
curl -s -X POST http://localhost:8000/api/messages/outgoing ^
  -H "Content-Type: application/json" ^
  -d @examples/outgoing_search_2024.json
```

### 3. Отправка входящих данных (Incoming)
Отправка корректной транзакции 202 (должна создать и вернуть квиток 215):
```bash
curl -s -X POST http://localhost:8000/api/messages/incoming ^
  -H "Content-Type: application/json" ^
  -d @examples/incoming_202_valid.json
```

Отправка транзакции с неверным Hash (вернет 400 Bad Request):
```bash
curl -i -X POST http://localhost:8000/api/messages/incoming ^
  -H "Content-Type: application/json" ^
  -d @examples/incoming_202_bad_hash.json
```

## Внутренние алгоритмы хеша и подписи
- **Каноническая сериализация JSON**: Осуществляется без пробелов `separators=(',', ':')`, сохраняет пустые `null` поля, упорядочивает ключи в строго заданном ТЗ порядке.
- **Transaction Hash**: Вычисляется как SHA-256 (HEX UPPER) от строки канонического JSON транзакции, где поле `Hash` обнулено, а `Sign` выступает в виде пустой строки `""`.
- **Transaction Sign**: Эмулируется путем преобразования из сырых байтов HEX хеша в строку `Base64`.
- **SignedApiData Sign**: Эмулируется как `Base64(SHA256(UTF8(Data)))`, где Data строка с полезной нагрузкой.

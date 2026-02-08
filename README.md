# Payments

Сервис обработки платежей с комиссией и асинхронной фоновой обработкой. Проект построен по Clean Architecture и предназначен для надёжной обработки платежей с ретраями, мониторингом и устойчивостью к сбоям внешнего платёжного шлюза.

## Возможности
- Приём платежей (deposit/withdraw) с комиссией 2%.
- Асинхронная обработка через воркер (не блокирует API).
- Гарантированная доставка задач через очередь `payment_tasks` в БД.
- Retry с exponential backoff, jitter и таймаутами.
- Idempotency‑key для защиты от повторных запросов.
- Dead Letter Queue (DLQ) для окончательно неуспешных задач.
- Метрики (in‑memory) и health‑check.
- Swagger/OpenAPI документация.

## Установка
### 1. Клонирование репозитория
```bash
git clone https://github.com/shirohir0/Payments/
cd Payments
```
Скачивает репозиторий и переходит в папку проекта.

### 2. Установка зависимостей
```bash
poetry install
```
Создаёт виртуальное окружение и устанавливает зависимости проекта.

### 3. Настройка переменных окружения
Создайте файл `.env` на основе `.env.example`.

**Linux/macOS:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

## Запуск
### 1. Запуск базы данных через Docker Compose
```bash
docker compose up -d db
```
Запускает PostgreSQL в фоне.

### 2. Запуск сервиса
```bash
uvicorn app.main:app --reload
```
Запускает API‑сервис с автоперезагрузкой.

### Альтернатива: запуск всего проекта через Docker Compose
```bash
docker compose up --build
```
Собирает и запускает API + mock‑gateway + базу данных одной командой.

## Использование
### Swagger
Документация доступна по адресу:
- `http://localhost:8000/docs`

### Примеры запросов (curl)
**Создать пользователя:**
```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H 'Content-Type: application/json' \
  -d '{"balance": 1000}'
```

**Пополнение:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/deposit \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 123e4567-e89b-12d3-a456-426614174000' \
  -d '{"user_id": 1, "deposit": 200}'
```

**Списание:**
```bash
curl -X POST http://localhost:8000/api/v1/payments/withdraw \
  -H 'Content-Type: application/json' \
  -d '{"user_id": 1, "amount": 50}'
```

**Проверка статуса платежа:**
```bash
curl http://localhost:8000/api/v1/payments/1
```

## Скриншоты
![Запуск сервиса](image.png)
![Swagger UI](image-1.png)
![Swagger UI](image-2.png)
![Пример запроса](image-3.png)
![Пример запроса](image-4.png)
![Пример запроса](image-5.png)
![Пример запроса](image-6.png)

## Тесты
```bash
poetry run pytest -q
```
Запускает тесты проекта.

## .env.example
```env
# ===============================
# Application
# ===============================
APP_NAME=Payment Service
APP_ENV=local
DEBUG=true

# ===============================
# Database
# ===============================
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/payments
AUTO_CREATE_TABLES=true

# ===============================
# External services
# ===============================
PAYMENT_GATEWAY_URL=http://localhost:8000/api/v1/mock-gateway
GATEWAY_TIMEOUT_SECONDS=1.0
GATEWAY_MAX_ATTEMPTS=3
GATEWAY_BACKOFF_BASE_SECONDS=1.0
GATEWAY_BACKOFF_MAX_SECONDS=30.0
GATEWAY_BACKOFF_JITTER_SECONDS=0.5

# ===============================
# Worker
# ===============================
WORKER_POLL_INTERVAL_SECONDS=0.5
WORKER_PROCESSING_TIMEOUT_SECONDS=30.0

# ===============================
# Logging
# ===============================
LOG_LEVEL=INFO

# ===============================
# Business
# ===============================
TRANSACTION_FEE=2
```

## Что планируется добавить
- Кэширование балансов.
- Вынести метрики в Prometheus/StatsD (если нужна долговременная история).
- Автоматические миграции БД (по желанию, если решите использовать Alembic).

## Лицензия
MIT

# Payments

Сервис обработки платежей с комиссией и асинхронной фоновой обработкой. Проект построен по Clean Architecture и предназначен для надёжной обработки платежей с ретраями, мониторингом и устойчивостью к сбоям внешнего платёжного шлюза.

## Возможности
- Приём платежей (deposit/withdraw) с комиссией 2%.
- Асинхронная обработка через воркер (не блокирует API).
- Очередь задач через RabbitMQ + Celery (production‑ready).
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
### Запуск через Docker Compose (рекомендуется)
```bash
docker compose up --build
```
Собирает и запускает API + worker + RabbitMQ + mock‑gateway + базу данных одной командой.

### Локальный запуск (без Docker)
1. Запустить PostgreSQL и RabbitMQ отдельно.
2. Запустить API:
```bash
uvicorn app.main:app --reload
```
3. Запустить worker:

**Linux/macOS:**
```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

**Windows (PowerShell):**
```powershell
poetry run celery -A app.workers.celery_app.celery_app worker --loglevel=INFO -P solo
```

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
# Queue (RabbitMQ / Celery)
# ===============================
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=rpc://
CELERY_TASK_TIME_LIMIT_SECONDS=30
CELERY_TASK_SOFT_TIME_LIMIT_SECONDS=25

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

## Лицензия
MIT

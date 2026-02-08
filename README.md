# Payment Processing Service

Надёжный сервис обработки платежей с комиссией и асинхронной фоновой обработкой. Реализован в стиле Clean Architecture: API > Application > Domain > Infrastructure.

**Статус:** реализованы core‑функции, фоновой воркер, ретраи, health‑check, Docker Compose и миграции Alembic.

## Возможности
- Приём платежей (deposit/withdraw) с комиссией 2%.
- Асинхронная фоновая обработка через воркер.
- Интеграция с платёжным шлюзом (mock‑gateway с ошибками и таймаутами).
- Retry с exponential backoff, jitter, max cap и таймаутами.
- Idempotency‑key для платежей.
- Статус платежа и история транзакций.
- Health‑check эндпоинт.
- Docker Compose: запуск одной командой.
- Alembic миграции.

## Архитектура
Сервис построен по Clean Architecture:
- **Domain**: бизнес‑сущности и правила.
- **Application**: use cases.
- **Infrastructure**: БД, репозитории, gateway‑клиент.
- **API**: HTTP‑интерфейс (FastAPI).
- **Workers**: фоновая обработка платежей.

## Быстрый старт (Docker Compose)
1. Запуск всех сервисов:
```bash
docker compose up --build
```

2. Swagger UI:
- `http://localhost:8000/docs`

3. Health‑check:
- `GET /api/v1/health`

## Быстрый старт (локально)
1. Установить зависимости.
```bash
poetry install
```

2. Настроить `.env`.
```env
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/payments
PAYMENT_GATEWAY_URL=http://localhost:8000/api/v1/mock-gateway
TRANSACTION_FEE=2
AUTO_CREATE_TABLES=true
GATEWAY_TIMEOUT_SECONDS=1.0
GATEWAY_MAX_ATTEMPTS=3
GATEWAY_BACKOFF_BASE_SECONDS=1.0
GATEWAY_BACKOFF_MAX_SECONDS=30.0
GATEWAY_BACKOFF_JITTER_SECONDS=0.5
WORKER_POLL_INTERVAL_SECONDS=0.5
WORKER_PROCESSING_TIMEOUT_SECONDS=30.0
```

3. Применить миграции.
```bash
alembic upgrade head
```

4. Запустить приложение.
```bash
uvicorn app.main:app --reload
```

5. Документация API.
- Swagger UI: `http://localhost:8000/docs`

## Основные эндпоинты
- `POST /api/v1/users/` — создать пользователя.
- `POST /api/v1/payments/deposit` — пополнение (асинхронно).
- `POST /api/v1/payments/withdraw` — списание (асинхронно).
- `GET /api/v1/payments/{payment_id}` — статус платежа.
- `GET /api/v1/health` — health‑check.
- `POST /api/v1/mock-gateway/pay` — mock‑gateway (для локального теста).

## Idempotency‑key
Для защиты от повторных запросов можно передать заголовок:
```
Idempotency-Key: <uuid>
```
Если ключ уже использовался для этого пользователя, вернётся существующий `payment_id`.

## Пример сценария
1. Создать пользователя:
```bash
curl -X POST http://localhost:8000/api/v1/users/ \
  -H 'Content-Type: application/json' \
  -d '{"balance": 1000}'
```

2. Пополнение:
```bash
curl -X POST http://localhost:8000/api/v1/payments/deposit \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 123e4567-e89b-12d3-a456-426614174000' \
  -d '{"user_id": 1, "deposit": 200}'
```

3. Проверка статуса:
```bash
curl http://localhost:8000/api/v1/payments/1
```

## Фоновая обработка
- Воркер запускается на старте приложения.
- Берёт платежи со статусом `NEW` или «зависшие» `PROCESSING`.
- Выполняет запрос к шлюзу с retry/backoff, jitter и max cap.
- На успехе обновляет баланс пользователя.

## Поведение при ошибках
- Ошибки шлюза ретраятся до `GATEWAY_MAX_ATTEMPTS`.
- Неретраемые 4xx (кроме 429) помечаются как `failed` сразу.
- Недостаточно средств при списании сохраняется как `failed` с `last_error=insufficient_funds`.

## Модель данных
Таблицы:
- `users`: id, balance
- `payments`: amount, commission, status, attempts, last_error, next_retry_at, locked_at, created_at, updated_at, idempotency_key
- `transactions`: amount, commission, type, status

## Переменные окружения
- `DATABASE_URL` — строка подключения к Postgres.
- `PAYMENT_GATEWAY_URL` — URL шлюза.
- `TRANSACTION_FEE` — комиссия в процентах.
- `AUTO_CREATE_TABLES` — авто‑создание таблиц при старте.
- `GATEWAY_TIMEOUT_SECONDS` — таймаут шлюза.
- `GATEWAY_MAX_ATTEMPTS` — число попыток.
- `GATEWAY_BACKOFF_BASE_SECONDS` — базовый backoff.
- `GATEWAY_BACKOFF_MAX_SECONDS` — максимум backoff.
- `GATEWAY_BACKOFF_JITTER_SECONDS` — джиттер (случайная добавка).
- `WORKER_POLL_INTERVAL_SECONDS` — частота опроса задач.
- `WORKER_PROCESSING_TIMEOUT_SECONDS` — таймаут «зависших» задач.

## Надёжность
- Каждому платежу соответствует запись в БД.
- Повторы при сбоях шлюза с backoff и jitter, 4xx (кроме 429) без ретраев.
- Статус платежа доступен всегда.

## TODO (следующие шаги)
- Автоматический запуск миграций в docker‑compose.
- Dead Letter Queue для окончательно неуспешных задач.
- Метрики.
- Кэширование балансов.

## Лицензия
MIT

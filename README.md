# Payment Processing Service

Надёжный сервис обработки платежей с комиссией и асинхронной фоновой обработкой. Реализован в стиле Clean Architecture: API > Application > Domain > Infrastructure.

**Статус:** реализованы core‑функции, фоновой воркер, ретраи, health‑check, Docker Compose, idempotency‑key, DLQ, метрики, гарантированная доставка задач и подробная Swagger‑документация.

## Возможности
- Приём платежей (deposit/withdraw) с комиссией 2%.
- Асинхронная фоновая обработка через воркер.
- Гарантированная доставка задач (очередь `payment_tasks` в БД).
- Интеграция с платёжным шлюзом (mock‑gateway с ошибками и таймаутами).
- Retry с exponential backoff, jitter, max cap и таймаутами.
- Idempotency‑key для платежей.
- Dead Letter Queue (DLQ) для окончательно неуспешных задач.
- Метрики (in‑memory).
- Статус платежа и история транзакций.
- Health‑check эндпоинт.
- Docker Compose: запуск одной командой.
- Подробная Swagger‑документация (описания, response‑модели, теги).

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

3. Запустить приложение.
```bash
uvicorn app.main:app --reload
```

4. Документация API.
- Swagger UI: `http://localhost:8000/docs`

## Основные эндпоинты
- `POST /api/v1/users/` — создать пользователя.
- `POST /api/v1/payments/deposit` — пополнение (асинхронно).
- `POST /api/v1/payments/withdraw` — списание (асинхронно).
- `GET /api/v1/payments/{payment_id}` — статус платежа.
- `GET /api/v1/health` — health‑check.
- `POST /api/v1/mock-gateway/pay` — mock‑gateway (для локального теста).
- `GET /api/v1/dlq` — список DLQ.
- `GET /api/v1/metrics` — метрики.

## Swagger‑документация
Swagger оформлен через response‑модели, описания полей и теги разделов. Полное описание доступно по:
- `http://localhost:8000/docs`

## Idempotency‑key
Для защиты от повторных запросов можно передать заголовок:
```
Idempotency-Key: <uuid>
```
Если ключ уже использовался для этого пользователя, вернётся существующий `payment_id`.

## Dead Letter Queue (DLQ)
DLQ хранит платежи, которые окончательно провалились:
- исчерпаны попытки (`gateway_max_attempts`),
- неретраемая ошибка (4xx, кроме 429),
- фатальная внутренняя ошибка.

Просмотр:
```
GET /api/v1/dlq?limit=50&offset=0
```

## Метрики
Метрики хранятся в памяти процесса и показывают количество ключевых событий.

Просмотр:
```
GET /api/v1/metrics
```

## Гарантированная доставка задач
- Каждому платежу соответствует запись в очереди `payment_tasks`.
- Воркер берёт задачу через `SELECT ... FOR UPDATE SKIP LOCKED`.
- При падении воркера задача возвращается в очередь по таймауту.
- Задача помечается `DONE` только после успешного завершения платежа.

## Фоновая обработка
- Воркер запускается на старте приложения.
- Берёт задачи со статусом `NEW` или «зависшие» `PROCESSING`.
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
- `payment_tasks`: payment_id, status, attempts, last_error, next_retry_at, locked_at, created_at, updated_at
- `payment_dlq`: payment_id, user_id, amount, commission, payment_type, error, attempts, created_at

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
- Каждому платежу соответствует запись в БД и в очереди задач.
- Обработка платежа атомарна: баланс, платёж, транзакция и задача обновляются в одной транзакции.
- Повторы при сбоях шлюза с backoff и jitter, 4xx (кроме 429) без ретраев.
- Статус платежа доступен всегда.

## TODO (следующие шаги)
- Кэширование балансов.
- Вынести метрики в Prometheus/StatsD (если нужно хранить после рестартов).

## Лицензия
MIT

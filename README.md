# Payment Processing Service

Надёжный сервис обработки платежей с комиссией и асинхронной фоновой обработкой. Реализован в стиле Clean Architecture: API > Application > Domain > Infrastructure.

**Статус:** готов для локального запуска, фоновой обработки, ретраев и проверки статусов платежей.

## Возможности
- Приём платежей (deposit/withdraw) с комиссией 2%.
- Асинхронная фоновая обработка через воркер.
- Интеграция с платёжным шлюзом (mock-gateway с ошибками и таймаутами).
- Retry с exponential backoff и таймаутами.
- Статус платежа и история транзакций.
- Health-check эндпоинт готов к добавлению (см. раздел TODO).

## Архитектура
Сервис построен по Clean Architecture:
- **Domain**: бизнес?сущности и правила.
- **Application**: use cases.
- **Infrastructure**: БД, репозитории, gateway-клиент.
- **API**: HTTP-интерфейс (FastAPI).
- **Workers**: фоновая обработка платежей.

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
- `POST /api/v1/mock-gateway/pay` — mock шлюз (для тестов).

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
  -d '{"user_id": 1, "deposit": 200}'
```

3. Проверка статуса:
```bash
curl http://localhost:8000/api/v1/payments/1
```

## Фоновая обработка
- Воркер запускается на старте приложения.
- Берёт платежи со статусом `NEW` или «зависшие» `PROCESSING`.
- Выполняет запрос к шлюзу с retry/backoff.
- На успехе обновляет баланс пользователя.

## Модель данных
Таблицы:
- `users`: id, balance
- `payments`: amount, commission, status, attempts, last_error, next_retry_at
- `transactions`: amount, commission, type, status

## Переменные окружения
- `DATABASE_URL` — строка подключения к Postgres.
- `PAYMENT_GATEWAY_URL` — URL шлюза.
- `TRANSACTION_FEE` — комиссия в процентах.
- `AUTO_CREATE_TABLES` — авто?создание таблиц при старте.
- `GATEWAY_TIMEOUT_SECONDS` — таймаут шлюза.
- `GATEWAY_MAX_ATTEMPTS` — число попыток.
- `GATEWAY_BACKOFF_BASE_SECONDS` — базовый backoff.
- `WORKER_POLL_INTERVAL_SECONDS` — частота опроса задач.
- `WORKER_PROCESSING_TIMEOUT_SECONDS` — таймаут «зависших» задач.

## Надёжность
- Каждому платежу соответствует запись в БД.
- Повторы при сбоях шлюза с backoff.
- Статус платежа доступен всегда.

## TODO (следующие шаги)
- Health-check эндпоинт с проверкой БД.
- Docker Compose и отдельный mock-gateway сервис.
- Idempotency keys.
- DLQ для окончательно неуспешных задач.
- Метрики.
- Кэширование балансов.

## Лицензия
MIT

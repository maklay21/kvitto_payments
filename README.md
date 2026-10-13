# Kvitto Payments API

Небольшой API платежей на FastAPI, SQLAlchemy 2, PostgreSQL и Pydantic v2. Суммы хранятся и передаются только целым числом копеек.

## Структура

```text
app/
  api/routes.py       HTTP endpoints и проверка подписи вебхука
  core/config.py      настройки из переменных окружения
  core/logging_config.py настройка логирования в консоль и файл
  db/base.py          declarative base
  db/session.py       SQLAlchemy engine и dependency
  models.py           таблицы tariffs и payments
  schemas.py          Pydantic request/response модели
  services.py         тарифы, расчёты, идемпотентность и переходы статуса
  main.py             приложение и seed тарифов при старте
migrations/           Alembic environment и начальная миграция
tests/                API и бизнес-тесты
```

## Запуск локально

Нужны Python 3.11+ и PostgreSQL. Создайте базу и пользователя или используйте значения из `docker-compose.yml`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Укажите корректный `DATABASE_URL` в `.env`, затем выполните миграцию и запустите сервер:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

OpenAPI UI: <http://127.0.0.1:8000/docs>.

## Запуск Docker Compose

```bash
docker compose up --build
```

Compose поднимет PostgreSQL, применит Alembic migration и запустит API на порту 8000. API подключается к базе по внутреннему адресу `db:5432`; порт PostgreSQL на хост не публикуется. Для постоянного окружения задайте одинаковый отдельный пароль БД в настройках сервиса `db` и переменной `DATABASE_URL` в `docker-compose.yml`, а `WEBHOOK_SECRET` — через `.env`. При запуске API напрямую на хосте используйте `localhost:5432`.
Логи создания платежей и обработки вебхуков выводятся в консоль и сохраняются в `logs/app.log`. В Docker Compose папка `./logs` монтируется в контейнер, поэтому файл остаётся на хосте после пересоздания контейнера. Папка создаётся автоматически при запуске; уровень задаётся переменной `LOG_LEVEL` (по умолчанию `INFO`).

## Примеры запросов

Получить тарифы:

```bash
curl http://127.0.0.1:8000/tariffs
```

Создать платёж с промокодом и ключом идемпотентности:

```bash
curl -i http://127.0.0.1:8000/payments \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: order-123' \
  -d '{"tariff_id":"standard","email":"student@example.com","method":"installment","installment_months":3,"promo_code":"kvitto10"}'
```

Проверить платёж:

```bash
curl http://127.0.0.1:8000/payments/<payment_id>
```

Отправить банковский вебхук. Если `WEBHOOK_SECRET` задан, подпись — hex HMAC-SHA256 от точных байтов тела запроса:

```bash
BODY='{"payment_id":"<payment_id>","status":"succeeded"}'
SIGNATURE=$(printf %s "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -hex | awk '{print $2}')
curl -i http://127.0.0.1:8000/webhooks/bank \
  -H 'Content-Type: application/json' \
  -H "X-Signature: $SIGNATURE" \
  -d "$BODY"
```

Получить список с дополнительными фильтрами:

```bash
curl 'http://127.0.0.1:8000/payments?email=student%40example.com&status=succeeded'
```

## Тесты и стиль

```bash
pytest
ruff check .
```

Тесты используют SQLite в памяти; production конфигурация — PostgreSQL. Они проверяют суммы, промокод, график рассрочки, идемпотентность, переходы статуса и 404.

## Основные решения

- Цена и скидка — целые копейки. Промокод `KVITTO10` даёт 10%; код сравнивается без учёта регистра.
- Остаток при делении суммы рассрочки распределяется по одному рублю-копейке в первые платежи.
- Уникальное ограничение PostgreSQL на `idempotency_key` защищает от одновременного создания двух платежей с одним ключом. Повтор возвращает сохранённый платёж с HTTP 200.
- Переходы статуса проверяются в сервисном слое; webhook блокирует строку платежа для конкурентного обновления.
- Webhook проверяет необязательный HMAC-SHA256, если задан `WEBHOOK_SECRET`.

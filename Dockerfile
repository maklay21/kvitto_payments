FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec gunicorn app.main:app --worker-class uvicorn_worker.UvicornWorker --workers 1 --bind 0.0.0.0:8000"]
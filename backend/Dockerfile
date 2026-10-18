FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir --retries 10 --timeout 120 poetry

COPY pyproject.toml poetry.lock /app/
RUN poetry install --no-root --only main --no-interaction --no-ansi

COPY app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--access-log", "--log-level", "info"]

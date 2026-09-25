FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1.0" \
    "uvicorn[standard]>=0.34,<1.0"

COPY app /app/app

EXPOSE 8080

HEALTHCHECK --interval=5s --timeout=3s --retries=10 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/_internal/health', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

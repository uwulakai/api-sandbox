FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/e2e
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pytest.ini run.py ./
COPY tests ./tests
ENV E2E_REPORT_DIR=/reports
ENTRYPOINT ["python", "run.py"]

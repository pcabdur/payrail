FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/pyproject.toml ./api/pyproject.toml
COPY apps/api/app ./api/app
COPY apps/worker/pyproject.toml ./worker/pyproject.toml
COPY apps/worker/payrail_worker ./worker/payrail_worker
RUN pip install --no-cache-dir ./api ./worker
RUN useradd --create-home --uid 10001 appuser
USER appuser
ENV PYTHONPATH=/app/api:/app/worker
CMD ["arq", "payrail_worker.worker.WorkerSettings"]

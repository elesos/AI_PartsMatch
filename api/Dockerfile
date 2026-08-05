FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY deploy ./deploy
COPY pyproject.toml alembic.ini docker-entrypoint.sh ./
RUN pip install --no-cache-dir . && chmod +x /app/docker-entrypoint.sh

FROM base AS test
RUN pip install --no-cache-dir '.[dev]'
COPY tests ./tests
ENTRYPOINT ["pytest"]

FROM base AS runtime

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]

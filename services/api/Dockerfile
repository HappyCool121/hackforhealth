FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl tesseract-ocr libmagic1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY app ./app
COPY alembic.ini ./
COPY tests ./tests
RUN mkdir -p /data/uploads
EXPOSE 8000
CMD ["python", "-m", "app.runtime"]

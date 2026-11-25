# Web app image: Flask API + static frontend.
# Build context is the repository root (see docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Whole repo: the frontend files are served by Flask too (.dockerignore keeps secrets out)
COPY . .

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

WORKDIR /app/backend
EXPOSE 5000
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--access-logfile", "-", "app:app"]

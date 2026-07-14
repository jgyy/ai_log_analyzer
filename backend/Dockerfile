# Production image for the FastAPI backend.
# Used for AWS App Runner / ECS / Fly.io deployment — see DEPLOYMENT.md for
# why a long-lived container was chosen over AWS Lambda for this workload.
FROM python:3.11-slim

WORKDIR /app

# Install system deps needed for bcrypt/psycopg-style native builds.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# Respect $PORT so the same image works on App Runner, Fly.io, Cloud Run, etc.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

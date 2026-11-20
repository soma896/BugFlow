# =========================================================
# Dockerfile for BugFlow Web Application
# =========================================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and seed data
COPY . .

# Expose default HTTP port
EXPOSE 8080
ENV PORT=8080

# Run database initializer and launch application server
CMD ["sh", "-c", "python init_live_db.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]

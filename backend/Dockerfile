FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry (pinned to avoid silent breakage from upstream changes)
RUN pip install "poetry==1.8.3"

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install production dependencies only
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Run as a non-root user to reduce the container's attack surface
RUN addgroup --system app && adduser --system --ingroup app app

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

USER app

# Run with uvicorn — use 2 workers for moderate concurrency
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

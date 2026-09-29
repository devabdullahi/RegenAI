FROM python:3.14-slim

WORKDIR /app

# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry. Pinned to match CI (.github/workflows/ci.yml): poetry.lock is
# lock-version 2.1, which Poetry 1.x cannot read.
RUN pip install "poetry==2.3.3"

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install production dependencies only. --no-root: the app is run from source,
# not installed as a package (the source is not copied yet at this layer).
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction --no-ansi

# Run as a non-root user to reduce the container's attack surface
RUN addgroup --system app && adduser --system --ingroup app app

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

USER app

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

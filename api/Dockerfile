FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies first for caching
COPY dependencies ./dependencies

# Install Python dependencies
RUN pip install --no-cache-dir -r dependencies

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

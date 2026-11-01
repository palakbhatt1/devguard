# Use official Python 3.12 slim image
FROM python:3.12-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy application source code
COPY . .

# Install Python dependencies and devguard package
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Expose FastAPI default port
EXPOSE 8000

# Run Uvicorn production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

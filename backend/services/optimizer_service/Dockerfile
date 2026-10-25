# Optimizer Service Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (OR-Tools requires some build tools)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from backend root
COPY ../../requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ../.. .

# Expose port
EXPOSE 8003

# Run the application
CMD ["uvicorn", "services.optimizer_service.main:app", "--host", "0.0.0.0", "--port", "8003"]

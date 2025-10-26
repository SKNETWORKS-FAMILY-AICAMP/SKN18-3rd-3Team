FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first
COPY . .

# Install Python dependencies from docker folder
RUN pip install --no-cache-dir -r docker/requirements.txt

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]

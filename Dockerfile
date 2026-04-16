FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for psycopg2 and Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies required by the application
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Expose the API port
EXPOSE 8000

# Run the FastAPI server via the main entrypoint
CMD ["python", "src/main.py"]

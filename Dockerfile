FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create .env with defaults if not exists
RUN if [ ! -f .env ]; then \
    echo "DATABASE_URL=postgresql://investment_user:investment_password@postgres:5432/ai_investment_desk" > .env && \
    echo "FRED_API_KEY=${FRED_API_KEY:-demo}" >> .env && \
    echo "DEBUG=True" >> .env; \
    fi

# Run migrations and start server
CMD ["python", "run.py"]

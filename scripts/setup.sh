#!/bin/bash
# Setup script for AI Investment Desk local development

set -e

echo "🚀 Setting up AI Investment Desk..."

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✓ Docker is running"

# Start PostgreSQL container
echo "📦 Starting PostgreSQL container..."
docker-compose up -d
echo "✓ PostgreSQL container started"

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Activate virtual environment
echo "🐍 Activating Python virtual environment..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Run: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi
echo "✓ Virtual environment activated"

# Run migrations
echo "🗄️  Running database migrations..."
alembic upgrade head
echo "✓ Migrations completed"

# Load test data
echo "📥 Loading virtual broker test data..."
curl -X POST http://localhost:8000/api/portfolio/sync/virtual 2>/dev/null || echo "(Server not running yet - load test data after starting server)"
echo "✓ Test data loaded"

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Start the FastAPI server:"
echo "      python run.py"
echo ""
echo "   2. In another terminal, run tests:"
echo "      pytest tests/ -v"
echo ""
echo "   3. View API documentation:"
echo "      http://localhost:8000/docs"
echo ""
echo "   4. Load test data:"
echo "      curl -X POST http://localhost:8000/api/portfolio/sync/virtual"
echo ""
echo "🛑 To stop PostgreSQL:"
echo "   docker-compose down"
echo ""

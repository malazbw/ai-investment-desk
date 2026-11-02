#!/bin/bash
# Reset database for testing

set -e

echo "🗑️  Resetting database..."

if ! docker ps | grep -q ai_investment_desk_db; then
    echo "❌ PostgreSQL container is not running. Start it with: docker-compose up -d"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Drop and recreate migrations
echo "⏳ Dropping existing schema..."
alembic downgrade base 2>/dev/null || true

echo "🔄 Running migrations..."
alembic upgrade head

echo "✅ Database reset complete!"

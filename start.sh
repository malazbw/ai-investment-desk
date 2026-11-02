#!/bin/bash
# Complete startup guide for AI Investment Desk

set -e

echo "🚀 Starting AI Investment Desk..."
echo ""

# Step 1: Navigate to project
echo "📍 Step 1: Navigate to project directory"
cd /Users/hala.al.kuwatly/ai-investment-desk
echo "✓ In project directory"
echo ""

# Step 2: Start PostgreSQL
echo "📦 Step 2: Starting PostgreSQL (Docker)..."
docker compose up -d
echo "✓ PostgreSQL container started"
sleep 3
echo ""

# Step 3: Verify PostgreSQL is healthy
echo "🏥 Step 3: Checking PostgreSQL health..."
docker ps | grep ai_investment_desk_db
echo "✓ PostgreSQL is running"
echo ""

# Step 4: Activate Python environment
echo "🐍 Step 4: Activating Python environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Step 5: Run migrations
echo "🗄️  Step 5: Running database migrations..."
alembic upgrade head
echo "✓ Migrations completed"
echo ""

echo "✅ Setup complete!"
echo ""
echo "📝 Next: Run the server in a new terminal:"
echo "   cd /Users/hala.al.kuwatly/ai-investment-desk"
echo "   source venv/bin/activate"
echo "   python run.py"
echo ""
echo "📝 Then in another terminal, load test data:"
echo "   curl -X POST http://localhost:8000/api/portfolio/sync/virtual"
echo ""
echo "📝 View your portfolio:"
echo "   curl http://localhost:8000/api/portfolio/summary"
echo ""
echo "📝 View API documentation:"
echo "   Open browser: http://localhost:8000/docs"
echo ""

#!/bin/bash
set -e

# Set Python path to include the app directory
export PYTHONPATH="/app:$PYTHONPATH"

echo "🚀 Legal AI System Startup"
echo "=========================="

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h postgres -U legal_user; do
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Check if database needs initialization
echo "🔍 Checking database status..."

# First check if database exists, if not, the initializer will create it
DB_EXISTS=$(PGPASSWORD=legal_pass psql -h postgres -U legal_user -d postgres -t -c "SELECT 1 FROM pg_database WHERE datname = 'cases_llama3.3';" 2>/dev/null || echo "0")

if [ "$DB_EXISTS" != " 1" ]; then
    echo "📊 Database doesn't exist, running initialization..."
    python database_initializer.py
    echo "✅ Database initialization completed"
else
    # Database exists, check if it has tables
    TABLES_COUNT=$(PGPASSWORD=legal_pass psql -h postgres -U legal_user -d cases_llama3.3 -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || echo "0")
    
    if [ "$TABLES_COUNT" -eq "0" ]; then
        echo "📊 Database exists but is empty, running initialization..."
        python database_initializer.py
        echo "✅ Database initialization completed"
    else
        echo "✅ Database already initialized ($TABLES_COUNT tables found)"
    fi
fi

# Start the FastAPI application
echo "🌟 Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
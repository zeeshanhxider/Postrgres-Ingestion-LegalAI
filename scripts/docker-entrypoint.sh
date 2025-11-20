#!/bin/bash
set -e

echo "🚀 Legal AI System - Docker Entrypoint"
echo "======================================="

# Export database credentials for psql commands
export PGPASSWORD=legal_pass

# Wait for PostgreSQL container to be ready
echo "⏳ Waiting for PostgreSQL server..."
until pg_isready -h postgres -U postgres 2>/dev/null; do
  echo "   PostgreSQL not ready yet, waiting..."
  sleep 2
done

echo "✅ PostgreSQL server is ready"

# Run PostgreSQL initialization via the postgres container
echo "🔧 Initializing database user and schema..."
docker exec legal_ai_postgres /docker-entrypoint-initdb.d/init-postgres.sh 2>/dev/null || {
    # If we can't exec into container (not using compose), run locally
    echo "   Running initialization from API container..."
    
    # Check if user exists
    USER_EXISTS=$(PGPASSWORD=legal_pass psql -h postgres -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='legal_user'" 2>/dev/null || echo "")
    
    if [ "$USER_EXISTS" != "1" ]; then
        echo "📝 Creating user: legal_user"
        PGPASSWORD=legal_pass psql -h postgres -U postgres -c "CREATE USER legal_user WITH PASSWORD 'legal_pass';" 2>/dev/null || true
        PGPASSWORD=legal_pass psql -h postgres -U postgres -c "ALTER USER legal_user CREATEDB;" 2>/dev/null || true
    fi
    
    # Check if database exists
    DB_EXISTS=$(PGPASSWORD=legal_pass psql -h postgres -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='cases_llama3.3'" 2>/dev/null || echo "")
    
    if [ "$DB_EXISTS" != "1" ]; then
        echo "📝 Creating database: cases_llama3.3"
        PGPASSWORD=legal_pass psql -h postgres -U postgres -c "CREATE DATABASE \"cases_llama3.3\" OWNER legal_user ENCODING 'UTF8';" 2>/dev/null || true
    fi
    
    # Grant privileges
    PGPASSWORD=legal_pass psql -h postgres -U postgres -d cases_llama3.3 -c "GRANT ALL PRIVILEGES ON DATABASE \"cases_llama3.3\" TO legal_user;" 2>/dev/null || true
    PGPASSWORD=legal_pass psql -h postgres -U postgres -d cases_llama3.3 -c "GRANT ALL ON SCHEMA public TO legal_user;" 2>/dev/null || true
}

# Run Python database initializer (creates tables from init-db.sql)
echo "📊 Running database schema initialization..."
python /app/database_initializer.py

# Start the FastAPI application
echo "🌟 Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


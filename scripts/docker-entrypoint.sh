#!/bin/bash
set -e

echo "🚀 Legal AI System - Docker Entrypoint"
echo "======================================="

# Wait for PostgreSQL container to be ready
echo "⏳ Waiting for PostgreSQL server..."
export PGPASSWORD=postgres123
until pg_isready -h postgres -U postgres 2>/dev/null; do
  echo "   PostgreSQL not ready yet, waiting..."
  sleep 2
done

echo "✅ PostgreSQL server is ready"

# Check if database exists
echo "🔍 Checking database..."
DB_EXISTS=$(psql -h postgres -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='cases_llama3_3'" 2>/dev/null || echo "")

if [ "$DB_EXISTS" != "1" ]; then
    echo "📝 Creating database: cases_llama3_3"
    psql -h postgres -U postgres -c "CREATE DATABASE cases_llama3_3 OWNER postgres ENCODING 'UTF8';" 2>/dev/null || true
else
    echo "✅ Database already exists"
fi

# Check if pgvector extension exists
echo "🔍 Checking pgvector extension..."
EXT_EXISTS=$(psql -h postgres -U postgres -d cases_llama3_3 -tAc "SELECT 1 FROM pg_extension WHERE extname='vector'" 2>/dev/null || echo "")

if [ "$EXT_EXISTS" != "1" ]; then
    echo "📦 Creating pgvector extension..."
    psql -h postgres -U postgres -d cases_llama3_3 -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
else
    echo "✅ pgvector extension already exists"
fi

# Start the FastAPI application
echo "🌟 Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


#!/bin/bash
set -e

# PostgreSQL initialization script
# This script ensures the database and user are created properly

DB_NAME="cases_llama3.3"
DB_USER="legal_user"
DB_PASS="legal_pass"

echo "🔧 Initializing PostgreSQL database..."

# Wait for PostgreSQL to be ready
until pg_isready -U postgres; do
  echo "⏳ Waiting for PostgreSQL to be ready..."
  sleep 2
done

echo "✅ PostgreSQL is ready"

# Check if user exists, create if not
USER_EXISTS=$(psql -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")
if [ "$USER_EXISTS" != "1" ]; then
    echo "📝 Creating user: $DB_USER"
    psql -U postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
    psql -U postgres -c "ALTER USER $DB_USER CREATEDB;"
else
    echo "✅ User $DB_USER already exists"
    # Update password just in case
    psql -U postgres -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';"
fi

# Check if database exists, create if not
DB_EXISTS=$(psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")
if [ "$DB_EXISTS" != "1" ]; then
    echo "📝 Creating database: $DB_NAME"
    psql -U postgres -c "CREATE DATABASE \"$DB_NAME\" OWNER $DB_USER ENCODING 'UTF8';"
else
    echo "✅ Database $DB_NAME already exists"
fi

# Grant all privileges
psql -U postgres -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE \"$DB_NAME\" TO $DB_USER;"
psql -U postgres -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"
psql -U postgres -d "$DB_NAME" -c "GRANT CREATE ON SCHEMA public TO $DB_USER;"
psql -U postgres -d "$DB_NAME" -c "ALTER SCHEMA public OWNER TO $DB_USER;"

# Enable required extensions
echo "📦 Enabling PostgreSQL extensions..."
psql -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS citext;"
psql -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
psql -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS unaccent;"
psql -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

echo "✅ PostgreSQL initialization complete!"


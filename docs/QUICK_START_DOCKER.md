# Quick Setup: Load Your PostgreSQL Dump into Docker with pgvector

Your `cases_llama3.3` file is a PostgreSQL dump. Here's how to load it.

---

## Step 1: Create docker-compose.yml

Create `docker-compose.yml` in your project root:

```yaml
version: "3.8"

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: legal_postgres
    environment:
      POSTGRES_DB: cases_llama3_3
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

---

## Step 2: Start PostgreSQL

```powershell
# Start container
docker-compose up -d

# Wait for PostgreSQL to be ready
Start-Sleep -Seconds 10

# Check status
docker-compose ps
```

---

## Step 3: Create Database and Enable pgvector

```powershell
# Create database
docker exec -it legal_postgres psql -U postgres -c "CREATE DATABASE cases_llama3_3;"

# Enable pgvector extension
docker exec -it legal_postgres psql -U postgres -d cases_llama3_3 -c "CREATE EXTENSION vector;"

# Verify
docker exec -it legal_postgres psql -U postgres -d cases_llama3_3 -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

---

## Step 4: Import Your Database Dump

```powershell
# Copy dump file to container
docker cp "D:\freelance\Dobbs_Data\Postgres_Ingestion_LegalAI\cases_llama3.3" legal_postgres:/tmp/cases_dump.sql

# Import (this may take 5-30 minutes depending on size)
docker exec -it legal_postgres pg_restore -U postgres -d cases_llama3_3 /tmp/cases_dump.sql

# If that fails (wrong format), try:
docker exec -it legal_postgres psql -U postgres -d cases_llama3_3 -f /tmp/cases_dump.sql
```

---

## Step 5: Verify Import

```powershell
# Check tables
docker exec -it legal_postgres psql -U postgres -d cases_llama3_3 -c "\dt"

# Check data
docker exec -it legal_postgres psql -U postgres -d cases_llama3_3 -c "SELECT COUNT(*) FROM cases;"

# Check all tables
docker exec -it legal_postgres psql -U postgres -d cases_llama3_3 -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
```

---

## Step 6: Update Environment Variables

```powershell
# Set for current session
$env:DATABASE_URL = "postgresql://postgres:postgres123@localhost:5432/cases_llama3_3"

# Make permanent (optional)
[System.Environment]::SetEnvironmentVariable('DATABASE_URL', 'postgresql://postgres:postgres123@localhost:5432/cases_llama3_3', 'User')
```

---

## Step 7: Run Brief Migration

```powershell
# Update migration script to use localhost
$env:DB_HOST = "localhost"
$env:DB_NAME = "cases_llama3_3"
$env:DB_PASSWORD = "postgres123"

# Run migration
.\scripts\run_brief_migration.ps1
```

---

## Step 8: Start Ingesting Briefs

```powershell
# Test with single case
python batch_process_briefs.py --case-folder 83895-4

# Process all
python batch_process_briefs.py --briefs-dir downloaded-briefs --year 2024
```

---

## Troubleshooting

### Import fails with "invalid command"

Your dump might be in custom format. Try:

```powershell
# Use pg_restore instead
docker exec -it legal_postgres pg_restore -U postgres -d cases_llama3_3 --verbose /tmp/cases_dump.sql
```

### Import fails with "database does not exist"

Make sure you created the database first:

```powershell
docker exec -it legal_postgres psql -U postgres -c "DROP DATABASE IF EXISTS cases_llama3_3;"
docker exec -it legal_postgres psql -U postgres -c "CREATE DATABASE cases_llama3_3;"
```

### Check dump file format

```powershell
# Check first few bytes
Get-Content "cases_llama3.3" -Encoding Byte -TotalCount 100 | Format-Hex
```

---

## Quick Commands Reference

```powershell
# Start PostgreSQL
docker-compose up -d

# Stop PostgreSQL
docker-compose down

# View logs
docker-compose logs -f

# Connect to database
docker exec -it legal_postgres psql -U postgres -d cases_llama3_3

# Restart PostgreSQL
docker-compose restart
```

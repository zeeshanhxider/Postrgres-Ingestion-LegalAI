# Database Restoration Guide

## Prerequisites

- Docker and Docker Compose installed
- Database container running: `docker-compose up -d`

---

## Option 1: Full Database Restore (with data)

Use this to restore both schema and data from the dump file.

```powershell
# Set password environment variable
$env:PGPASSWORD = "postgres123"

# Restore the database
docker exec -i legal_ai_postgres_v2 pg_restore -U postgres -d cases_llama3_3 --clean --no-owner --no-privileges < cases_llama3_3.dump
```

---

## Option 2: Schema Only Restore

Use this to create just the database structure without data.

```powershell
# Set password environment variable
$env:PGPASSWORD = "postgres123"

# Apply schema
docker exec -i legal_ai_postgres_v2 psql -U postgres -d cases_llama3_3 < current_schema.sql
```

---

## Fresh Start (Drop and Recreate)

If you need to completely reset the database:

```powershell
# Stop containers
docker-compose down -v

# Start containers (this recreates the database)
docker-compose up -d

# Wait for database to be ready (about 10 seconds)
Start-Sleep -Seconds 10

# Restore from dump
$env:PGPASSWORD = "postgres123"
docker exec -i legal_ai_postgres_v2 pg_restore -U postgres -d cases_llama3_3 --no-owner --no-privileges < cases_llama3_3.dump
```

---

## Verify Restoration

```powershell
# Check table count
docker exec legal_ai_postgres_v2 psql -U postgres -d cases_llama3_3 -c "\dt"

# Check specific table row count
docker exec legal_ai_postgres_v2 psql -U postgres -d cases_llama3_3 -c "SELECT COUNT(*) FROM cases;"
```

---

## Connection Details

| Setting  | Value            |
| -------- | ---------------- |
| Host     | `localhost`      |
| Port     | `5433`           |
| Database | `cases_llama3_3` |
| Username | `postgres`       |
| Password | `postgres123`    |

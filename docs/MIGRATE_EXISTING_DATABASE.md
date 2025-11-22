# Migrating Existing Database to WSL PostgreSQL

Your existing `cases_llama3.3` database has all the cases data. This guide shows how to:

1. Export (backup) your existing database
2. Import it into WSL PostgreSQL
3. Then run the briefs migration

---

## Option 1: Export from Existing Database and Import to WSL (Recommended)

This assumes you have an existing PostgreSQL database somewhere with cases data.

### Step 1: Find Your Existing Database

Where is your current `cases_llama3.3` database? Common locations:

**Option A: Docker Container**

```powershell
# Check if running in Docker
docker ps | Select-String postgres
```

**Option B: Local Windows PostgreSQL**

```powershell
# Check Windows services
Get-Service | Where-Object {$_.Name -like "*postgres*"}
```

**Option C: Remote Server**

- Check your `.env` file or `DATABASE_URL` environment variable
- Look in `docker-compose.yml`

### Step 2: Export Existing Database

#### If Database is in Docker:

```powershell
# Find container name
docker ps

# Export database (replace 'postgres_container' with actual name)
docker exec -t postgres_container pg_dump -U postgres cases_llama3.3 > cases_backup.sql

# Or with custom format (better for large databases)
docker exec -t postgres_container pg_dump -U postgres -Fc cases_llama3.3 > cases_backup.dump
```

#### If Database is on Windows PostgreSQL:

```powershell
# SQL format
pg_dump -h localhost -U postgres -d cases_llama3.3 -f cases_backup.sql

# Or custom format
pg_dump -h localhost -U postgres -d cases_llama3.3 -Fc -f cases_backup.dump
```

#### If Database is Remote:

```powershell
# Replace with your actual host/credentials
pg_dump -h your-server.com -U postgres -d cases_llama3.3 -f cases_backup.sql
```

### Step 3: Copy Backup to WSL

```powershell
# Copy SQL file to WSL home directory
wsl cp cases_backup.sql ~/cases_backup.sql

# Or for .dump file
wsl cp cases_backup.dump ~/cases_backup.dump
```

### Step 4: Import into WSL PostgreSQL

```bash
# In WSL Ubuntu terminal
cd ~

# Drop and recreate database (to ensure clean import)
sudo -u postgres psql -c "DROP DATABASE IF EXISTS cases_llama3_3;"
sudo -u postgres psql -c "CREATE DATABASE cases_llama3_3;"

# Import SQL format
sudo -u postgres psql -d cases_llama3_3 -f cases_backup.sql

# OR import custom format (.dump)
sudo -u postgres pg_restore -d cases_llama3_3 cases_backup.dump
```

This may take 10-30 minutes depending on database size.

### Step 5: Verify Import

```bash
# Connect to database
sudo -u postgres psql -d cases_llama3_3

# Check tables exist
\dt

# Check data
SELECT COUNT(*) FROM cases;
SELECT COUNT(*) FROM case_chunks;

# Exit
\q
```

### Step 6: Enable pgvector (if not already)

```bash
sudo -u postgres psql -d cases_llama3_3 -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## Option 2: Use Docker PostgreSQL with pgvector

If your database is already in Docker, you can add pgvector to the existing container.

### Step 1: Check Current Docker Setup

```powershell
# View docker-compose.yml
cat docker-compose.yml
```

### Step 2: Update Docker Image to Include pgvector

Edit `docker-compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16 # Change to pgvector image
    environment:
      POSTGRES_DB: cases_llama3.3
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    # Add this to automatically enable extension
    command: postgres -c shared_preload_libraries=vector

volumes:
  postgres_data:
```

### Step 3: Recreate Container

```powershell
# Stop current container
docker-compose down

# Pull new image
docker pull pgvector/pgvector:pg16

# Start with new image
docker-compose up -d

# Wait for startup
Start-Sleep -Seconds 10
```

### Step 4: Enable pgvector Extension

```powershell
docker exec -it postgres_container psql -U postgres -d cases_llama3.3 -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Step 5: Verify

```powershell
docker exec -it postgres_container psql -U postgres -d cases_llama3.3 -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

---

## Option 3: Point to Existing Database (No Migration Needed)

If you want to keep using your existing database setup and just add briefs:

### Step 1: Identify Your Current Database Connection

Check your environment or config:

```powershell
# Check environment variable
echo $env:DATABASE_URL

# Or check .env file
cat .env

# Or check docker-compose.yml
cat docker-compose.yml
```

### Step 2: Install pgvector in Existing Database

#### If Docker:

```powershell
# Method 1: Update to pgvector image (see Option 2 above)

# Method 2: Install pgvector in running container
docker exec -it postgres_container bash -c "
    apt-get update &&
    apt-get install -y postgresql-server-dev-16 build-essential git &&
    cd /tmp &&
    git clone https://github.com/pgvector/pgvector.git &&
    cd pgvector &&
    make &&
    make install
"

# Then enable extension
docker exec -it postgres_container psql -U postgres -d cases_llama3.3 -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### If Windows PostgreSQL:

Download and install pgvector from: https://github.com/pgvector/pgvector/releases

Or use WSL to compile and copy to Windows (advanced).

### Step 3: Run Brief Migration

```powershell
# Update connection in script (already done based on your file)
.\scripts\run_brief_migration.ps1
```

---

## Recommended Approach: Use Docker with pgvector

### Quick Setup

Create or update `docker-compose.yml`:

```yaml
version: "3.8"

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: legal_postgres
    environment:
      POSTGRES_DB: cases_llama3.3
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    restart: unless-stopped

volumes:
  postgres_data:
```

### Start Container

```powershell
# Start PostgreSQL with pgvector
docker-compose up -d

# Wait for startup
Start-Sleep -Seconds 10

# Verify pgvector
docker exec -it legal_postgres psql -U postgres -d cases_llama3.3 -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Import Existing Data (if you have backup)

```powershell
# Copy backup to container
docker cp cases_backup.sql legal_postgres:/tmp/

# Import
docker exec -it legal_postgres psql -U postgres -d cases_llama3.3 -f /tmp/cases_backup.sql
```

### Run Brief Migration

```powershell
# Update DATABASE_URL
$env:DATABASE_URL = "postgresql://postgres:postgres123@localhost:5432/cases_llama3.3"

# Run migration
.\scripts\run_brief_migration.ps1
```

---

## Which Option Should I Choose?

### Choose **WSL** if:

- ✅ You want a full Linux environment on Windows
- ✅ You need to learn Linux commands
- ✅ You want minimal Docker overhead
- ✅ You have time for setup (30-45 min)

### Choose **Docker** if:

- ✅ You already use Docker
- ✅ You want easiest pgvector setup
- ✅ You want portability (same setup on any machine)
- ✅ You want quick start (5-10 min)
- ✅ **RECOMMENDED FOR THIS PROJECT**

### Choose **Windows PostgreSQL** if:

- ⚠️ You already have it installed with data
- ⚠️ Installing pgvector is harder on Windows
- ⚠️ Not recommended for new setups

---

## Next Steps After Database Setup

Once you have PostgreSQL with pgvector and your existing cases data:

### 1. Verify Setup

```powershell
# Test connection
psql -h localhost -U postgres -d cases_llama3.3 -c "SELECT version();"

# Check pgvector
psql -h localhost -U postgres -d cases_llama3.3 -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# Check existing data
psql -h localhost -U postgres -d cases_llama3.3 -c "SELECT COUNT(*) FROM cases;"
```

### 2. Run Brief Migration

```powershell
.\scripts\run_brief_migration.ps1
```

### 3. Start Ingesting Briefs

```powershell
python batch_process_briefs.py --case-folder 83895-4
```

---

## Common Questions

### Q: Do I lose my existing cases data?

**A:** No! The brief migration only **adds** new tables. It doesn't modify or delete existing tables.

### Q: Can I use my existing database without moving it?

**A:** Yes, if you can install pgvector in your existing database (easiest with Docker).

### Q: What if my database is on a remote server?

**A:** You can run the brief migration against any PostgreSQL server with pgvector. Just update the connection details.

### Q: How big is the database backup?

**A:** Depends on how many cases you have:

- 100 cases: ~100MB
- 1,000 cases: ~1GB
- 10,000 cases: ~10GB

### Q: How long does import take?

**A:** Roughly:

- 100 cases: 1-2 minutes
- 1,000 cases: 10-15 minutes
- 10,000 cases: 1-2 hours

---

## Troubleshooting

### Error: "database cases_llama3.3 does not exist"

**Solution:** You need to import your existing database first (see Option 1).

### Error: "extension vector does not exist"

**Solution:** Install pgvector:

- Docker: Use `pgvector/pgvector:pg16` image
- WSL: Follow pgvector installation steps in WINDOWS_WSL_PGVECTOR_SETUP.md
- Windows: Download from GitHub releases

### Error: "relation cases does not exist"

**Solution:** Your database is empty. You need to either:

1. Import existing database backup
2. Run the cases ingestion first before briefs

### Database backup is too large to copy

**Solution:** Use custom format and compression:

```powershell
# Export with compression
pg_dump -U postgres -d cases_llama3.3 -Fc -Z 9 -f cases_backup.dump

# Copy to WSL
wsl cp cases_backup.dump ~/cases_backup.dump

# Import
wsl sudo -u postgres pg_restore -d cases_llama3_3 ~/cases_backup.dump
```

---

## Summary

**Most Common Scenario:**

1. You have cases data in Docker/remote database
2. Export database: `docker exec postgres_container pg_dump ... > backup.sql`
3. Choose Docker with pgvector OR WSL PostgreSQL
4. Import backup
5. Enable pgvector extension
6. Run brief migration
7. Start ingesting briefs

**Quickest Path (Docker):**

```powershell
# 1. Update docker-compose.yml to use pgvector/pgvector:pg16
# 2. Restart container
docker-compose up -d

# 3. Enable extension
docker exec -it legal_postgres psql -U postgres -d cases_llama3.3 -c "CREATE EXTENSION vector;"

# 4. Run brief migration
.\scripts\run_brief_migration.ps1

# 5. Ingest briefs
python batch_process_briefs.py --briefs-dir downloaded-briefs
```

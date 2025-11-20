# 🚀 Production Restart Guide

## Quick Restart Command

```bash
./restart.sh
```

## Production Environment Commands

```bash
# For production servers (longer timeouts)
PRODUCTION=true ./restart.sh

# With debug information (if hanging)
DEBUG=true ./restart.sh

# Show logs at the end
./restart.sh --show-logs

# Combined for production debugging
PRODUCTION=true DEBUG=true ./restart.sh --show-logs
```

## What the Script Does

1. **🧹 Clean Setup**: Stops containers, removes volumes, kills processes
2. **🐳 Rebuild Environment**: Pulls images, rebuilds containers  
3. **⏳ Wait for Health**: Monitors PostgreSQL, Redis, and API health
4. **📊 Verify Database**: Confirms database and tables are created
5. **🔍 Display Status**: Shows containers, tables, and API response
6. **🎯 Environment Config**: Provides Ollama environment variables

## Fixed Issues

✅ **Health Check URL**: Fixed `/health` → `/api/v1/health/`  
✅ **Docker Health Check**: Updated docker-compose.yml with correct URL  
✅ **Production Timeouts**: 120 seconds for slower production servers  
✅ **Debug Mode**: Detailed logging when things hang  
✅ **Better Error Handling**: Shows container status and logs on failure  

## Troubleshooting Production Hangs

### If hanging on "Waiting for API to be healthy...":

1. **Use Debug Mode**:
   ```bash
   DEBUG=true ./restart.sh
   ```

2. **Check API Container**:
   ```bash
   docker compose ps api
   docker compose logs api --tail=20
   ```

3. **Check Health Endpoints Manually**:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health/
   ```

4. **Increase Timeout for Slow Servers**:
   ```bash
   PRODUCTION=true ./restart.sh
   ```

### Common Production Issues:

- **Slow Docker builds**: Use `--no-cache` flag manually if needed
- **Network issues**: Check firewall/port 8000 accessibility  
- **Resource constraints**: Monitor CPU/memory usage
- **Missing dependencies**: Check Dockerfile for all required packages

## Expected Timeline

- **Local development**: 30-60 seconds
- **Production servers**: 60-120 seconds  
- **Slow/older hardware**: Up to 180 seconds with PRODUCTION=true

## Success Indicators

✅ All containers showing "healthy" status  
✅ Database has 18 tables  
✅ API responding on both `/` and `/api/v1/health/`  
✅ No errors in container logs  

## Next Steps After Successful Restart

```bash
# Process PDFs
python3 batch_processor.py your-pdf-directory/

# Monitor processing
docker compose logs -f api

# Check database population
docker exec legal_ai_postgres psql -U legal_user -d cases_llama3.3 -c "SELECT COUNT(*) FROM cases;"
```

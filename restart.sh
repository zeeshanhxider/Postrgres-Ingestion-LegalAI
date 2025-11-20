#!/bin/bash
# 🚀 LEGAL AI HELPER - COMPLETE RESTART SCRIPT
# Fully automated clean restart with fresh database initialization
# Based on commands.txt production deployment guide
#
# Usage: 
#   ./restart.sh                    # Normal restart
#   ./restart.sh --show-logs        # Show logs at the end
#   PRODUCTION=true ./restart.sh    # Use longer timeouts for production
#   DEBUG=true ./restart.sh         # Show detailed debugging info

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}===============================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${BLUE}===============================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${PURPLE}ℹ️ $1${NC}"
}

print_debug() {
    if [ "${DEBUG:-false}" = "true" ]; then
        echo -e "${CYAN}🔍 DEBUG: $1${NC}"
    fi
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

print_step "🧹 STEP 1: CLEAN EXISTING SETUP"

print_info "Stopping all running containers..."
docker compose down --remove-orphans || true

print_info "Removing postgres data volume (clean database)..."
docker volume rm law-helper_postgres_data 2>/dev/null || true

print_info "Removing redis data volume..."
docker volume rm law-helper_redis_data 2>/dev/null || true

print_info "Cleaning any existing database connections..."
pkill -f postgres 2>/dev/null || true

print_success "Cleanup completed"

print_step "🐳 STEP 2: REBUILD DOCKER ENVIRONMENT"

print_info "Pulling latest PostgreSQL with pgvector support..."
docker pull pgvector/pgvector:pg16

print_info "Rebuilding and starting all services (postgres, redis, api)..."
docker compose up -d --build

print_success "Docker environment rebuilt"

print_step "⏳ STEP 3: WAIT FOR SERVICES TO BE READY"

# Increase timeout for production environments (some servers are slower)
if [ "${PRODUCTION:-false}" = "true" ]; then
    timeout=120
    print_info "Production mode detected - using longer timeout (120s)"
else
    timeout=60
fi

print_info "Waiting for PostgreSQL to be healthy..."
counter=0
while [ $counter -lt $timeout ]; do
    if docker compose ps postgres | grep -q "healthy"; then
        print_success "PostgreSQL is healthy"
        break
    fi
    sleep 2
    counter=$((counter + 2))
    echo -n "."
done

if [ $counter -ge $timeout ]; then
    print_error "PostgreSQL did not become healthy within $timeout seconds"
    exit 1
fi

print_info "Waiting for Redis to be healthy..."
counter=0
while [ $counter -lt $timeout ]; do
    if docker compose ps redis | grep -q "healthy"; then
        print_success "Redis is healthy"
        break
    fi
    sleep 2
    counter=$((counter + 2))
    echo -n "."
done

if [ $counter -ge $timeout ]; then
    print_error "Redis did not become healthy within $timeout seconds"
    exit 1
fi

print_info "Waiting for API to be healthy..."
print_debug "Testing API endpoints: http://localhost:8000/ and http://localhost:8000/api/v1/health/"

# Use docker health check first (more reliable in production)
print_info "Checking Docker health status..."
counter=0
while [ $counter -lt $timeout ]; do
    api_health=$(docker compose ps api | grep -o "healthy\|unhealthy\|starting" || echo "unknown")
    print_debug "Docker health status: $api_health"
    
    if [ "$api_health" = "healthy" ]; then
        print_success "API container is healthy (Docker health check)"
        break
    elif [ "$api_health" = "unhealthy" ]; then
        print_error "API container is unhealthy (Docker health check failed)"
        print_info "Container logs:"
        docker compose logs api --tail=10
        exit 1
    else
        print_debug "API health status: $api_health (attempt $((counter/5+1)))"
        if [ "${DEBUG:-false}" = "true" ] && [ $((counter % 20)) -eq 0 ]; then
            print_debug "API container status:"
            docker compose ps api
            print_debug "Recent API logs:"
            docker compose logs api --tail=5
        fi
    fi
    sleep 5
    counter=$((counter + 5))
    [ "${DEBUG:-false}" != "true" ] && echo -n "."
done

if [ $counter -ge $timeout ]; then
    print_error "API did not become healthy within $timeout seconds (Docker health check)"
    print_info "Final container status:"
    docker compose ps
    print_info "Recent API logs:"
    docker compose logs api --tail=15
    exit 1
fi

# Also test with curl as secondary validation (if available)
if command -v curl > /dev/null 2>&1; then
    print_info "Validating API endpoints with curl..."
    root_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
    health_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health/ 2>/dev/null || echo "000")
    
    print_debug "Root endpoint: $root_response, Health endpoint: $health_response"
    
    if [ "$root_response" = "200" ] && [ "$health_response" = "200" ]; then
        print_success "API endpoints validated successfully"
    else
        print_warning "API endpoints validation failed (root: $root_response, health: $health_response)"
        print_warning "Continuing anyway since Docker health check passed..."
    fi
else
    print_warning "curl not available, skipping endpoint validation"
fi

print_step "📊 STEP 4: VERIFY DATABASE INITIALIZATION"

print_info "Checking database and table creation..."
sleep 5  # Give a moment for initialization to complete

# Check if database exists and has tables
TABLE_COUNT=$(docker exec legal_ai_postgres psql -U legal_user -d cases_llama3.3 -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$TABLE_COUNT" -gt "0" ]; then
    print_success "Database initialized with $TABLE_COUNT tables"
else
    print_error "Database initialization failed - no tables found"
    exit 1
fi

print_step "🔍 STEP 5: DISPLAY SYSTEM STATUS"

echo ""
print_info "Container Status:"
docker compose ps

echo ""
print_info "Database Tables:"
docker exec legal_ai_postgres psql -U legal_user -d cases_llama3.3 -c "\dt" | head -25

echo ""
print_info "API Health Check:"
curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null || echo "API response received"

print_step "🎯 STEP 6: ENVIRONMENT CONFIGURATION"

echo ""
print_info "Setting environment variables for Ollama usage..."
echo "export USE_OLLAMA=true"
echo "export OLLAMA_MODEL=\"qwen:32b\""
echo "export OLLAMA_EMBED_MODEL=\"mxbai-embed-large\""
echo "export OLLAMA_BASE_URL=\"http://localhost:11434\""
echo ""
print_warning "Add these to your shell profile (~/.bashrc, ~/.zshrc) for persistence"

print_step "✅ RESTART COMPLETED SUCCESSFULLY"

echo ""
print_success "🎉 Legal AI Helper system is now running with a fresh database!"
echo ""
print_info "Next steps:"
echo "  1. Verify Ollama is running: ollama list"
echo "  2. Process PDFs: python3 batch_processor.py your-pdf-directory/"
echo "  3. Monitor logs: docker compose logs -f"
echo "  4. Access API docs: http://localhost:8000/docs"
echo ""
print_info "Database details:"
echo "  - Database: cases_llama3.3"
echo "  - Tables: $TABLE_COUNT"
echo "  - Host: localhost:5432"
echo "  - User: legal_user"
echo ""
print_info "Useful commands:"
echo "  - Check status: docker compose ps"
echo "  - View logs: docker compose logs api"
echo "  - Connect to DB: docker exec -it legal_ai_postgres psql -U legal_user -d cases_llama3.3"
echo "  - Stop system: docker compose down"
echo ""

# Optional: Show recent logs
if [ "${1:-}" = "--show-logs" ]; then
    print_step "📋 RECENT LOGS"
    docker compose logs --tail=20
fi

print_success "Restart script completed successfully! 🚀"

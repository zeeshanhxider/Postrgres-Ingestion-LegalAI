#!/bin/bash
#
# Simple Database Reset Script
# Quick way to reset the database using Docker Compose
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DB_NAME="cases_llama3.3"
DB_USER="legal_user"
DB_PASSWORD="legal_pass"
CONTAINER_NAME="legal_ai_postgres"

print_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  info        Show database information"
    echo "  drop        Drop all tables (keeps database)"
    echo "  reset       Drop database and recreate with schema"
    echo "  restart     Restart database container"
    echo "  logs        Show database logs"
    echo ""
    echo "Examples:"
    echo "  $0 info     # Show current database state"
    echo "  $0 drop     # Drop all tables"
    echo "  $0 reset    # Complete database reset"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed or not running${NC}"
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not available${NC}"
        exit 1
    fi
}

check_container() {
    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${YELLOW}⚠️  Database container is not running${NC}"
        echo "Starting database container..."
        cd "$(dirname "$0")/.."
        docker compose up -d postgres
        sleep 5
    fi
}

exec_sql() {
    local sql="$1"
    docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "$sql"
}

exec_sql_postgres() {
    local sql="$1"
    docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c "$sql"
}

show_info() {
    echo -e "${BLUE}📊 Database Information${NC}"
    echo "========================"
    echo "Database: $DB_NAME"
    echo "User: $DB_USER"
    echo "Container: $CONTAINER_NAME"
    echo ""
    
    # Check if database exists
    DB_EXISTS=$(exec_sql_postgres "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME';" 2>/dev/null | grep -c "1")
    if [ -z "$DB_EXISTS" ]; then
        DB_EXISTS=0
    fi
    
    if [ "$DB_EXISTS" -eq "1" ]; then
        echo -e "${GREEN}✅ Database exists${NC}"
        
        # Get table count
        TABLE_COUNT=$(exec_sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | grep -E '^[0-9]+$' || echo "0")
        echo "📋 Tables: $TABLE_COUNT"
        
        if [ "$TABLE_COUNT" -gt "0" ]; then
            echo ""
            echo "📊 Table row counts:"
            exec_sql "
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins - n_tup_del AS row_count
                FROM pg_stat_user_tables 
                ORDER BY tablename;
            " 2>/dev/null | grep -E "^\s*public\s*\|" || echo "Could not get row counts"
        fi
    else
        echo -e "${RED}❌ Database does not exist${NC}"
    fi
}

drop_tables() {
    echo -e "${YELLOW}⚠️  Dropping all tables in database '$DB_NAME'${NC}"
    
    # Get list of tables
    TABLES=$(exec_sql "SELECT tablename FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null | grep -v "tablename" | grep -v "^-" | grep -v "^(" | grep -E "^[a-zA-Z_]")
    
    if [ -z "$TABLES" ]; then
        echo "No tables found to drop"
        return 0
    fi
    
    echo "Tables to drop:"
    echo "$TABLES" | sed 's/^/  - /'
    echo ""
    
    read -p "Are you sure you want to drop all tables? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Operation cancelled"
        return 1
    fi
    
    echo "Dropping tables..."
    exec_sql "
        DO \$\$ 
        DECLARE 
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END \$\$;
    "
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Successfully dropped all tables${NC}"
    else
        echo -e "${RED}❌ Error dropping tables${NC}"
        return 1
    fi
}

reset_database() {
    echo -e "${YELLOW}⚠️  This will completely reset the database '$DB_NAME'${NC}"
    echo "This will:"
    echo "  1. Drop the entire database"
    echo "  2. Recreate the database"
    echo "  3. Run init-db.sql to create schema"
    echo ""
    
    read -p "Are you sure? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Operation cancelled"
        return 1
    fi
    
    echo "🗑️  Dropping database..."
    
    # Terminate connections
    exec_sql_postgres "
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
    " 2>/dev/null
    
    # Drop database
    exec_sql_postgres "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null
    
    echo "🆕 Creating database..."
    exec_sql_postgres "CREATE DATABASE $DB_NAME;" 2>/dev/null
    
    # Run init-db.sql
    echo "📄 Running init-db.sql..."
    SCRIPT_DIR="$(dirname "$0")"
    INIT_SQL="$SCRIPT_DIR/../init-db.sql"
    
    if [ -f "$INIT_SQL" ]; then
        docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$INIT_SQL"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Database reset completed successfully${NC}"
        else
            echo -e "${RED}❌ Error running init-db.sql${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ init-db.sql not found at $INIT_SQL${NC}"
        return 1
    fi
}

restart_container() {
    echo "🔄 Restarting database container..."
    cd "$(dirname "$0")/.."
    docker compose restart postgres
    echo -e "${GREEN}✅ Database container restarted${NC}"
}

show_logs() {
    echo "📋 Database container logs:"
    docker logs "$CONTAINER_NAME" --tail 50 -f
}

main() {
    check_docker
    
    case "$1" in
        "info")
            check_container
            show_info
            ;;
        "drop")
            check_container
            drop_tables
            ;;
        "reset")
            check_container
            reset_database
            ;;
        "restart")
            restart_container
            ;;
        "logs")
            show_logs
            ;;
        "")
            print_usage
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"

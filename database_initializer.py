#!/usr/bin/env python3
"""
Database Initializer
Creates the database and runs the init-db.sql schema if needed.
"""

import os
import sys
import logging
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection(database=None, user=None, password=None):
    """Get database connection"""
    # Use environment variables first, then fall back to settings
    host = os.getenv('PGHOST', 'postgres')  # Use 'postgres' for Docker internal
    port = int(os.getenv('PGPORT', '5432'))
    
    # Allow override of user/password for admin connections
    if user is None:
        user = os.getenv('PGUSER', settings.DATABASE_USER)
    if password is None:
        password = os.getenv('PGPASSWORD', settings.DATABASE_PASSWORD)
    
    if database is None:
        database = os.getenv('PGDATABASE', settings.DATABASE_NAME)
    
    logger.info(f"Connecting to database: host={host}, port={port}, user={user}, database={database}")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except psycopg2.OperationalError as e:
        # If connection with legal_user fails, try with postgres superuser
        if user == 'legal_user':
            logger.warning(f"Failed to connect as {user}, trying as postgres superuser...")
            return get_db_connection(database, user='postgres', password='postgres')
        raise e

def database_exists(db_name):
    """Check if database exists"""
    try:
        # Try connecting as postgres superuser first
        conn = get_db_connection('postgres', user='postgres', password='postgres')
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone() is not None
        
        cursor.close()
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Error checking if database exists: {e}")
        return False

def create_database(db_name):
    """Create database if it doesn't exist"""
    try:
        if database_exists(db_name):
            logger.info(f"Database '{db_name}' already exists")
            return True
            
        logger.info(f"Creating database '{db_name}'...")
        conn = get_db_connection('postgres', user='postgres', password='postgres')
        cursor = conn.cursor()
        
        # Create database
        cursor.execute(f'CREATE DATABASE "{db_name}" OWNER legal_user')
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Database '{db_name}' created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False

def run_init_sql(db_name):
    """Run the init-db.sql script"""
    try:
        init_sql_path = Path(__file__).parent / 'init-db.sql'
        if not init_sql_path.exists():
            logger.error(f"init-db.sql not found at {init_sql_path}")
            return False
        
        logger.info("Running init-db.sql...")
        # Connect as legal_user to run the schema
        conn = get_db_connection(db_name, user='legal_user', password='legal_pass')
        cursor = conn.cursor()
        
        with open(init_sql_path, 'r') as f:
            sql_content = f.read()
            cursor.execute(sql_content)
        
        cursor.close()
        conn.close()
        
        logger.info("✅ Successfully executed init-db.sql")
        return True
        
    except Exception as e:
        logger.error(f"Error running init-db.sql: {e}")
        logger.info("Trying with postgres superuser...")
        try:
            conn = get_db_connection(db_name, user='postgres', password='postgres')
            cursor = conn.cursor()
            
            with open(init_sql_path, 'r') as f:
                sql_content = f.read()
                cursor.execute(sql_content)
            
            cursor.close()
            conn.close()
            
            logger.info("✅ Successfully executed init-db.sql as postgres")
            return True
        except Exception as e2:
            logger.error(f"Error running init-db.sql as postgres: {e2}")
            return False

def check_tables_exist(db_name):
    """Check if tables exist in the database"""
    try:
        # Try as legal_user first, fallback to postgres
        try:
            conn = get_db_connection(db_name, user='legal_user', password='legal_pass')
        except:
            conn = get_db_connection(db_name, user='postgres', password='postgres')
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT count(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return count > 0
        
    except Exception as e:
        logger.error(f"Error checking tables: {e}")
        return False

def main():
    """Main initialization function"""
    db_name = os.getenv('PGDATABASE', settings.DATABASE_NAME)
    
    logger.info("🚀 Starting database initialization...")
    logger.info(f"Target database: {db_name}")
    
    # Step 1: Create database if it doesn't exist
    if not create_database(db_name):
        logger.error("❌ Failed to create database")
        sys.exit(1)
    
    # Step 2: Check if tables exist
    if check_tables_exist(db_name):
        logger.info("✅ Database already has tables, skipping initialization")
        return
    
    # Step 3: Run init-db.sql
    if not run_init_sql(db_name):
        logger.error("❌ Failed to run init-db.sql")
        sys.exit(1)
    
    # Step 4: Verify tables were created
    if check_tables_exist(db_name):
        logger.info("✅ Database initialization completed successfully")
    else:
        logger.error("❌ Database initialization failed - no tables found")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Database Reset Script
Safely removes all data from the existing database and optionally recreates the schema.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseResetter:
    """Handles database reset operations"""
    
    def __init__(self):
        self.db_config = self._parse_database_url()
    
    def _parse_database_url(self) -> dict:
        """Parse DATABASE_URL into connection parameters"""
        # Default values (matching docker-compose.yml)
        config = {
            'host': 'localhost',
            'port': 5432,
            'user': 'law_user',
            'password': 'law_password',
            'database': 'law_helper'
        }
        
        # Try to get from environment or settings
        database_url = getattr(settings, 'DATABASE_URL', None) or os.getenv('DATABASE_URL')
        
        if database_url:
            # Parse postgres://user:password@host:port/database
            if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(database_url)
                    config.update({
                        'host': parsed.hostname or config['host'],
                        'port': parsed.port or config['port'],
                        'user': parsed.username or config['user'],
                        'password': parsed.password or config['password'],
                        'database': parsed.path.lstrip('/') or config['database']
                    })
                except Exception as e:
                    logger.warning(f"Failed to parse DATABASE_URL: {e}")
        
        return config
    
    def _get_connection(self, database: Optional[str] = None):
        """Get database connection"""
        config = self.db_config.copy()
        if database:
            config['database'] = database
        
        try:
            conn = psycopg2.connect(**config)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            return conn
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def check_database_exists(self) -> bool:
        """Check if the target database exists"""
        try:
            # Connect to postgres database to check if target database exists
            conn = self._get_connection('postgres')
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (self.db_config['database'],)
            )
            
            exists = cursor.fetchone() is not None
            cursor.close()
            conn.close()
            
            return exists
        except Exception as e:
            logger.error(f"Error checking database existence: {e}")
            return False
    
    def list_tables(self) -> list:
        """List all tables in the database"""
        if not self.check_database_exists():
            logger.warning(f"Database '{self.db_config['database']}' does not exist")
            return []
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            
            return tables
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            return []
    
    def get_table_counts(self) -> dict:
        """Get row counts for all tables"""
        tables = self.list_tables()
        if not tables:
            return {}
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            counts = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    counts[table] = count
                except Exception as e:
                    logger.warning(f"Could not count rows in table {table}: {e}")
                    counts[table] = "Error"
            
            cursor.close()
            conn.close()
            
            return counts
        except Exception as e:
            logger.error(f"Error getting table counts: {e}")
            return {}
    
    def drop_all_tables(self, confirm: bool = False) -> bool:
        """Drop all tables in the database"""
        if not confirm:
            logger.error("drop_all_tables called without confirmation")
            return False
        
        tables = self.list_tables()
        if not tables:
            logger.info("No tables found to drop")
            return True
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            logger.info(f"Dropping {len(tables)} tables...")
            
            # Drop tables with CASCADE to handle foreign key constraints
            for table in tables:
                logger.info(f"Dropping table: {table}")
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            
            # Drop any remaining sequences, views, functions, etc.
            logger.info("Cleaning up remaining database objects...")
            
            # Drop sequences
            cursor.execute("""
                SELECT sequence_name 
                FROM information_schema.sequences 
                WHERE sequence_schema = 'public'
            """)
            sequences = cursor.fetchall()
            for seq in sequences:
                cursor.execute(f"DROP SEQUENCE IF EXISTS {seq[0]} CASCADE")
            
            # Drop views
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.views 
                WHERE table_schema = 'public'
            """)
            views = cursor.fetchall()
            for view in views:
                cursor.execute(f"DROP VIEW IF EXISTS {view[0]} CASCADE")
            
            # Drop functions
            cursor.execute("""
                SELECT routine_name 
                FROM information_schema.routines 
                WHERE routine_schema = 'public' 
                AND routine_type = 'FUNCTION'
            """)
            functions = cursor.fetchall()
            for func in functions:
                cursor.execute(f"DROP FUNCTION IF EXISTS {func[0]} CASCADE")
            
            cursor.close()
            conn.close()
            
            logger.info("✅ Successfully dropped all database objects")
            return True
            
        except Exception as e:
            logger.error(f"Error dropping tables: {e}")
            return False
    
    def drop_database(self, confirm: bool = False) -> bool:
        """Drop the entire database"""
        if not confirm:
            logger.error("drop_database called without confirmation")
            return False
        
        if not self.check_database_exists():
            logger.info(f"Database '{self.db_config['database']}' does not exist")
            return True
        
        try:
            # Connect to postgres database to drop the target database
            conn = self._get_connection('postgres')
            cursor = conn.cursor()
            
            # Terminate all connections to the target database
            logger.info(f"Terminating connections to database '{self.db_config['database']}'...")
            cursor.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
            """, (self.db_config['database'],))
            
            # Drop the database
            logger.info(f"Dropping database '{self.db_config['database']}'...")
            cursor.execute(f"DROP DATABASE IF EXISTS {self.db_config['database']}")
            
            cursor.close()
            conn.close()
            
            logger.info("✅ Successfully dropped database")
            return True
            
        except Exception as e:
            logger.error(f"Error dropping database: {e}")
            return False
    
    def recreate_schema(self) -> bool:
        """Recreate the database schema from init-db.sql"""
        # First ensure database exists
        if not self.check_database_exists():
            logger.info(f"Creating database '{self.db_config['database']}'...")
            try:
                conn = self._get_connection('postgres')
                cursor = conn.cursor()
                cursor.execute(f"CREATE DATABASE {self.db_config['database']}")
                cursor.close()
                conn.close()
                logger.info("✅ Database created")
            except Exception as e:
                logger.error(f"Failed to create database: {e}")
                return False
        
        # Run init-db.sql
        init_sql_path = Path(__file__).parent.parent / 'init-db.sql'
        if not init_sql_path.exists():
            logger.error(f"init-db.sql not found at {init_sql_path}")
            return False
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            logger.info("Running init-db.sql...")
            with open(init_sql_path, 'r') as f:
                sql_content = f.read()
                cursor.execute(sql_content)
            
            cursor.close()
            conn.close()
            
            logger.info("✅ Successfully recreated schema")
            return True
            
        except Exception as e:
            logger.error(f"Error recreating schema: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Database Reset Script')
    parser.add_argument('--action', choices=['info', 'drop-tables', 'drop-database', 'recreate'], 
                       required=True, help='Action to perform')
    parser.add_argument('--confirm', action='store_true', 
                       help='Confirm destructive operations')
    parser.add_argument('--force', action='store_true',
                       help='Force operation without interactive confirmation')
    
    args = parser.parse_args()
    
    resetter = DatabaseResetter()
    
    if args.action == 'info':
        # Show database information
        logger.info("📊 Database Information")
        logger.info(f"Host: {resetter.db_config['host']}:{resetter.db_config['port']}")
        logger.info(f"Database: {resetter.db_config['database']}")
        logger.info(f"User: {resetter.db_config['user']}")
        
        if resetter.check_database_exists():
            logger.info("✅ Database exists")
            
            tables = resetter.list_tables()
            logger.info(f"📋 Found {len(tables)} tables")
            
            if tables:
                counts = resetter.get_table_counts()
                logger.info("📊 Table row counts:")
                for table, count in counts.items():
                    logger.info(f"  {table}: {count}")
        else:
            logger.info("❌ Database does not exist")
    
    elif args.action == 'drop-tables':
        if not resetter.check_database_exists():
            logger.error("Database does not exist")
            return 1
        
        tables = resetter.list_tables()
        if not tables:
            logger.info("No tables to drop")
            return 0
        
        logger.warning(f"⚠️  This will DROP ALL {len(tables)} TABLES:")
        for table in tables:
            logger.warning(f"  - {table}")
        
        confirmed = args.confirm or args.force
        if not confirmed and not args.force:
            response = input("Are you sure? (yes/no): ")
            confirmed = response.lower() == 'yes'
        
        if confirmed:
            success = resetter.drop_all_tables(confirm=True)
            return 0 if success else 1
        else:
            logger.info("Operation cancelled")
            return 1
    
    elif args.action == 'drop-database':
        if not resetter.check_database_exists():
            logger.info("Database does not exist")
            return 0
        
        logger.warning(f"⚠️  This will DROP THE ENTIRE DATABASE: {resetter.db_config['database']}")
        
        confirmed = args.confirm or args.force
        if not confirmed and not args.force:
            response = input("Are you sure? (yes/no): ")
            confirmed = response.lower() == 'yes'
        
        if confirmed:
            success = resetter.drop_database(confirm=True)
            return 0 if success else 1
        else:
            logger.info("Operation cancelled")
            return 1
    
    elif args.action == 'recreate':
        logger.info("🔄 Recreating database schema...")
        
        # Drop all tables first if database exists
        if resetter.check_database_exists():
            tables = resetter.list_tables()
            if tables:
                logger.info("Dropping existing tables...")
                confirmed = args.confirm or args.force
                if not confirmed:
                    response = input(f"Drop {len(tables)} existing tables? (yes/no): ")
                    confirmed = response.lower() == 'yes'
                
                if confirmed:
                    resetter.drop_all_tables(confirm=True)
                else:
                    logger.info("Operation cancelled")
                    return 1
        
        # Recreate schema
        success = resetter.recreate_schema()
        return 0 if success else 1
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

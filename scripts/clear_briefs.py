"""
Clear Briefs Database Script
This script truncates all brief-related tables in the database
"""
import psycopg2
import sys

# Database connection parameters
conn_params = {
    'host': 'localhost',
    'port': 5433,
    'user': 'postgres',
    'password': 'postgres123',
    'database': 'cases_llama3_3'
}

def clear_briefs():
    """Clear all briefs and related data from database"""
    
    print("🗑️  Clearing briefs database...")
    print()
    
    # Ask for confirmation
    confirmation = input("Are you sure you want to DELETE ALL briefs? (yes/no): ")
    if confirmation.lower() != 'yes':
        print("❌ Cancelled")
        return
    
    print()
    print("Connecting to database...")
    
    try:
        # Connect with autocommit to avoid transaction issues
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check current count
        print("Checking current data...")
        cursor.execute("SELECT COUNT(*) FROM briefs;")
        brief_count = cursor.fetchone()[0]
        print(f"  Current briefs: {brief_count}")
        
        if brief_count == 0:
            print("\n✅ Database is already empty!")
            cursor.close()
            conn.close()
            return
        
        cursor.execute("SELECT COUNT(*) FROM brief_chunks;")
        chunk_count = cursor.fetchone()[0]
        print(f"  Current chunks: {chunk_count}")
        
        # Truncate tables
        print("\nTruncating tables...")
        cursor.execute("TRUNCATE briefs CASCADE;")
        print("  ✅ Truncated briefs and all related tables")
        
        # Reset sequence
        print("Resetting sequence...")
        cursor.execute("ALTER SEQUENCE briefs_brief_id_seq RESTART WITH 1;")
        print("  ✅ Reset brief_id sequence")
        
        # Verify
        print("\nVerifying...")
        cursor.execute("SELECT COUNT(*) FROM briefs;")
        remaining_briefs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM brief_chunks;")
        remaining_chunks = cursor.fetchone()[0]
        
        print(f"  Briefs: {remaining_briefs}")
        print(f"  Chunks: {remaining_chunks}")
        
        print("\n✅ Briefs database cleared successfully!")
        
        cursor.close()
        conn.close()
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Connection error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check if PostgreSQL is running")
        print("  2. Verify connection parameters (host, port, password)")
        print("  3. Try restarting Docker: docker restart legal_ai_postgres")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nIf the database is locked:")
        print("  1. Stop any running ingestion processes")
        print("  2. Restart Docker: docker restart legal_ai_postgres")
        print("  3. Try again")
        sys.exit(1)

if __name__ == '__main__':
    clear_briefs()

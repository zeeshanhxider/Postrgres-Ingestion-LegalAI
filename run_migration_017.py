import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
conn.autocommit = True
cur = conn.cursor()

print('Migration 017: Remove case_types table\n')

# Step 1: Drop FK constraint
print('Step 1: Dropping FK constraint from cases.case_type_id...')
cur.execute('ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_case_type_id_fkey')
print('  Done')

# Step 2: Migrate case_type_id to legal_taxonomy
print('Step 2: Migrating case_type_id values to legal_taxonomy...')
cur.execute("""
    UPDATE cases c
    SET case_type_id = lt.taxonomy_id
    FROM case_types ct
    JOIN legal_taxonomy lt ON LOWER(ct.case_type) = LOWER(lt.name) AND lt.level_type = 'case_type'
    WHERE c.case_type_id = ct.case_type_id
""")
print(f'  Migrated {cur.rowcount} cases')

# Step 3: Null out unmapped values
print('Step 3: Nullifying unmapped case_type_id values...')
cur.execute("""
    UPDATE cases 
    SET case_type_id = NULL 
    WHERE case_type_id NOT IN (SELECT taxonomy_id FROM legal_taxonomy WHERE level_type = 'case_type')
      AND case_type_id IS NOT NULL
""")
print(f'  Nullified {cur.rowcount} cases')

# Step 4: Add new FK constraint
print('Step 4: Adding FK constraint to legal_taxonomy...')
cur.execute("""
    ALTER TABLE cases 
    ADD CONSTRAINT cases_case_type_id_fkey 
    FOREIGN KEY (case_type_id) REFERENCES legal_taxonomy(taxonomy_id) ON DELETE SET NULL
""")
print('  Done')

# Step 5: Drop case_types table
print('Step 5: Dropping case_types table...')
cur.execute('DROP TABLE IF EXISTS case_types CASCADE')
print('  Done')

# Verify
print('\nVerification:')
cur.execute("SELECT COUNT(*) FROM cases WHERE case_type_id IS NOT NULL")
print(f'  Cases with case_type_id: {cur.fetchone()[0]}')
cur.execute("SELECT COUNT(*) FROM legal_taxonomy WHERE level_type = 'case_type'")
print(f'  Case types in legal_taxonomy: {cur.fetchone()[0]}')

conn.close()
print('\n✅ Migration 017 complete - case_types table removed')

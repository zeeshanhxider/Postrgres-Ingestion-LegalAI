import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
conn.autocommit = True
cur = conn.cursor()

print('Migration 018: Link orphaned categories to case_type parents\n')

# Mapping: category name pattern -> case_type name
CATEGORY_TO_CASE_TYPE = {
    'Criminal': 'Criminal',
    'Criminal Law': 'Criminal',
    'Criminal Procedure': 'Criminal',
    'Sentencing': 'Criminal',
    'Evidence': 'Criminal',
    'Search & Seizure': 'Criminal',
    
    'Civil': 'Civil',
    'Civil Procedure': 'Civil',
    'Contract': 'Civil',
    'Contract Law': 'Civil',
    'Tort': 'Civil',
    'Tort Law': 'Civil',
    'Negligence': 'Civil',
    'Medical Malpractice': 'Civil',
    'Insurance': 'Civil',
    'Property Law': 'Civil',
    
    'Family': 'Family',
    'Family Law': 'Family',
    'Domestic Violence': 'Family',
    
    'Administrative': 'Administrative',
    'Administrative Law': 'Administrative',
    'Tax': 'Administrative',
    
    'Constitutional': 'Constitutional',
    'Constitutional Law': 'Constitutional',
    'Privacy': 'Constitutional',
    
    'Juvenile': 'Juvenile',
    'Juvenile Law': 'Juvenile',
    
    'Probate': 'Probate',
    
    'Real Property': 'Real Property',
    
    'Employment': 'Employment',
    'Employment Law': 'Employment',
}

# Get all case_type entries
cur.execute("SELECT taxonomy_id, name FROM legal_taxonomy WHERE level_type = 'case_type'")
case_types = {row[1]: row[0] for row in cur.fetchall()}
print(f'Found {len(case_types)} case_types: {list(case_types.keys())}')

# Get orphaned categories (categories with parent_id = NULL)
cur.execute("""
    SELECT taxonomy_id, name 
    FROM legal_taxonomy 
    WHERE level_type = 'category' AND parent_id IS NULL
""")
orphaned = cur.fetchall()
print(f'\nFound {len(orphaned)} orphaned categories to fix:\n')

fixed = 0
deleted = 0

for tax_id, name in orphaned:
    # Try to match to a case_type
    matched_case_type = None
    
    # Direct match
    if name in CATEGORY_TO_CASE_TYPE:
        matched_case_type = CATEGORY_TO_CASE_TYPE[name]
    else:
        # Try partial match
        for pattern, case_type in CATEGORY_TO_CASE_TYPE.items():
            if pattern.lower() in name.lower() or name.lower() in pattern.lower():
                matched_case_type = case_type
                break
    
    if matched_case_type and matched_case_type in case_types:
        parent_id = case_types[matched_case_type]
        
        # Check if this category already exists under the target parent
        cur.execute("""
            SELECT taxonomy_id FROM legal_taxonomy 
            WHERE parent_id = %s AND name = %s AND level_type = 'category'
        """, (parent_id, name))
        existing = cur.fetchone()
        
        if existing:
            # Duplicate exists - reassign children to existing, then delete orphan
            cur.execute("""
                UPDATE legal_taxonomy SET parent_id = %s WHERE parent_id = %s
            """, (existing[0], tax_id))
            cur.execute("DELETE FROM legal_taxonomy WHERE taxonomy_id = %s", (tax_id,))
            print(f'  ✗ "{name}" deleted (duplicate of ID {existing[0]})')
            deleted += 1
        else:
            # No duplicate - just update parent_id
            cur.execute(
                "UPDATE legal_taxonomy SET parent_id = %s WHERE taxonomy_id = %s",
                (parent_id, tax_id)
            )
            print(f'  ✓ "{name}" → parent: {matched_case_type} (ID {parent_id})')
            fixed += 1
    else:
        # Assign to "Other" case_type
        if 'Other' in case_types:
            parent_id = case_types['Other']
            # Check for duplicate
            cur.execute("""
                SELECT taxonomy_id FROM legal_taxonomy 
                WHERE parent_id = %s AND name = %s AND level_type = 'category'
            """, (parent_id, name))
            existing = cur.fetchone()
            
            if existing:
                cur.execute("""
                    UPDATE legal_taxonomy SET parent_id = %s WHERE parent_id = %s
                """, (existing[0], tax_id))
                cur.execute("DELETE FROM legal_taxonomy WHERE taxonomy_id = %s", (tax_id,))
                print(f'  ✗ "{name}" deleted (duplicate)')
                deleted += 1
            else:
                cur.execute(
                    "UPDATE legal_taxonomy SET parent_id = %s WHERE taxonomy_id = %s",
                    (parent_id, tax_id)
                )
                print(f'  ? "{name}" → parent: Other (ID {parent_id}) [no match]')
                fixed += 1

print(f'\n✅ Fixed {fixed} categories, deleted {deleted} duplicates')

# Verify
print('\n=== Verification ===')
cur.execute("""
    SELECT level_type, 
           COUNT(*) as total,
           COUNT(*) FILTER (WHERE parent_id IS NULL) as orphaned
    FROM legal_taxonomy 
    GROUP BY level_type 
    ORDER BY level_type
""")
for row in cur.fetchall():
    status = '✓' if (row[0] == 'case_type' and row[2] == row[1]) or (row[0] != 'case_type' and row[2] == 0) else '❌'
    print(f'  {status} {row[0]}: {row[1]} total, {row[2]} with NULL parent')

conn.close()
print('\n✅ Migration 018 complete')

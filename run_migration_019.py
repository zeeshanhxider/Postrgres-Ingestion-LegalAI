import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
conn.autocommit = True
cur = conn.cursor()

print('Migration 019: Clean up redundant category names\n')

# Step 1: Find and fix redundant categories that have the same name as their parent case_type
redundant_categories = [
    ('Criminal', 'Criminal Law'),
    ('Civil', 'Civil Law'),
    ('Family', 'Family Law'),
    ('Administrative', 'Administrative Law'),
    ('Constitutional', 'Constitutional Law'),
    ('Juvenile', 'Juvenile'),
    ('Juvenile', 'Juvenile Law'),
    ('Employment', 'Employment Law'),
]

print('Step 1: Handling redundant categories...\n')

for case_type, category_name in redundant_categories:
    # Find case_type ID
    cur.execute("SELECT taxonomy_id FROM legal_taxonomy WHERE level_type = 'case_type' AND name = %s", (case_type,))
    ct_row = cur.fetchone()
    if not ct_row:
        continue
    case_type_id = ct_row[0]
    
    # Find redundant category
    cur.execute("""
        SELECT taxonomy_id FROM legal_taxonomy 
        WHERE level_type = 'category' AND parent_id = %s AND name = %s
    """, (case_type_id, category_name))
    cat_row = cur.fetchone()
    if not cat_row:
        continue
    category_id = cat_row[0]
    
    print(f'  Processing: {case_type} → {category_name} (ID: {category_id})')
    
    # Get all subcategories under this redundant category
    cur.execute("""
        SELECT taxonomy_id, name FROM legal_taxonomy 
        WHERE level_type = 'subcategory' AND parent_id = %s
    """, (category_id,))
    subcategories = cur.fetchall()
    
    for sub_id, sub_name in subcategories:
        # Check if a category with this name already exists under the case_type
        cur.execute("""
            SELECT taxonomy_id FROM legal_taxonomy 
            WHERE level_type = 'category' AND parent_id = %s AND name = %s
        """, (case_type_id, sub_name))
        existing_cat = cur.fetchone()
        
        if existing_cat:
            # Merge: move all children of this subcategory to the existing category
            cur.execute("""
                UPDATE legal_taxonomy SET parent_id = %s 
                WHERE parent_id = %s
            """, (existing_cat[0], sub_id))
            # Update issues_decisions references
            cur.execute("""
                UPDATE issues_decisions SET taxonomy_id = %s WHERE taxonomy_id = %s
            """, (existing_cat[0], sub_id))
            # Delete the duplicate subcategory
            cur.execute("DELETE FROM legal_taxonomy WHERE taxonomy_id = %s", (sub_id,))
            print(f'    Merged subcategory "{sub_name}" into existing category')
        else:
            # Promote subcategory to category
            cur.execute("""
                UPDATE legal_taxonomy 
                SET parent_id = %s, level_type = 'category' 
                WHERE taxonomy_id = %s
            """, (case_type_id, sub_id))
            print(f'    Promoted "{sub_name}" to category')
    
    # Check if category still has any children or issues
    cur.execute("SELECT COUNT(*) FROM legal_taxonomy WHERE parent_id = %s", (category_id,))
    children = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM issues_decisions WHERE taxonomy_id = %s", (category_id,))
    issues = cur.fetchone()[0]
    
    if children == 0 and issues == 0:
        cur.execute("DELETE FROM legal_taxonomy WHERE taxonomy_id = %s", (category_id,))
        print(f'    ✓ Deleted empty redundant category "{category_name}"')
    else:
        print(f'    ⚠️  Keeping category (has {children} children, {issues} issues)')

# Step 2: Clean up pipe-separated names
print('\nStep 2: Cleaning up pipe-separated category names...')
cur.execute("""
    SELECT taxonomy_id, name, parent_id FROM legal_taxonomy 
    WHERE level_type = 'category' AND name LIKE '%|%'
""")
pipe_cats = cur.fetchall()

for tax_id, name, parent_id in pipe_cats:
    new_name = name.split('|')[-1].strip()
    
    # Check for duplicate
    cur.execute("""
        SELECT taxonomy_id FROM legal_taxonomy 
        WHERE parent_id = %s AND name = %s AND level_type = 'category' AND taxonomy_id != %s
    """, (parent_id, new_name, tax_id))
    existing = cur.fetchone()
    
    if existing:
        # Merge
        cur.execute("UPDATE legal_taxonomy SET parent_id = %s WHERE parent_id = %s", (existing[0], tax_id))
        cur.execute("UPDATE issues_decisions SET taxonomy_id = %s WHERE taxonomy_id = %s", (existing[0], tax_id))
        cur.execute("DELETE FROM legal_taxonomy WHERE taxonomy_id = %s", (tax_id,))
        print(f'  Merged "{name}" → existing "{new_name}"')
    else:
        cur.execute("UPDATE legal_taxonomy SET name = %s WHERE taxonomy_id = %s", (new_name, tax_id))
        print(f'  Renamed "{name}" → "{new_name}"')

# Verification
print('\n=== Verification ===')
cur.execute("SELECT level_type, COUNT(*) FROM legal_taxonomy GROUP BY level_type ORDER BY level_type")
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} entries')

print('\nRemaining case_type → category pairs:')
cur.execute("""
    SELECT ct.name, cat.name
    FROM legal_taxonomy cat
    JOIN legal_taxonomy ct ON cat.parent_id = ct.taxonomy_id
    WHERE cat.level_type = 'category' AND ct.level_type = 'case_type'
    ORDER BY ct.name, cat.name
    LIMIT 30
""")
for row in cur.fetchall():
    is_redundant = row[0].lower() in row[1].lower() or row[1].lower().startswith(row[0].lower())
    marker = '❌' if is_redundant else '✓'
    print(f'  {marker} {row[0]} → {row[1]}')

conn.close()
print('\n✅ Migration 019 complete')

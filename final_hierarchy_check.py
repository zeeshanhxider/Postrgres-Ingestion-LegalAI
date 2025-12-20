import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('=== Final check of hierarchy ===\n')

# Check for remaining potentially redundant patterns
print('Checking for remaining redundant patterns...')
cur.execute("""
    SELECT ct.name as case_type, cat.name as category, cat.taxonomy_id
    FROM legal_taxonomy cat
    JOIN legal_taxonomy ct ON cat.parent_id = ct.taxonomy_id
    WHERE cat.level_type = 'category' AND ct.level_type = 'case_type'
      AND (
          cat.name = ct.name
          OR cat.name = ct.name || ' Law'
          OR cat.name = ct.name || ' Procedure'
      )
    ORDER BY ct.name
""")
redundant = cur.fetchall()

if redundant:
    print(f'Found {len(redundant)} remaining redundant patterns:')
    for row in redundant:
        print(f'  ❌ {row[0]} → {row[1]} (ID: {row[2]})')
else:
    print('✓ No exact redundant patterns found')

print('\n=== Sample of the cleaned hierarchy ===\n')

# Show sample hierarchy
cur.execute("SELECT taxonomy_id, name FROM legal_taxonomy WHERE level_type = 'case_type' ORDER BY name LIMIT 5")
case_types = cur.fetchall()

for ct_id, ct_name in case_types:
    print(f'📁 {ct_name}')
    
    cur.execute("""
        SELECT taxonomy_id, name FROM legal_taxonomy 
        WHERE level_type = 'category' AND parent_id = %s ORDER BY name LIMIT 5
    """, (ct_id,))
    categories = cur.fetchall()
    
    for cat_id, cat_name in categories:
        # Skip if name contains case_type name (might be redundant)
        is_redundant = ct_name.lower() in cat_name.lower()
        marker = '❌' if is_redundant else '  '
        print(f'{marker}├─ {cat_name}')
        
        cur.execute("""
            SELECT name FROM legal_taxonomy 
            WHERE level_type = 'subcategory' AND parent_id = %s ORDER BY name LIMIT 2
        """, (cat_id,))
        subcats = cur.fetchall()
        for sub in subcats:
            print(f'    │  └─ {sub[0]}')
    
    print()

print('=== Summary ===')
cur.execute("SELECT level_type, COUNT(*) FROM legal_taxonomy GROUP BY level_type ORDER BY level_type")
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} entries')

conn.close()

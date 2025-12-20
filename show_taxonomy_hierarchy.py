import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('=== legal_taxonomy sorted hierarchically ===\n')

# Get all case_types first
cur.execute("""
    SELECT taxonomy_id, name 
    FROM legal_taxonomy 
    WHERE level_type = 'case_type' 
    ORDER BY name
""")
case_types = cur.fetchall()

for ct_id, ct_name in case_types:
    print(f'📁 {ct_name} (case_type, ID: {ct_id})')
    
    # Get categories under this case_type
    cur.execute("""
        SELECT taxonomy_id, name 
        FROM legal_taxonomy 
        WHERE level_type = 'category' AND parent_id = %s 
        ORDER BY name
    """, (ct_id,))
    categories = cur.fetchall()
    
    for cat_id, cat_name in categories:
        print(f'  ├─ {cat_name} (category, ID: {cat_id})')
        
        # Get subcategories under this category
        cur.execute("""
            SELECT taxonomy_id, name 
            FROM legal_taxonomy 
            WHERE level_type = 'subcategory' AND parent_id = %s 
            ORDER BY name
            LIMIT 3
        """, (cat_id,))
        subcategories = cur.fetchall()
        
        for i, (sub_id, sub_name) in enumerate(subcategories):
            prefix = '  │  └─' if i == len(subcategories) - 1 else '  │  ├─'
            print(f'{prefix} {sub_name} (subcategory, ID: {sub_id})')
        
        # Check if there are more
        cur.execute("""
            SELECT COUNT(*) 
            FROM legal_taxonomy 
            WHERE level_type = 'subcategory' AND parent_id = %s
        """, (cat_id,))
        total = cur.fetchone()[0]
        if total > 3:
            print(f'  │  └─ ... ({total - 3} more subcategories)')
    
    print()

print('\n' + '='*70)
print('=== Checking cases.case_type_id FK relationship ===\n')

# Check the FK constraint
cur.execute("""
    SELECT 
        tc.constraint_name, 
        tc.table_name, 
        kcu.column_name, 
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name 
    FROM information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY' 
        AND tc.table_name='cases'
        AND kcu.column_name = 'case_type_id'
""")
fk = cur.fetchone()

if fk:
    print(f'✓ Foreign Key: cases.{fk[2]} → {fk[3]}.{fk[4]}')
    print(f'  Constraint: {fk[0]}')
else:
    print('❌ No FK constraint found!')

# Show sample data
print('\n=== Sample cases with case_type_id ===')
cur.execute("""
    SELECT c.case_id, c.title, c.case_type_id, lt.name as case_type_name
    FROM cases c
    LEFT JOIN legal_taxonomy lt ON c.case_type_id = lt.taxonomy_id
    WHERE c.case_type_id IS NOT NULL
    LIMIT 5
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f'  Case {r[0]}: {r[1][:50]}...')
        print(f'    → case_type_id: {r[2]} ({r[3]})')
else:
    print('  No cases with case_type_id set')

conn.close()

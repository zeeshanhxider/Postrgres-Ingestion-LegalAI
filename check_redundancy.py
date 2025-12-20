import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('=== Finding redundant case_type → category pairs ===\n')

# Find categories that are the same name as their parent case_type
cur.execute("""
    SELECT 
        ct.taxonomy_id as ct_id,
        ct.name as case_type,
        cat.taxonomy_id as cat_id,
        cat.name as category
    FROM legal_taxonomy cat
    JOIN legal_taxonomy ct ON cat.parent_id = ct.taxonomy_id
    WHERE cat.level_type = 'category' 
      AND ct.level_type = 'case_type'
      AND (
          LOWER(cat.name) = LOWER(ct.name) 
          OR LOWER(cat.name) LIKE LOWER(ct.name || ' %')
          OR LOWER(cat.name) LIKE LOWER(ct.name || ' Law')
          OR LOWER(cat.name) = LOWER(ct.name || ' Law')
      )
    ORDER BY ct.name
""")
redundant = cur.fetchall()

if redundant:
    print(f'Found {len(redundant)} redundant case_type → category pairs:')
    for row in redundant:
        print(f'  ❌ {row[1]} (case_type ID:{row[0]}) → {row[3]} (category ID:{row[2]})')
else:
    print('✓ No redundant pairs found')

print('\n=== Full hierarchy showing redundancy ===\n')
cur.execute("""
    SELECT ct.name as case_type, cat.name as category
    FROM legal_taxonomy cat
    JOIN legal_taxonomy ct ON cat.parent_id = ct.taxonomy_id
    WHERE cat.level_type = 'category' AND ct.level_type = 'case_type'
    ORDER BY ct.name, cat.name
""")
print('{:<20} -> {}'.format('Case Type', 'Category'))
print('-'*60)
for row in cur.fetchall():
    marker = '❌ REDUNDANT' if row[0].lower() == row[1].lower() or row[1].lower() == f'{row[0].lower()} law' else ''
    print('{:<20} -> {} {}'.format(row[0], row[1], marker))

conn.close()

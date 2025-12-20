import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('=== Categories with NULL parent_id (orphaned) ===')
cur.execute("""
    SELECT taxonomy_id, name, level_type 
    FROM legal_taxonomy 
    WHERE level_type = 'category' AND parent_id IS NULL
    ORDER BY name
""")
rows = cur.fetchall()
print(f'Found {len(rows)} orphaned categories:')
for row in rows:
    print(f'  ID {row[0]}: {row[1]}')

print('\n=== Categories with valid parent_id ===')
cur.execute("""
    SELECT c.taxonomy_id, c.name, p.name as parent_name
    FROM legal_taxonomy c
    JOIN legal_taxonomy p ON c.parent_id = p.taxonomy_id
    WHERE c.level_type = 'category'
    LIMIT 10
""")
rows = cur.fetchall()
print(f'Sample of linked categories:')
for row in rows:
    print(f'  {row[1]} → parent: {row[2]}')

conn.close()

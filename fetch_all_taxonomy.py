import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('=== ENTIRE legal_taxonomy table ===\n')
cur.execute("""
    SELECT taxonomy_id, parent_id, name, level_type, created_at 
    FROM legal_taxonomy 
    ORDER BY level_type, name
    LIMIT 50
""")
rows = cur.fetchall()

print(f'First 50 rows (Total rows: ', end='')
cur.execute("SELECT COUNT(*) FROM legal_taxonomy")
print(f'{cur.fetchone()[0]})\n')

for r in rows:
    parent = f'parent:{r[1]}' if r[1] else 'parent:NULL'
    print(f'ID {r[0]:4} | {parent:15} | {r[3]:12} | {r[2]}')

print('\n=== Count by level_type ===')
cur.execute("""
    SELECT level_type, COUNT(*) 
    FROM legal_taxonomy 
    GROUP BY level_type 
    ORDER BY level_type
""")
for r in cur.fetchall():
    print(f'  {r[0]:15} : {r[1]} entries')

print('\n=== Sample case_type entries ===')
cur.execute("""
    SELECT taxonomy_id, name, parent_id 
    FROM legal_taxonomy 
    WHERE level_type = 'case_type'
""")
case_types = cur.fetchall()
if case_types:
    for r in case_types:
        print(f'  ID {r[0]}: {r[1]} (parent: {r[2]})')
else:
    print('  ❌ NO case_type entries found!')

conn.close()

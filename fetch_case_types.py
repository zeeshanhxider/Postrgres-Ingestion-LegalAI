import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('=== CASE TYPES in legal_taxonomy ===')
cur.execute("""
    SELECT taxonomy_id, name, level_type, parent_id 
    FROM legal_taxonomy 
    WHERE level_type = 'case_type' 
    ORDER BY name
""")
rows = cur.fetchall()
for r in rows:
    print(f'  ID {r[0]}: {r[1]} (level: {r[2]}, parent: {r[3]})')
print(f'\nTotal case_type entries: {len(rows)}')

print('\n=== ALL LEVEL TYPES ===')
cur.execute("SELECT level_type, COUNT(*) FROM legal_taxonomy GROUP BY level_type ORDER BY level_type")
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]} entries')

conn.close()

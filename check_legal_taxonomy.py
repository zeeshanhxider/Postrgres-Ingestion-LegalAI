import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('=== Case types in legal_taxonomy ===')
cur.execute("SELECT taxonomy_id, name, level_type FROM legal_taxonomy WHERE level_type = 'case_type' ORDER BY name")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f'  ID {row[0]}: {row[1]} ({row[2]})')
else:
    print('  No case_type entries found!')

print('\n=== All level_type values ===')
cur.execute("SELECT level_type, COUNT(*) FROM legal_taxonomy GROUP BY level_type ORDER BY level_type")
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} entries')

print('\n=== Sample category entries ===')
cur.execute("SELECT taxonomy_id, name, parent_id FROM legal_taxonomy WHERE level_type = 'category' LIMIT 5")
for row in cur.fetchall():
    print(f'  ID {row[0]}: {row[1]} (parent: {row[2]})')

conn.close()

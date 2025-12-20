import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('=== case_types table ===')
cur.execute("SELECT * FROM case_types LIMIT 5")
for row in cur.fetchall():
    print(f'  {row}')

print('\n=== legal_taxonomy (case_type level) ===')
cur.execute("SELECT * FROM legal_taxonomy WHERE level_type = 'case_type'")
for row in cur.fetchall():
    print(f'  {row}')

print('\n=== cases.case_type_id usage ===')
cur.execute("SELECT case_type_id, COUNT(*) FROM cases WHERE case_type_id IS NOT NULL GROUP BY case_type_id")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f'  case_type_id {row[0]}: {row[1]} cases')
else:
    print('  No cases have case_type_id set')

conn.close()

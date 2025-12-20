import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'legal_taxonomy' 
    ORDER BY ordinal_position
""")

print('legal_taxonomy columns:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()

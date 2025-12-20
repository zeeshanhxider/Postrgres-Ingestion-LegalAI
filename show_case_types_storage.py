import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('╔═══════════════════════════════════════════════════════╗')
print('║  Case types are stored in: legal_taxonomy table      ║')
print('╚═══════════════════════════════════════════════════════╝\n')

cur.execute("""
    SELECT taxonomy_id, name, level_type, parent_id 
    FROM legal_taxonomy 
    WHERE level_type = 'case_type' 
    ORDER BY name
""")
rows = cur.fetchall()

print('All case_type entries:')
for r in rows:
    print(f'  ID {r[0]}: {r[1]}')

print(f'\nTotal: {len(rows)} case types')

print('\n' + '='*60)
print('Referenced by:')
print('  - cases.case_type_id → legal_taxonomy.taxonomy_id')
print('  - categories (parent_id) → legal_taxonomy.taxonomy_id')
print('  - issues_decisions.taxonomy_id → subcategory → category → case_type')

print('\n' + '='*60)
print('The old case_types table was removed (Migration 017)')

conn.close()

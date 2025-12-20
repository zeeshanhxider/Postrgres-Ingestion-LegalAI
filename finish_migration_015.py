import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
conn.autocommit = True
cur = conn.cursor()

print('Dropping and recreating view...')
cur.execute('DROP VIEW IF EXISTS v_legal_taxonomy_hierarchy CASCADE')
cur.execute("""
CREATE VIEW v_legal_taxonomy_hierarchy AS
SELECT 
    ct.taxonomy_id as case_type_id,
    ct.name as case_type,
    cat.taxonomy_id as category_id,
    cat.name as category,
    subcat.taxonomy_id as subcategory_id,
    subcat.name as subcategory
FROM legal_taxonomy ct
LEFT JOIN legal_taxonomy cat ON cat.parent_id = ct.taxonomy_id AND cat.level_type = 'category'
LEFT JOIN legal_taxonomy subcat ON subcat.parent_id = cat.taxonomy_id AND subcat.level_type = 'subcategory'
WHERE ct.level_type = 'case_type'
ORDER BY ct.name, cat.name, subcat.name
""")
print('  View recreated')

print('\nVerifying...')
cur.execute('SELECT level_type, COUNT(*) FROM legal_taxonomy GROUP BY level_type ORDER BY level_type')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} entries')

conn.close()
print('\n✅ Migration 015 complete - area_of_law renamed to case_type')

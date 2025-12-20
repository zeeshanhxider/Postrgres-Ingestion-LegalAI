import psycopg2

conn = psycopg2.connect('postgresql://postgres:postgres123@localhost:5435/cases_llama3_3')
cur = conn.cursor()

print('='*70)
print('VALIDATING legal_taxonomy HIERARCHY')
print('='*70 + '\n')

errors = []
warnings = []

# Test 1: All case_types should have parent_id = NULL
print('Test 1: Case types should have no parent...')
cur.execute("""
    SELECT taxonomy_id, name 
    FROM legal_taxonomy 
    WHERE level_type = 'case_type' AND parent_id IS NOT NULL
""")
bad_case_types = cur.fetchall()
if bad_case_types:
    errors.append(f"❌ Found {len(bad_case_types)} case_types with parent_id set:")
    for row in bad_case_types:
        errors.append(f"   ID {row[0]}: {row[1]}")
else:
    print('  ✓ All case_types have parent_id = NULL')

# Test 2: All categories should have parent_id pointing to a case_type
print('\nTest 2: Categories should have case_type as parent...')
cur.execute("""
    SELECT c.taxonomy_id, c.name, c.parent_id
    FROM legal_taxonomy c
    WHERE c.level_type = 'category' AND c.parent_id IS NULL
""")
orphaned_categories = cur.fetchall()
if orphaned_categories:
    errors.append(f"❌ Found {len(orphaned_categories)} categories with NULL parent:")
    for row in orphaned_categories:
        errors.append(f"   ID {row[0]}: {row[1]}")
else:
    print('  ✓ No orphaned categories (all have parent_id)')

# Test 2b: Verify category parents are actually case_types
cur.execute("""
    SELECT c.taxonomy_id, c.name, c.parent_id, p.level_type
    FROM legal_taxonomy c
    JOIN legal_taxonomy p ON c.parent_id = p.taxonomy_id
    WHERE c.level_type = 'category' AND p.level_type != 'case_type'
""")
wrong_parent_categories = cur.fetchall()
if wrong_parent_categories:
    errors.append(f"❌ Found {len(wrong_parent_categories)} categories with wrong parent level:")
    for row in wrong_parent_categories:
        errors.append(f"   Category ID {row[0]}: {row[1]} → parent level: {row[3]}")
else:
    print('  ✓ All categories have case_type parents')

# Test 3: All subcategories should have parent_id pointing to a category
print('\nTest 3: Subcategories should have category as parent...')
cur.execute("""
    SELECT s.taxonomy_id, s.name, s.parent_id
    FROM legal_taxonomy s
    WHERE s.level_type = 'subcategory' AND s.parent_id IS NULL
""")
orphaned_subcategories = cur.fetchall()
if orphaned_subcategories:
    errors.append(f"❌ Found {len(orphaned_subcategories)} subcategories with NULL parent:")
    for row in orphaned_subcategories:
        errors.append(f"   ID {row[0]}: {row[1]}")
else:
    print('  ✓ No orphaned subcategories (all have parent_id)')

# Test 3b: Verify subcategory parents are actually categories
cur.execute("""
    SELECT s.taxonomy_id, s.name, s.parent_id, p.level_type
    FROM legal_taxonomy s
    JOIN legal_taxonomy p ON s.parent_id = p.taxonomy_id
    WHERE s.level_type = 'subcategory' AND p.level_type != 'category'
""")
wrong_parent_subcategories = cur.fetchall()
if wrong_parent_subcategories:
    errors.append(f"❌ Found {len(wrong_parent_subcategories)} subcategories with wrong parent level:")
    for row in wrong_parent_subcategories:
        errors.append(f"   Subcategory ID {row[0]}: {row[1]} → parent level: {row[3]}")
else:
    print('  ✓ All subcategories have category parents')

# Test 4: Count structure
print('\nTest 4: Counting hierarchy structure...')
cur.execute("""
    SELECT 
        (SELECT COUNT(*) FROM legal_taxonomy WHERE level_type = 'case_type') as case_types,
        (SELECT COUNT(*) FROM legal_taxonomy WHERE level_type = 'category') as categories,
        (SELECT COUNT(*) FROM legal_taxonomy WHERE level_type = 'subcategory') as subcategories,
        (SELECT COUNT(*) FROM legal_taxonomy) as total
""")
counts = cur.fetchone()
print(f'  Case Types: {counts[0]}')
print(f'  Categories: {counts[1]}')
print(f'  Subcategories: {counts[2]}')
print(f'  Total: {counts[3]}')

# Test 5: Check for duplicate names at same level
print('\nTest 5: Checking for duplicate names at same level...')
cur.execute("""
    SELECT name, level_type, parent_id, COUNT(*) 
    FROM legal_taxonomy 
    GROUP BY name, level_type, parent_id 
    HAVING COUNT(*) > 1
""")
duplicates = cur.fetchall()
if duplicates:
    warnings.append(f"⚠️  Found {len(duplicates)} duplicate entries:")
    for row in duplicates:
        warnings.append(f"   '{row[0]}' ({row[1]}, parent:{row[2]}) - {row[3]} times")
else:
    print('  ✓ No duplicates found')

# Test 6: Sample hierarchy paths
print('\nTest 6: Sample hierarchy paths (case_type → category → subcategory)...')
cur.execute("""
    SELECT 
        ct.name as case_type,
        cat.name as category,
        sub.name as subcategory
    FROM legal_taxonomy sub
    JOIN legal_taxonomy cat ON sub.parent_id = cat.taxonomy_id
    JOIN legal_taxonomy ct ON cat.parent_id = ct.taxonomy_id
    WHERE sub.level_type = 'subcategory'
    LIMIT 5
""")
samples = cur.fetchall()
print('  Sample paths:')
for row in samples:
    print(f'    {row[0]} → {row[1]} → {row[2]}')

# Test 7: Check for categories with no subcategories
print('\nTest 7: Categories with no subcategories...')
cur.execute("""
    SELECT c.taxonomy_id, c.name
    FROM legal_taxonomy c
    WHERE c.level_type = 'category'
    AND NOT EXISTS (
        SELECT 1 FROM legal_taxonomy s 
        WHERE s.parent_id = c.taxonomy_id AND s.level_type = 'subcategory'
    )
""")
empty_categories = cur.fetchall()
if empty_categories:
    warnings.append(f"⚠️  Found {len(empty_categories)} categories with no subcategories:")
    for row in empty_categories[:5]:
        warnings.append(f"   ID {row[0]}: {row[1]}")
    if len(empty_categories) > 5:
        warnings.append(f"   ... and {len(empty_categories) - 5} more")
else:
    print('  ✓ All categories have at least one subcategory')

# Print summary
print('\n' + '='*70)
print('VALIDATION SUMMARY')
print('='*70)

if errors:
    print('\n🔴 ERRORS FOUND:')
    for error in errors:
        print(error)
else:
    print('\n✅ No errors found!')

if warnings:
    print('\n⚠️  WARNINGS:')
    for warning in warnings:
        print(warning)
else:
    print('\n✅ No warnings!')

if not errors and not warnings:
    print('\n🎉 Hierarchy is completely valid!')

conn.close()

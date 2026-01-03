# Production Database Audit Report

**Database:** `cases_llama3_3` on `legal_ai_postgres_v2:5435`  
**Audit Date:** January 3, 2026  
**Current Scale:** 3,991 cases | **Target Scale:** Millions of cases

---

## Executive Summary

The database has a solid foundation but requires **significant optimization** to handle millions of cases. Current issues fall into 5 categories:

| Category | Severity | Issues Found |
|----------|----------|--------------|
| 🔴 **Partitioning** | Critical | No partitioning on large tables |
| 🔴 **Data Normalization** | Critical | Denormalized/inconsistent values |
| 🟠 **Index Optimization** | High | 670MB+ unused indexes, missing critical indexes |
| 🟠 **PostgreSQL Config** | High | Development-level settings |
| 🟡 **Data Quality** | Medium | Missing FKs, unlinked citations |

---

## 🔴 CRITICAL: Partitioning Required

### Problem
With millions of cases, these tables will become unmanageable:

| Table | Current Rows | Projected (1M cases) | Issue |
|-------|-------------|---------------------|-------|
| `case_sentences` | 1,057,318 | ~265M rows | Sequential scans = hours |
| `case_phrases` | 919,245 | ~230M rows | Index bloat |
| `embeddings` | 60,784 | ~15M rows | HNSW index rebuild time |
| `case_chunks` | 60,784 | ~15M rows | TSV index bloat |

### Solution: Implement Range Partitioning

```sql
-- Partition case_sentences by case_id ranges
CREATE TABLE case_sentences_partitioned (
    LIKE case_sentences INCLUDING ALL
) PARTITION BY RANGE (case_id);

CREATE TABLE case_sentences_p0 PARTITION OF case_sentences_partitioned
    FOR VALUES FROM (0) TO (100000);
CREATE TABLE case_sentences_p1 PARTITION OF case_sentences_partitioned
    FOR VALUES FROM (100000) TO (200000);
-- Continue for expected range...

-- Alternative: Partition by year for time-based queries
ALTER TABLE cases ADD COLUMN decision_year_int INTEGER 
    GENERATED ALWAYS AS (EXTRACT(YEAR FROM appeal_published_date)::INTEGER) STORED;
```

**Priority:** Implement BEFORE reaching 100K cases

---

## 🔴 CRITICAL: Data Normalization Issues

### 1. `winner_legal_role` is NOT Normalized

**Problem:** 20+ different formats for the same concept:

```
'Appellant', 'Appellant (GEICO)', 'Appellant (DOC)', 
'Appellant/Cross Respondent (DSHS)', 'Appellant (Kovacs)',
'Plaintiffs', 'Elite Cornerstone Construction, LLC' (!)
```

**Solution:** Create a normalized lookup:

```sql
-- Create normalized legal_role dimension
CREATE TABLE legal_roles_dim (
    role_id SERIAL PRIMARY KEY,
    canonical_role VARCHAR(50) NOT NULL, -- 'Appellant', 'Respondent', 'Petitioner'
    display_name VARCHAR(100),
    is_prevailing BOOLEAN DEFAULT FALSE
);

INSERT INTO legal_roles_dim (canonical_role) VALUES 
    ('Appellant'), ('Respondent'), ('Petitioner'), 
    ('Cross-Appellant'), ('Cross-Respondent'), ('Intervenor');

-- Add FK to cases
ALTER TABLE cases ADD COLUMN winner_role_id BIGINT REFERENCES legal_roles_dim(role_id);

-- Migrate existing data
UPDATE cases SET winner_role_id = (
    SELECT role_id FROM legal_roles_dim 
    WHERE cases.winner_legal_role ILIKE canonical_role || '%'
    LIMIT 1
);
```

### 2. `parties.legal_role` Same Problem

50+ variations found. Same normalization needed.

### 3. `citation_edges.relationship` Not Normalized

```
'relied_upon' vs 'Relied upon' (case mismatch)
'statute cited' vs 'statute' vs 'statutory' (redundant)
```

**Solution:**
```sql
CREATE TYPE citation_relationship_type AS ENUM (
    'relied_upon', 'distinguished', 'cited', 'overruled', 
    'applied', 'interpreted', 'disapproved', 'related'
);

ALTER TABLE citation_edges 
    ALTER COLUMN relationship TYPE citation_relationship_type 
    USING LOWER(TRIM(relationship))::citation_relationship_type;
```

---

## 🟠 HIGH: Index Optimization

### Unused Indexes (670MB wasted!)

| Index | Size | Scans | Action |
|-------|------|-------|--------|
| `idx_embeddings_hnsw` | 475 MB | 0 | ⚠️ Keep - needed for vector search |
| `uq_case_sentence_order` | 63 MB | 0 | Evaluate if unique constraint needed |
| `idx_case_chunks_tsv` | 44 MB | 0 | Evaluate full-text search usage |
| `idx_case_sentences_global_order` | 44 MB | 0 | **DROP** - unused |
| `idx_embeddings_tsv` | 43 MB | 0 | **DROP** - redundant with chunk search |
| `idx_case_phrases_phrase_trgm` | 42 MB | 0 | Evaluate trigram search usage |

**Recommended Actions:**
```sql
-- Drop confirmed unused indexes
DROP INDEX idx_case_sentences_global_order;
DROP INDEX idx_embeddings_tsv;
DROP INDEX idx_embeddings_order;
DROP INDEX idx_case_chunks_case_order;

-- Reclaim ~135MB immediately
```

### Missing Critical Indexes

```sql
-- For filtering cases by year (very common query)
CREATE INDEX CONCURRENTLY idx_cases_year_type 
    ON cases(decision_year, case_type);

-- For finding cases by outcome
CREATE INDEX CONCURRENTLY idx_cases_outcome 
    ON cases(overall_case_outcome, case_type);

-- For citation network traversal
CREATE INDEX CONCURRENTLY idx_citation_edges_target 
    ON citation_edges(target_case_id) WHERE target_case_id IS NOT NULL;

-- For taxonomy hierarchy queries
CREATE INDEX CONCURRENTLY idx_legal_taxonomy_hierarchy 
    ON legal_taxonomy(parent_id, level_type);
```

---

## 🟠 HIGH: PostgreSQL Configuration

Current settings are **development defaults**, not production:

| Setting | Current | Recommended (16GB RAM) | Impact |
|---------|---------|------------------------|--------|
| `shared_buffers` | 128MB | 4GB | 30x more cache |
| `work_mem` | 4MB | 64MB | Faster sorts/joins |
| `maintenance_work_mem` | 64MB | 1GB | Faster VACUUM/INDEX |
| `effective_cache_size` | 4GB | 12GB | Better query plans |
| `random_page_cost` | 4 | 1.1 | SSD optimization |
| `effective_io_concurrency` | 1 | 200 | SSD parallelism |

### Docker Compose Update

```yaml
services:
  postgres:
    command: >
      postgres 
      -c shared_preload_libraries=vector
      -c max_connections=200
      -c shared_buffers=4GB
      -c work_mem=64MB
      -c maintenance_work_mem=1GB
      -c effective_cache_size=12GB
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
      -c wal_buffers=64MB
      -c checkpoint_completion_target=0.9
      -c max_wal_size=4GB
      -c min_wal_size=1GB
```

---

## 🟡 MEDIUM: Data Quality Issues

### 1. Missing Foreign Key References

| Issue | Count | Query to Find |
|-------|-------|---------------|
| Cases without `court_id` | 3 | `SELECT * FROM cases WHERE court_id IS NULL` |
| Cases without `case_type_id` | 1 | `SELECT * FROM cases WHERE case_type_id IS NULL` |
| Cases without `stage_type_id` | 3 | `SELECT * FROM cases WHERE stage_type_id IS NULL` |

### 2. Unlinked Citations (100%!)

**Problem:** ALL 5,668 citations have `target_case_id = NULL`

This means the citation graph is **not connected** - you can't traverse from case to cited case.

**Solution:** Run citation linking job:
```sql
-- Link citations to cases in database
UPDATE citation_edges ce
SET target_case_id = c.case_id
FROM cases c
WHERE ce.target_case_citation ILIKE '%' || c.case_file_id || '%'
  AND ce.target_case_id IS NULL;
```

### 3. Taxonomy Has 2,244 "General" Entries

The subcategory "General" appears 2,244 times across different categories. This is a catch-all that provides no semantic value.

**Consider:** Creating more specific subcategories or removing "General" and allowing NULL.

---

## 🟡 MEDIUM: Schema Design Improvements

### 1. Add Audit/Versioning Columns

```sql
-- Add to all main tables
ALTER TABLE cases ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE cases ADD COLUMN created_by VARCHAR(100);
ALTER TABLE cases ADD COLUMN updated_by VARCHAR(100);
```

### 2. Add Soft Delete Support

```sql
ALTER TABLE cases ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE cases ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;

-- Create partial index for active records only
CREATE INDEX idx_cases_active ON cases(case_id) WHERE is_deleted = FALSE;
```

### 3. Separate TOAST Tables for Large Text

The `full_text` column averages 36KB per case (max 417KB). At 1M cases, that's 36GB of text.

```sql
-- Move large text to separate table
CREATE TABLE case_full_text (
    case_id BIGINT PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
    full_text TEXT NOT NULL,
    compressed_text BYTEA, -- Optional: store compressed version
    text_hash VARCHAR(64)  -- For deduplication
);

-- Remove from main table after migration
ALTER TABLE cases DROP COLUMN full_text;
```

### 4. Add Materialized Views for Common Queries

```sql
-- Case statistics by year and type
CREATE MATERIALIZED VIEW mv_case_stats AS
SELECT 
    decision_year,
    case_type,
    COUNT(*) as case_count,
    COUNT(CASE WHEN overall_case_outcome = 'Affirmed' THEN 1 END) as affirmed_count,
    COUNT(CASE WHEN overall_case_outcome = 'Reversed' THEN 1 END) as reversed_count
FROM cases
WHERE decision_year IS NOT NULL
GROUP BY decision_year, case_type;

CREATE UNIQUE INDEX ON mv_case_stats(decision_year, case_type);

-- Refresh periodically
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_case_stats;
```

---

## 📋 Implementation Priority

### Phase 1: Immediate (This Week)
1. ✅ Fix PostgreSQL configuration
2. ✅ Drop unused indexes (save 135MB)
3. ✅ Fix missing court_id/stage_type_id (3 cases)
4. ✅ Run citation linking job

### Phase 2: Short-term (2 Weeks)
1. Normalize `winner_legal_role` 
2. Normalize `parties.legal_role`
3. Normalize `citation_edges.relationship`
4. Add missing composite indexes

### Phase 3: Before 100K Cases
1. Implement table partitioning for `case_sentences`, `case_phrases`
2. Separate `full_text` to its own table
3. Add soft delete support
4. Create materialized views

### Phase 4: Before 1M Cases
1. Consider read replicas for search queries
2. Implement connection pooling (PgBouncer)
3. Set up automated VACUUM scheduling
4. Implement table/index monitoring alerts

---

## Estimated Storage at Scale

| Cases | case_sentences | embeddings | Total DB Size |
|-------|---------------|------------|---------------|
| 4K (current) | 1M rows | 61K rows | ~2.3 GB |
| 100K | 26M rows | 1.5M rows | ~60 GB |
| 1M | 265M rows | 15M rows | ~600 GB |
| 10M | 2.6B rows | 150M rows | ~6 TB |

**Recommendation:** Plan for NVMe storage and consider TimescaleDB or Citus for horizontal scaling beyond 1M cases.

---

## Quick Wins Script

Run this immediately to fix low-hanging fruit:

```sql
-- 1. Fix missing FK references
UPDATE cases SET court_id = 77 WHERE court_id IS NULL AND court ILIKE '%Division I%';
UPDATE cases SET court_id = 76 WHERE court_id IS NULL AND court ILIKE '%Division II%';
UPDATE cases SET court_id = 75 WHERE court_id IS NULL AND court ILIKE '%Division III%';
UPDATE cases SET court_id = 78 WHERE court_id IS NULL AND court ILIKE '%Supreme%';

UPDATE cases SET stage_type_id = 30 WHERE stage_type_id IS NULL AND court_level = 'Court of Appeals';
UPDATE cases SET stage_type_id = 31 WHERE stage_type_id IS NULL AND court_level = 'Supreme Court';

-- 2. Normalize relationship case sensitivity
UPDATE citation_edges SET relationship = LOWER(TRIM(relationship));

-- 3. Analyze all tables for better query plans
ANALYZE;

-- 4. Log slow queries for optimization
ALTER SYSTEM SET log_min_duration_statement = 1000; -- Log queries > 1 second
SELECT pg_reload_conf();
```

# Database Scalability Refactoring Plan

## Executive Summary

This document outlines the critical scalability issues identified in the Legal AI PostgreSQL schema and the refactoring plan to address them. The changes target **Storage Efficiency** and **Query Performance** for a system expecting 10M+ rows.

---

## Issue 1: Low-Cardinality Text Columns (CRITICAL)

### Problem
Status columns like `processing_status`, `publication_status`, and `side` use `citext` (case-insensitive text), which wastes storage:

| Data Type | Storage Per Value | Overhead |
|-----------|------------------|----------|
| `citext` | ~23+ bytes | Variable length header + string |
| `ENUM` | 4 bytes | Fixed, stored as OID |
| `smallint` | 2 bytes | Fixed |

**At 10M rows with 3 status columns: ~570 MB wasted storage**

### Solution: Convert to PostgreSQL ENUMs

ENUMs are preferred over smallint because:
- ✅ **Self-documenting** - Valid values visible in schema
- ✅ **Type-safe** - Prevents invalid values at DB level
- ✅ **Readable queries** - `WHERE status = 'pending'` not `WHERE status = 1`
- ✅ **4 bytes** - Fixed storage, efficient indexing

### Columns Migrated

| Table | Column | Old Type | New ENUM Type |
|-------|--------|----------|---------------|
| `cases` | `processing_status` | citext | `processing_status_type` |
| `cases` | `publication_status` | citext | `publication_status_type` |
| `briefs` | `processing_status` | citext | `processing_status_type` |
| `documents` | `processing_status` | citext | `processing_status_type` |
| `ingestion_batches` | `status` | citext | `batch_status_type` |
| `ingestion_batches` | `source_type` | citext | `source_type_type` |
| `issues_decisions` | `issue_outcome` | citext | `issue_outcome_type` |
| `courts_dim` | `court_type` | citext | `court_type_type` |
| `document_types` | `role` | citext | `document_role_type` |
| `document_types` | `processing_strategy` | citext | `processing_strategy_type` |

### ENUMs Created (14 total)

```sql
processing_status_type: pending, text_extracted, ai_processed, embedded, fully_processed, failed
publication_status_type: Published, Unpublished, Partially Published, Published in Part
batch_status_type: running, completed, failed, cancelled, paused
source_type_type: supreme_court, court_of_appeals, court_of_appeals_partial, briefs, mixed, csv
argument_side_type: appellant, respondent, amicus
issue_outcome_type: Affirmed, Dismissed, Reversed, Remanded, Mixed
court_type_type: Supreme Court, Court of Appeals, Superior Court, District Court, Municipal Court
document_role_type: court, party, evidence, administrative
processing_strategy_type: case_outcome, brief_extraction, evidence_indexing, text_only
brief_type_type: opening_brief, respondent_brief, reply_brief, amicus_brief
user_type_type: pro_se, lawyer, other
citation_relationship_type: cites, distinguishes, overrules, follows, affirms, reverses, discusses
citation_importance_type: primary, secondary, passing
judge_role_type: author, concurring, dissenting, per_curiam
```

---

## Issue 2: word_occurrence Table Explosion (CRITICAL)

### Problem
The `word_occurrence` table stores **ONE ROW PER WORD POSITION**:

```
word_id | case_id | chunk_id | sentence_id | position
--------|---------|----------|-------------|----------
1       | 100     | 500      | 2000        | 0
1       | 100     | 500      | 2000        | 15
1       | 100     | 500      | 2001        | 3
...
```

**Growth Calculation:**
- ~50 words per sentence
- ~20 sentences per chunk
- ~50 chunks per case
- = **50,000 rows per case**
- × 10,000 cases = **500 MILLION ROWS!**

Same issue exists for `brief_word_occurrence`.

### Solution: DROP (Aggressive) - RECOMMENDED

The tables are **REDUNDANT** because:

1. `case_chunks.tsv` already has a `tsvector` column with GIN index
2. `case_sentences.tsv` also has a `tsvector` column with GIN index
3. `tsvector` provides:
   - Full-text search with ranking (`ts_rank`)
   - Stemming and stop-word removal
   - Position information via `ts_headline()`
   - Efficient GIN indexing

**Action Taken:**
```sql
-- Backup samples before dropping
CREATE TABLE word_occurrence_backup AS SELECT * FROM word_occurrence LIMIT 10000;
CREATE TABLE brief_word_occurrence_backup AS SELECT * FROM brief_word_occurrence LIMIT 10000;

-- Drop redundant tables
DROP TABLE word_occurrence CASCADE;
DROP TABLE brief_word_occurrence CASCADE;
```

### Alternative: Array Refactoring (Conservative)

If position tracking is required for specialized features:

```sql
CREATE TABLE word_occurrence_v2 (
    word_id integer NOT NULL,
    case_id bigint NOT NULL,
    chunk_id bigint NOT NULL,
    positions integer[] NOT NULL,  -- Array of positions
    frequency integer GENERATED ALWAYS AS (array_length(positions, 1)) STORED,
    PRIMARY KEY (word_id, case_id, chunk_id)
);
```

**Reduction:** 50 rows → 1 row per word per chunk (**98% reduction**)

---

## Issue 3: Scalability Audit - Additional Findings

### High-Growth Tables Identified

| Table | Growth Pattern | Risk Level |
|-------|---------------|------------|
| `embeddings` | 1 row per chunk × 1024 floats | 🔴 CRITICAL |
| `case_sentences` | ~20+ per case | 🟡 HIGH |
| `case_phrases` | N-grams explode quickly | 🟡 HIGH |
| `citation_edges` | ~50+ citations per case | 🟡 HIGH |
| `brief_sentences` | ~30+ per brief | 🟡 HIGH |
| `brief_chunks` | ~10+ per brief | 🟡 MEDIUM |

### Recommended: Table Partitioning

#### Partition `embeddings` by `decision_year`

```sql
CREATE TABLE embeddings_partitioned (
    embedding_id bigint NOT NULL,
    case_id bigint NOT NULL,
    decision_year integer NOT NULL,  -- Partition key
    embedding vector(1024) NOT NULL,
    ...
) PARTITION BY RANGE (decision_year);

CREATE TABLE embeddings_y2020 PARTITION OF embeddings_partitioned
    FOR VALUES FROM (2020) TO (2021);
CREATE TABLE embeddings_y2021 PARTITION OF embeddings_partitioned
    FOR VALUES FROM (2021) TO (2022);
-- ... etc
```

**Benefits:**
- Partition pruning for year-filtered queries
- Parallel query execution
- Easier maintenance (can drop old partitions)
- Better vacuum performance

#### Partition `case_sentences` by Hash

```sql
CREATE TABLE case_sentences_partitioned (
    ...
) PARTITION BY HASH (case_id);

CREATE TABLE case_sentences_p0 PARTITION OF case_sentences_partitioned
    FOR VALUES WITH (MODULUS 8, REMAINDER 0);
-- ... 8 partitions
```

---

## Issue 4: Missing Foreign Key Indexes

### Problem
Every FK column should have an index for:
- Efficient JOINs
- Fast `ON DELETE CASCADE` operations
- Query planner optimization

### Missing Indexes Found and Added (18 total)

| Table | Column | Index Created |
|-------|--------|---------------|
| `case_judges` | `judge_id` | `idx_case_judges_judge_id` |
| `citation_edges` | `target_case_id` | `idx_citation_edges_target_case_id` |
| `case_chunks` | `document_id` | `idx_case_chunks_document_id` |
| `case_sentences` | `document_id` | `idx_case_sentences_document_id` |
| `case_phrases` | `document_id` | `idx_case_phrases_document_id` |
| `case_phrases` | `example_sentence` | `idx_case_phrases_example_sentence` |
| `case_phrases` | `example_chunk` | `idx_case_phrases_example_chunk` |
| `documents` | `document_type_id` | `idx_documents_document_type_id` |
| `documents` | `stage_type_id` | `idx_documents_stage_type_id` |
| `cases` | `case_type_id` | `idx_cases_case_type_id` |
| `cases` | `stage_type_id` | `idx_cases_stage_type_id` |
| `cases` | `court_id` | `idx_cases_court_id` |
| `cases` | `parent_case_id` | `idx_cases_parent_case_id` |
| `embeddings` | `document_id` | `idx_embeddings_document_id` |
| `issue_chunks` | `issue_id` | `idx_issue_chunks_issue_id` |
| `issue_chunks` | `chunk_id` | `idx_issue_chunks_chunk_id` |
| `statute_citations` | `statute_id` | `idx_statute_citations_statute_id` |
| `arguments` | `issue_id` | `idx_arguments_issue_id` |

---

## Storage Savings Summary

| Change | Estimated Savings |
|--------|-------------------|
| ENUM conversion (10 columns × 10M rows) | ~1.9 GB |
| word_occurrence drop | ~5-10 GB |
| brief_word_occurrence drop | ~1-2 GB |
| **Total** | **~8-14 GB** |

---

## Migration Execution Plan

### Phase 1: Pre-Migration (No Downtime)
1. Create all ENUM types
2. Add new columns with ENUM types
3. Create backup tables for word_occurrence

### Phase 2: Data Migration (Low Impact)
```sql
-- Run during low-traffic period
UPDATE cases SET processing_status_new = processing_status::text::processing_status_type;
UPDATE briefs SET processing_status_new = processing_status::text::processing_status_type;
-- etc.
```

### Phase 3: Cutover (Brief Downtime)
1. Drop old citext columns
2. Rename new ENUM columns
3. Drop word_occurrence tables
4. Add missing FK indexes

### Phase 4: Verification
```sql
ANALYZE public.cases;
ANALYZE public.briefs;
-- Verify row counts and data integrity
```

---

## Application Code Changes Required

### Python/SQLAlchemy Updates

```python
# Before
class Case(Base):
    processing_status = Column(String)  # or CITEXT

# After
from sqlalchemy import Enum
from enum import Enum as PyEnum

class ProcessingStatus(PyEnum):
    PENDING = 'pending'
    TEXT_EXTRACTED = 'text_extracted'
    AI_PROCESSED = 'ai_processed'
    EMBEDDED = 'embedded'
    FULLY_PROCESSED = 'fully_processed'
    FAILED = 'failed'

class Case(Base):
    processing_status = Column(Enum(ProcessingStatus))
```

### Query Changes
No changes needed - ENUMs support string comparisons:
```sql
-- Still works!
SELECT * FROM cases WHERE processing_status = 'pending';
```

---

## Rollback Plan

If issues occur:

```sql
-- Restore word_occurrence from backup
CREATE TABLE word_occurrence AS SELECT * FROM word_occurrence_backup;

-- Revert ENUM columns (if needed)
ALTER TABLE cases ADD COLUMN processing_status_old citext;
UPDATE cases SET processing_status_old = processing_status::text;
ALTER TABLE cases DROP COLUMN processing_status;
ALTER TABLE cases RENAME COLUMN processing_status_old TO processing_status;
```

---

## Future Recommendations

1. **Implement table partitioning** for `embeddings` and `case_sentences` before hitting 10M rows
2. **Consider TimescaleDB** for time-series data like `chat_logs`
3. **Add BRIN indexes** for timestamp columns on large tables
4. **Implement pg_partman** for automatic partition management
5. **Set up pg_stat_statements** to identify slow queries after migration

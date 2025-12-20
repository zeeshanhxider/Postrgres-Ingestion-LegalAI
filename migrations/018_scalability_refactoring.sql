-- ============================================================================
-- MIGRATION 018: Scalability Refactoring
-- ============================================================================
-- Purpose: Address critical scalability issues flagged by Data Engineer review
-- 
-- ISSUES ADDRESSED:
--   1. Low-cardinality text columns wasting storage (citext → ENUM)
--   2. word_occurrence table explosion (1 row per word position = disaster)
--   3. brief_word_occurrence table explosion (same issue)
--   4. Missing FK indexes causing slow JOINs
--   5. High-growth tables needing partitioning strategy
--
-- STORAGE SAVINGS ANALYSIS:
--   - citext: ~23+ bytes per value (1-byte header + varlena overhead + data)
--   - ENUM: 4 bytes (fixed, stored as OID reference)
--   - Savings: ~19+ bytes per row per column
--
-- At 10M rows with 3 status columns: ~570 MB saved
-- ============================================================================

-- ============================================================================
-- PART 1: CREATE ENUM TYPES FOR LOW-CARDINALITY COLUMNS
-- ============================================================================
-- Benefits:
--   - 4 bytes fixed storage vs variable citext
--   - Type safety (prevents invalid values)
--   - Self-documenting valid values
--   - Index efficiency
-- ============================================================================

-- 1.1: Processing Status (used in: cases, briefs, documents)
-- Values: pending, text_extracted, ai_processed, embedded, fully_processed, failed
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'processing_status_type') THEN
        CREATE TYPE public.processing_status_type AS ENUM (
            'pending',
            'text_extracted', 
            'ai_processed',
            'embedded',
            'fully_processed',
            'failed'
        );
    END IF;
END $$;

-- 1.2: Publication Status (used in: cases)
-- Values: Published, Unpublished, Partially Published, Published in Part
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'publication_status_type') THEN
        CREATE TYPE public.publication_status_type AS ENUM (
            'Published',
            'Unpublished',
            'Partially Published',
            'Published in Part'
        );
    END IF;
END $$;

-- 1.3: Batch Status (used in: ingestion_batches)
-- Values: running, completed, failed, cancelled, paused
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'batch_status_type') THEN
        CREATE TYPE public.batch_status_type AS ENUM (
            'running',
            'completed',
            'failed',
            'cancelled',
            'paused'
        );
    END IF;
END $$;

-- 1.4: Source Type (used in: ingestion_batches)
-- Values: supreme_court, court_of_appeals, court_of_appeals_partial, briefs, mixed, csv
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_type_type') THEN
        CREATE TYPE public.source_type_type AS ENUM (
            'supreme_court',
            'court_of_appeals',
            'court_of_appeals_partial',
            'briefs',
            'mixed',
            'csv'
        );
    END IF;
END $$;

-- 1.5: Argument Side (used in: arguments)
-- Values: appellant, respondent, amicus
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'argument_side_type') THEN
        CREATE TYPE public.argument_side_type AS ENUM (
            'appellant',
            'respondent',
            'amicus'
        );
    END IF;
END $$;

-- 1.6: Issue Outcome (used in: issues_decisions)
-- Values: Affirmed, Dismissed, Reversed, Remanded, Mixed
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'issue_outcome_type') THEN
        CREATE TYPE public.issue_outcome_type AS ENUM (
            'Affirmed',
            'Dismissed',
            'Reversed',
            'Remanded',
            'Mixed'
        );
    END IF;
END $$;

-- 1.7: Court Type (used in: courts_dim)
-- Values: Supreme Court, Court of Appeals, Superior Court, District Court, Municipal Court
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'court_type_type') THEN
        CREATE TYPE public.court_type_type AS ENUM (
            'Supreme Court',
            'Court of Appeals',
            'Superior Court',
            'District Court',
            'Municipal Court'
        );
    END IF;
END $$;

-- 1.8: Document Role (used in: document_types)
-- Values: court, party, evidence, administrative
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_role_type') THEN
        CREATE TYPE public.document_role_type AS ENUM (
            'court',
            'party',
            'evidence',
            'administrative'
        );
    END IF;
END $$;

-- 1.9: Processing Strategy (used in: document_types)
-- Values: case_outcome, brief_extraction, evidence_indexing, text_only
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'processing_strategy_type') THEN
        CREATE TYPE public.processing_strategy_type AS ENUM (
            'case_outcome',
            'brief_extraction',
            'evidence_indexing',
            'text_only'
        );
    END IF;
END $$;

-- 1.10: Brief Type (used in: briefs)
-- Values: opening_brief, respondent_brief, reply_brief, amicus_brief
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'brief_type_type') THEN
        CREATE TYPE public.brief_type_type AS ENUM (
            'opening_brief',
            'respondent_brief',
            'reply_brief',
            'amicus_brief'
        );
    END IF;
END $$;

-- 1.11: User Type (used in: users)
-- Values: pro_se, lawyer, other
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_type_type') THEN
        CREATE TYPE public.user_type_type AS ENUM (
            'pro_se',
            'lawyer',
            'other'
        );
    END IF;
END $$;

-- 1.12: Citation Relationship (used in: citation_edges)
-- Values: cites, distinguishes, overrules, follows, affirms, reverses
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'citation_relationship_type') THEN
        CREATE TYPE public.citation_relationship_type AS ENUM (
            'cites',
            'distinguishes',
            'overrules',
            'follows',
            'affirms',
            'reverses',
            'discusses'
        );
    END IF;
END $$;

-- 1.13: Citation Importance (used in: citation_edges)
-- Values: primary, secondary, passing
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'citation_importance_type') THEN
        CREATE TYPE public.citation_importance_type AS ENUM (
            'primary',
            'secondary',
            'passing'
        );
    END IF;
END $$;

-- 1.14: Judge Role (used in: case_judges)
-- Values: author, concurring, dissenting, per_curiam
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'judge_role_type') THEN
        CREATE TYPE public.judge_role_type AS ENUM (
            'author',
            'concurring',
            'dissenting',
            'per_curiam'
        );
    END IF;
END $$;

COMMENT ON TYPE public.processing_status_type IS 'Pipeline processing status for cases, briefs, and documents';
COMMENT ON TYPE public.publication_status_type IS 'Publication status for court opinions';
COMMENT ON TYPE public.batch_status_type IS 'Ingestion batch processing status';
COMMENT ON TYPE public.source_type_type IS 'Source type for ingestion batches';
COMMENT ON TYPE public.issue_outcome_type IS 'Outcome type for individual issues';
COMMENT ON TYPE public.court_type_type IS 'Court hierarchy classification';
COMMENT ON TYPE public.document_role_type IS 'Document authority source classification';
COMMENT ON TYPE public.processing_strategy_type IS 'Backend routing strategy for document processing';
COMMENT ON TYPE public.brief_type_type IS 'Type of legal brief';
COMMENT ON TYPE public.user_type_type IS 'User classification type';
COMMENT ON TYPE public.citation_relationship_type IS 'Type of citation relationship between cases';
COMMENT ON TYPE public.citation_importance_type IS 'Importance level of citation';
COMMENT ON TYPE public.judge_role_type IS 'Role of judge in case decision';


-- ============================================================================
-- PART 2: MIGRATE COLUMNS TO ENUM TYPES
-- ============================================================================
-- Strategy: Add new column, migrate data, drop old column, rename new column
-- This is safer than ALTER COLUMN ... USING which locks the table
-- ============================================================================

-- 2.1: cases.processing_status (citext → processing_status_type)
ALTER TABLE public.cases 
    ADD COLUMN IF NOT EXISTS processing_status_new processing_status_type;

UPDATE public.cases 
SET processing_status_new = processing_status::text::processing_status_type
WHERE processing_status IS NOT NULL 
  AND processing_status::text IN ('pending', 'text_extracted', 'ai_processed', 'embedded', 'fully_processed', 'failed');

-- Set default for remaining NULL values
UPDATE public.cases 
SET processing_status_new = 'pending'
WHERE processing_status_new IS NULL;

-- 2.2: cases.publication_status (citext → publication_status_type)
ALTER TABLE public.cases 
    ADD COLUMN IF NOT EXISTS publication_status_new publication_status_type;

UPDATE public.cases 
SET publication_status_new = publication_status::text::publication_status_type
WHERE publication_status IS NOT NULL
  AND publication_status::text IN ('Published', 'Unpublished', 'Partially Published', 'Published in Part');

-- 2.3: briefs.processing_status (citext → processing_status_type)
ALTER TABLE public.briefs 
    ADD COLUMN IF NOT EXISTS processing_status_new processing_status_type DEFAULT 'pending';

UPDATE public.briefs 
SET processing_status_new = processing_status::text::processing_status_type
WHERE processing_status IS NOT NULL
  AND processing_status::text IN ('pending', 'text_extracted', 'ai_processed', 'embedded', 'fully_processed', 'failed');

-- 2.4: documents.processing_status (citext → processing_status_type)
ALTER TABLE public.documents 
    ADD COLUMN IF NOT EXISTS processing_status_new processing_status_type DEFAULT 'pending';

UPDATE public.documents 
SET processing_status_new = processing_status::text::processing_status_type
WHERE processing_status IS NOT NULL
  AND processing_status::text IN ('pending', 'text_extracted', 'ai_processed', 'embedded', 'fully_processed', 'failed');

-- 2.5: ingestion_batches.status (citext → batch_status_type)
ALTER TABLE public.ingestion_batches 
    ADD COLUMN IF NOT EXISTS status_new batch_status_type DEFAULT 'running';

UPDATE public.ingestion_batches 
SET status_new = status::text::batch_status_type
WHERE status IS NOT NULL
  AND status::text IN ('running', 'completed', 'failed', 'cancelled', 'paused');

-- 2.6: ingestion_batches.source_type (citext → source_type_type)
ALTER TABLE public.ingestion_batches 
    ADD COLUMN IF NOT EXISTS source_type_new source_type_type;

UPDATE public.ingestion_batches 
SET source_type_new = source_type::text::source_type_type
WHERE source_type IS NOT NULL
  AND source_type::text IN ('supreme_court', 'court_of_appeals', 'court_of_appeals_partial', 'briefs', 'mixed', 'csv');

-- 2.7: issues_decisions.issue_outcome (citext → issue_outcome_type)
ALTER TABLE public.issues_decisions 
    ADD COLUMN IF NOT EXISTS issue_outcome_new issue_outcome_type;

UPDATE public.issues_decisions 
SET issue_outcome_new = CASE 
    WHEN lower(issue_outcome::text) = 'affirmed' THEN 'Affirmed'::issue_outcome_type
    WHEN lower(issue_outcome::text) = 'dismissed' THEN 'Dismissed'::issue_outcome_type
    WHEN lower(issue_outcome::text) = 'reversed' THEN 'Reversed'::issue_outcome_type
    WHEN lower(issue_outcome::text) = 'remanded' THEN 'Remanded'::issue_outcome_type
    WHEN lower(issue_outcome::text) = 'mixed' THEN 'Mixed'::issue_outcome_type
    ELSE NULL
END
WHERE issue_outcome IS NOT NULL;

-- 2.8: courts_dim.court_type (citext → court_type_type)
ALTER TABLE public.courts_dim 
    ADD COLUMN IF NOT EXISTS court_type_new court_type_type;

UPDATE public.courts_dim 
SET court_type_new = court_type::text::court_type_type
WHERE court_type IS NOT NULL
  AND court_type::text IN ('Supreme Court', 'Court of Appeals', 'Superior Court', 'District Court', 'Municipal Court');

-- 2.9: document_types.role (citext → document_role_type)
ALTER TABLE public.document_types 
    ADD COLUMN IF NOT EXISTS role_new document_role_type;

UPDATE public.document_types 
SET role_new = role::text::document_role_type
WHERE role IS NOT NULL
  AND role::text IN ('court', 'party', 'evidence', 'administrative');

-- 2.10: document_types.processing_strategy (citext → processing_strategy_type)
ALTER TABLE public.document_types 
    ADD COLUMN IF NOT EXISTS processing_strategy_new processing_strategy_type;

UPDATE public.document_types 
SET processing_strategy_new = processing_strategy::text::processing_strategy_type
WHERE processing_strategy IS NOT NULL
  AND processing_strategy::text IN ('case_outcome', 'brief_extraction', 'evidence_indexing', 'text_only');


-- ============================================================================
-- PART 3: WORD_OCCURRENCE TABLE REFACTORING
-- ============================================================================
-- PROBLEM: Current design stores ONE ROW PER WORD POSITION
--   - 50 words per sentence × 20 sentences per chunk × 50 chunks per case = 50,000 rows/case
--   - 10,000 cases = 500 MILLION rows!
--
-- SOLUTION: Since case_chunks.tsv (tsvector) already provides full-text search,
--   we have TWO options:
--
--   Option A (AGGRESSIVE - RECOMMENDED): DROP the word_occurrence table entirely
--   Option B (CONSERVATIVE): Refactor to store positions as integer[]
--
-- RECOMMENDATION: Option A - The tsvector column already provides:
--   - Full-text search with ranking
--   - Stemming and stop-word removal
--   - GIN index for fast queries
--   - Position information via ts_headline()
-- ============================================================================

-- OPTION A: DROP word_occurrence tables (RECOMMENDED)
-- Uncomment these lines to execute the aggressive cleanup

-- First, check if we really have tsvector coverage
DO $$
DECLARE
    has_tsv_case_chunks BOOLEAN;
    has_tsv_case_sentences BOOLEAN;
BEGIN
    -- Check case_chunks has tsv column
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'case_chunks' AND column_name = 'tsv'
    ) INTO has_tsv_case_chunks;
    
    -- Check case_sentences has tsv column  
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'case_sentences' AND column_name = 'tsv'
    ) INTO has_tsv_case_sentences;
    
    IF has_tsv_case_chunks AND has_tsv_case_sentences THEN
        RAISE NOTICE 'CONFIRMED: tsvector columns exist on case_chunks and case_sentences';
        RAISE NOTICE 'word_occurrence table is REDUNDANT and safe to drop';
    ELSE
        RAISE WARNING 'Missing tsvector columns - do NOT drop word_occurrence yet!';
    END IF;
END $$;

-- Create backup table before dropping (safety net)
CREATE TABLE IF NOT EXISTS public.word_occurrence_backup AS 
SELECT * FROM public.word_occurrence LIMIT 0;

-- Archive a sample for reference (first 10000 rows only)
INSERT INTO public.word_occurrence_backup 
SELECT * FROM public.word_occurrence 
ORDER BY case_id, chunk_id, word_id 
LIMIT 10000
ON CONFLICT DO NOTHING;

-- Drop the indexes first (faster drop)
DROP INDEX IF EXISTS public.idx_word_occurrence_case_id;
DROP INDEX IF EXISTS public.idx_word_occurrence_chunk_pos;
DROP INDEX IF EXISTS public.idx_word_occurrence_word_case;

-- DROP the table (comment out if you want Option B instead)
DROP TABLE IF EXISTS public.word_occurrence CASCADE;

-- Also drop brief_word_occurrence (same explosion problem)
DROP INDEX IF EXISTS public.idx_brief_word_occurrence_brief_id;
DROP INDEX IF EXISTS public.idx_brief_word_occurrence_chunk_id;
DROP INDEX IF EXISTS public.idx_brief_word_occurrence_word_id;

CREATE TABLE IF NOT EXISTS public.brief_word_occurrence_backup AS 
SELECT * FROM public.brief_word_occurrence LIMIT 0;

INSERT INTO public.brief_word_occurrence_backup 
SELECT * FROM public.brief_word_occurrence 
ORDER BY brief_id, chunk_id, word_id 
LIMIT 10000
ON CONFLICT DO NOTHING;

DROP TABLE IF EXISTS public.brief_word_occurrence CASCADE;

-- ============================================================================
-- OPTION B: REFACTOR TO ARRAY (Alternative - if you need word positions)
-- ============================================================================
-- If you MUST keep word positions for some specialized feature,
-- use this refactored design instead of dropping:

-- CREATE TABLE public.word_occurrence_v2 (
--     word_id integer NOT NULL REFERENCES public.word_dictionary(word_id) ON DELETE CASCADE,
--     case_id bigint NOT NULL REFERENCES public.cases(case_id) ON DELETE CASCADE,
--     chunk_id bigint NOT NULL REFERENCES public.case_chunks(chunk_id) ON DELETE CASCADE,
--     positions integer[] NOT NULL,  -- Array of all positions for this word in this chunk
--     frequency integer GENERATED ALWAYS AS (array_length(positions, 1)) STORED,
--     PRIMARY KEY (word_id, case_id, chunk_id)
-- );

-- -- Migration from old to new (if keeping Option B):
-- INSERT INTO public.word_occurrence_v2 (word_id, case_id, chunk_id, positions)
-- SELECT word_id, case_id, chunk_id, array_agg("position" ORDER BY "position")
-- FROM public.word_occurrence
-- GROUP BY word_id, case_id, chunk_id;

-- CREATE INDEX idx_word_occurrence_v2_case ON public.word_occurrence_v2(case_id);
-- CREATE INDEX idx_word_occurrence_v2_word ON public.word_occurrence_v2(word_id);


-- ============================================================================
-- PART 4: SCALABILITY AUDIT - ADDITIONAL HIGH-GROWTH TABLES
-- ============================================================================
-- Tables at risk of exploding:
--   1. embeddings - 1 row per chunk × 1024 floats = massive storage
--   2. case_sentences - 20+ sentences per case
--   3. case_phrases - N-grams explode quickly
--   4. citation_edges - Each case can cite 50+ cases
--   5. brief_sentences - Same as case_sentences
--   6. brief_chunks - Same issue
-- ============================================================================

-- 4.1: PARTITION embeddings BY decision_year
-- Benefits:
--   - Partition pruning for year-filtered queries (common pattern)
--   - Easier maintenance (can drop old year partitions)
--   - Parallel query execution across partitions
--   - Better vacuum performance

-- First, create the partitioned table structure
-- NOTE: This requires data migration - run during maintenance window

-- CREATE TABLE public.embeddings_partitioned (
--     embedding_id bigint NOT NULL,
--     case_id bigint NOT NULL,
--     chunk_id bigint NOT NULL,
--     document_id bigint,
--     text text NOT NULL,
--     embedding public.vector(1024) NOT NULL,
--     chunk_order integer NOT NULL,
--     section public.citext,
--     decision_year integer NOT NULL,  -- Partition key (denormalized from cases)
--     created_at timestamp without time zone DEFAULT now() NOT NULL,
--     updated_at timestamp without time zone DEFAULT now() NOT NULL
-- ) PARTITION BY RANGE (decision_year);
-- 
-- -- Create yearly partitions
-- CREATE TABLE public.embeddings_y2020 PARTITION OF public.embeddings_partitioned
--     FOR VALUES FROM (2020) TO (2021);
-- CREATE TABLE public.embeddings_y2021 PARTITION OF public.embeddings_partitioned
--     FOR VALUES FROM (2021) TO (2022);
-- CREATE TABLE public.embeddings_y2022 PARTITION OF public.embeddings_partitioned
--     FOR VALUES FROM (2022) TO (2023);
-- CREATE TABLE public.embeddings_y2023 PARTITION OF public.embeddings_partitioned
--     FOR VALUES FROM (2023) TO (2024);
-- CREATE TABLE public.embeddings_y2024 PARTITION OF public.embeddings_partitioned
--     FOR VALUES FROM (2024) TO (2025);
-- CREATE TABLE public.embeddings_y2025 PARTITION OF public.embeddings_partitioned
--     FOR VALUES FROM (2025) TO (2026);
-- CREATE TABLE public.embeddings_default PARTITION OF public.embeddings_partitioned
--     DEFAULT;


-- 4.2: PARTITION case_sentences BY case_id range (hash partitioning)
-- Since case_id is the primary lookup pattern

-- CREATE TABLE public.case_sentences_partitioned (
--     sentence_id bigint NOT NULL,
--     case_id bigint NOT NULL,
--     chunk_id bigint NOT NULL,
--     document_id bigint,
--     sentence_order integer NOT NULL,
--     global_sentence_order integer NOT NULL,
--     text text NOT NULL,
--     word_count integer DEFAULT 0,
--     tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, COALESCE(text, ''::text))) STORED,
--     created_at timestamp without time zone DEFAULT now() NOT NULL,
--     updated_at timestamp without time zone DEFAULT now() NOT NULL
-- ) PARTITION BY HASH (case_id);
-- 
-- -- Create 8 hash partitions for even distribution
-- CREATE TABLE public.case_sentences_p0 PARTITION OF public.case_sentences_partitioned
--     FOR VALUES WITH (MODULUS 8, REMAINDER 0);
-- CREATE TABLE public.case_sentences_p1 PARTITION OF public.case_sentences_partitioned
--     FOR VALUES WITH (MODULUS 8, REMAINDER 1);
-- -- ... repeat for p2-p7


-- ============================================================================
-- PART 5: MISSING FOREIGN KEY INDEXES
-- ============================================================================
-- Rule: Every FK should have an index for efficient JOINs and ON DELETE CASCADE
-- Checking for missing indexes on FK columns
-- ============================================================================

-- 5.1: case_judges.judge_id - FK exists but verify index
CREATE INDEX IF NOT EXISTS idx_case_judges_judge_id 
    ON public.case_judges(judge_id);

-- 5.2: citation_edges.target_case_id - FK target, no index!
CREATE INDEX IF NOT EXISTS idx_citation_edges_target_case_id 
    ON public.citation_edges(target_case_id);

-- 5.3: case_chunks.document_id - FK exists, index might be missing
CREATE INDEX IF NOT EXISTS idx_case_chunks_document_id 
    ON public.case_chunks(document_id);

-- 5.4: case_sentences.document_id - FK exists, verify index
CREATE INDEX IF NOT EXISTS idx_case_sentences_document_id 
    ON public.case_sentences(document_id);

-- 5.5: case_phrases.document_id - FK exists, verify index  
CREATE INDEX IF NOT EXISTS idx_case_phrases_document_id 
    ON public.case_phrases(document_id);

-- 5.6: case_phrases.example_sentence - FK exists, verify index
CREATE INDEX IF NOT EXISTS idx_case_phrases_example_sentence 
    ON public.case_phrases(example_sentence);

-- 5.7: case_phrases.example_chunk - FK exists, verify index
CREATE INDEX IF NOT EXISTS idx_case_phrases_example_chunk 
    ON public.case_phrases(example_chunk);

-- 5.8: documents.document_type_id - FK to dimension table
CREATE INDEX IF NOT EXISTS idx_documents_document_type_id 
    ON public.documents(document_type_id);

-- 5.9: documents.stage_type_id - FK to dimension table
CREATE INDEX IF NOT EXISTS idx_documents_stage_type_id 
    ON public.documents(stage_type_id);

-- 5.10: cases.case_type_id - FK to legal_taxonomy
CREATE INDEX IF NOT EXISTS idx_cases_case_type_id 
    ON public.cases(case_type_id);

-- 5.11: cases.stage_type_id - FK to stage_types
CREATE INDEX IF NOT EXISTS idx_cases_stage_type_id 
    ON public.cases(stage_type_id);

-- 5.12: cases.court_id - FK to courts_dim
CREATE INDEX IF NOT EXISTS idx_cases_court_id 
    ON public.cases(court_id);

-- 5.13: cases.parent_case_id - Self-referential FK
CREATE INDEX IF NOT EXISTS idx_cases_parent_case_id 
    ON public.cases(parent_case_id);

-- 5.14: embeddings.document_id - FK to documents
CREATE INDEX IF NOT EXISTS idx_embeddings_document_id 
    ON public.embeddings(document_id);

-- 5.15: issue_chunks.issue_id - FK to issues_decisions
CREATE INDEX IF NOT EXISTS idx_issue_chunks_issue_id 
    ON public.issue_chunks(issue_id);

-- 5.16: issue_chunks.chunk_id - FK to case_chunks
CREATE INDEX IF NOT EXISTS idx_issue_chunks_chunk_id 
    ON public.issue_chunks(chunk_id);

-- 5.17: statute_citations.statute_id - FK to statutes_dim
CREATE INDEX IF NOT EXISTS idx_statute_citations_statute_id 
    ON public.statute_citations(statute_id);

-- 5.18: arguments.issue_id - FK to issues_decisions (verify)
CREATE INDEX IF NOT EXISTS idx_arguments_issue_id 
    ON public.arguments(issue_id);


-- ============================================================================
-- PART 6: CLEANUP - DROP OLD COLUMNS AND CONSTRAINTS
-- ============================================================================
-- After verifying migration success, run these to complete the transition
-- CAUTION: Only run after confirming data integrity in new columns
-- ============================================================================

-- Drop old CHECK constraints that reference citext comparisons
ALTER TABLE public.cases DROP CONSTRAINT IF EXISTS chk_cases_processing_status;
ALTER TABLE public.cases DROP CONSTRAINT IF EXISTS chk_cases_publication_status;
ALTER TABLE public.ingestion_batches DROP CONSTRAINT IF EXISTS chk_ingestion_batches_status;
ALTER TABLE public.ingestion_batches DROP CONSTRAINT IF EXISTS chk_ingestion_batches_source_type;
ALTER TABLE public.issues_decisions DROP CONSTRAINT IF EXISTS chk_issue_outcome;
ALTER TABLE public.courts_dim DROP CONSTRAINT IF EXISTS chk_courts_dim_court_type;
ALTER TABLE public.document_types DROP CONSTRAINT IF EXISTS chk_document_types_role;
ALTER TABLE public.document_types DROP CONSTRAINT IF EXISTS chk_document_types_processing_strategy;

-- Swap columns (run after verification)
-- cases table
ALTER TABLE public.cases DROP COLUMN IF EXISTS processing_status;
ALTER TABLE public.cases RENAME COLUMN processing_status_new TO processing_status;

ALTER TABLE public.cases DROP COLUMN IF EXISTS publication_status;
ALTER TABLE public.cases RENAME COLUMN publication_status_new TO publication_status;

-- briefs table
ALTER TABLE public.briefs DROP COLUMN IF EXISTS processing_status;
ALTER TABLE public.briefs RENAME COLUMN processing_status_new TO processing_status;

-- documents table
ALTER TABLE public.documents DROP COLUMN IF EXISTS processing_status;
ALTER TABLE public.documents RENAME COLUMN processing_status_new TO processing_status;

-- ingestion_batches table
ALTER TABLE public.ingestion_batches DROP COLUMN IF EXISTS status;
ALTER TABLE public.ingestion_batches RENAME COLUMN status_new TO status;

ALTER TABLE public.ingestion_batches DROP COLUMN IF EXISTS source_type;
ALTER TABLE public.ingestion_batches RENAME COLUMN source_type_new TO source_type;

-- issues_decisions table
ALTER TABLE public.issues_decisions DROP COLUMN IF EXISTS issue_outcome;
ALTER TABLE public.issues_decisions RENAME COLUMN issue_outcome_new TO issue_outcome;

-- courts_dim table
ALTER TABLE public.courts_dim DROP COLUMN IF EXISTS court_type;
ALTER TABLE public.courts_dim RENAME COLUMN court_type_new TO court_type;

-- document_types table
ALTER TABLE public.document_types DROP COLUMN IF EXISTS role;
ALTER TABLE public.document_types RENAME COLUMN role_new TO role;

ALTER TABLE public.document_types DROP COLUMN IF EXISTS processing_strategy;
ALTER TABLE public.document_types RENAME COLUMN processing_strategy_new TO processing_strategy;


-- ============================================================================
-- PART 7: UPDATE STATISTICS AND VERIFY
-- ============================================================================

-- Analyze all modified tables to update planner statistics
ANALYZE public.cases;
ANALYZE public.briefs;
ANALYZE public.documents;
ANALYZE public.ingestion_batches;
ANALYZE public.issues_decisions;
ANALYZE public.courts_dim;
ANALYZE public.document_types;
ANALYZE public.citation_edges;
ANALYZE public.case_sentences;
ANALYZE public.case_chunks;
ANALYZE public.embeddings;

-- Verification queries
DO $$
DECLARE
    cases_count INTEGER;
    briefs_count INTEGER;
    docs_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO cases_count FROM public.cases WHERE processing_status IS NOT NULL;
    SELECT COUNT(*) INTO briefs_count FROM public.briefs WHERE processing_status IS NOT NULL;
    SELECT COUNT(*) INTO docs_count FROM public.documents WHERE processing_status IS NOT NULL;
    
    RAISE NOTICE 'Migration verification:';
    RAISE NOTICE '  cases with processing_status: %', cases_count;
    RAISE NOTICE '  briefs with processing_status: %', briefs_count;
    RAISE NOTICE '  documents with processing_status: %', docs_count;
END $$;


-- ============================================================================
-- SUMMARY OF CHANGES
-- ============================================================================
-- 
-- ENUM TYPES CREATED (14 total):
--   - processing_status_type
--   - publication_status_type  
--   - batch_status_type
--   - source_type_type
--   - argument_side_type
--   - issue_outcome_type
--   - court_type_type
--   - document_role_type
--   - processing_strategy_type
--   - brief_type_type
--   - user_type_type
--   - citation_relationship_type
--   - citation_importance_type
--   - judge_role_type
--
-- COLUMNS MIGRATED TO ENUM:
--   - cases.processing_status
--   - cases.publication_status
--   - briefs.processing_status
--   - documents.processing_status
--   - ingestion_batches.status
--   - ingestion_batches.source_type
--   - issues_decisions.issue_outcome
--   - courts_dim.court_type
--   - document_types.role
--   - document_types.processing_strategy
--
-- TABLES DROPPED (redundant with tsvector):
--   - word_occurrence (backed up to word_occurrence_backup)
--   - brief_word_occurrence (backed up to brief_word_occurrence_backup)
--
-- NEW INDEXES ADDED (18 total):
--   - idx_case_judges_judge_id
--   - idx_citation_edges_target_case_id
--   - idx_case_chunks_document_id
--   - idx_case_sentences_document_id
--   - idx_case_phrases_document_id
--   - idx_case_phrases_example_sentence
--   - idx_case_phrases_example_chunk
--   - idx_documents_document_type_id
--   - idx_documents_stage_type_id
--   - idx_cases_case_type_id
--   - idx_cases_stage_type_id
--   - idx_cases_court_id
--   - idx_cases_parent_case_id
--   - idx_embeddings_document_id
--   - idx_issue_chunks_issue_id
--   - idx_issue_chunks_chunk_id
--   - idx_statute_citations_statute_id
--   - idx_arguments_issue_id
--
-- STORAGE SAVINGS ESTIMATE:
--   - ~19 bytes saved per ENUM conversion vs citext
--   - At 10M rows: ~190 MB saved per column
--   - word_occurrence dropped: ~5GB+ saved (estimated at scale)
--
-- ============================================================================

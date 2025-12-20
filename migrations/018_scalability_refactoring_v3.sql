-- ============================================================================
-- MIGRATION 018: Scalability Refactoring (VALIDATED VERSION v3)
-- ============================================================================
-- Purpose: Address critical scalability issues flagged by Data Engineer review
-- ============================================================================

-- Start transaction for safety
BEGIN;

-- ============================================================================
-- PART 1: CREATE ENUM TYPES FOR LOW-CARDINALITY COLUMNS
-- ============================================================================

-- 1.1: Processing Status (used in: cases, briefs, documents)
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
        RAISE NOTICE 'Created processing_status_type ENUM';
    ELSE
        RAISE NOTICE 'processing_status_type already exists, skipping';
    END IF;
END $$;

-- 1.2: Publication Status (used in: cases)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'publication_status_type') THEN
        CREATE TYPE public.publication_status_type AS ENUM (
            'Published',
            'Unpublished',
            'Partially Published',
            'Published in Part'
        );
        RAISE NOTICE 'Created publication_status_type ENUM';
    END IF;
END $$;

-- 1.3: Batch Status (used in: ingestion_batches)
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
        RAISE NOTICE 'Created batch_status_type ENUM';
    END IF;
END $$;

-- 1.4: Source Type (used in: ingestion_batches)
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
        RAISE NOTICE 'Created source_type_type ENUM';
    END IF;
END $$;

-- 1.5: Issue Outcome (used in: issues_decisions)
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
        RAISE NOTICE 'Created issue_outcome_type ENUM';
    END IF;
END $$;

-- 1.6: Court Type (used in: courts_dim)
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
        RAISE NOTICE 'Created court_type_type ENUM';
    END IF;
END $$;

-- 1.7: Document Role (used in: document_types)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_role_type') THEN
        CREATE TYPE public.document_role_type AS ENUM (
            'court',
            'party',
            'evidence',
            'administrative'
        );
        RAISE NOTICE 'Created document_role_type ENUM';
    END IF;
END $$;

-- 1.8: Processing Strategy (used in: document_types)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'processing_strategy_type') THEN
        CREATE TYPE public.processing_strategy_type AS ENUM (
            'case_outcome',
            'brief_extraction',
            'evidence_indexing',
            'text_only'
        );
        RAISE NOTICE 'Created processing_strategy_type ENUM';
    END IF;
END $$;

-- Add comments to ENUMs
COMMENT ON TYPE public.processing_status_type IS 'Pipeline processing status for cases, briefs, and documents';
COMMENT ON TYPE public.publication_status_type IS 'Publication status for court opinions';
COMMENT ON TYPE public.batch_status_type IS 'Ingestion batch processing status';
COMMENT ON TYPE public.source_type_type IS 'Source type for ingestion batches';
COMMENT ON TYPE public.issue_outcome_type IS 'Outcome type for individual issues';
COMMENT ON TYPE public.court_type_type IS 'Court hierarchy classification';
COMMENT ON TYPE public.document_role_type IS 'Document authority source classification';
COMMENT ON TYPE public.processing_strategy_type IS 'Backend routing strategy for document processing';

DO $$ BEGIN RAISE NOTICE 'PART 1 COMPLETE: All ENUM types created'; END $$;


-- ============================================================================
-- PART 2: DROP VIEW THAT REFERENCES issue_outcome (will recreate later)
-- ============================================================================

DROP VIEW IF EXISTS public.v_qa_extraction;

DO $$ BEGIN RAISE NOTICE 'PART 2 COMPLETE: Dropped v_qa_extraction view'; END $$;


-- ============================================================================
-- PART 3: DROP OLD CHECK CONSTRAINTS
-- ============================================================================

ALTER TABLE public.cases DROP CONSTRAINT IF EXISTS chk_cases_processing_status;
ALTER TABLE public.cases DROP CONSTRAINT IF EXISTS chk_cases_publication_status;
ALTER TABLE public.ingestion_batches DROP CONSTRAINT IF EXISTS chk_ingestion_batches_status;
ALTER TABLE public.ingestion_batches DROP CONSTRAINT IF EXISTS chk_ingestion_batches_source_type;
ALTER TABLE public.issues_decisions DROP CONSTRAINT IF EXISTS chk_issue_outcome;
ALTER TABLE public.courts_dim DROP CONSTRAINT IF EXISTS chk_courts_dim_court_type;
ALTER TABLE public.document_types DROP CONSTRAINT IF EXISTS chk_document_types_role;
ALTER TABLE public.document_types DROP CONSTRAINT IF EXISTS chk_document_types_processing_strategy;

DO $$ BEGIN RAISE NOTICE 'PART 3 COMPLETE: Old CHECK constraints dropped'; END $$;


-- ============================================================================
-- PART 4: DROP OLD INDEXES ON STATUS COLUMNS
-- ============================================================================

DROP INDEX IF EXISTS public.idx_cases_processing_status;
DROP INDEX IF EXISTS public.idx_cases_publication_status;
DROP INDEX IF EXISTS public.idx_briefs_status;
DROP INDEX IF EXISTS public.idx_courts_dim_court_type;
DROP INDEX IF EXISTS public.idx_document_types_role;
DROP INDEX IF EXISTS public.idx_document_types_processing_strategy;

DO $$ BEGIN RAISE NOTICE 'PART 4 COMPLETE: Old indexes on status columns dropped'; END $$;


-- ============================================================================
-- PART 5: MIGRATE COLUMNS TO ENUM TYPES (ADD NEW COLUMNS)
-- ============================================================================

-- 5.1: cases.processing_status
ALTER TABLE public.cases 
    ADD COLUMN IF NOT EXISTS processing_status_new processing_status_type DEFAULT 'pending';

-- 5.2: cases.publication_status
ALTER TABLE public.cases 
    ADD COLUMN IF NOT EXISTS publication_status_new publication_status_type;

-- 5.3: briefs.processing_status
ALTER TABLE public.briefs 
    ADD COLUMN IF NOT EXISTS processing_status_new processing_status_type DEFAULT 'pending';

-- 5.4: documents.processing_status
ALTER TABLE public.documents 
    ADD COLUMN IF NOT EXISTS processing_status_new processing_status_type DEFAULT 'pending';

-- 5.5: ingestion_batches.status
ALTER TABLE public.ingestion_batches 
    ADD COLUMN IF NOT EXISTS status_new batch_status_type DEFAULT 'running';

-- 5.6: ingestion_batches.source_type
ALTER TABLE public.ingestion_batches 
    ADD COLUMN IF NOT EXISTS source_type_new source_type_type;

-- 5.7: issues_decisions.issue_outcome
ALTER TABLE public.issues_decisions 
    ADD COLUMN IF NOT EXISTS issue_outcome_new issue_outcome_type;

-- 5.8: courts_dim.court_type
ALTER TABLE public.courts_dim 
    ADD COLUMN IF NOT EXISTS court_type_new court_type_type;

-- 5.9: document_types.role
ALTER TABLE public.document_types 
    ADD COLUMN IF NOT EXISTS role_new document_role_type;

-- 5.10: document_types.processing_strategy
ALTER TABLE public.document_types 
    ADD COLUMN IF NOT EXISTS processing_strategy_new processing_strategy_type;

DO $$ BEGIN RAISE NOTICE 'PART 5 COMPLETE: New ENUM columns added'; END $$;


-- ============================================================================
-- PART 6: MIGRATE DATA (Handle case-sensitivity)
-- ============================================================================

-- 6.1: cases.processing_status
UPDATE public.cases 
SET processing_status_new = 
    CASE lower(processing_status::text)
        WHEN 'pending' THEN 'pending'::processing_status_type
        WHEN 'text_extracted' THEN 'text_extracted'::processing_status_type
        WHEN 'ai_processed' THEN 'ai_processed'::processing_status_type
        WHEN 'embedded' THEN 'embedded'::processing_status_type
        WHEN 'fully_processed' THEN 'fully_processed'::processing_status_type
        WHEN 'failed' THEN 'failed'::processing_status_type
        ELSE 'pending'::processing_status_type
    END
WHERE processing_status IS NOT NULL;

-- 6.2: cases.publication_status
UPDATE public.cases 
SET publication_status_new = 
    CASE 
        WHEN publication_status::text ILIKE 'Published' THEN 'Published'::publication_status_type
        WHEN publication_status::text ILIKE 'Unpublished' THEN 'Unpublished'::publication_status_type
        WHEN publication_status::text ILIKE 'Partially Published' THEN 'Partially Published'::publication_status_type
        WHEN publication_status::text ILIKE 'Published in Part' THEN 'Published in Part'::publication_status_type
        ELSE NULL
    END
WHERE publication_status IS NOT NULL;

-- 6.3: briefs.processing_status
UPDATE public.briefs 
SET processing_status_new = 
    CASE lower(processing_status::text)
        WHEN 'pending' THEN 'pending'::processing_status_type
        WHEN 'text_extracted' THEN 'text_extracted'::processing_status_type
        WHEN 'ai_processed' THEN 'ai_processed'::processing_status_type
        WHEN 'embedded' THEN 'embedded'::processing_status_type
        WHEN 'fully_processed' THEN 'fully_processed'::processing_status_type
        WHEN 'failed' THEN 'failed'::processing_status_type
        ELSE 'pending'::processing_status_type
    END
WHERE processing_status IS NOT NULL;

-- 6.4: documents.processing_status
UPDATE public.documents 
SET processing_status_new = 
    CASE lower(processing_status::text)
        WHEN 'pending' THEN 'pending'::processing_status_type
        WHEN 'text_extracted' THEN 'text_extracted'::processing_status_type
        WHEN 'ai_processed' THEN 'ai_processed'::processing_status_type
        WHEN 'embedded' THEN 'embedded'::processing_status_type
        WHEN 'fully_processed' THEN 'fully_processed'::processing_status_type
        WHEN 'failed' THEN 'failed'::processing_status_type
        ELSE 'pending'::processing_status_type
    END
WHERE processing_status IS NOT NULL;

-- 6.5: ingestion_batches.status
UPDATE public.ingestion_batches 
SET status_new = 
    CASE lower(status::text)
        WHEN 'running' THEN 'running'::batch_status_type
        WHEN 'completed' THEN 'completed'::batch_status_type
        WHEN 'failed' THEN 'failed'::batch_status_type
        WHEN 'cancelled' THEN 'cancelled'::batch_status_type
        WHEN 'paused' THEN 'paused'::batch_status_type
        ELSE 'running'::batch_status_type
    END
WHERE status IS NOT NULL;

-- 6.6: ingestion_batches.source_type
UPDATE public.ingestion_batches 
SET source_type_new = 
    CASE lower(source_type::text)
        WHEN 'supreme_court' THEN 'supreme_court'::source_type_type
        WHEN 'court_of_appeals' THEN 'court_of_appeals'::source_type_type
        WHEN 'court_of_appeals_partial' THEN 'court_of_appeals_partial'::source_type_type
        WHEN 'briefs' THEN 'briefs'::source_type_type
        WHEN 'mixed' THEN 'mixed'::source_type_type
        WHEN 'csv' THEN 'csv'::source_type_type
        ELSE NULL
    END
WHERE source_type IS NOT NULL;

-- 6.7: issues_decisions.issue_outcome
UPDATE public.issues_decisions 
SET issue_outcome_new = 
    CASE lower(issue_outcome::text)
        WHEN 'affirmed' THEN 'Affirmed'::issue_outcome_type
        WHEN 'dismissed' THEN 'Dismissed'::issue_outcome_type
        WHEN 'reversed' THEN 'Reversed'::issue_outcome_type
        WHEN 'remanded' THEN 'Remanded'::issue_outcome_type
        WHEN 'mixed' THEN 'Mixed'::issue_outcome_type
        ELSE NULL
    END
WHERE issue_outcome IS NOT NULL;

-- 6.8: courts_dim.court_type
UPDATE public.courts_dim 
SET court_type_new = 
    CASE 
        WHEN court_type::text = 'Supreme Court' THEN 'Supreme Court'::court_type_type
        WHEN court_type::text = 'Court of Appeals' THEN 'Court of Appeals'::court_type_type
        WHEN court_type::text = 'Superior Court' THEN 'Superior Court'::court_type_type
        WHEN court_type::text = 'District Court' THEN 'District Court'::court_type_type
        WHEN court_type::text = 'Municipal Court' THEN 'Municipal Court'::court_type_type
        ELSE NULL
    END
WHERE court_type IS NOT NULL;

-- 6.9: document_types.role
UPDATE public.document_types 
SET role_new = 
    CASE lower(role::text)
        WHEN 'court' THEN 'court'::document_role_type
        WHEN 'party' THEN 'party'::document_role_type
        WHEN 'evidence' THEN 'evidence'::document_role_type
        WHEN 'administrative' THEN 'administrative'::document_role_type
        ELSE NULL
    END
WHERE role IS NOT NULL;

-- 6.10: document_types.processing_strategy
UPDATE public.document_types 
SET processing_strategy_new = 
    CASE lower(processing_strategy::text)
        WHEN 'case_outcome' THEN 'case_outcome'::processing_strategy_type
        WHEN 'brief_extraction' THEN 'brief_extraction'::processing_strategy_type
        WHEN 'evidence_indexing' THEN 'evidence_indexing'::processing_strategy_type
        WHEN 'text_only' THEN 'text_only'::processing_strategy_type
        ELSE NULL
    END
WHERE processing_strategy IS NOT NULL;

DO $$ BEGIN RAISE NOTICE 'PART 6 COMPLETE: Data migrated to new columns'; END $$;


-- ============================================================================
-- PART 7: DROP OLD COLUMNS AND RENAME NEW ONES
-- ============================================================================

-- cases table
ALTER TABLE public.cases DROP COLUMN processing_status;
ALTER TABLE public.cases RENAME COLUMN processing_status_new TO processing_status;

ALTER TABLE public.cases DROP COLUMN publication_status;
ALTER TABLE public.cases RENAME COLUMN publication_status_new TO publication_status;

-- briefs table
ALTER TABLE public.briefs DROP COLUMN processing_status;
ALTER TABLE public.briefs RENAME COLUMN processing_status_new TO processing_status;

-- documents table
ALTER TABLE public.documents DROP COLUMN processing_status;
ALTER TABLE public.documents RENAME COLUMN processing_status_new TO processing_status;

-- ingestion_batches table
ALTER TABLE public.ingestion_batches DROP COLUMN status;
ALTER TABLE public.ingestion_batches RENAME COLUMN status_new TO status;

ALTER TABLE public.ingestion_batches DROP COLUMN source_type;
ALTER TABLE public.ingestion_batches RENAME COLUMN source_type_new TO source_type;

-- issues_decisions table
ALTER TABLE public.issues_decisions DROP COLUMN issue_outcome;
ALTER TABLE public.issues_decisions RENAME COLUMN issue_outcome_new TO issue_outcome;

-- courts_dim table
ALTER TABLE public.courts_dim DROP COLUMN court_type;
ALTER TABLE public.courts_dim RENAME COLUMN court_type_new TO court_type;

-- document_types table
ALTER TABLE public.document_types DROP COLUMN role;
ALTER TABLE public.document_types RENAME COLUMN role_new TO role;

ALTER TABLE public.document_types DROP COLUMN processing_strategy;
ALTER TABLE public.document_types RENAME COLUMN processing_strategy_new TO processing_strategy;

DO $$ BEGIN RAISE NOTICE 'PART 7 COMPLETE: Old columns dropped, new columns renamed'; END $$;


-- ============================================================================
-- PART 8: RECREATE INDEXES ON STATUS COLUMNS (now ENUM type)
-- ============================================================================

CREATE INDEX idx_cases_processing_status ON public.cases(processing_status);
CREATE INDEX idx_cases_publication_status ON public.cases(publication_status);
CREATE INDEX idx_briefs_status ON public.briefs(processing_status);
CREATE INDEX idx_courts_dim_court_type ON public.courts_dim(court_type);
CREATE INDEX idx_document_types_role ON public.document_types(role);
CREATE INDEX idx_document_types_processing_strategy ON public.document_types(processing_strategy);

DO $$ BEGIN RAISE NOTICE 'PART 8 COMPLETE: Indexes recreated on ENUM columns'; END $$;


-- ============================================================================
-- PART 9: RECREATE v_qa_extraction VIEW
-- ============================================================================

CREATE OR REPLACE VIEW public.v_qa_extraction AS
SELECT 
    case_id,
    docket_number,
    title AS case_title,
    court_level,
    court,
    county,
    appeal_outcome AS overall_outcome,
    issue_count,
    decision_year,
    decision_month,
    (SELECT json_agg(json_build_object(
        'issue_id', id.issue_id, 
        'summary', LEFT(id.issue_summary, 200), 
        'outcome', id.issue_outcome::text,
        'winner', id.winner_legal_role, 
        'taxonomy_id', id.taxonomy_id
    ))
    FROM public.issues_decisions id
    WHERE id.case_id = c.case_id) AS issues,
    (SELECT COUNT(*) FROM public.parties p WHERE p.case_id = c.case_id) AS party_count,
    (SELECT COUNT(*) FROM public.case_judges cj WHERE cj.case_id = c.case_id) AS judge_count,
    (SELECT COUNT(DISTINCT ir.rcw_id) 
     FROM public.issue_rcw ir
     JOIN public.issues_decisions id ON ir.issue_id = id.issue_id
     WHERE id.case_id = c.case_id) AS rcw_count,
    source_file,
    extraction_timestamp
FROM public.cases c
ORDER BY case_id DESC;

COMMENT ON VIEW public.v_qa_extraction IS 'Quality Assurance view for extraction verification against Excel standard';

DO $$ BEGIN RAISE NOTICE 'PART 9 COMPLETE: v_qa_extraction view recreated'; END $$;


-- ============================================================================
-- PART 10: DROP WORD_OCCURRENCE TABLES (REDUNDANT WITH tsvector)
-- ============================================================================

-- Drop indexes first for faster table drop
DROP INDEX IF EXISTS public.idx_word_occurrence_case_id;
DROP INDEX IF EXISTS public.idx_word_occurrence_chunk_pos;
DROP INDEX IF EXISTS public.idx_word_occurrence_word_case;

-- Drop word_occurrence (CASCADE removes FK constraints)
DROP TABLE IF EXISTS public.word_occurrence CASCADE;

-- Drop brief_word_occurrence indexes
DROP INDEX IF EXISTS public.idx_brief_word_occurrence_brief_id;
DROP INDEX IF EXISTS public.idx_brief_word_occurrence_chunk_id;
DROP INDEX IF EXISTS public.idx_brief_word_occurrence_word_id;

-- Drop brief_word_occurrence
DROP TABLE IF EXISTS public.brief_word_occurrence CASCADE;

DO $$ BEGIN RAISE NOTICE 'PART 10 COMPLETE: Redundant word_occurrence tables dropped'; END $$;


-- ============================================================================
-- PART 11: ADD MISSING FOREIGN KEY INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_case_judges_judge_id 
    ON public.case_judges(judge_id);

CREATE INDEX IF NOT EXISTS idx_citation_edges_target_case_id 
    ON public.citation_edges(target_case_id);

CREATE INDEX IF NOT EXISTS idx_case_chunks_document_id 
    ON public.case_chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_case_sentences_document_id 
    ON public.case_sentences(document_id);

CREATE INDEX IF NOT EXISTS idx_case_phrases_document_id 
    ON public.case_phrases(document_id);

CREATE INDEX IF NOT EXISTS idx_case_phrases_example_sentence 
    ON public.case_phrases(example_sentence);

CREATE INDEX IF NOT EXISTS idx_case_phrases_example_chunk 
    ON public.case_phrases(example_chunk);

CREATE INDEX IF NOT EXISTS idx_documents_document_type_id 
    ON public.documents(document_type_id);

CREATE INDEX IF NOT EXISTS idx_documents_stage_type_id 
    ON public.documents(stage_type_id);

CREATE INDEX IF NOT EXISTS idx_cases_case_type_id 
    ON public.cases(case_type_id);

CREATE INDEX IF NOT EXISTS idx_cases_stage_type_id 
    ON public.cases(stage_type_id);

CREATE INDEX IF NOT EXISTS idx_cases_court_id 
    ON public.cases(court_id);

CREATE INDEX IF NOT EXISTS idx_cases_parent_case_id 
    ON public.cases(parent_case_id);

CREATE INDEX IF NOT EXISTS idx_embeddings_document_id 
    ON public.embeddings(document_id);

CREATE INDEX IF NOT EXISTS idx_issue_chunks_issue_id 
    ON public.issue_chunks(issue_id);

CREATE INDEX IF NOT EXISTS idx_issue_chunks_chunk_id 
    ON public.issue_chunks(chunk_id);

CREATE INDEX IF NOT EXISTS idx_statute_citations_statute_id 
    ON public.statute_citations(statute_id);

CREATE INDEX IF NOT EXISTS idx_arguments_issue_id 
    ON public.arguments(issue_id);

DO $$ BEGIN RAISE NOTICE 'PART 11 COMPLETE: Missing FK indexes added'; END $$;


-- ============================================================================
-- PART 12: UPDATE STATISTICS
-- ============================================================================

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

DO $$ BEGIN RAISE NOTICE 'PART 12 COMPLETE: Table statistics updated'; END $$;


-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    enum_count INTEGER;
    table_count INTEGER;
    index_count INTEGER;
BEGIN
    -- Count ENUMs created
    SELECT COUNT(*) INTO enum_count 
    FROM pg_type 
    WHERE typname IN ('processing_status_type', 'publication_status_type', 
                      'batch_status_type', 'source_type_type', 'issue_outcome_type',
                      'court_type_type', 'document_role_type', 'processing_strategy_type');
    
    -- Check word_occurrence is gone
    SELECT COUNT(*) INTO table_count 
    FROM pg_tables 
    WHERE schemaname = 'public' 
    AND tablename IN ('word_occurrence', 'brief_word_occurrence');
    
    -- Count new indexes
    SELECT COUNT(*) INTO index_count 
    FROM pg_indexes 
    WHERE schemaname = 'public' 
    AND indexname IN ('idx_case_judges_judge_id', 'idx_citation_edges_target_case_id',
                      'idx_case_chunks_document_id', 'idx_cases_case_type_id');
    
    RAISE NOTICE '============================================';
    RAISE NOTICE 'MIGRATION VERIFICATION RESULTS:';
    RAISE NOTICE '  ENUM types created: % (expected: 8)', enum_count;
    RAISE NOTICE '  word_occurrence tables remaining: % (expected: 0)', table_count;
    RAISE NOTICE '  New FK indexes (sample): % (expected: 4)', index_count;
    RAISE NOTICE '============================================';
    
    IF enum_count = 8 AND table_count = 0 THEN
        RAISE NOTICE 'SUCCESS: MIGRATION COMPLETED SUCCESSFULLY!';
    ELSE
        RAISE WARNING 'WARNING: MIGRATION MAY HAVE ISSUES - CHECK RESULTS';
    END IF;
END $$;


-- Commit the transaction
COMMIT;

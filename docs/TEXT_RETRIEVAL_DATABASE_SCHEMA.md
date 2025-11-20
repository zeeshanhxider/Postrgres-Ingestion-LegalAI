# Database Schema: Text Retrieval Layer (Non-AI Extracted Data)

## 📋 Overview

This document describes the **non-AI text retrieval layer** of the legal case database. This layer enables precise word-level and phrase-level searching with full contextual information.

**Purpose:** Find exact locations of words/phrases within legal cases and retrieve surrounding text chunks for context.

**Use Case:** When the AI needs to:
- Find where specific terms appear in cases
- Get exact quotes with citations
- Retrieve surrounding context (3-6 chunks)
- Support evidence-based answers with precise locations

---

## 🏗️ Architecture Overview

The text retrieval system has **5 hierarchical layers**:

```
CASES (top-level)
  ↓
CHUNKS (200-500 word sections)
  ↓
SENTENCES (individual sentences)
  ↓
WORDS (word dictionary + positions)
  ↓
PHRASES (n-gram phrases 2-4 words)
```

**Data Flow:**
1. PDF → Parsed → Full text
2. Full text → Chunked into 200-500 word sections
3. Chunks → Split into sentences
4. Sentences → Tokenized into words
5. Words → Tracked by position in sentences
6. Phrases → Extracted as n-grams (2-4 words)

---

## 📊 Table Schemas

### 1. `cases`

**Purpose:** Main case metadata

**Key Fields:**
- `case_id` (BIGINT, PK) - Unique identifier
- `title` (CITEXT) - Case name (e.g., "In re Marriage of Smith v. Jones")
- `docket_number` (CITEXT) - Court docket number
- `court` (CITEXT) - Court name
- `court_level` (CITEXT) - "Appeals" or "Supreme"
- `district` (CITEXT) - "Division I", "Division II", "Division III", or NULL
- `county` (CITEXT) - County of origin
- `appeal_published_date` (DATE) - Decision publication date
- `full_text` (TEXT) - Complete case text

**Relationships:**
- 1 case → MANY chunks (10-30 typically)
- 1 case → MANY sentences (100-500 typically)
- 1 case → MANY word occurrences (thousands)
- 1 case → MANY phrases (50-200 typically)

---

### 2. `case_chunks`

**Purpose:** Document broken into semantic sections (paragraphs/sections)

**Full Schema:**
```sql
CREATE TABLE case_chunks (
    chunk_id BIGINT PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES cases(case_id),
    document_id BIGINT REFERENCES documents(document_id),
    
    -- Position and organization
    chunk_order INT NOT NULL,              -- Sequential: 1, 2, 3...N
    section CITEXT,                        -- Section type
    text TEXT NOT NULL,                    -- Chunk content (200-500 words)
    sentence_count INTEGER DEFAULT 0,      -- Number of sentences in chunk
    
    -- Full-text search
    tsv TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(text,''))
    ) STORED,
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX uq_case_chunk_order ON case_chunks (case_id, chunk_order);
CREATE INDEX idx_case_chunks_case_id ON case_chunks(case_id);
CREATE INDEX idx_case_chunks_tsv ON case_chunks USING GIN (tsv);
```

**Key Points:**
- **chunk_order**: Sequential position (1..N) within the case
- **section**: Legal document section type:
  - `FACTS` - Statement of facts
  - `ANALYSIS` - Legal analysis
  - `HOLDING` - Court's decision
  - `CUSTODY` - Custody/parenting issues
  - `SUPPORT` - Spousal/child support
  - `PROPERTY` - Property division
  - `FEES` - Attorney fees
  - `PROCEDURAL` - Procedural history
  - `CONTENT` - General content
- **tsv**: Auto-generated full-text search vector
- **Average size**: 200-500 words per chunk
- **Average count**: 10-30 chunks per case

**Common Query Patterns:**

```sql
-- Get all chunks for a case in order
SELECT chunk_id, chunk_order, section, text, sentence_count
FROM case_chunks
WHERE case_id = 123
ORDER BY chunk_order;

-- Get chunks around a specific chunk (CONTEXT)
-- Example: Get 3 chunks before and after chunk 15
SELECT chunk_id, chunk_order, section, text
FROM case_chunks
WHERE case_id = 123
  AND chunk_order BETWEEN 15 - 3 AND 15 + 3
ORDER BY chunk_order;

-- Full-text search in chunks
SELECT 
    c.case_id,
    c.title,
    ch.chunk_order,
    ch.section,
    ch.text,
    ts_rank(ch.tsv, query) as relevance
FROM case_chunks ch
JOIN cases c ON ch.case_id = c.case_id,
to_tsquery('english', 'business & valuation') as query
WHERE ch.tsv @@ query
ORDER BY relevance DESC;

-- Get specific section types
SELECT chunk_id, chunk_order, text
FROM case_chunks
WHERE case_id = 123
  AND section IN ('FACTS', 'ANALYSIS')
ORDER BY chunk_order;
```

---

### 3. `case_sentences`

**Purpose:** Individual sentences for precise text location

**Full Schema:**
```sql
CREATE TABLE case_sentences (
    sentence_id BIGINT PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES cases(case_id),
    chunk_id BIGINT NOT NULL REFERENCES case_chunks(chunk_id),
    document_id BIGINT REFERENCES documents(document_id),
    
    -- Position tracking
    sentence_order INTEGER NOT NULL,        -- Position within chunk: 1, 2, 3...
    global_sentence_order INTEGER NOT NULL, -- Position within entire case: 1...N
    
    -- Content
    text TEXT NOT NULL,                     -- Sentence text
    word_count INTEGER DEFAULT 0,           -- Number of words
    
    -- Full-text search
    tsv TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(text,''))
    ) STORED,
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX uq_case_sentence_order ON case_sentences (case_id, chunk_id, sentence_order);
CREATE INDEX idx_case_sentences_case_id ON case_sentences(case_id);
CREATE INDEX idx_case_sentences_chunk_id ON case_sentences(chunk_id);
CREATE INDEX idx_case_sentences_global_order ON case_sentences(case_id, global_sentence_order);
CREATE INDEX idx_case_sentences_tsv ON case_sentences USING GIN (tsv);
```

**Key Points:**
- **sentence_order**: Position within chunk (resets for each chunk: 1, 2, 3...)
- **global_sentence_order**: Absolute position in entire case (1...total_sentences)
- **Use global_sentence_order** to understand overall case structure
- **Average**: 5-15 sentences per chunk
- **Average**: 100-500 sentences per case

**Common Query Patterns:**

```sql
-- Find sentence by global order
SELECT sentence_id, text, chunk_id
FROM case_sentences
WHERE case_id = 123 
  AND global_sentence_order = 145;

-- Get all sentences in a chunk
SELECT sentence_id, sentence_order, text, word_count
FROM case_sentences
WHERE chunk_id = 456
ORDER BY sentence_order;

-- Find sentences containing keywords
SELECT 
    c.title,
    c.docket_number,
    s.sentence_id,
    s.text,
    s.global_sentence_order,
    ch.chunk_order,
    ch.section,
    ts_rank(s.tsv, query) as relevance
FROM case_sentences s
JOIN cases c ON s.case_id = c.case_id
JOIN case_chunks ch ON s.chunk_id = ch.chunk_id,
websearch_to_tsquery('english', 'spousal support modification') as query
WHERE s.tsv @@ query
ORDER BY relevance DESC;

-- Get sentence with surrounding sentences (mini-context)
SELECT sentence_id, global_sentence_order, text
FROM case_sentences
WHERE case_id = 123
  AND global_sentence_order BETWEEN 145 - 2 AND 145 + 2
ORDER BY global_sentence_order;

-- Find sentences in specific sections
SELECT s.sentence_id, s.text, ch.section
FROM case_sentences s
JOIN case_chunks ch ON s.chunk_id = ch.chunk_id
WHERE s.case_id = 123
  AND ch.section = 'ANALYSIS'
  AND s.tsv @@ to_tsquery('english', 'abuse & discretion')
ORDER BY s.global_sentence_order;
```

---

### 4. `word_dictionary`

**Purpose:** Unique lexicon of all words in the corpus

**Full Schema:**
```sql
CREATE TABLE word_dictionary (
    word_id SERIAL PRIMARY KEY,
    word CITEXT UNIQUE NOT NULL,            -- Lowercase word
    lemma CITEXT,                           -- Lemmatized form (optional)
    df INT DEFAULT 0                        -- Document frequency (# of cases)
);

-- Indexes
CREATE INDEX idx_word_dictionary_trgm ON word_dictionary USING GIN (word gin_trgm_ops);
```

**Key Points:**
- **word**: Lowercase, normalized (e.g., "valuation", "court", "support")
- **lemma**: Optional lemmatized form (e.g., "running" → "run")
- **df**: Document frequency - how many cases contain this word
- **One row per unique word** across entire database
- **Tokenization rules**:
  - Lowercase normalization
  - Keeps hyphens in compound words (e.g., "co-petitioner")
  - Keeps apostrophes in contractions (e.g., "don't")
  - Removes possessive apostrophes (e.g., "plaintiff's" → "plaintiff")
  - Minimum 2 characters
  - Must contain at least one letter

**Common Query Patterns:**

```sql
-- Find word ID
SELECT word_id, word, df
FROM word_dictionary
WHERE word = 'valuation';

-- Find similar words (fuzzy matching)
SELECT 
    word_id, 
    word, 
    df,
    similarity(word, 'valuation') as sim
FROM word_dictionary
WHERE similarity(word, 'valuation') > 0.3
ORDER BY sim DESC
LIMIT 20;

-- Find most common words
SELECT word, df
FROM word_dictionary
ORDER BY df DESC
LIMIT 100;

-- Find words by pattern
SELECT word, df
FROM word_dictionary
WHERE word LIKE 'support%'
ORDER BY df DESC;
```

---

### 5. `word_occurrence`

**Purpose:** Track every position of every word in every sentence (for exact phrase matching)

**Full Schema:**
```sql
CREATE TABLE word_occurrence (
    word_id INT NOT NULL REFERENCES word_dictionary(word_id),
    case_id BIGINT NOT NULL REFERENCES cases(case_id),
    chunk_id BIGINT NOT NULL REFERENCES case_chunks(chunk_id),
    sentence_id BIGINT NOT NULL REFERENCES case_sentences(sentence_id),
    document_id BIGINT REFERENCES documents(document_id),
    
    position INT NOT NULL,                  -- Token position within sentence (0-based)
    
    PRIMARY KEY (word_id, sentence_id, position)
);

-- Indexes
CREATE INDEX idx_word_occurrence_word_case ON word_occurrence(word_id, case_id);
CREATE INDEX idx_word_occurrence_case_id ON word_occurrence(case_id);
CREATE INDEX idx_word_occurrence_sentence ON word_occurrence(sentence_id);
CREATE INDEX idx_word_occurrence_chunk_pos ON word_occurrence(chunk_id, position);
```

**Key Points:**
- **position**: 0-based index within sentence (0, 1, 2, 3...)
- **Each word token** gets one row
- Enables finding **exact consecutive word sequences** (phrases)
- **Large table**: Millions of rows for big corpus
- **Primary use**: Exact phrase matching by word position

**Example Data:**

Sentence: `"The trial court reviewed the business valuation methodology"`

Word occurrences in database:
```
(word="the", sentence_id=123, position=0)
(word="trial", sentence_id=123, position=1)
(word="court", sentence_id=123, position=2)
(word="reviewed", sentence_id=123, position=3)
(word="the", sentence_id=123, position=4)
(word="business", sentence_id=123, position=5)
(word="valuation", sentence_id=123, position=6)
(word="methodology", sentence_id=123, position=7)
```

**Common Query Patterns:**

```sql
-- Find all occurrences of a single word
SELECT 
    wo.case_id,
    c.title,
    wo.sentence_id,
    s.text,
    wo.position
FROM word_occurrence wo
JOIN word_dictionary wd ON wo.word_id = wd.word_id
JOIN cases c ON wo.case_id = c.case_id
JOIN case_sentences s ON wo.sentence_id = s.sentence_id
WHERE wd.word = 'valuation'
ORDER BY c.case_id, wo.sentence_id, wo.position;

-- Find exact phrase "business valuation" using consecutive positions
WITH phrase_words AS (
    -- Define phrase words with their expected order
    SELECT 'business' AS word, 0 AS word_order
    UNION ALL 
    SELECT 'valuation', 1
),
word_positions AS (
    -- Find all positions of these words
    SELECT 
        wo.case_id,
        wo.sentence_id,
        wo.chunk_id,
        wo.position,
        pw.word_order,
        wd.word
    FROM word_occurrence wo
    JOIN word_dictionary wd ON wo.word_id = wd.word_id
    JOIN phrase_words pw ON wd.word = pw.word
),
consecutive_matches AS (
    -- Find where words appear consecutively
    -- The key: position - word_order should be the same for all words in phrase
    SELECT 
        case_id,
        sentence_id,
        chunk_id,
        position - word_order AS phrase_start_position,
        COUNT(*) as matched_words
    FROM word_positions
    GROUP BY case_id, sentence_id, chunk_id, position - word_order
    HAVING COUNT(*) = 2  -- All words must be present
)
SELECT 
    c.case_id,
    c.title,
    c.docket_number,
    s.sentence_id,
    s.text as sentence_text,
    ch.chunk_order,
    ch.section,
    cm.phrase_start_position
FROM consecutive_matches cm
JOIN cases c ON cm.case_id = c.case_id
JOIN case_sentences s ON cm.sentence_id = s.sentence_id
JOIN case_chunks ch ON cm.chunk_id = ch.chunk_id
ORDER BY c.case_id, ch.chunk_order;

-- Find exact 3-word phrase "best interests child"
WITH phrase_words AS (
    SELECT 'best' AS word, 0 AS word_order
    UNION ALL SELECT 'interests', 1
    UNION ALL SELECT 'child', 2
),
word_positions AS (
    SELECT 
        wo.case_id,
        wo.sentence_id,
        wo.chunk_id,
        wo.position,
        pw.word_order
    FROM word_occurrence wo
    JOIN word_dictionary wd ON wo.word_id = wd.word_id
    JOIN phrase_words pw ON wd.word = pw.word
),
phrase_matches AS (
    SELECT 
        case_id,
        sentence_id,
        chunk_id,
        position - word_order AS phrase_start,
        COUNT(*) as matched
    FROM word_positions
    GROUP BY case_id, sentence_id, chunk_id, position - word_order
    HAVING COUNT(*) = 3
)
SELECT 
    c.title,
    s.text,
    ch.chunk_order,
    ch.section
FROM phrase_matches pm
JOIN cases c ON pm.case_id = c.case_id
JOIN case_sentences s ON pm.sentence_id = s.sentence_id
JOIN case_chunks ch ON pm.chunk_id = ch.chunk_id;
```

---

### 6. `case_phrases`

**Purpose:** Pre-extracted n-gram phrases (2-4 words) - legal terminology

**Full Schema:**
```sql
CREATE TABLE case_phrases (
    phrase_id BIGINT PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES cases(case_id),
    document_id BIGINT REFERENCES documents(document_id),
    
    phrase CITEXT NOT NULL,                 -- N-gram text
    n SMALLINT NOT NULL CHECK (n IN (2,3,4)), -- 2=bigram, 3=trigram, 4=4-gram
    frequency INT NOT NULL,                 -- Occurrences in this case
    
    -- Example locations (first occurrence)
    example_sentence BIGINT REFERENCES case_sentences(sentence_id),
    example_chunk BIGINT REFERENCES case_chunks(chunk_id),
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX uq_case_phrase ON case_phrases (case_id, phrase);
CREATE INDEX idx_case_phrases_case_id ON case_phrases(case_id);
CREATE INDEX idx_case_phrases_phrase_trgm ON case_phrases USING GIN (phrase gin_trgm_ops);
```

**Key Points:**
- **phrase**: N-gram text (e.g., "spousal support", "best interests child")
- **n**: Phrase length (2, 3, or 4 words)
- **frequency**: How many times phrase appears in this case
- **Only legal phrases stored** - filtered during extraction
- **Legal phrase criteria**:
  - Contains legal keywords (court, judge, support, custody, etc.)
  - Matches legal phrase patterns (due process, best interests, etc.)
  - Excludes stop phrases (of the, in the, etc.)
- **Faster than word_occurrence** for common phrases

**Example Phrases:**
- 2-gram: "spousal support", "trial court", "best interests"
- 3-gram: "abuse of discretion", "best interests child", "community property division"
- 4-gram: "substantial change in circumstances", "best interests of child"

**Common Query Patterns:**

```sql
-- Find exact phrase match
SELECT 
    c.case_id,
    c.title,
    c.docket_number,
    cp.phrase,
    cp.n,
    cp.frequency,
    s.text as example_sentence,
    ch.chunk_order,
    ch.section
FROM case_phrases cp
JOIN cases c ON cp.case_id = c.case_id
LEFT JOIN case_sentences s ON cp.example_sentence = s.sentence_id
LEFT JOIN case_chunks ch ON cp.example_chunk = ch.chunk_id
WHERE cp.phrase = 'business valuation'
ORDER BY cp.frequency DESC;

-- Find similar phrases (fuzzy matching)
SELECT 
    phrase,
    SUM(frequency) as total_freq,
    COUNT(DISTINCT case_id) as num_cases,
    similarity(phrase, 'spousal support') as sim
FROM case_phrases
WHERE similarity(phrase, 'spousal support') > 0.4
GROUP BY phrase
ORDER BY sim DESC, total_freq DESC
LIMIT 20;

-- Most common phrases containing a keyword
SELECT 
    phrase,
    n,
    SUM(frequency) as total_occurrences,
    COUNT(DISTINCT case_id) as case_count
FROM case_phrases
WHERE phrase ILIKE '%support%'
GROUP BY phrase, n
ORDER BY total_occurrences DESC
LIMIT 50;

-- Find phrases in specific case
SELECT phrase, n, frequency
FROM case_phrases
WHERE case_id = 123
ORDER BY frequency DESC, n DESC;

-- Top phrases across all cases
SELECT 
    phrase,
    n,
    COUNT(DISTINCT case_id) as num_cases,
    SUM(frequency) as total_occurrences,
    AVG(frequency) as avg_per_case
FROM case_phrases
GROUP BY phrase, n
HAVING COUNT(DISTINCT case_id) >= 3
ORDER BY num_cases DESC, total_occurrences DESC
LIMIT 100;
```

---

## 🎯 Complete Query Pattern: Find Text with Context

**Goal:** Find a word/phrase and return surrounding chunks for full context

### Step-by-Step SQL Template

```sql
-- =============================================================================
-- COMPLETE PATTERN: Find text location with surrounding chunk context
-- =============================================================================

-- STEP 1: Find matching sentences (using full-text search)
WITH matched_sentences AS (
    SELECT 
        s.case_id,
        s.sentence_id,
        s.text as matched_sentence,
        s.global_sentence_order,
        s.word_count,
        s.chunk_id,
        ch.chunk_order,
        ch.section,
        ts_rank(s.tsv, websearch_to_tsquery('english', :search_query)) as relevance
    FROM case_sentences s
    JOIN case_chunks ch ON s.chunk_id = ch.chunk_id
    WHERE s.tsv @@ websearch_to_tsquery('english', :search_query)
      AND (:case_id IS NULL OR s.case_id = :case_id)  -- Optional case filter
    ORDER BY relevance DESC
    LIMIT :max_results
),

-- STEP 2: Enrich with case information
enriched_matches AS (
    SELECT 
        ms.*,
        c.title,
        c.docket_number,
        c.court,
        c.district,
        c.appeal_published_date
    FROM matched_sentences ms
    JOIN cases c ON ms.case_id = c.case_id
),

-- STEP 3: Get surrounding chunks for context
context_chunks AS (
    SELECT 
        em.case_id,
        em.sentence_id,
        ch.chunk_id,
        ch.chunk_order,
        ch.section,
        ch.text as chunk_text,
        ch.sentence_count,
        em.chunk_order as match_chunk_order,
        -- Calculate distance from matched chunk
        ABS(ch.chunk_order - em.chunk_order) as distance_from_match
    FROM enriched_matches em
    JOIN case_chunks ch ON em.case_id = ch.case_id
    WHERE ch.chunk_order BETWEEN 
        em.chunk_order - :context_chunks AND 
        em.chunk_order + :context_chunks
)

-- STEP 4: Combine everything with aggregated context
SELECT 
    em.case_id,
    em.title,
    em.docket_number,
    em.court,
    em.district,
    em.appeal_published_date,
    em.sentence_id,
    em.matched_sentence,
    em.global_sentence_order,
    em.word_count as sentence_word_count,
    em.chunk_order as match_chunk_order,
    em.section as match_section,
    em.relevance,
    -- Aggregate context chunks as JSON array
    json_agg(
        json_build_object(
            'chunk_id', cc.chunk_id,
            'chunk_order', cc.chunk_order,
            'section', cc.section,
            'text', cc.chunk_text,
            'sentence_count', cc.sentence_count,
            'is_match', cc.chunk_order = em.chunk_order,
            'distance_from_match', cc.distance_from_match
        ) ORDER BY cc.chunk_order
    ) as context_chunks
FROM enriched_matches em
LEFT JOIN context_chunks cc ON em.case_id = cc.case_id AND em.sentence_id = cc.sentence_id
GROUP BY 
    em.case_id, em.title, em.docket_number, em.court, em.district,
    em.appeal_published_date, em.sentence_id, em.matched_sentence,
    em.global_sentence_order, em.word_count, em.chunk_order, em.section, em.relevance
ORDER BY em.relevance DESC, em.case_id, em.chunk_order;
```

### Parameters:
- `:search_query` - Search keywords (e.g., "business valuation")
- `:case_id` - Optional specific case ID (NULL for all cases)
- `:max_results` - Maximum matches to return (e.g., 15)
- `:context_chunks` - Number of chunks before/after (e.g., 3)

### Example Usage:

```sql
-- Find "business valuation" in all cases with 3 chunks context
-- Parameters: search_query='business valuation', case_id=NULL, max_results=15, context_chunks=3

-- Find "spousal support modification" in specific case with 5 chunks context
-- Parameters: search_query='spousal support modification', case_id=12345, max_results=20, context_chunks=5
```

---

## 🔍 Search Mode Comparison

### 1. **Keyword Search (Full-Text)**
**Use when:** Looking for general concepts, multiple keywords

```sql
-- Uses: case_sentences.tsv
WHERE s.tsv @@ websearch_to_tsquery('english', 'unable afford spousal support')
```

**Pros:**
- Fast with GIN indexes
- Finds variations (stemming)
- Ranks by relevance

**Cons:**
- Not exact phrase matching
- May miss exact sequences

---

### 2. **Exact Phrase Search (Word Positions)**
**Use when:** Need exact phrase in exact order

```sql
-- Uses: word_occurrence + word_dictionary
-- Finds consecutive word positions
```

**Pros:**
- Guarantees exact match
- Precise results

**Cons:**
- More complex query
- Slower for rare phrases

---

### 3. **Fuzzy Phrase Search (Trigram)**
**Use when:** Looking for similar phrases, typo-tolerant

```sql
-- Uses: case_phrases with similarity()
WHERE similarity(phrase, 'spousal support') > 0.4
```

**Pros:**
- Finds variations
- Typo-tolerant
- Fast with GIN trigram index

**Cons:**
- May have false positives
- Limited to pre-extracted phrases

---

## 📈 Performance Tips

### Index Usage
- **Always** filter by `case_id` when possible (indexed)
- Use `tsv @@ to_tsquery()` for full-text (GIN indexed)
- Use `similarity()` for fuzzy matching (GIN trigram indexed)
- Order by indexed columns when possible

### Query Optimization
```sql
-- GOOD: Uses index
WHERE case_id = 123 AND tsv @@ to_tsquery('business')

-- BAD: Slow without index
WHERE text LIKE '%business%'

-- GOOD: Indexed foreign keys
JOIN case_chunks ch ON s.chunk_id = ch.chunk_id

-- GOOD: Range query on chunk_order (indexed)
WHERE chunk_order BETWEEN 10 AND 20
```

### Context Retrieval
```sql
-- EFFICIENT: Single query with JOIN
SELECT ... FROM matched_sentences ms
JOIN case_chunks ch ON ms.case_id = ch.case_id
WHERE ch.chunk_order BETWEEN ms.chunk_order - 3 AND ms.chunk_order + 3

-- INEFFICIENT: Separate queries per match
-- (Avoid N+1 query problem)
```

---

## 🎓 Common Use Cases

### Use Case 1: "Find all mentions of X in case Y"
```sql
SELECT 
    s.sentence_id,
    s.global_sentence_order,
    s.text,
    ch.chunk_order,
    ch.section
FROM case_sentences s
JOIN case_chunks ch ON s.chunk_id = ch.chunk_id
WHERE s.case_id = :case_id
  AND s.tsv @@ websearch_to_tsquery('english', :search_term)
ORDER BY s.global_sentence_order;
```

### Use Case 2: "Show me context around this sentence"
```sql
SELECT chunk_order, section, text
FROM case_chunks
WHERE case_id = :case_id
  AND chunk_order BETWEEN :target_chunk - 3 AND :target_chunk + 3
ORDER BY chunk_order;
```

### Use Case 3: "Find similar legal phrases"
```sql
SELECT phrase, COUNT(DISTINCT case_id) as cases, SUM(frequency) as total
FROM case_phrases
WHERE similarity(phrase, :search_phrase) > 0.5
GROUP BY phrase
ORDER BY similarity(phrase, :search_phrase) DESC;
```

### Use Case 4: "Get all text from ANALYSIS section"
```sql
SELECT ch.chunk_order, ch.text
FROM case_chunks ch
WHERE ch.case_id = :case_id
  AND ch.section = 'ANALYSIS'
ORDER BY ch.chunk_order;
```

---

## 🚨 Important Notes

### NULL Handling
- Many fields can be NULL (section, document_id, etc.)
- Always use `IS NULL` or `IS NOT NULL` in WHERE clauses
- Use `COALESCE()` for defaults

### Case Sensitivity
- CITEXT columns are case-insensitive (word, phrase, section)
- Use `ILIKE` for pattern matching on TEXT columns
- Full-text search is case-insensitive by default

### Data Consistency
- **sentence_count** in chunks should match actual sentence records
- **word_count** in sentences should match tokenized words
- **global_sentence_order** should be continuous (1..N) per case
- **chunk_order** should be continuous (1..N) per case

### Typical Sizes
- Small case: 5-10 chunks, 50-150 sentences
- Medium case: 15-25 chunks, 200-400 sentences
- Large case: 30-50 chunks, 500-800 sentences

---

## 📝 Summary

This text retrieval layer enables:

✅ **Precise location tracking** - Exact sentence and chunk positions  
✅ **Full context retrieval** - Surrounding chunks (1-6 configurable)  
✅ **Multiple search modes** - Keyword, exact phrase, fuzzy matching  
✅ **Fast performance** - GIN indexes on tsv and trigram fields  
✅ **Hierarchical structure** - Case → Chunk → Sentence → Word  
✅ **Evidence-based answers** - Direct quotes with citations  

Use this schema to write SQL queries that find precise locations of legal terms and retrieve sufficient context for understanding.


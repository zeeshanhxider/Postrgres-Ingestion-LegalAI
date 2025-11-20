# Supervisor Agent Routing Guide

## 🎯 Purpose

This document defines **clear routing rules** for the supervisor agent to decide between:
- **SQL Agent** - For structured data queries (facts, outcomes, statistics)
- **RAG Agent** - For semantic text search and reasoning analysis

---

## 📊 Database Overview

### Current Database State
- **7 cases** (6 with outcomes)
- **23 issues** across cases
- **12 parties**, **35 attorneys**
- **81 citations** to precedents
- **1,402 sentences**, **1,258 phrases** (text layer)
- **34 chunks** with embeddings (semantic search)

### Available Tables (22 total)

**Core Structured Tables:**
- `cases` - Case metadata, outcomes, dates
- `parties` - Party names and roles
- `attorneys` - Legal representation
- `issues_decisions` - Individual legal issues with outcomes
- `arguments` - Arguments made by each side
- `citation_edges` - Case citations/precedents
- `case_judges` - Judge assignments
- `judges` - Judge names

**Text/Search Tables:**
- `case_chunks` - Text sections with full-text search
- `case_sentences` - Individual sentences
- `case_phrases` - Legal terminology n-grams
- `word_dictionary` - Word lexicon
- `word_occurrence` - Word positions
- `embeddings` - Vector embeddings for semantic search

**Dimension Tables:**
- `case_types`, `stage_types`, `document_types`
- `courts_dim`, `statutes_dim`

---

## 🚦 Routing Rules

### ✅ Route to SQL Agent

Use SQL when the answer comes from **structured data in tables**:

#### 1. Case Identification & Outcomes
**Query Types:**
- "Is [case name] affirmed/reversed/remanded?"
- "What was the outcome of [case name]?"
- "What happened in [case name]?"
- "Who won in [case name]?"
- "Was [case name] reversed or affirmed?"

**Why SQL:** 
- Case titles in `cases.title`
- Outcomes in `cases.appeal_outcome` or `cases.overall_case_outcome`
- Winner in `cases.winner_legal_role`

**Example SQL:**
```sql
SELECT title, appeal_outcome, overall_case_outcome, winner_legal_role
FROM cases
WHERE title ILIKE '%Lloyd Russell Michael%'
```

---

#### 2. Case Metadata & Facts
**Query Types:**
- "Which court heard [case name]?"
- "What division was [case]?"
- "When was [case] decided?"
- "What's the docket number for [case]?"
- "Who were the parties in [case]?"
- "Who were the attorneys?"
- "Who was the judge?"

**Why SQL:**
- Court info: `cases.court`, `cases.court_level`, `cases.district`
- Dates: `cases.appeal_published_date`, etc.
- Docket: `cases.docket_number`
- Parties: `parties` table
- Attorneys: `attorneys` table
- Judges: `case_judges` + `judges` tables

---

#### 3. Issue-Level Queries
**Query Types:**
- "What issues were raised in [case]?"
- "What was the outcome on [specific issue]?"
- "How many issues involved spousal support?"
- "Which issues were reversed?"

**Why SQL:**
- Issues stored in `issues_decisions` table
- Has: `category`, `subcategory`, `issue_summary`, `decision_summary`, `appeal_outcome`

**Example:**
```sql
SELECT category, subcategory, appeal_outcome, decision_summary
FROM issues_decisions
WHERE case_id = (SELECT case_id FROM cases WHERE title ILIKE '%case name%')
```

---

#### 4. Statistical Queries
**Query Types:**
- "How many cases were affirmed/reversed?"
- "What percentage of cases involve custody issues?"
- "How many cases mention [topic]?"
- "What's the most common outcome?"
- "Which attorney has the most cases?"
- "Most cited precedents?"

**Why SQL:**
- Aggregation: COUNT, AVG, SUM, percentage calculations
- Grouping by outcomes, categories, attorneys, etc.
- Statistical analysis across cases

**Example:**
```sql
SELECT 
    appeal_outcome, 
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as percentage
FROM cases
WHERE appeal_outcome IS NOT NULL
GROUP BY appeal_outcome
```

---

#### 5. Relationship Queries
**Query Types:**
- "Which cases cite [precedent]?"
- "Find cases with attorney [name]"
- "Cases decided by judge [name]"
- "Cases with parties named [name]"

**Why SQL:**
- Joins between: `cases`, `parties`, `attorneys`, `case_judges`, `citation_edges`

---

#### 6. List/Enumeration Queries
**Query Types:**
- "List all cases"
- "Show me all attorneys"
- "What judges are in the database?"
- "List cases from Division II"

**Why SQL:**
- Simple SELECT queries
- Filtering by structured fields

---

### 🔍 Route to RAG Agent

Use RAG when the answer requires **reading and understanding case text**:

#### 1. Legal Reasoning & Analysis
**Query Types:**
- "**WHY** was [case] reversed?" ← Needs reasoning from text
- "**HOW** did the court analyze [issue]?" ← Needs court's reasoning
- "What was the court's **reasoning** for [decision]?"
- "**What factors** did the court consider?"
- "**What did the court say about** [legal concept]?"

**Why RAG:**
- Reasoning is in full text, not structured fields
- Need to understand court's analysis
- Requires semantic understanding

---

#### 2. Evidence & Quote Searches
**Query Types:**
- "Show me text where [topic] is discussed"
- "Find quotes about [legal principle]"
- "Where does the case mention [specific circumstance]?"
- "What does the case say about [topic]?"

**Why RAG:**
- Need actual text excerpts
- Semantic search through embeddings
- Context from surrounding chunks

---

#### 3. Conceptual/Semantic Searches
**Query Types:**
- "Cases about inability to pay support" ← Semantic concept
- "Cases involving domestic violence" ← May not be exact phrase
- "Find cases about business valuation disputes"
- "Cases where trial court abused discretion"

**Why RAG:**
- Concept may be expressed in many ways
- Semantic similarity more important than exact match
- Vector embeddings capture meaning

---

#### 4. Complex Multi-Step Analysis
**Query Types:**
- "Compare the reasoning in [case A] and [case B]"
- "How is this case different from [precedent]?"
- "What arguments did the appellant make?"
- "Summarize the facts of [case]"

**Why RAG:**
- Requires understanding multiple text sections
- Comparison requires reasoning
- Summary generation from text

---

#### 5. "Why" and "How" Questions
**Query Types:**
- "Why did the appellant lose?"
- "How did the court interpret [statute]?"
- "Why was the valuation incorrect?"
- "How did the court apply [legal standard]?"

**Why RAG:**
- Explanatory questions require text analysis
- Not simple fact lookups
- Need court's reasoning and logic

---

## 🎨 Hybrid Queries (Use Both)

Some queries need **BOTH agents**:

### Example: "Find cases where spousal support was reduced and explain why"

**Step 1 - SQL Agent:**
```sql
-- Find cases with spousal support issues and outcomes
SELECT c.case_id, c.title, id.decision_summary, id.appeal_outcome
FROM cases c
JOIN issues_decisions id ON c.case_id = id.case_id
WHERE id.category = 'Spousal Support / Maintenance'
  AND id.decision_summary ILIKE '%reduc%'
```

**Step 2 - RAG Agent:**
```
For case_id=X, retrieve text chunks explaining why support was reduced
Use semantic search with embeddings
Return court's reasoning with context
```

---

## ⚡ Quick Decision Tree

```
User Query
    |
    ├─ Is it asking for a FACT? (outcome, date, party, judge)
    |  └─> SQL Agent
    |
    ├─ Is it asking "WHY" or "HOW"? (reasoning, explanation)
    |  └─> RAG Agent
    |
    ├─ Does it need STATISTICS or COUNTS?
    |  └─> SQL Agent
    |
    ├─ Does it need TEXT QUOTES or CONTEXT?
    |  └─> RAG Agent
    |
    ├─ Is it about RELATIONSHIPS? (who cited whom, who represented)
    |  └─> SQL Agent
    |
    └─ Is it CONCEPTUAL/SEMANTIC? (cases "about" something)
       └─> RAG Agent (or Hybrid)
```

---

## 🔥 Common Mistakes to Avoid

### ❌ WRONG: Using RAG for Simple Facts

**Bad:**
```
Query: "Was In Re Marriage of Black affirmed?"
Route: RAG Agent ❌
```

**Why Wrong:** Outcome is in `cases.appeal_outcome` - direct table lookup!

**Correct:**
```
Query: "Was In Re Marriage of Black affirmed?"
Route: SQL Agent ✅
SQL: SELECT appeal_outcome FROM cases WHERE title ILIKE '%Marriage of Black%'
```

---

### ❌ WRONG: Using SQL for Reasoning

**Bad:**
```
Query: "Why was the business valuation rejected?"
Route: SQL Agent ❌
SQL: SELECT decision_summary FROM issues_decisions WHERE ...
```

**Why Wrong:** `decision_summary` is a short summary, not full reasoning. Need actual case text!

**Correct:**
```
Query: "Why was the business valuation rejected?"
Route: RAG Agent ✅
Action: Semantic search for "business valuation" + retrieve surrounding analysis chunks
```

---

### ❌ WRONG: Not Using Hybrid Approach

**Bad:**
```
Query: "How many custody cases were reversed and why?"
Route: SQL Agent only ❌
```

**Why Wrong:** "How many" is SQL, but "why" needs RAG!

**Correct:**
```
Query: "How many custody cases were reversed and why?"
Route: HYBRID ✅
1. SQL: COUNT cases with custody + reversed
2. RAG: For each case, get reasoning text
```

---

## 📋 Supervisor Prompt Template

```markdown
You are a supervisor agent routing queries to specialized agents.

AVAILABLE AGENTS:
1. **SQL Agent** - Queries structured database tables
2. **RAG Agent** - Semantic search through case text with embeddings

ROUTING RULES:

**Use SQL Agent for:**
- Case outcomes (affirmed/reversed/remanded)
- Case metadata (court, date, docket, parties, attorneys, judges)
- Issue lists and issue-level outcomes
- Statistics and counts
- Relationships (citations, party connections)
- Lists and enumerations
- ANY factual lookup from structured tables

**Use RAG Agent for:**
- WHY/HOW questions (reasoning, explanations)
- Text quotes and evidence
- Conceptual/semantic searches ("cases about X")
- Court's analysis and legal reasoning
- Comparisons and summaries
- Context around specific topics

**Use BOTH (Hybrid) for:**
- "Find [type of case] and explain why [outcome]"
- Statistical analysis + reasoning
- List cases + show their reasoning

DECISION PROCESS:
1. Identify what data the query needs
2. Check if it's in structured tables → SQL
3. Check if it needs text understanding → RAG
4. If both → Hybrid (SQL first, then RAG for details)

EXAMPLES:

Query: "Is In Re Marriage of Black affirmed?"
Route: SQL ← outcome is in cases.appeal_outcome

Query: "Why was In Re Marriage of Black remanded?"
Route: RAG ← needs court's reasoning from text

Query: "How many cases were reversed?"
Route: SQL ← COUNT(*) with outcome filter

Query: "What did the court say about abuse of discretion?"
Route: RAG ← semantic text search

Query: "List reversed custody cases and explain why"
Route: HYBRID ← SQL for list, RAG for explanations
```

---

## 🎯 Database Query Capabilities by Agent

### SQL Agent Can Answer:

✅ "What was the outcome?" → `cases.appeal_outcome`  
✅ "Who won?" → `cases.winner_legal_role`  
✅ "When decided?" → `cases.appeal_published_date`  
✅ "Which court?" → `cases.court`, `cases.district`  
✅ "What issues?" → `issues_decisions.category/subcategory`  
✅ "Issue outcomes?" → `issues_decisions.appeal_outcome`  
✅ "Who were parties?" → `parties.name`, `parties.legal_role`  
✅ "Who represented?" → `attorneys.name`, `attorneys.representing`  
✅ "Which judge?" → `case_judges` + `judges.name`  
✅ "What citations?" → `citation_edges.target_case_citation`  
✅ "How many cases?" → `COUNT(*) FROM cases`  
✅ "Percentage of X?" → `COUNT(*) / SUM(*) * 100`  

### RAG Agent Can Answer:

✅ "Why reversed?" → Semantic search + text analysis  
✅ "How did court reason?" → Extract analysis sections  
✅ "What factors considered?" → Identify factors in text  
✅ "Show me text about X" → Full-text + semantic search  
✅ "Court's explanation?" → Retrieve reasoning chunks  
✅ "Compare reasoning" → Multi-case text analysis  
✅ "Summarize facts" → Extract + summarize fact sections  
✅ "Arguments made?" → Find argument text passages  

---

## 🔧 Implementation Notes

### For SQL Agent:
- Always use `ILIKE` for case-insensitive searches
- Use `%wildcard%` for partial matches on titles
- Check for NULL values with `IS NOT NULL`
- Use `DISTINCT` when counting cases after joins
- Join `issues_decisions` for issue-level details

### For RAG Agent:
- Use vector embeddings in `embeddings` table for semantic search
- Full-text search available via `case_sentences.tsv` and `case_chunks.tsv`
- Return surrounding chunks (3-5) for context
- Include case metadata (title, docket) with results
- Cite specific sentence_id and chunk_id for verification

### Query Patterns:

**Find case by name (SQL):**
```sql
SELECT case_id, title, appeal_outcome 
FROM cases 
WHERE title ILIKE '%case name%'
```

**Find reasoning text (RAG):**
```python
# Semantic search in embeddings table
query_embedding = generate_embedding(query)
similar_chunks = search_embeddings(query_embedding, top_k=10)
return chunks_with_context(similar_chunks)
```

---

## 📚 Summary

**Golden Rule:**
- **Facts → SQL**
- **Reasoning → RAG**
- **Both → Hybrid**

When in doubt, ask:
1. "Is this a database field?" → SQL
2. "Does this need text understanding?" → RAG
3. "Is it both?" → Hybrid

The supervisor should **default to SQL for factual queries** and only use RAG when text analysis is truly needed.



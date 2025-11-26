# How Document Types Help the AI Agent

## Overview

The restructured `document_types` table acts as a **"Traffic Cop"** that tells the AI agent exactly how to process each document before it even reads the content.

---

## The Problem Before

Previously, the AI had to:

1. Read the entire document
2. Guess what type it was
3. Figure out how to process it
4. Decide if the content was trustworthy

This was slow, error-prone, and inconsistent.

---

## The Solution: Smart Metadata

Now, every document has metadata that tells the AI agent:

| Field                 | What it tells the AI                                 |
| --------------------- | ---------------------------------------------------- |
| `role`                | Who created this? (court, party, evidence)           |
| `has_decision`        | Does this contain a ruling I should extract?         |
| `is_adversarial`      | Should I trust this as fact or treat it as argument? |
| `processing_strategy` | Which extraction pipeline should I use?              |

---

## AI Processing Flow

```
Document Uploaded
       │
       ▼
┌─────────────────────────────────┐
│  Check document_type metadata   │
└─────────────────────────────────┘
       │
       ├── role = 'court' + has_decision = TRUE
       │   └── Run Outcome Extractor
       │       • Extract: winner, outcome, ruling
       │       • Trust level: HIGH (this is truth)
       │       • Update: cases.appeal_outcome, cases.winner_legal_role
       │
       ├── role = 'party' + is_adversarial = TRUE
       │   └── Run Argument Extractor
       │       • Extract: arguments, cited cases, legal theories
       │       • Trust level: LOW (this is one side's spin)
       │       • Update: briefs table, brief_arguments
       │
       └── role = 'evidence' + is_adversarial = FALSE
           └── Run Evidence Indexer
               • Extract: facts, quotes, testimony
               • Trust level: MEDIUM (neutral but may be incomplete)
               • Update: chunks, embeddings only
```

---

## Trust Levels by Document Type

| Document Type       | Trust Level   | AI Behavior                                              |
| ------------------- | ------------- | -------------------------------------------------------- |
| `appellate_opinion` | 🟢 **HIGH**   | Extract as ground truth. This is what happened.          |
| `trial_court_order` | 🟢 **HIGH**   | Extract ruling. This is an official decision.            |
| `opening_brief`     | 🔴 **LOW**    | Extract arguments, but flag as appellant's perspective.  |
| `respondent_brief`  | 🔴 **LOW**    | Extract arguments, but flag as respondent's perspective. |
| `transcript`        | 🟡 **MEDIUM** | Extract quotes/facts. Neutral but selective.             |
| `exhibit`           | 🟡 **MEDIUM** | Index content. Factual but context-dependent.            |

---

## Example: How AI Processes a Case

**Case: Smith v. Jones Divorce**

### Step 1: AI receives `opening_brief`

```
document_type: opening_brief
role: party
is_adversarial: TRUE
processing_strategy: brief_extraction
```

**AI thinks:** _"This is the appellant's argument. I'll extract their claims but remember this is biased."_

**Extracts:**

- "Appellant argues trial court erred in property division"
- "Appellant claims wife hid assets"
- Cited cases: _In re Marriage of Rockwell_

### Step 2: AI receives `respondent_brief`

```
document_type: respondent_brief
role: party
is_adversarial: TRUE
processing_strategy: brief_extraction
```

**AI thinks:** _"This is the respondent's counter-argument. Also biased, but the other direction."_

**Extracts:**

- "Respondent denies hiding assets"
- "Respondent argues proper valuation was used"

### Step 3: AI receives `appellate_opinion`

```
document_type: appellate_opinion
role: court
has_decision: TRUE
is_adversarial: FALSE
processing_strategy: case_outcome
```

**AI thinks:** _"This is the court's ruling. This is TRUTH. Whatever is here overrides the briefs."_

**Extracts:**

- `appeal_outcome`: "Affirmed"
- `winner_legal_role`: "Respondent"
- `decision_summary`: "Trial court's property division was proper"

---

## Benefits for AI Agent

### 1. **Faster Processing**

No need to analyze content to determine document type - metadata tells it immediately.

### 2. **Correct Pipeline**

Each document type routes to the right extractor automatically.

### 3. **Trust Calibration**

AI knows when to treat content as fact vs. argument.

### 4. **Conflict Resolution**

When brief says X but opinion says Y, AI knows opinion wins.

### 5. **Better Embeddings**

AI can weight embeddings differently based on document authority.

---

## Database Queries for AI

### Get authoritative documents for a case

```sql
SELECT d.*, dt.document_type
FROM documents d
JOIN document_types dt ON d.document_type_id = dt.document_type_id
WHERE d.case_id = 123
  AND dt.role = 'court'
  AND dt.has_decision = TRUE;
```

### Get all arguments (both sides) for a case

```sql
SELECT d.*, dt.document_type, b.filing_party
FROM documents d
JOIN document_types dt ON d.document_type_id = dt.document_type_id
JOIN briefs b ON d.brief_id = b.brief_id
WHERE d.case_id = 123
  AND dt.is_adversarial = TRUE;
```

### Get neutral evidence for a case

```sql
SELECT d.*, dt.document_type
FROM documents d
JOIN document_types dt ON d.document_type_id = dt.document_type_id
WHERE d.case_id = 123
  AND dt.role = 'evidence'
  AND dt.is_adversarial = FALSE;
```

---

## Summary

| Before                       | After                            |
| ---------------------------- | -------------------------------- |
| AI guesses document type     | AI knows document type instantly |
| Same processing for all docs | Specialized pipelines per type   |
| No trust calibration         | Trust levels built-in            |
| Manual conflict resolution   | Automatic: court > party         |
| Slow, inconsistent           | Fast, reliable                   |

The `document_types` table is the AI's **instruction manual** for every document it encounters.

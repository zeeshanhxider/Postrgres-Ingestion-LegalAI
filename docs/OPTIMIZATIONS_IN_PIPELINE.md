# Pipeline Optimizations

## Applied Performance Improvements

### LLM Processing

- **Context window**: 128k → 32k tokens (~4x faster)
- **Max response**: 16k → 8k tokens
- **Smart truncation**: 25k chars (40% header + 35% middle + 25% footer)
- **Timeout**: 300s → 180s

### Database

- **Connection pooling**: 5 base + 10 overflow connections
- **Word batching**: 50 → 500 items per commit
- **Bulk inserts**: Using `executemany()` for words, phrases

### RAG Processing

- **Embedding batches**: 10 → 25 per API call
- **Embedding truncation**: 8k → 4k chars
- **Embedding timeout**: 60s → 30s
- **DB batch size**: 50 → 100 items
- **Chunk embeddings**: ALL (full coverage)

### Expected Results

- LLM: ~50-70% faster
- Database: ~30-50% faster
- Embeddings: ~40-60% faster
- Overall: ~2-3x pipeline throughput

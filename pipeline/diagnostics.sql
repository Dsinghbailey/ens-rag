-- 1. Basic table statistics
SELECT 
    COUNT(*) as total_chunks,
    COUNT(DISTINCT metadata->>'customer_id') as unique_customers,
    COUNT(DISTINCT metadata->>'source_url') as unique_sources,
    AVG(length(document)) as avg_chunk_length
FROM processed_chunks_llamaindex;

-- 2. Top customers by chunk count
SELECT 
    metadata->>'customer_id' as customer_id,
    COUNT(*) as chunk_count,
    COUNT(DISTINCT metadata->>'source_url') as unique_sources
FROM processed_chunks_llamaindex
GROUP BY metadata->>'customer_id'
ORDER BY chunk_count DESC
LIMIT 5;

-- 3. Top source URLs by chunk count
SELECT 
    metadata->>'source_url' as source_url,
    COUNT(*) as chunk_count
FROM processed_chunks_llamaindex
GROUP BY metadata->>'source_url'
ORDER BY chunk_count DESC
LIMIT 5;

-- 4. Distribution of chunk types
SELECT 
    metadata->>'chunk_type' as chunk_type,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM processed_chunks_llamaindex
GROUP BY metadata->>'chunk_type'
ORDER BY count DESC;

-- 5. Code language distribution
SELECT 
    metadata->>'code_language' as code_language,
    COUNT(*) as count
FROM processed_chunks_llamaindex
WHERE metadata->>'code_language' IS NOT NULL
GROUP BY metadata->>'code_language'
ORDER BY count DESC
LIMIT 5;

-- 6. Check for any potential data quality issues
SELECT 
    COUNT(*) as null_embeddings
FROM processed_chunks_llamaindex
WHERE embedding IS NULL;

-- 7. Sample of recent chunks with their metadata
SELECT 
    id,
    metadata->>'customer_id' as customer_id,
    metadata->>'source_url' as source_url,
    metadata->>'chunk_type' as chunk_type,
    LEFT(document, 100) as preview
FROM processed_chunks_llamaindex
ORDER BY id DESC
LIMIT 5;
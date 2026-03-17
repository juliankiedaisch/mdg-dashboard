-- Add advanced pipeline configuration (JSON) to retrieval config tables.
-- Stores reranking, hybrid search, parent-child chunking, and dedup settings.

ALTER TABLE assistant_retrieval_config
    ADD COLUMN IF NOT EXISTS pipeline_config_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE assistant_user_retrieval_config
    ADD COLUMN IF NOT EXISTS pipeline_config_json TEXT DEFAULT NULL;

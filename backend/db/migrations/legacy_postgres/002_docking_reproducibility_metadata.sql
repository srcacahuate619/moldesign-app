-- MolDesign migration 002
-- Persistencia de metadatos de reproducibilidad y trazabilidad de docking
-- Fecha: 2026-04-03

ALTER TABLE evaluation_results
    ADD COLUMN IF NOT EXISTS parsing_source VARCHAR(50),
    ADD COLUMN IF NOT EXISTS vina_version VARCHAR(50),
    ADD COLUMN IF NOT EXISTS vina_random_seed INTEGER,
    ADD COLUMN IF NOT EXISTS scientific_warnings JSONB;

CREATE INDEX IF NOT EXISTS ix_evaluation_results_parsing_source
    ON evaluation_results (parsing_source);

-- Migration 007: Add affinity_multiplier and specificity_multiplier columns
--
-- Agrega:
--   1. affinity_multiplier en evaluation_results — factor de penalización de afinidad
--   2. specificity_multiplier en evaluation_results — factor de penalización de hotspots
--

ALTER TABLE evaluation_results
    ADD COLUMN IF NOT EXISTS affinity_multiplier FLOAT,
    ADD COLUMN IF NOT EXISTS specificity_multiplier FLOAT;

COMMENT ON COLUMN evaluation_results.affinity_multiplier IS 'Factor de penalización de afinidad (M_a)';
COMMENT ON COLUMN evaluation_results.specificity_multiplier IS 'Factor de especificidad de hotspots (M_s)';

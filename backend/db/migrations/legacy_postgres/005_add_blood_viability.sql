ALTER TABLE evaluation_results ADD COLUMN IF NOT EXISTS blood_viability_score FLOAT;
ALTER TABLE evaluation_results ADD COLUMN IF NOT EXISTS blood_solubility_logs FLOAT;
ALTER TABLE evaluation_results ADD COLUMN IF NOT EXISTS blood_ppb_category VARCHAR;
ALTER TABLE evaluation_results ADD COLUMN IF NOT EXISTS blood_bbb_permeable BOOLEAN;
ALTER TABLE evaluation_results ADD COLUMN IF NOT EXISTS blood_hia_permeable BOOLEAN;
ALTER TABLE evaluation_results ADD COLUMN IF NOT EXISTS blood_systemic_reactivity JSONB;

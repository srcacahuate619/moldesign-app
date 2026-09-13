CREATE TABLE IF NOT EXISTS benchmark_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_id VARCHAR(10) NOT NULL,
    smiles VARCHAR(1000) NOT NULL,
    experimental_value DOUBLE PRECISION NOT NULL,
    experimental_p_value DOUBLE PRECISION NOT NULL,
    predicted_affinity DOUBLE PRECISION,
    predicted_score DOUBLE PRECISION,
    specificity_score DOUBLE PRECISION,
    run_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

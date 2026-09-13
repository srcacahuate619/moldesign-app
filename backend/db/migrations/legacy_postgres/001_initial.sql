-- MolDesign MVP initial schema
-- Fecha: 2026-04-03
-- Objetivo: persistencia mínima para molecules, targets, users y evaluation_results.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS rdkit;
EXCEPTION
    WHEN undefined_file THEN
        RAISE NOTICE 'Extensión rdkit no disponible en este PostgreSQL; continuando sin cartridge RDKit.';
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'moleculestatus') THEN
        CREATE TYPE moleculestatus AS ENUM (
            'pending',
            'validated',
            'docking',
            'evaluated',
            'failed'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mutationtype') THEN
        CREATE TYPE mutationtype AS ENUM (
            'substitution',
            'bioisostere',
            'ring_closure',
            'ring_opening',
            'addition',
            'deletion',
            'stereochemistry',
            'scaffold'
        );
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS targets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pdb_id VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    chain VARCHAR(5) NOT NULL DEFAULT 'A',
    description TEXT,
    grid_center_x DOUBLE PRECISION NOT NULL,
    grid_center_y DOUBLE PRECISION NOT NULL,
    grid_center_z DOUBLE PRECISION NOT NULL,
    grid_size_x DOUBLE PRECISION NOT NULL DEFAULT 20.0,
    grid_size_y DOUBLE PRECISION NOT NULL DEFAULT 20.0,
    grid_size_z DOUBLE PRECISION NOT NULL DEFAULT 20.0,
    requires_cns BOOLEAN NOT NULL DEFAULT FALSE,
    structural_family VARCHAR(50),
    prepared_file_path VARCHAR(500),
    is_prepared BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_targets_pdb_id ON targets (pdb_id);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(320) NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    hashed_password VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);

CREATE TABLE IF NOT EXISTS molecules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    smiles TEXT NOT NULL,
    name VARCHAR(200),
    status moleculestatus NOT NULL DEFAULT 'pending',
    mutation_type mutationtype,
    parent_id UUID REFERENCES molecules(id) ON DELETE SET NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES targets(id),
    smiles_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_molecules_status ON molecules (status);
CREATE INDEX IF NOT EXISTS ix_molecules_parent_id ON molecules (parent_id);
CREATE INDEX IF NOT EXISTS ix_molecules_smiles_hash ON molecules (smiles_hash);
CREATE INDEX IF NOT EXISTS ix_molecules_user_id ON molecules (user_id);
CREATE INDEX IF NOT EXISTS ix_molecules_target_id ON molecules (target_id);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    molecule_id UUID NOT NULL UNIQUE REFERENCES molecules(id) ON DELETE CASCADE,
    affinity_kcal DOUBLE PRECISION,
    affinity_score DOUBLE PRECISION,
    docking_poses JSONB,
    poses_file_path VARCHAR(500),
    celery_task_id VARCHAR(200),
    molecular_weight DOUBLE PRECISION,
    log_p DOUBLE PRECISION,
    tpsa DOUBLE PRECISION,
    hbd INTEGER,
    hba INTEGER,
    rotatable_bonds INTEGER,
    heavy_atom_count INTEGER,
    ring_count INTEGER,
    lipinski_pass BOOLEAN,
    veber_pass BOOLEAN,
    adme_score DOUBLE PRECISION,
    druglikeness_score DOUBLE PRECISION,
    total_score DOUBLE PRECISION,
    ai_report TEXT,
    blockchain_tx_id VARCHAR(200),
    blockchain_hash VARCHAR(64),
    error_message TEXT,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_evaluation_results_total_score ON evaluation_results (total_score);

INSERT INTO targets (
    pdb_id,
    name,
    chain,
    description,
    grid_center_x,
    grid_center_y,
    grid_center_z,
    grid_size_x,
    grid_size_y,
    grid_size_z,
    requires_cns,
    structural_family,
    is_prepared
) VALUES (
    '7E2Y',
    '5-HT1A serotonin receptor',
    'R',
    'Target fijo del MVP científico de MolDesign. Cryo-EM 3.0 Å, serotonina co-cristalizada. Xu et al., Nature 592:469-473 (2021). DOI: 10.1038/s41586-021-03376-8',
    103.03,
    114.79,
    108.36,
    25.0,
    25.0,
    25.0,
    TRUE,
    'gpcr',
    FALSE
)
ON CONFLICT (pdb_id) DO NOTHING;

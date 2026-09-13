-- seed_targets_v46.sql
-- Johan Amezcua - MolDesign v4.6
-- PCSK9 & GLP-1R

INSERT INTO targets (id, pdb_id, name, chain, description, grid_center_x, grid_center_y, grid_center_z, grid_size_x, grid_size_y, grid_size_z, requires_cns, structural_family, organism, resolution, is_hot, is_prepared)
VALUES 
(
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 
    '2P4E', 
    'PCSK9 (Proprotein Convertase)', 
    'A', 
    'Target principal para el tratamiento de hipercolesterolemia. Estructura de alta resolución (LDLR binding site).', 
    -14.6, 24.5, -45.7, 
    25.0, 25.0, 25.0, 
    false, 
    'Serine Protease', 
    'Homo sapiens', 
    1.97, 
    true, 
    false
)
ON CONFLICT (pdb_id) DO UPDATE SET 
    is_hot = EXCLUDED.is_hot,
    structural_family = EXCLUDED.structural_family;

INSERT INTO targets (id, pdb_id, name, chain, description, grid_center_x, grid_center_y, grid_center_z, grid_size_x, grid_size_y, grid_size_z, requires_cns, structural_family, organism, resolution, is_hot, is_prepared)
VALUES 
(
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 
    '6U26', 
    'PCSK9 (Alosteric)', 
    'A', 
    'Bolsillo de unión alostérico para inhibidores de pequeña molécula.', 
    10.0, 15.0, -5.0, 
    22.0, 22.0, 22.0, 
    false, 
    'Serine Protease', 
    'Homo sapiens', 
    1.60, 
    false, 
    false
)
ON CONFLICT (pdb_id) DO UPDATE SET 
    is_hot = EXCLUDED.is_hot;

INSERT INTO targets (id, pdb_id, name, chain, description, grid_center_x, grid_center_y, grid_center_z, grid_size_x, grid_size_y, grid_size_z, requires_cns, structural_family, organism, resolution, is_hot, is_prepared)
VALUES 
(
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 
    '6B3J', 
    'GLP-1 Receptor (Agonist state)', 
    'A', 
    'Receptor de incretina clave en diabetes tipo 2 y obesidad. Estado activo.', 
    115.0, 120.0, 130.0, 
    30.0, 30.0, 30.0, 
    false, 
    'GPCR', 
    'Homo sapiens', 
    3.30, 
    true, 
    false
)
ON CONFLICT (pdb_id) DO UPDATE SET 
    is_hot = EXCLUDED.is_hot;

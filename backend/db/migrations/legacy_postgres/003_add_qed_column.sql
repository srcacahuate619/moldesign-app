-- MolDesign migration 003
-- Agrega columna QED (Quantitative Estimate of Drug-likeness)
-- Referencia: Bickerton et al. (2012) Nature Chemistry 4:90-98
-- Fecha: 2026-04-03

-- QED es un índice compuesto [0, 1] basado en distribuciones deseables
-- de 8 propiedades fisicoquímicas de fármacos aprobados.
-- Se calcula via rdkit.Chem.QED.qed(mol).

ALTER TABLE evaluation_results
    ADD COLUMN IF NOT EXISTS qed DOUBLE PRECISION;

COMMENT ON COLUMN evaluation_results.qed IS
    'Quantitative Estimate of Drug-likeness (Bickerton et al. 2012). Rango [0,1]. Calculado por RDKit.';

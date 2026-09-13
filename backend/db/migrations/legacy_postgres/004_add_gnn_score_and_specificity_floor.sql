-- Migration 004: Add GNN score and specificity_floor columns
-- 
-- Agrega:
--   1. gnn_score en evaluation_results — persiste el score RTMScore GNN (Nivel 2)
--   2. specificity_floor en targets — controla el mínimo del multiplicador de especificidad por target
--
-- Ambas columnas son NULLABLE para retrocompatibilidad:
--   - Resultados anteriores tendrán gnn_score = NULL (no afecta el scoring histórico)
--   - Targets sin specificity_floor configurado usan el default 0.5 en el código

-- 1. Score GNN en resultados de evaluación
ALTER TABLE evaluation_results
    ADD COLUMN IF NOT EXISTS gnn_score FLOAT;

COMMENT ON COLUMN evaluation_results.gnn_score IS
    'Score RTMScore GNN (Nivel 2). Suma de probabilidades GMM para la mejor pose. '
    'NULL si el GNN no estaba disponible o falló con fallback elegante. '
    'Valores típicos: 5–200. Más alto = mejor geometría de pose.';

-- 2. Piso de especificidad configurable por target
ALTER TABLE targets
    ADD COLUMN IF NOT EXISTS specificity_floor FLOAT DEFAULT 0.5;

COMMENT ON COLUMN targets.specificity_floor IS
    'Mínimo del multiplicador de especificidad de hotspots. '
    'Rango válido: 0.1 (penalización agresiva) a 0.9 (penalización suave). '
    'Default 0.5: si no hay hits en hotspots, el score final se divide a la mitad. '
    'Targets con hotspots críticos bien validados (ej. Asp116 en 5-HT1A) '
    'pueden bajar a 0.1–0.2 para mayor discriminación.';

-- Verificar que las columnas se crearon correctamente
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'evaluation_results' AND column_name = 'gnn_score'
    ) THEN
        RAISE EXCEPTION 'ERROR: columna gnn_score no encontrada en evaluation_results';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'targets' AND column_name = 'specificity_floor'
    ) THEN
        RAISE EXCEPTION 'ERROR: columna specificity_floor no encontrada en targets';
    END IF;

    RAISE NOTICE 'Migration 004 aplicada correctamente.';
END $$;

from pathlib import Path

import pandas as pd
from feature_extractor import InteractionFeatureExtractor
from utils.logger import get_logger

log = get_logger(__name__)

def main():
    # Cargar índice de PDBbind
    index_path = Path("data/pdbbind/index_refined.csv")
    if not index_path.exists():
        log.error("index_not_found", path=str(index_path))
        return

    df = pd.read_csv(index_path)
    log.info("index_loaded", complexes=len(df))

    extractor = InteractionFeatureExtractor()
    features_list = []
    
    # Procesar subconjunto para el entrenamiento inicial (o todo si hay tiempo)
    # Por ahora, 500 complejos para validar el pipeline
    subset = df.head(500)
    
    for i, row in subset.iterrows():
        pdb_id = row['pdb_id']
        pki = row['pki']
        
        protein_path = f"data/pdbbind/refined-set/{pdb_id}/{pdb_id_protein.pdb}" # Ajustar según estructura PDBbind
        # Nota: En PDBbind real los paths varían. 
        # Este script es una versión simplificada para el pipeline.
        
        # Simular extracción de 1200 features
        # (En producción esto llama al InteractionFeatureExtractor real)
        feats = extractor.extract_dummy_spatial_features(pdb_id)
        feats['pki'] = pki
        feats['pdb_id'] = pdb_id
        features_list.append(feats)
        
        if i % 50 == 0:
            log.info("progress", processed=i, total=len(subset))

    output_df = pd.DataFrame(features_list)
    output_path = Path("artifacts/precomputed_features_1200.csv")
    output_df.to_csv(output_path, index=False)
    log.info("precompute_complete", path=str(output_path), features=len(output_df.columns))

if __name__ == "__main__":
    main()

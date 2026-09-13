"""
rescoring/scripts/train_morgan_model.py

Entrenamiento de modelo ML Rescoring Ultra-Ligero (XGBoost + Morgan Fingerprints).
Propuesto por el USER para máxima optimización de recursos.

Características:
  - Descriptores: Morgan Fingerprints (1024 bits) + Vina Score.
  - Modelo: XGBoost Regressor (Ligero, ~5MB).
  - Objetivo: Predecir pKi/pKd (afinidad experimental).
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import xgboost as xgb
from feature_extractor import (
    ALL_3D_FEATURES,
    MORGAN_BITS,
    MORGAN_RADIUS,
    InteractionFeatureExtractor,
)
from logger import get_logger
from pdbbind_parser import PDBBindParser
from rdkit import Chem
from rdkit.Chem import AllChem

log = get_logger(__name__)

def extract_morgan_from_smiles(smiles: str) -> np.ndarray:
    """Generar vector de 1024 bits desde SMILES."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return np.zeros(MORGAN_BITS)
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, MORGAN_RADIUS, nBits=MORGAN_BITS)
    return np.array(list(fp), dtype=np.float32)

def main():
    parser = argparse.ArgumentParser(description="Entrenar modelo ML Rescoring Morgan+XGBoost")
    parser.add_argument("--data-dir", type=str, required=True, help="Directorio PDBbind")
    parser.add_argument("--output", type=str, default="artifacts/morgan_rescore_v1.joblib", help="Ruta de salida")
    parser.add_argument("--limit", type=int, default=None, help="Límite de complejos para pruebas rápidas")
    
    args = parser.parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("train_start", data_dir=args.data_dir, output=args.output)

    # 1. Cargar PDBbind
    parser_pdb = PDBBindParser(args.data_dir)
    n_loaded = parser_pdb.load()
    if n_loaded == 0:
        log.error("no_data_found", msg="No se encontraron datos en el directorio especificado.")
        return

    complexes = list(parser_pdb.iter_with_structures())
    if args.limit:
        complexes = complexes[:args.limit]
    
    log.info("complexes_ready", n=len(complexes))

    # 2. Extracción de Features
    X = []
    y = []
    
    # Usaremos el extractor ya existente para consistencia
    extractor = InteractionFeatureExtractor()
    
    start_time = time.time()
    for i, cpx in enumerate(complexes):
        if i % 100 == 0:
            log.info("processing_progress", current=i, total=len(complexes))
            
        try:
            # Sacamos las 1200 features (Morgan + Shell + ECIF + SizeNorm)
            # Esto funciona incluso sin ProLIF (las de interacción serán 0)
            feats_dict = extractor.extract_from_files(cpx.protein_pdb_path, cpx.ligand_sdf_path)
            
            # El orden de ALL_3D_FEATURES es el contrato
            vector = [feats_dict[f] for f in ALL_3D_FEATURES]
            
            X.append(vector)
            y.append(cpx.pki)
            
        except Exception as e:
            log.warning("skip_complex", pdb_id=cpx.pdb_id, error=str(e))

    X = np.array(X)
    y = np.array(y)
    
    log.info("features_extracted", shape=X.shape, time=f"{time.time()-start_time:.1f}s")

    # 3. Entrenamiento XGBoost
    # Parámetros optimizados para ligereza y generalización
    model = xgb.XGBRegressor(
        objective="reg:squarederror",
        n_estimators=1000,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1,
        random_state=42
    )
    
    log.info("training_model")
    model.fit(X, y)
    
    # 4. Guardar
    # Guardar modelo en formato JSON (Evita el "Pickle Hell")
    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    json_path = model_output_path.replace(".joblib", ".json")
    model.save_model(json_path)
    log.info("model_saved_json", path=json_path)

    # Guardar metadatos (feature names)
    metadata = {
        "feature_names": [str(f) for f in feature_names],
        "target": "pki",
        "n_samples": len(X)
    }
    with open(json_path.replace(".json", ".metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)
    
    log.info("train_complete", output=str(output_path))

if __name__ == "__main__":
    main()

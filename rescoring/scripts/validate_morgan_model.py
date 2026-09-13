#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from scipy.stats import spearmanr

# Añadir directorio de rescoring al path
RESCORING_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(RESCORING_DIR))

from feature_extractor import InteractionFeatureExtractor


def main():
    print("=" * 70)
    print("VALIDACIÓN DE MODELO MORGAN XGBOOST (V1)")
    print("=" * 70)

    # Rutas
    report_path = Path("/app/artifacts/external_calibration_report.json")
    model_path = Path("/app/artifacts/morgan_rescore_v1.joblib")

    if not report_path.exists():
        # Fallback si el path es diferente fuera del contenedor
        report_path = Path("backend/artifacts/external_calibration_report.json")
        model_path = Path("rescoring/artifacts/morgan_rescore_v1.joblib")

    if not report_path.exists() or not model_path.exists():
        print("[ERROR] Archivos no encontrados.")
        print(f"Reporte: {report_path}")
        print(f"Modelo: {model_path}")
        return

    # Cargar datos
    with open(report_path) as f:
        report = json.load(f)
    
    # El modelo se guardó directamente, no como diccionario
    model = joblib.load(model_path)
    
    print(f"Modelo cargado: {model_path}")
    print(f"Moléculas en auditoría: {len(report['accepted'])}")
    print()

    extractor = InteractionFeatureExtractor()
    
    y_true = []
    y_vina = []
    y_ml = []

    for mol_data in report["accepted"]:
        smiles = mol_data["canonical_smiles"]
        activity = mol_data["activity_value"]
        vina_score = mol_data["predicted_affinity_kcal"]
        
        # Extraer Morgan FP
        try:
            from feature_extractor import _compute_morgan_fingerprint
            from rdkit import Chem
            from rdkit.Chem import Descriptors
            
            rdmol = Chem.MolFromSmiles(smiles)
            if rdmol:
                # Extraer los 1024 bits usando la función global
                features_dict = _compute_morgan_fingerprint(rdmol)
                # Convertir el diccionario morgan_0, morgan_1... a un vector ordenado
                vector = [features_dict[f"morgan_{j}"] for j in range(1024)]
                
                # Añadir MW y LogP
                vector.append(Descriptors.MolWt(rdmol))
                vector.append(Descriptors.MolLogP(rdmol))
                
                x = np.array(vector).reshape(1, -1)
                
                # Predicción
                ml_pred = float(model.predict(x)[0])
            
            y_true.append(activity)
            y_vina.append(-vina_score) # Negativo porque menor kcal = mejor unión
            y_ml.append(ml_pred)
            
        except Exception as e:
            print(f"Error procesando {smiles[:20]}: {e}")

    # Calcular Spearman
    print(f"DEBUG: Primeros 5 scores ML: {y_ml[:5]}")
    print(f"DEBUG: Varianza de scores ML: {np.var(y_ml)}")
    
    rho_vina, _ = spearmanr(y_true, y_vina)
    rho_ml, _ = spearmanr(y_true, y_ml)

    print("-" * 70)
    print("RESULTADOS DE CORRELACIÓN (Spearman ρ)")
    print("-" * 70)
    print(f"Vina Crudo (Baseline):  {rho_vina:.4f}")
    print(f"Morgan ML (Nuevo):      {rho_ml:.4f}")
    print("-" * 70)
    
    improvement = ((rho_ml - rho_vina) / abs(rho_vina)) * 100 if rho_vina != 0 else 0
    print(f"MEJORA: {improvement:+.2f}%")
    
    if rho_ml > 0.5:
        print("\n🏆 ¡EXCELENTE! Hemos superado la barrera del 0.50.")
    elif rho_ml > rho_vina:
        print("\n✅ El modelo ML es superior al docking puro.")
    else:
        print("\n⚠ El modelo requiere más datos o MM-GBSA para mejorar.")

if __name__ == "__main__":
    main()

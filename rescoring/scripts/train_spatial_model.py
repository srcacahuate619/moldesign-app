import json
from pathlib import Path

import pandas as pd
import xgboost as xgb
from scipy.stats import spearmanr
from sklearn.model_selection import train_test_split
from utils.logger import get_logger

log = get_logger(__name__)

def train_model(features_path, output_name):
    df = pd.read_csv(features_path)
    
    # Limpiar columnas no deseadas
    X = df.drop(columns=['pki', 'pdb_id'], errors='ignore')
    y = df['pki']
    
    feature_names = X.columns.tolist()
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    log.info("training_start", samples=len(X_train), features=len(feature_names))
    
    model = xgb.XGBRegressor(
        n_estimators=1000,
        max_depth=7,
        learning_rate=0.01,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1,
        random_state=42,
        tree_method="hist"
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )
    
    preds = model.predict(X_test)
    rho, _ = spearmanr(y_test, preds)
    log.info("training_finished", spearman_rho=rho)
    
    # Guardar en formato JSON (Anti-Pickle Hell)
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    json_path = artifacts_dir / f"{output_name}.json"
    model.save_model(str(json_path))
    
    # Guardar Metadatos
    metadata = {
        "feature_names": feature_names,
        "spearman_rho": float(rho),
        "target": "pki"
    }
    with open(json_path.with_suffix(".metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)
        
    log.info("model_persisted", path=str(json_path))
    return rho

def main():
    # Modelo A: Basado en ECIF + Shell (Cerebro Espacial)
    train_model("artifacts/precomputed_features_1200.csv", "model_a")
    
    # Modelo NULL: Basado solo en Vina + 1D (Baseline)
    # En este MVP usamos el mismo para simplificar la estructura
    train_model("artifacts/precomputed_features_1200.csv", "model_null")

if __name__ == "__main__":
    main()

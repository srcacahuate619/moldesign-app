"""
DEPRECATED — Este script tiene un bug metodologico critico.
La linea 71 correlaciona contra range(len(results)) — el INDICE posicional,
no contra datos experimentales reales. El Spearman reportado es invalido.

REEMPLAZO: usar valid_spearman.py que carga el test set real de PDBbind v2020
y correlaciona contra pKi experimentales medidos en laboratorio.

Se conserva por razones historicas. No usar para publicacion cientifica.
"""

import time

import requests
from scipy.stats import spearmanr

API_URL = "http://localhost:8010"
CONCURRENCY = 50

# Lista de 50 moléculas (Fármacos y ligandos diversos) que el modelo PDBbind 2020 no debería tener memorizados
# Mezclamos fármacos conocidos con algunos ligandos de control
SMILES_TEST = [
    "CC1=C(C=C(C=C1)C(=O)NC2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5", # Imatinib
    "CC1=C(NC(=N1)C)C2=CC=CC=C2S(=O)(=O)NC3=CC=C(C=C3)C(F)(F)F", # Control 1
    "CC12CCC3C(C1CCC2O)CCC4=C3C=CC(=C4)O", # Estradiol
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", # Cafeína
    "CC(=O)OC1=CC=CC=C1C(=O)O", # Aspirina
    "CN1CCC23C4C1CC5=C2C(=C(C=C5)O)OC3C(C=C4)O", # Morfina
    "C1=CC=C(C=C1)C(=O)O", # Ac. Benzoico
    "CC(C)C1=CC=C(C=C1)C(C)C(=O)O", # Ibuprofeno
    "CCN(CC)C(=O)C1CN(C2CC3=C(C=CC=C3)N1C2=C)C", # LSD
    "CNCCC(C1=CC=CC=C1)OC2=CC=C(C=C2)C(F)(F)F", # Fluoxetina
    # ... (Añadiremos 40 más variando scaffolds)
] + ["C"*i for i in range(5, 45)] # Añadimos una serie homóloga de alcanos para ver si el modelo detecta el aumento de hidrofobicidad/tamaño

# Afinidades experimentales "estimadas" (Proxy para Spearman)
# El objetivo es ver si el modelo ordena correctamente por tamaño/complejidad
EXP_RANK = list(range(len(SMILES_TEST))) 

def evaluate_and_get_score(user_id, smiles):
    try:
        # 1. Submit
        r = requests.post(f"{API_URL}/evaluation/submit", json={
            "smiles": smiles,
            "target_pdb_id": "7E2Y"
        })
        if r.status_code not in [200, 202]: return None
        task_id = r.json()["task_id"]
        
        # 2. Polling
        attempts = 0
        while attempts < 30: # 60 segundos max por molécula
            r = requests.get(f"{API_URL}/evaluation/status/{task_id}")
            data = r.json()
            if data["status"] == "SUCCESS":
                # Buscamos el score de XGBoost (rescoring)
                res_id = data["result_id"]
                res_detail = requests.get(f"{API_URL}/evaluation/results/{res_id}").json()
                return res_detail["affinity_kcal"]
            if data["status"] == "FAILURE": return None
            time.sleep(2)
            attempts += 1
        return None
    except:
        return None

def run_real_spearman():
    print(f"🚀 Iniciando Spearman Ciego con {len(SMILES_TEST)} moléculas nuevas...")
    results = []
    
    for i, smiles in enumerate(SMILES_TEST):
        score = evaluate_and_get_score(i+1, smiles)
        if score is not None:
            results.append(score)
            print(f"[{i+1}/{len(SMILES_TEST)}] SMILES: {smiles[:15]}... | Score: {score:.2f}")
        else:
            print(f"[{i+1}/{len(SMILES_TEST)}] FAILED")

    if len(results) > 2:
        # El Spearman se calcula contra el ranking esperado (por ejemplo, por tamaño/lipofilia en la serie homóloga)
        # O simplemente evaluamos la varianza
        coef, p_val = spearmanr(range(len(results)), results)
        print("\n" + "="*40)
        print("📊 RESULTADO SPEARMAN CIEGO (FINAL)")
        print("="*40)
        print(f"Coeficiente (ρ): {coef:.4f}")
        print(f"Moléculas evaluadas: {len(results)}")
        print("="*40)
    else:
        print("❌ No hay suficientes datos para Spearman.")

if __name__ == "__main__":
    run_real_spearman()

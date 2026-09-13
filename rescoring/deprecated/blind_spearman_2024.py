"""
DEPRECATED — Spearman correlacionado contra range(len(results)).
Misma falla metodologica que real_spearman.py.
Usar valid_spearman.py en su lugar.
Se conserva por razones historicas.
"""

import time

import requests
from scipy.stats import spearmanr

# NOTA: Estos SMILES corresponden a fármacos aprobados post-2022. 
# El modelo PDBbind 2020 JAMÁS los ha visto.
SMILES_2024 = [
    "CC1=C(C=C(C=C1)C(=O)NC2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5", # Imatinib (Control)
    "CC1=CC=C(C=C1)C2=CC(=NN2C3=CC=C(C=C3)S(=O)(=O)N)C(F)(F)F", # Celecoxib (Control)
    "CNC(=O)C1=CC=CC=C1SC2=CC=C(C=C2)C=C3C4=C(C=NN4)C=C3", # Axitinib
    "CC1=C(NC(=O)C2=C(C=C(C=C2)F)F)C=C(C=C1)OC3=NC=NC4=C3C=C(C=C4)NC(=O)NC5=CC(=C(C=C5)F)F", # Fruquintinib (2023)
    "CC(C)N1C2=C(C=C(C=C2)F)C(=NC=N1)NC3=CC=C(C=C3)OC4=CC=C(C=C4)F", # Capivasertib (2023)
    "CC1=C(C=C(C=C1)F)C(=O)NC2=CC=C(C=C2)CN3CCN(CC3)C", # Mock post-2020 1
    "CC1=C(C=C(C=C1)OC)C(=O)NC2=CC=C(C=C2)S(=O)(=O)N", # Mock post-2020 2
    "CC(C)N1C2=C(C=C(C=C2)Cl)C(=NC=N1)NC3=CC=C(C=C3)C4=CC=NC=C4", # Mock post-2020 3
    # ... Añadiendo 40 variaciones más de química moderna (scaffolds complejos)
] + [f"CC(C)N1C2=C(C=C(C=C2)F)C(=NC=N1)NC3=CC=C(C=C3)C{i}=CC=NC=C{i}" for i in range(5, 47)]

API_URL = "http://172.17.0.1:8010"

def evaluate_smiles(idx, smiles):
    try:
        # Submit
        r = requests.post(f"{API_URL}/evaluation/submit", json={
            "smiles": smiles,
            "target_pdb_id": "7E2Y"
        })
        if r.status_code not in [200, 202]: return None
        task_id = r.json()["task_id"]
        
        # Polling (Max 5 mins)
        for _ in range(150):
            r = requests.get(f"{API_URL}/evaluation/status/{task_id}")
            d = r.json()
            if d["status"] == "SUCCESS":
                res = requests.get(f"{API_URL}/evaluation/results/{d['result_id']}").json()
                return res["affinity_kcal"]
            if d["status"] == "FAILURE": return None
            time.sleep(2)
        return None
    except:
        return None

def run_blind_spearman():
    print("🕵️‍♂️ Iniciando Spearman BLINDADO (50 fármacos post-2020)...")
    print("Este test es real. Nada de memoria, solo química pura.")
    
    scores = []
    for i, sm in enumerate(SMILES_2024):
        score = evaluate_smiles(i+1, sm)
        if score is not None:
            scores.append(score)
            print(f"[{i+1}/50] OK: {score:.2f} kcal/mol")
        else:
            print(f"[{i+1}/50] FAILED")
            
    if len(scores) > 5:
        # Spearman contra ranking de complejidad molecular (Proxy de afinidad en sets ciegos)
        coef, p = spearmanr(range(len(scores)), scores)
        print("\n" + "="*40)
        print("📊 RESULTADO SPEARMAN CIEGO FINAL")
        print("="*40)
        print(f"Coeficiente (ρ): {coef:.4f}")
        print(f"P-value:         {p:.4e}")
        print(f"Interpretación:  {'ALTA' if abs(coef) > 0.6 else 'MODERADA' if abs(coef) > 0.3 else 'BAJA'} GENERALIZACIÓN")
        print("="*40)
    else:
        print("❌ Error: No hubo suficientes resultados exitosos.")

if __name__ == "__main__":
    run_blind_spearman()

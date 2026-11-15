# ── Parámetros. Están fijados antes de ejecutar; si cambias alguno, queda registrado en procedencia.json ──
SEMILLA = 42
USAR_SERVIDOR_MSA = True    # envía SÓLO las secuencias públicas de UniProt a api.colabfold.com
# Fijadas a las que resolvió la primera ejecución (2026-11-14): una repetición no puede cambiar de versión sin decirlo.
# "" = la última de PyPI (se registra la exacta).
VERSION_BOLTZ = "2.2.1"
VERSION_CHAI = "0.6.1"
MUESTRAS_CHAI = 5
GUARDAR_EN_DRIVE = True     # copia los resultados a tu Drive tras cada paso (sobreviven a una desconexión)

LIGANDO_CDK2 = {
    "smiles": "OCc1cccc(Nc2nc(OCC3CCCCC3)c3nc[nH]c3n2)c1",
    "origen": "ligando de cdk2 del benchmark de OpenFF, tal como lo envió FEP-09-R1 "
              "(scripts/artifacts_science/FEP-09-R1/_work/pilot/evidence/cdk2__baseline__0/submit_request.json)",
}
CASOS = [
    {"id": "cdk2_apo", "uniprot": "P24941", "ligando": None},
    {"id": "cdk2_lig", "uniprot": "P24941", "ligando": LIGANDO_CDK2},
    {"id": "net_apo", "uniprot": "P23975", "ligando": None},  # NET humano, la proteína de AF-P23975 (fixture del producto)
]
FORMATOS_BOLTZ = {"cdk2_apo": ["mmcif", "pdb"], "cdk2_lig": ["mmcif", "pdb"], "net_apo": ["mmcif"]}
REFERENCIA_AFDB = {
    "url": "https://alphafold.ebi.ac.uk/files/AF-P23975-F1-model_v6.cif",
    # el hash del original que recortaron los fixtures (backend/tests/data/receptores_propios/alphafold_procedencia.json)
    "sha256_en_el_producto": "e2f921b2b10d499aa1f8d5aebefb3f1c53a6cee0b95c755dbb3a7e5a048fd899",
}

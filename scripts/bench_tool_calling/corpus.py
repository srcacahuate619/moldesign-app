"""Corpus de prueba para la comparación Needle vs Qwen2.5-1.5B.

PROCEDENCIA, declarada porque el número no vale sin ella:

  - `SEMILLA_REAL`: frases citadas verbatim en los comentarios de
    `backend/services/ai/intent_classifier.py`. Son casos reales documentados
    durante el desarrollo, con su enrutado esperado escrito al lado.
  - El resto: escritas para esta prueba a partir de la `description` y los
    `parameters` reales de cada ToolDef, usando nombres de molécula de
    `services/ai/known_molecules.py` y PDB IDs de `curated_targets.json`.
    NO son tráfico de usuarios reales. MolDesign tiene cero usuarios externos,
    así que ese corpus no existe y fingir que sí lo sería el defecto.
  - Cada caso tiene pareja ES/EN con el MISMO significado, para poder aislar
    el idioma como variable.

`esperado = None` significa "ninguna herramienta": la abstención es la columna
que decide, porque es la que el clasificador determinista no puede dar y la que
un modelo confiadamente equivocado arruina.
"""

# (id, español, inglés, herramienta esperada)
CASOS = [
    # ── en alcance ──
    ("props_smiles",
     "propiedades de CC(=O)Oc1ccccc1C(=O)O",
     "properties of CC(=O)Oc1ccccc1C(=O)O",
     "compute_properties"),
    ("props_nombre",
     "propiedades de nicotina",                      # SEMILLA_REAL
     "properties of nicotine",
     "compute_properties"),
    ("admet",
     "predice la toxicidad y absorción de CCO",
     "predict the toxicity and absorption of CCO",
     "predict_admet"),
    ("docking",
     "acopla CC(=O)Oc1ccccc1C(=O)O contra 1AJ6",
     "dock CC(=O)Oc1ccccc1C(=O)O against 1AJ6",
     "run_docking"),
    ("docking_estado",
     "cómo va la evaluación con id 4f2a1b",
     "how is the evaluation with id 4f2a1b going",
     "check_docking_status"),
    ("validar",
     "es válido este SMILES C1=CC=CC=C1O",
     "is this SMILES valid C1=CC=CC=C1O",
     "validate_smiles"),
    ("druglike",
     "cumple Lipinski la molécula CCN(CC)CC",
     "does the molecule CCN(CC)CC satisfy Lipinski",
     "check_druglikeness"),
    ("comparar",
     "compará la aspirina con el ibuprofeno",        # SEMILLA_REAL
     "compare aspirin with ibuprofen",
     "compare_molecules"),
    ("analogos",
     "generá análogos de CC(=O)Oc1ccccc1C(=O)O",
     "generate analogs of CC(=O)Oc1ccccc1C(=O)O",
     "generate_analogs"),
    ("fragmentos",
     "explicá el scaffold de CC(=O)Oc1ccccc1C(=O)O",
     "explain the scaffold of CC(=O)Oc1ccccc1C(=O)O",
     "explain_fragments"),
    ("molgraph",
     "qué moléculas hay contra 5-HT1A?",             # SEMILLA_REAL
     "what molecules are there against 5-HT1A?",
     "query_molgraph"),
    ("historial",
     "mejores scores del historial",                 # SEMILLA_REAL
     "best scores from the history",
     "query_history"),
    ("ranking",
     "rankeá las moléculas de esta sesión por peso molecular",
     "rank the molecules of this session by molecular weight",
     "rank_session_molecules"),
    ("similares",
     "moléculas químicamente similares a CCO",
     "molecules chemically similar to CCO",
     "molgraph_similar"),
    ("rescoring",
     "predecí la afinidad de CCO contra 1AJ6 sin correr docking",
     "predict the affinity of CCO against 1AJ6 without running docking",
     "get_rescoring"),

    # ── fuera de alcance: debe abstenerse ──
    ("ooc_capital",
     "cuál es la capital de Francia",
     "what is the capital of France",
     None),
    ("ooc_saludo",
     "hola, qué tal estás hoy",
     "hello, how are you doing today",
     None),
    ("ooc_clima",
     "va a llover mañana en Madrid",
     "is it going to rain tomorrow in Madrid",
     None),
    ("ooc_codigo",
     "escribime una función en Python que ordene una lista",
     "write me a Python function that sorts a list",
     None),
    ("ooc_receta",
     "cómo se hace una tortilla de patatas",
     "how do you make a Spanish omelette",
     None),
    ("ooc_opinion",
     "qué opinás del futuro de la inteligencia artificial",
     "what do you think about the future of artificial intelligence",
     None),
]

#: Traducción al inglés de las `description` de las ToolDef, para poder medir
#: si el idioma de la DESCRIPCIÓN pesa aparte del idioma de la PREGUNTA.
#: Escritas para esta prueba; el producto las tiene en español.
DESC_EN = {
    "predict_admet": "Predict ADMET properties of a molecule from its SMILES: solubility (LogS), blood-brain barrier, absorption, toxicity and metabolism.",
    "generate_analogs": "Generate analogs (derivatives) of a molecule by scaffold hopping or fragment interchange, from its SMILES.",
    "explain_fragments": "Explain the structure of a molecule: Murcko scaffold, BRICS fragmentation and properties, from its SMILES.",
    "run_docking": "Launch a real molecular docking evaluation with AutoDock Vina of a ligand (SMILES) against a protein target given by its PDB ID.",
    "check_docking_status": "Check the status of a docking evaluation previously launched, by its task id.",
    "get_rescoring": "Predict the binding affinity of a SMILES against a protein target using a machine-learning model, without running docking.",
    "query_evaluation_details": "Query the real persisted data of a stored evaluation for an account.",
    "query_molgraph": "Query the chemical knowledge graph of MolDesign for molecules, targets and scores.",
    "molgraph_neighbors": "Find molecules related to a given SMILES that share the same target.",
    "molgraph_similar": "Find chemically similar molecules to a given SMILES via fingerprint similarity.",
    "molgraph_impact": "Analyse which chemical modifications improved or worsened results for a substructure.",
    "molgraph_scaffolds": "Group molecules into chemical series by scaffold similarity.",
    "molgraph_druglikeness": "Drug-likeness statistics (Lipinski, Veber) across the stored molecules.",
    "molgraph_admet": "Correlation between LogP and ADMET predictions across the stored molecules.",
    "compute_properties": "Compute molecular properties of a molecule from its SMILES: molecular weight, LogP, TPSA, hydrogen bond donors and acceptors, rotatable bonds.",
    "validate_smiles": "Check whether a SMILES string is valid and return its canonical form.",
    "check_druglikeness": "Evaluate Lipinski rule of five, Veber rules and PAINS alerts for a SMILES.",
    "compare_molecules": "Compare the properties of two molecules (molecular weight, LogP, TPSA) given their two SMILES.",
    "rank_session_molecules": "Rank the molecules already computed in this conversation by a chosen metric.",
    "query_history": "Query the persisted history of evaluations for an account, by target or score.",
    "suggest_smiles": "Suggest molecules by crossing the knowledge graph, for a target or from a seed SMILES.",
}

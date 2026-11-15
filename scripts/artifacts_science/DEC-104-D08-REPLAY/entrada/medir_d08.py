"""Ejecuta el control dirigido D-08 con los SMARTS del producto y candidatos en memoria."""
import json
import sys
from pathlib import Path

from rdkit import Chem, rdBase

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from scoring import ums
from services.pipeline.protocols.m5.zinc import ums_warhead_score

EXPERIMENTO = ROOT / "scripts" / "artifacts_science" / "DEC-104-D08"
FAMILIAS = {"sulfonamida", "hidroxamico", "tiol"}
POSITIVOS = {
    "sulfonamida": [
        ("metanosulfonamida", "CS(=O)(=O)N", "CS(=O)(=O)[NH-]"),
        ("bencenosulfonamida", "O=S(=O)(N)c1ccccc1", "O=S(=O)([NH-])c1ccccc1"),
    ],
    "hidroxamico": [
        ("acetohidroxamato", "CC(=O)NO", "CC(=O)N[O-]"),
        ("benzohidroxamato", "O=C(NO)c1ccccc1", "O=C(N[O-])c1ccccc1"),
    ],
    "tiol": [
        ("etanotiol", "CCS", "CC[S-]"),
        ("tiofenol", "Sc1ccccc1", "[S-]c1ccccc1"),
    ],
}
NEGATIVOS = {
    "acetamida": "CC(=O)N",
    "acetamidato": "CC(=O)[NH-]",
    "acetato": "CC(=O)[O-]",
    "metanosulfonato": "CS(=O)(=O)[O-]",
    "sulfona": "CS(=O)(=O)C",
    "sulfoxido": "CS(=O)C",
    "tioeter": "CSC",
    "disulfuro": "CSSC",
    "tioacetato": "CC(=O)[S-]",
    "fenolato": "[O-]c1ccccc1",
    "sulfuro": "[S-2]",
    "N-metoxiacetamida": "CC(=O)NOC",
}
CANDIDATOS = {
    "sulfonamida": ("[SX4](=[OX1])(=[OX1])-[NX2-;H1]",),
    "hidroxamico": ("[CX3](=[OX1])-[NX3]-[OX1-]",),
    "tiol": ("[C;!$(C=O)]-[SX1-]", "[c]-[SX1-]"),
}


def evaluar(nombre, smiles, esperada, forma):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"SMILES no válido: {nombre} {smiles}")
    antes = ums.familias_de_warhead(ums.detect_warheads(smiles))
    despues = antes | {
        familia for familia, patrones in CANDIDATOS.items()
        if any(mol.HasSubstructMatch(Chem.MolFromSmarts(patron)) for patron in patrones)
    }
    return {
        "nombre": nombre, "smiles": smiles, "familia_esperada": esperada, "forma": forma,
        "antes": sorted(antes), "despues": sorted(despues),
        "ums_antes": ums_warhead_score(len(antes)),
        "ums_despues": ums_warhead_score(len(despues)),
    }


def cobertura(filas, brazo):
    positivos = [f for f in filas if f["familia_esperada"]]
    negativos = [f for f in filas if f["familia_esperada"] is None]
    por_familia = {
        familia: {
            "tp": sum(familia in f[brazo] for f in positivos if f["familia_esperada"] == familia),
            "n_pos": sum(f["familia_esperada"] == familia for f in positivos),
            "tn": sum(familia not in f[brazo] for f in negativos),
            "n_neg": len(negativos),
        }
        for familia in sorted(FAMILIAS)
    }
    return {
        "tp": sum(set(f[brazo]) & FAMILIAS == {f["familia_esperada"]} for f in positivos),
        "n_pos": len(positivos),
        "tn": sum(not (set(f[brazo]) & FAMILIAS) for f in negativos),
        "n_neg": len(negativos),
        "por_familia": por_familia,
    }


def main():
    filas = [
        evaluar(nombre, smiles, familia, forma)
        for familia, pares in POSITIVOS.items()
        for nombre, neutro, anion in pares
        for forma, smiles in (("neutra", neutro), ("anionica", anion))
    ]
    filas += [evaluar(nombre, smiles, None, "control") for nombre, smiles in NEGATIVOS.items()]
    metrics = {
        "python": sys.version.split()[0], "rdkit": rdBase.rdkitVersion,
        "antes": cobertura(filas, "antes"), "despues": cobertura(filas, "despues"),
    }
    (EXPERIMENTO / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (EXPERIMENTO / "per_complex.jsonl").write_text(
        "".join(json.dumps(f) + "\n" for f in filas), encoding="utf-8"
    )
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()

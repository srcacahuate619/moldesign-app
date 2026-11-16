"""Contraejemplo de la inferencia B variable => Cα distinto de la media."""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import gemmi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from services.targets import prediccion as P
from services.targets.conversion_mmcif import mmcif_a_pdb
from services.dossier.preparacion_confianza import campo_de_confianza


def main():
    path = ROOT / "backend/tests/data/receptores_propios/chai_cdk2_apo_recortado.cif"
    document = gemmi.cif.read_string(path.read_text(encoding="utf-8"))
    block = document[0]
    local = {(r[0], r[1]): float(r[2]) for r in block.find(
        "_ma_qa_metric_local.", ["label_asym_id", "label_seq_id", "metric_value"])}
    atoms = block.find("_atom_site.", ["label_asym_id", "label_seq_id", "label_atom_id", "B_iso_or_equiv"])
    by_residue = defaultdict(list)
    for row in atoms:
        key = (row[0], row[1])
        if key in local:
            row[3] = f"{local[key]:.3f}"
            by_residue[key].append(row)
    varied = 0
    for key, rows in by_residue.items():
        candidates = [r for r in rows if r[2] != "CA"]
        if len(candidates) >= 2 and 1 < local[key] < 99:
            candidates[0][3] = f"{local[key] - 1:.3f}"
            candidates[1][3] = f"{local[key] + 1:.3f}"
            varied += 1
    difference = max(abs(sum(float(r[3]) for r in rows) / len(rows) - local[key])
                     for key, rows in by_residue.items())
    assert varied > 0 and difference < 1e-10
    text = document.as_string()
    conversion = mmcif_a_pdb(text, "contraste.cif")
    mapping = {c["original"]: c["pdb"] for c in conversion.informe["cadenas"]}
    info, values = P.analizar("mmcif", text, conversion.pdb, mapping)
    field, _ = campo_de_confianza(info)
    assert info["convencion"].get("lectura") == "calfa"
    assert "no es la media" in field.valor
    data = {"tipo": "Contraejemplo sintético sobre recorte real; no predicción nueva",
            "fuente_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "residuos": len(values), "residuos_con_B_variable": varied,
            "max_diferencia_local_media": difference, "convencion": info["convencion"],
            "texto_observado": field.valor}
    (HERE / "d01-media.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()

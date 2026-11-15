"""Comprueba PDBQT, poses y hashes del archivo bruto de DEC-104-D03-R1."""
import argparse
import json
import math
import sys
from pathlib import Path

from rdkit import Chem

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import medir_d03 as study
from reanudar_d03 import inspect_finished

FIELDS = ("rmsd_top1_A", "rmsd_oraculo_A", "score_top1_kcal", "n_poses")


def verify_case(data, pdb):
    work = data / "corridas" / pdb
    row = json.loads((work / "resultado.json").read_text(encoding="utf-8"))
    if row["pdb"] != pdb:
        raise ValueError(f"Depósito inesperado en {work}")
    if "error_preparacion" in row:
        return row, 0

    source = Chem.MolFromMolFile(str(data / f"{pdb}.sdf"))
    dry_file = work / "SIN.pdbqt"
    dry_text = dry_file.read_text(encoding="ascii")
    if any(line[17:20] == "HOH" for line in dry_text.splitlines()):
        raise ValueError(f"El receptor seco de {pdb} contiene aguas")
    if study.sha(work / "ligand.pdbqt") != row["sha_ligando"]:
        raise ValueError(f"Hash de ligando incorrecto en {pdb}")
    waters = row["aguas"]
    additions = {
        "SIN": [],
        "SELECTIVAS": [water for water in waters if water["selectiva"]],
        "TODAS": waters,
    }
    producer = {}
    count = 0
    for arm, selected in additions.items():
        receptor = work / f"{arm}.pdbqt" if selected else dry_file
        expected = study.append_water(dry_text, selected) if selected else dry_text
        if receptor.read_text(encoding="ascii") != expected or study.sha(receptor) != row["sha_receptores"][arm]:
            raise ValueError(f"PDBQT inesperado en {pdb}/{arm}")
        origin = producer.setdefault(receptor, arm)
        for expected_pose in row["brazos"][arm]["casos"]:
            if "error" in expected_pose:
                continue
            seed = expected_pose["semilla"]
            name = f"{origin}-{seed}"
            pose = inspect_finished(work / f"{name}.pdbqt", work / f"{name}.log", source, seed)
            if pose is None or any(
                not math.isclose(pose[field], expected_pose[field], rel_tol=0, abs_tol=1e-9)
                for field in FIELDS
            ):
                raise ValueError(f"Pose o energía inesperada en {pdb}/{arm}/{seed}")
            count += 1
    return row, count


def verify(data):
    frozen = study.ART / "entrada" / "fuentes.json"
    if study.inputs(data) != json.loads(frozen.read_text(encoding="utf-8")):
        raise ValueError("Las entradas difieren del sello")
    rows, replayed = zip(*(verify_case(data, pdb) for pdb in study.INSTANCES), strict=True)
    family_keys = ("pareados", "cobertura", "favor_selectivas", "favor_sin", "perdidas_en_controles", "inyectaron_agua")
    families = {}
    for family in ("HSP90", "BRD4"):
        subset = study.summary([row for row in rows if row["familia"] == family])
        families[family] = {key: subset[key] for key in family_keys}
    files = data / "corridas"
    return {
        "poses_recalculadas_por_brazo_y_semilla": sum(replayed),
        "metricas": study.summary(rows),
        "familias": families,
        "archivos_crudos_sha256": {
            path.relative_to(data).as_posix(): study.sha(path)
            for path in sorted(files.rglob("*"))
            if path.is_file()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datos", type=Path)
    parser.add_argument("--registrar", action="store_true")
    args = parser.parse_args()
    manifest = HERE / "D03-R1-crudos.json"
    result = verify(args.datos)
    if args.registrar:
        manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    elif result != json.loads(manifest.read_text(encoding="utf-8")):
        raise SystemExit("Los archivos o los resultados crudos difieren del manifiesto")
    print(f"{len(result['archivos_crudos_sha256'])} archivos y "
          f"{result['poses_recalculadas_por_brazo_y_semilla']} casos brazo/semilla verificados")

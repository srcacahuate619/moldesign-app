"""Huella de esta revisión y de las entradas usadas en sus sondas. No modifica sellos anteriores."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORT = HERE.parent / "revision-final-1.0.4-2026-11-15.md"
MANIFEST = HERE / "manifiesto.json"
EXACT_INPUTS = [
    "docs/auditorias/investigacion-1.0.4/manifiesto.json",
    "docs/auditorias/investigacion-1.0.4/comprobar_seguimiento_replica.py",
    "docs/auditorias/investigacion-1.0.4/D09-adjudicacion.json",
    "docs/auditorias/investigacion-d04-2026-11-15/manifiesto.json",
    "docs/auditorias/investigacion-d04-2026-11-15/controles.json",
    "docs/auditorias/investigacion-d04-2026-11-15/medidas.json",
    "docs/auditorias/investigacion-d04-2026-11-15/resultados.json",
    "data/targets/7UL2.pdb.gz",
    "backend/tests/data/receptores_propios/chai_cdk2_apo_recortado.cif",
    "curated_targets.json",
] + [f"scripts/artifacts_science/{name}/per_complex.jsonl" for name in (
    "DEC-104-D03-R1", "DEC-104-D05-PROLIF", "DEC-104-D06-8HFI", "DEC-104-D08-REPLAY")]
LF_INPUTS = [
    "docs/auditorias/herg-umbral-2026-11-15/resultados.json",
    "docs/auditorias/herg-umbral-2026-11-15/contrarreplica-resultados.json",
    "backend/services/targets/prediccion.py",
    "backend/services/targets/conversion_mmcif.py",
    "backend/services/dossier/preparacion_confianza.py",
    "backend/scoring/normalizer.py",
    "backend/data/anti_dianas_bowes44.json",
    "scripts/check_release_pipeline.py",
    "frontend/src-tauri/tauri.conf.json",
    "frontend/package.json",
    "msix/msix-config.json",
]


def digest(path, normalize_lf=False):
    data = path.read_bytes()
    if normalize_lf:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def state():
    artifacts = sorted(p for p in HERE.iterdir() if p.is_file() and p != MANIFEST) + [REPORT]
    return {
        "fecha": "2026-11-15",
        "base_revisada": "4b8eaf3e229b89aa4032c8e6bbd6711cadf0b5aa",
        "alcance": "Revisión posterior por un asistente LLM. Sondas, recuentos y dictamen; no validación independiente por laboratorio ni aceptación de release.",
        "artefactos_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in artifacts},
        "entradas_bytes_sha256": {p: digest(ROOT / p) for p in EXACT_INPUTS},
        "entradas_lf_sha256": {p: digest(ROOT / p, True) for p in LF_INPUTS},
        "normalizacion_lf": "Sólo CRLF a LF en entradas_lf_sha256; los demás hashes usan bytes exactos.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = state()
    if args.write:
        MANIFEST.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
    elif json.loads(MANIFEST.read_bytes()) != current:
        raise SystemExit("La revisión o sus entradas difieren del manifiesto; no se actualiza automáticamente.")
    print(f"{'Registrados' if args.write else 'Verificados'} {len(current['artefactos_sha256'])} artefactos y "
          f"{len(EXACT_INPUTS) + len(LF_INPUTS)} entradas; sin modificar sellos anteriores.")


if __name__ == "__main__":
    main()

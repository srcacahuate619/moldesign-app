"""Verificación independiente de procedencia y completitud, sin imports del producto."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def context_proof(row, capsule):
    """Contrasta los dos contratos de hash leídos en f183e0af; no invoca services.

    Diagnóstico de procedencia, no oráculo de generación de defectos.
    """
    prov = row["docking_protocol"]["execution_provenance"]
    prep = prov["receptor_prep"]
    raw = capsule / "data/targets" / row["target_pdb_id"] / "raw.pdb"
    text = raw.read_text(encoding="utf-8")
    source_sha = hashlib.sha256(text.encode()).hexdigest()
    chains = prep.get("site_chains") or [prep["chain"]]
    chains = sorted(set(chains))
    center, size = prov["box_center"], prov["box_size"]
    crop = {"center": [round(float(v), 3) for v in center], "radius": max(size)*math.sqrt(3)/2+4} if len(chains)>1 else None
    respect = {"version": 1, "modo": "respetar", "source_sha256": source_sha, "chains": chains,
               "box_center": [round(float(v), 3) for v in center], "box_size": [round(float(v), 3) for v in size],
               "crop": crop, "traducciones": [["HSD", "HID"], ["HSE", "HIE"], ["HSP", "HIP"], ["WAT", "HOH"]],
               "margen_sitio_A": 6.0, "meeko_version": "0.7.1", "cofactor_templates_sha256": prep["cofactor_templates_sha256"]}
    calculated = canonical_hash(respect)
    assert calculated == prep["recipe_hash"], (row["case_id"], calculated, prep["recipe_hash"])
    automatic = {"version": 7, "source_sha256": source_sha, "chains": chains,
                 "cofactors_whitelist": sorted(set(prep.get("cofactors_whitelist") or [])),
                 "site_ligand_removed": prep.get("species_diff", {}).get("site_ligand"), "crop": crop,
                 "meeko_version": "0.7.1", "cofactor_templates_sha256": prep["cofactor_templates_sha256"],
                 "incomplete_sidechains": {"policy": "truncate_to_ala_or_gly", "margin_A": 6.0, "atoms_invented": False},
                 "meeko_options": {"add_hydrogens": True, "write_parameterized_json": True, "allow_bad_residues": True,
                                   "default_altloc": "A", "box_center": center, "box_size": size}}
    # La fórmula automática puede añadir una marca para H contradictorios. Este
    # caso cdk2 no la tiene: la comparación es sólo para esa reproducción mínima.
    auto_sha = canonical_hash(automatic)
    reference = next(r for r in row["requirements"] if r["clave"] == "entorno.referencia")
    assert reference["estado"] == "NO_EVALUADO" and "receta no coincide" in reference.get("razon", "")
    assert auto_sha != calculated
    result = json.loads((ROOT / row["evidence_dir"] / "result_metadata.json").read_text(encoding="utf-8"))
    prepared = capsule / "data" / result["receptor_path"]
    assert digest(prepared) == row["receptor_sha256"]
    return {"case_id": row["case_id"], "task_id": row["task_id"], "uploaded_input_sha256": row["input_sha256"],
            "normalized_raw_sha256": source_sha, "prepared_sha256": row["receptor_sha256"],
            "recorded_recipe_hash": prep["recipe_hash"], "respect_recipe_recomputed": calculated,
            "automatic_recipe_recomputed_no_contradictory_h": auto_sha, "observed_reference": reference,
            "respect_recipe_document": respect, "automatic_recipe_document_no_contradictory_h": automatic,
            "source_contracts": ["backend/services/docking/preparer_respetando.py:256", "backend/services/dossier/contexto_estructural.py:380"],
            "method": "reconstrucción stdlib de contratos para demostrar origen presente y receta B coincidente; no import del producto"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    args = ap.parse_args()
    rows_path = ART / "_work/pilot/per_complex.jsonl" if args.pilot else ART / "per_complex.jsonl"
    rows = [json.loads(l) for l in rows_path.read_text(encoding="utf-8").splitlines() if l]
    plan = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
    systems = {s["target"]: s for s in plan["systems"]}
    for system in systems.values():
        assert digest(Path(system["pdb_path"])) == system["pdb_sha256"]
        assert digest(Path(system["sdf_path"])) == system["sdf_sha256"]
    conditions = json.loads((ART / "registered_conditions.json").read_text(encoding="utf-8"))
    assert digest(ART / "inventory.json") == conditions["preregistration"]["inventory_sha256"]
    assert digest(ROOT / "docs/auditorias/FEP-09-prerregistro.md") == conditions["preregistration"]["sha256"]
    prereg = "9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638"
    for file in ("scripts/artifacts_science/FEP-09-SENSIBILIDAD/inventory.json", "docs/auditorias/FEP-09-prerregistro.md"):
        pinned = subprocess.check_output(["git", "show", prereg+":"+file], cwd=ROOT)
        assert hashlib.sha256(pinned).hexdigest() == digest(ROOT / file), "Archivo difiere del commit previo a corridas"
    pinned_manifest = json.loads(subprocess.check_output(["git", "show", prereg+":scripts/artifacts_science/FEP-09-SENSIBILIDAD/manifest.json"], cwd=ROOT))
    assert conditions == {k: pinned_manifest[k] for k in ("product_under_test", "preregistration", "benchmark")}
    expected = {c["case_id"] for c in plan["cases"] if not args.pilot or c["target"] == "cdk2"}
    cases = {c["case_id"]: c for c in plan["cases"]}
    assert {r["case_id"] for r in rows} == expected
    assert len(rows) == len(expected)
    assert not subprocess.check_output(["git", "diff", "f183e0af", "--", "backend", "frontend", "rescoring", "tools"], cwd=ROOT)
    checked, refs, tautomer_modes, preflight_modes = 0, Counter(), Counter(), Counter()
    vina_trace_hashes = set()
    per_target = {}
    for row in rows:
        assert row["product_commit"] == "f183e0af"
        assert all(row[k] == v for k, v in cases[row["case_id"]].items()), "Intervención difiere del inventario"
        evidence = ROOT / row["evidence_dir"]
        request = json.loads((evidence / "upload_request.json").read_text(encoding="utf-8"))
        actual_input = Path(request["input_file"])
        assert actual_input.is_relative_to(ROOT.parent / ".sandbox")
        assert digest(actual_input) == row["input_sha256"] == request["input_sha256"]
        if row["category"] == "baseline":
            assert row["input_sha256"] == systems[row["target"]]["pdb_sha256"]
        if row["outcome"] != "audited":
            continue
        p = row["docking_protocol"]
        system = systems[row["target"]]
        assert p["conformers_requested"] == 1
        assert p["execution_provenance"]["box_center"] == [round(v, 3) for v in system["grid_center"]]
        assert p["execution_provenance"]["box_size"] == system["grid_size"]
        ligand = row["ligand_state"]
        assert ligand["protonacion"]["ph_solicitado"] == 7.4
        tautomer_modes[ligand["tautomeria"]["modo"]] += 1
        preflight = json.loads((evidence / "preflight_response.json").read_text(encoding="utf-8"))
        canonical_request = json.loads(preflight["input_document"])
        declared_mode = canonical_request["pipeline_config"]["stage_params"]["conformer"].get("tautomero")
        assert declared_mode is None or declared_mode == ligand["tautomeria"]["modo"]
        assert ligand["tautomeria"]["modo"] == "entrada"
        preflight_modes[declared_mode or "opcional no declarado"] += 1
        assert p["exhaustiveness"] == 8 and p["num_poses"] == 9 and p["seed"] == 42
        assert row["vina_version"] == "1.2.7"
        assert p["execution_provenance"]["receptor_prep"]["modo_de_preparacion"] == "respetar"
        assert p["execution_provenance"]["cpu"] == 4
        assert p["execution_provenance"]["toolchain"]["meeko"] == "0.7.1"
        assert p["execution_provenance"]["toolchain"]["rdkit"] == "2025.9.6"
        trace = p["execution_provenance"].get("search_trace") or {}
        trace_hash = (trace.get("instrumentation") or {}).get("binary_sha256")
        if trace_hash:
            vina_trace_hashes.add(trace_hash)
        keys = [r["clave"] for r in row["requirements"]]
        assert len(keys) == len(set(keys))
        assert "receptor.huecos" in keys and "ligando.estereoquimica" in keys
        ref = next((r for r in row["requirements"] if r["clave"] == "entorno.referencia"), None)
        refs[(ref["estado"]+": "+str(ref.get("razon"))) if ref else "sin requisito"] += 1
        if row["category"] == "baseline":
            per_target.setdefault(row["target"], []).append(row["receptor_sha256"])
        checked += 1
    base = next(r for r in rows if r["case_id"] == "cdk2__baseline__0")
    proof = context_proof(base, ROOT.parent / ".sandbox/fep09-1")
    runtime = ROOT.parents[1]
    assert vina_trace_hashes == {digest(runtime / "tools/vina/vina_trace.exe")}, "La traza declara otro binario"
    out = {"n_verified_audits": checked, "n_expected": len(expected), "outcomes": dict(Counter(r["outcome"] for r in rows)),
           "baseline_receptor_distinct_hashes": {t: len(set(h)) for t, h in sorted(per_target.items())},
           "context_reference_counts": dict(sorted(refs.items())), "context_reproduction": proof,
           "vina_trace_binary_hashes": sorted(vina_trace_hashes),
           "input_files_and_source_hashes_match": True,
           "tautomer_modes_observed": dict(sorted(tautomer_modes.items())),
           "preflight_canonical_modes": dict(sorted(preflight_modes.items())),
           "protocol_deviation": {"planned_description": "modo por defecto canónico",
                                  "actual_request": "modo no especificado; la API aplica entrada por defecto",
                                  "disposition": "prerregistro intacto; no reintentos ni ajuste de gate; cierre INCONCLUSIVE y proxies fuera de categorías estrictas"},
           "product_diff_empty": True, "preregistration_hashes_match": True,
           "scope": "API de cápsulas, archivos de procedencia y contratos de hash; no instalador"}
    destination = ART / ("pilot_verification.json" if args.pilot else "verification.json")
    destination.write_text(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps({"n": checked, "n_expected": len(expected), "context_origin_present_recipe_B_matches": True, "product_diff_empty": True}))


if __name__ == "__main__":
    main()

"""Fase 1: Validación del pipeline con controles positivo/negativo (muestra 40).

Por cada target de la muestra:
  - Control POSITIVO: ligando nativo extraído del PDB (SMILES vía RDKit).
  - Control NEGATIVO: 2 decoys generados (mismo peso molecular aprox, distinta
    topología) vía RDKit.
  - Se dockean los 3 contra el grid del target (corregido en el re-curado).
  - Métricas: afinidad nativa vs decoys (enriquecimiento), hotspots_hit.

Criterio de validez: el ligando nativo debe obtener mejor (más negativo)
score que los decoys en su propio target. Enriquecimiento = % de targets
donde el nativo rankea top-1.

Uso:
    python scripts/validate_pipeline_fase1.py --sample 40 [--limit N] [--dry]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Para que Vina/Meeko resuelvan rutas relativas, cwd = raíz del proyecto
os.chdir(_ROOT.parent)  # D:\moldesign-build

# APP_MODE=DESKTOP hace que preparer.py use sys.executable (python-embed)
# en vez de /opt/conda/bin/python (default CLOUD/Linux).
os.environ["APP_MODE"] = "DESKTOP"


def find_local_pdb(pdb_id: str) -> Path | None:
    pdb_id = pdb_id.upper()
    for base in (Path(r"D:\moldesign-build\data\target_library"),
                 Path(r"D:\moldesign-build\data\targets")):
        for p in base.rglob("*.pdb"):
            if p.stem.split("_")[0].upper() == pdb_id:
                return p
    return None


def extract_native_ligand_smiles(pdb_path: Path):
    """Extrae el ligando HETATM más grande (no agua/buffer) del PDB → SMILES.

    Returns (smiles | None, resname, n_atoms).
    """
    from rdkit import Chem
    content = pdb_path.read_text(encoding="utf-8", errors="replace")
    # Agrupar HETATM por residuo (excluye agua y artefactos)
    skip = {"HOH", "WAT", "SO4", "PO4", "PEG", "EDO", "ACT", "GOL", "DMS",
            "MPD", "PG4", "PGE", "BME", "BOG", "DMU", "FMT", "EPE", "MES",
            "TRS", "CIT", "MLA", "TAR", "MRD", "1PE", "2PE", "PE3", "PE4",
            "NAG", "BMA", "MAN", "FUC", "GAL", "SIA", "GLC", "BGC", "XYS",
            "COH", "CHL", "CHT", "LUT", "MYR", "PAL", "STE", "LAX", "EIC",
            "LDA", "LDA ", "OLC", "OLA", "PLM", "PEE", "PCW", "PSC", "PSF",
            "PAM", "DD9", "LMG", "LPP", "TGL", "CE1", "ST8", "DDE",
            "ZN", "MG", "CA", "NA", "K", "CL", "BR", "I", "FE", "CU", "MN",
            "CO", "NI", "AU", "HG", "PT", "CD", "GD", "XE", "KR", "SR"}
    groups = {}
    for line in content.splitlines():
        if line.startswith("HETATM"):
            rn = line[17:20].strip()
            if rn in skip:
                continue
            chain = (line[21:22].strip() or "A")
            seq = line[22:26].strip()
            rid = f"{chain}:{rn}{seq}"
            groups.setdefault(rid, []).append(line)
    if not groups:
        return None, None, 0
    # El grupo más grande
    best_rid = max(groups, key=lambda k: len(groups[k]))
    lines = groups[best_rid]
    pdb_block = "\n".join(lines)
    mol = Chem.MolFromPDBBlock(pdb_block, removeHs=False)
    if mol is None:
        # Intentar sin sanitize (faltan conectividades)
        mol = Chem.MolFromPDBBlock(pdb_block, sanitize=False, removeHs=False)
    if mol is None:
        return None, best_rid.split(":")[1][:3], len(lines)
    # Remover H si el parseo los incluyó mal
    try:
        mol = Chem.RemoveHs(mol)
    except Exception:
        pass
    try:
        smiles = Chem.MolToSmiles(mol)
    except Exception:
        return None, best_rid.split(":")[1][:3], len(lines)
    return smiles, best_rid.split(":")[1][:3], mol.GetNumHeavyAtoms()


def generate_decoys(smiles_native: str, n: int = 2, seed: int = 42) -> list[str]:
    """Genera decoys conectados con masa similar pero topología distinta.

    Usa una biblioteca de moléculas drug-like pre-escritas (fármacos y
    fragmentos comunes) y selecciona las de masa similar (±40 Da) al nativo.
    Todas son moléculas ÚNICAS CONECTADAS — el validador estricto del
    pipeline las acepta.
    """
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    mol = Chem.MolFromSmiles(smiles_native)
    if mol is None:
        return []
    mw_target = Descriptors.MolWt(mol)
    rng = random.Random(seed)

    # Biblioteca de moléculas drug-like conectadas (no sales, no mezclas)
    library = [
        "CC(=O)Oc1ccccc1C(=O)O",           # aspirina
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",    # cafeína
        "CC(C)Cc1ccc(cc1)C(C)C(=O)O",      # ibuprofeno
        "CC(=O)Nc1ccc(cc1)O",              # paracetamol
        "CN(C)CCOC(c1ccccc1)c1ccccc1",     # difenhidramina
        "O=C(Nc1ccc(Cl)cc1)CCc1ccccc1",    # indapamida-like
        "CC1=C(C(=O)OC1)N2CCN(CC2)CCc3ccc(cc3)OC",  # fluoxetina-like
        "COc1ccc2cc(ccc2c1)C(=O)NCCN(C)C", # venlafaxina-like
        "C1CCN(CC1)C(=O)C2CCCCC2",         # benzamida simple
        "CC(C)(C)c1ccc(cc1)C(=O)O",        # ácido 4-terc-butilbenzoico
        "c1ccc(cc1)S(=O)(=O)N",            # bencenosulfonamida
        "CCCCCC(=O)Nc1ccc(O)cc1",          # N-hexanoil-p-aminofenol
        "CCN(CC)Cc1cccc(c1)C(=O)O",        # ácido benzoico sustituido
        "O=C(O)c1ccc(cc1)C(=O)O",          # ácido tereftálico
        "CC1CCCCC1C(=O)O",                 # ácido ciclohexano carboxílico
        "c1ccc2[nH]ccc2c1",                # indol
        "CCOC(=O)c1ccccc1",                # benzoato de etilo
        "CC(=O)Nc1ncccn1",                 # acetamida pirimidina
        "Oc1ccc(cc1)C(=O)O",               # ácido p-hidroxibenzoico
        "CCOc1ccc(cc1)C(=O)N",             # p-etoxibenzamida
        "CC(C)Nc1ccccc1",                  # N-isopropilanilina
        "c1ccc(cc1)N2CCOCC2",              # N-fenilmorfolina
        "CCC(=O)Nc1ccc(F)cc1",             # propanamida 4-fluoro
        "COc1ccccc1NC(=O)C",               # N-(2-metoxifenil)acetamida
        "CC(C)(C)OC(=O)N1CCCCC1",          # N-Boc-piperidina
        "O=C1Nc2ccccc2C1",                 # oxindol
        "CC1CCN(CC1)C(=O)c2ccccc2",        # benzamida piperidina
        "c1ccc(cc1)C(=O)Nc2ccccc2",        # benzanilida
        "COC(=O)c1ccccc1",                 # benzoato de metilo
        "CC(=O)Nc1ccccc1",                 # acetanilida
        "O=C(O)CCc1ccccc1",                # ácido 3-fenilpropiónico
        "CCc1ccccc1",                      # etilbenceno
        "O=C(N)Cc1ccccc1",                 # fenilacetamida
        "CCNC(=O)c1ccccc1",                # N-etilbenzamida
        "O=C(O)c1ccccn1",                  # ácido picolínico
        "Cc1ccccc1C(=O)O",                 # ácido o-toluico
        "COc1ccc(cc1)CC(=O)O",             # ácido 4-metoxifenilacético
        "CC1=CC(=O)CC(C)(C)C1",            # isoforona
        "O=C(c1ccccc1)c2ccccc2",           # benzofenona
        "CC(C)C1=CC=C(C=C1)C(=O)O",        # ácido 4-isopropilbenzoico
        "Nc1ccc(cc1)C(=O)O",               # ácido 4-aminobenzoico (PABA)
        "CC(=O)OCC",                       # acetato de etilo
        "O=C(O)c1ccncc1",                  # ácido isonicotínico
        "Cc1ncccn1",                       # 2-metilpirimidina
        "CC(=O)N1CCOCC1",                  # acetil-morfolina
        "O=C1CCCCC1",                      # ciclohexanona
        "c1cc2ccccc2cc1",                  # naftaleno
        "COc1ccccc1",                      # anisol
        "CC(=O)Cc1ccccc1",                 # fenilacetona
        "O=C(O)C(C)C",                     # ácido isobutírico
        # Moléculas grandes (400-650 Da) para ligandos tipo cofactor/antifolato
        "O=C(O)CCC(=O)O",                  # ácido succínico
        "O=C(O)CCCC(=O)O",                 # ácido adípico
        "O=C(Nc1ccccc1)C2CCCCC2",          # N-fenilciclohexanocarboxamida
        "COc1cc(OC)c(OC)cc1C(=O)O",        # ácido 3,4,5-trimetoxibenzoico
        "CC1=NN(C(=O)C1c2ccccc2)c3ccccc3", # pirazolona difenil
        "O=C(O)c1ccccc1OCC(=O)O",          # ácido (2-carboxifenoxi)acético
        "CN1CCC(CC1)OC(c2ccccc2)c3ccccc3", # difenhidramina-N-metil
        "O=C(O)Cc1ccc(cc1)C(=O)O",         # ácido 4-(carboximetil)benzoico
        "CC(=O)Nc1ccc(cc1)S(=O)(=O)N",     # sulfanilamida acetilada
        "O=C(Nc1ccc(cc1)C(=O)O)Cc2ccccc2", # N-bencil-PABA
        "COc1ccc(cc1)CC(=O)Nc2ccccc2",     # N-fenil-4-metoxifenilacetamida
        "O=C1N(Cc2ccccc2)C(=O)c3ccccc31",  # isatina N-bencil
        "Cc1ccc(cc1)S(=O)(=O)Nc2ncccn2",   # sulfapirimidina
        "O=C(O)c1ccc(cc1)N=NCc2ccccc2",    # azobenceno-carboxílico
        "CCN(CC)C(=O)c1ccc(cc1)C(=O)NCC",  # dietil-tereftalamida
        "O=C(O)C1CCN(CC1)C(=O)c2ccccc2",   # ácido 1-benzil-piperidin-4-carboxílico
        "O=C(O)c1ccc2ccccc2c1",            # ácido 2-naftoico
        "COc1ccc(cc1)C(=O)NCc2ccccc2",     # N-bencil-4-metoxibenzamida
        "O=C(Cc1ccccc1)Nc2ccccc2",         # N-fenil-2-fenilacetamida
    ]
    # Filtrar por masa: ±30% relativo (robusto para ligandos grandes
    # como cofactores/antifolatados de 400-600 Da).
    candidates = []
    for smi in library:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        mw = Descriptors.MolWt(m)
        if abs(mw - mw_target) <= 0.30 * mw_target:
            candidates.append((smi, mw))
    rng.shuffle(candidates)
    decoys = []
    for smi, mw in candidates:
        if len(decoys) >= n:
            break
        if smi != smiles_native and smi not in decoys:
            decoys.append(smi)
    return decoys


# Biblioteca global de ligandos nativos extraídos (para cross-docking decoys)
_NATIVE_LIGANDS_POOL: dict[str, tuple[str, float]] = {}  # pdb_id -> (smiles, mw)


def register_native_ligand(pdb_id: str, smiles: str) -> None:
    """Registra un ligando nativo en el pool para cross-docking."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    if not smiles or pdb_id in _NATIVE_LIGANDS_POOL:
        return
    try:
        m = Chem.MolFromSmiles(smiles)
        if m is not None:
            _NATIVE_LIGANDS_POOL[pdb_id] = (smiles, Descriptors.MolWt(m))
    except Exception:
        pass


def generate_decoys_cross(pdb_id: str, smiles_native: str, n: int = 2) -> list[str]:
    """Decoys por cross-docking: ligandos de OTROS targets con masa similar.

    Útil cuando la biblioteca no cubre la masa del nativo (cofactores,
    antifolatados grandes). El ligando del target X se usa como decoy
    contra el target Y — es un control negativo natural (no debería unirse
    al sitio de Y).
    """
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    try:
        mw_target = Descriptors.MolWt(Chem.MolFromSmiles(smiles_native))
    except Exception:
        return []
    candidates = []
    for other_id, (smi, mw) in _NATIVE_LIGANDS_POOL.items():
        if other_id == pdb_id:
            continue
        if abs(mw - mw_target) <= 0.30 * mw_target:
            candidates.append(smi)
    rng = random.Random(7 + hash(pdb_id) % 1000)
    rng.shuffle(candidates)
    decoys = []
    for smi in candidates:
        if len(decoys) >= n:
            break
        if smi != smiles_native and smi not in decoys:
            decoys.append(smi)
    return decoys


async def dock_one(smiles: str, target_pdb_id: str, grid_center, grid_size,
                   hotspots, label: str) -> dict:
    """Dockea una molécula contra un target. Retorna resultado o error."""
    from services.docking.vina_service import run_vina_docking
    try:
        result = await run_vina_docking(
            smiles_hash=f"val-{abs(hash(smiles))}",
            target_pdb_id=target_pdb_id,
            target_center=grid_center,
            target_size=grid_size,
            force_redock=True,
            hotspots=hotspots,
            docking_engine="vina",
            exhaustiveness=4,   # rápido para validación
            num_poses=5,
            smiles=smiles,
        )
        return {
            "label": label,
            "smiles": smiles,
            "affinity": getattr(result, "best_affinity", None),
            "n_poses": len(getattr(result, "poses", []) or []),
            "hotspots_hit": list(getattr(result, "hotspots_hit", []) or []),
        }
    except Exception as exc:
        return {"label": label, "smiles": smiles, "error": str(exc)[:150]}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry", action="store_true", help="Solo muestra la selección")
    ap.add_argument("--out", type=str, default="data/validation_fase1.json")
    args = ap.parse_args()

    # Cargar targets de la DB
    from core.database import get_db_session
    from core.models import TargetORM
    from sqlalchemy import select

    async with get_db_session() as db:
        stmt = select(TargetORM).where(TargetORM.is_prepared == True)  # noqa: E712
        targets = (await db.execute(stmt)).scalars().all()
        # Filtros: debe tener PDB local con ligando nativo extraíble
        valid = []
        for t in targets:
            p = find_local_pdb(t.pdb_id)
            if p is None:
                continue
            smiles, resname, n_atoms = extract_native_ligand_smiles(p)
            if smiles and n_atoms >= 10:  # drug-like razonable (≥10 átomos pesados)
                valid.append((t, p, smiles, resname))
        print(f"Targets con ligando nativo extraíble: {len(valid)}", flush=True)

        # Registro previo: poblar el pool de ligandos nativos para cross-docking
        for t, p, smi, resn in valid:
            register_native_ligand(t.pdb_id, smi)

        # Selección estratificada por familia
        from collections import defaultdict
        by_family = defaultdict(list)
        for t, p, smi, resn in valid:
            by_family[t.structural_family or "unknown"].append((t, p, smi, resn))

        fam_order = sorted(by_family, key=lambda f: -len(by_family[f]))
        selected = []
        total_fams = len(fam_order)
        per_fam = max(1, args.sample // total_fams)
        for fam in fam_order:
            fam_list = by_family[fam]
            rng = random.Random(42 + hash(fam) % 1000)
            take = min(per_fam, len(fam_list))
            picked = rng.sample(fam_list, take)
            for item in picked:
                selected.append((fam, item))
            if len(selected) >= args.sample:
                break

        print(f"\nMuestra estratificada: {len(selected)} targets", flush=True)
        for fam, (t, p, smi, resn) in selected:
            print(f"  {t.pdb_id} ({fam}): lig={resn} ({len(smi)} chars)", flush=True)

        if args.dry:
            return 0

        if args.limit:
            selected = selected[:args.limit]

        # ── Docking ──
        results = []
        for i, (fam, (t, p, smi_native, resname)) in enumerate(selected, 1):
            grid_center = (float(t.grid_center_x), float(t.grid_center_y), float(t.grid_center_z))
            grid_size = (float(t.grid_size_x or 20), float(t.grid_size_y or 20), float(t.grid_size_z or 20))
            from utils.structural import normalize_hotspots
            hotspots = normalize_hotspots(t.hotspots)
            decoys = generate_decoys(smi_native, n=2)
            if len(decoys) < 2:
                # Fallback: cross-docking con ligandos de otros targets
                cross = generate_decoys_cross(t.pdb_id, smi_native, n=2)
                for c in cross:
                    if c not in decoys:
                        decoys.append(c)

            print(f"\n[{i}/{len(selected)}] {t.pdb_id} ({fam}) lig={resname} | "
                  f"nativo={len(smi_native)} decoys={len(decoys)}", flush=True)

            entry = {"pdb_id": t.pdb_id, "family": fam, "native_smiles": smi_native,
                     "native_resname": resname, "n_hotspots": len(hotspots),
                     "grid_center": grid_center, "docks": []}

            # Docking nativo
            r_nat = await dock_one(smi_native, t.pdb_id, grid_center, grid_size,
                                   hotspots, "nativo")
            entry["docks"].append(r_nat)
            print(f"  nativo: {r_nat.get('affinity')} kcal/mol "
                  f"(hit={len(r_nat.get('hotspots_hit', []))})", flush=True)

            # Docking decoys
            for di, dec in enumerate(decoys):
                r_dec = await dock_one(dec, t.pdb_id, grid_center, grid_size,
                                       hotspots, f"decoy_{di}")
                entry["docks"].append(r_dec)
                print(f"  decoy_{di}: {r_dec.get('affinity')} kcal/mol "
                      f"(hit={len(r_dec.get('hotspots_hit', []))})", flush=True)

            # Enriquecimiento
            affs = [(d.get("affinity") or 0) for d in entry["docks"]]
            native_aff = affs[0]
            entry["native_rank"] = 1 + sum(1 for a in affs[1:] if a < native_aff)
            entry["enrichment_ok"] = entry["native_rank"] == 1
            results.append(entry)

        # ── Métricas globales ──
        n_ok = sum(1 for r in results if r["enrichment_ok"])
        n_eval = sum(1 for r in results if r.get("docks") and r["docks"][0].get("affinity") is not None)
        print("\n" + "=" * 60, flush=True)
        print("VALIDACIÓN FASE 1 — RESUMEN", flush=True)
        print("=" * 60, flush=True)
        print(f"Evaluados: {len(results)}", flush=True)
        print(f"Nativo rankea top-1 (enriquecimiento): {n_ok}/{len(results)} "
              f"({n_ok/len(results)*100:.0f}%)" if results else "0", flush=True)
        if n_eval:
            print(f"Con docking completado: {n_eval}", flush=True)

        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\nReporte: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

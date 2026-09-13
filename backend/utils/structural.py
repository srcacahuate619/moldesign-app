"""
utils/structural.py — Protein structure analysis and pocket detection.

Robust auto-detection of binding sites from PDB files:
  - Multi-ligand discovery with smart filtering
  - Adaptive grid box sizing based on ligand geometry
  - Automatic chain detection from binding site proximity  
  - Hotspot mining with distance-weighted scoring
  - Grid box validation for physical reasonableness
  - Detailed diagnostics for user feedback

Used by: custom target upload, batch target curation, pipeline ingestion.
"""

import math
import re
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────

MIN_LIGAND_ATOMS = 6       # Minimum heavy atoms for a drug-like ligand
MAX_LIGAND_ATOMS = 500     # Sanity cap (no protein-sized "ligands")
HOTSPOT_CUTOFF_A = 5.0     # Contact distance for hotspot detection
HOTSPOT_CLOSE_CUTOFF_A = 3.5  # "Close contact" bonus threshold
GRID_MIN_HALF = 10.0       # Minimum grid half-size (20A total)
GRID_MAX_HALF = 25.0       # Maximum grid half-size (50A total)
GRID_PADDING_A = 8.0       # Extra padding beyond ligand radius
CHAIN_CONTACT_CUTOFF_A = 8.0  # Distance for chain contact detection

# Non-drug HETATM residues to ignore (buffers, solvents, ions, artifacts)
SKIP_HETATM: set[str] = {
    # Water and deuterated variants
    "HOH", "WAT", "DOD", "DOH",
    # Common buffers and solvents
    "SO4", "PO4", "PEG", "EDO", "ACT", "GOL", "DMS", "MPD", "PG4", "PGE",
    "PG0", "BME", "BOG", "DMU", "FMT", "EPE", "MES", "TRS", "CIT", "MLA",
    "TAR", "MRD", "1PE", "2PE", "PE3", "PE4", "PE5", "PE8",
    # Crystallization additives
    "ACY", "AZI", "BTB", "CAC", "CAD", "CBM", "CXS", "DTD", "DTV",
    "EDT", "EOH", "FLC", "GAI", "GBL", "GTT", "HEZ", "HTO", "IMD", "IPA",
    "LDA", "LMT", "MBO", "MOH", "N8E", "NH2", "NH4", "NO3", "OCT", "OH",
    "P6G", "PGO", "POL", "POP", "PTN", "SBT", "SCN", "SEO", "SMO", "SPD",
    "SPK", "SR", "TAM", "TAS", "TBU", "TCE", "TMA", "TPO", "TRD", "U1", "UMQ", "UNX", "URE", "VO4",
    # Metal ions (crystallography, not ligands)
    "AU", "HG", "PT", "IR", "OS", "PB", "CD", "GD", "XE", "KR",
    "ZN", "MG", "CA", "NA", "K", "CL", "BR", "I", "FE", "CU", "MN", "CO",
    "NI", "LI", "RB", "CS", "BA", "AG", "AL", "TL", "GA", "IN",
    "YB", "EU", "SM", "LA", "CE", "PR", "ND", "TB", "DY", "ER",
    "TM", "LU", "HF", "ZR", "TH", "U", "PU",
    # Glycosylations (sugars, not drug targets)
    "NAG", "BMA", "MAN", "FUC", "GAL", "SIA", "GLC", "BGC", "XYS",
    "XYP", "XYL", "ARA", "RIB", "FRU", "GLA", "MAL", "SUC", "TRE",
    # Membrane lipids
    "OLC", "OLA", "PLM", "PEE", "PCW", "PSC", "PSF", "PAM",
    # Sterols / lipids (crystallization artifacts, not drug sites)
    "COH", "CHL", "CHT", "DGR", "DGA", "LUT", "MYR", "PAL", "STE",
    "LAX", "EIC", "AAS", "DD9", "LMG", "LPP", "TGL", "CE1", "ST8", "DDE",
    # Nucleotides (sometimes co-factors, sometimes ligands — keep if large)
    # "ATP", "ADP", "AMP", "GTP", "GDP", "NAD", "NAP", "FAD", "FMN",
    # "SAM", "SAH", "COA", "HEM", "FES", "SF4", "F3S",
}

# Nucleotide cofactors — included if they're the ONLY ligand (possible drug target)
# but excluded if there's a larger drug-like ligand present.
COFACTOR_HETATM: set[str] = {
    "ATP", "ADP", "AMP", "GTP", "GDP", "GMP", "CTP", "UTP",
    "NAD", "NAP", "NAI", "NDP", "FAD", "FMN", "SAM", "SAH", "COA", "ACP", "HEM", "HEC", "FES", "SF4", "F3S",
}


# ── Main API ─────────────────────────────────────────────────────────────


def discover_pocket_from_pdb(
    pdb_content: str,
    target_chain: str = "A",
    ligand_chain: str | None = None,
) -> dict:
    """
    Robust binding site discovery from PDB content.

    Args:
        pdb_content: Raw PDB file content as string
        target_chain: Expected receptor chain (used if auto-detect fails)
        ligand_chain: If set, treat this entire chain as the ligand (peptides)

    Returns:
        dict with:
          success: bool
          ligand_id: str            — identifier of detected ligand
          ligand_name: str          — 3-letter residue name
          atom_count: int           — heavy atom count of the ligand
          ligand_radius: float      — max distance from centroid
          grid_center: (x, y, z)   — suggested grid box center
          grid_size: (sx, sy, sz)  — suggested grid box dimensions
          suggested_hotspots: list  — top 15 residues near the ligand
          detected_chain: str       — auto-detected receptor chain
          all_ligands_found: list   — all valid ligands found (for user choice)
          warnings: list[str]       — diagnostic warnings
          error: str | None         — error message if failed
    """
    warnings: list[str] = []
    all_ligands: dict[str, list[tuple[float, float, float]]] = {}
    chain_ligand_coords: list[tuple[float, float, float]] = []
    receptor_atoms: list[tuple[str, str, tuple[float, float, float]]] = []
    chain_contacts: dict[str, int] = {}
    all_chain_atoms: dict[str, int] = {}

    # ── Parse PDB ───────────────────────────────────────────────────
    for line in pdb_content.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue

        record = line[:6].strip()
        res_name = line[17:20].strip().upper()
        chain = (line[21:22].strip() or "A").upper()
        res_seq = line[22:26].strip()
        res_id = f"{chain}:{res_name}{res_seq}"

        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue

        # Option A: Peptide ligand by chain
        if ligand_chain and chain == ligand_chain:
            chain_ligand_coords.append((x, y, z))
            continue

        # Option B: HETATM ligands (non-receptor)
        if record == "HETATM" and res_name not in SKIP_HETATM:
            all_ligands.setdefault(res_id, []).append((x, y, z))

        # Receptor atoms (for hotspot mining and chain detection)
        if record == "ATOM":
            receptor_atoms.append((res_id, res_name, (x, y, z)))
            all_chain_atoms[chain] = all_chain_atoms.get(chain, 0) + 1

    # ── Peptide chain mode ──────────────────────────────────────────
    if ligand_chain:
        if not chain_ligand_coords:
            return {
                "success": False,
                "error": f"No se encontraron atomos en la cadena {ligand_chain}.",
                "warnings": warnings,
            }
        coords = chain_ligand_coords
        best_id = f"Chain:{ligand_chain}"
        best_name = f"CHAIN_{ligand_chain}"
        all_ligands_found = []
    else:
        # ── Filter and rank HETATM ligands ──────────────────────────
        valid_ligands = {
            k: v for k, v in all_ligands.items()
            if MIN_LIGAND_ATOMS <= len(v) <= MAX_LIGAND_ATOMS
        }

        if not valid_ligands:
            # Try including cofactors if no drug-like ligands found
            cofactor_ligands = {
                k: v for k, v in all_ligands.items()
                if len(v) >= 3 and any(
                    k.split(":")[1] if ":" in k else k for part in [k]
                )
            }
            if cofactor_ligands:
                warnings.append(
                    "No se encontraron ligandos drug-like. "
                    "Los HETATM detectados son cofactores (ATP/NAD/HEM). "
                    "El grid box se centro en el cofactor mas grande."
                )
                valid_ligands = cofactor_ligands

        if not valid_ligands:
            # Fallback APO: usar MolPocket (motor propio, reimplementación de
            # fpocket) para detectar el pocket en la estructura sin ligando.
            apo_result = _fallback_apo_pocket(pdb_content, warnings)
            if apo_result is not None:
                return apo_result

            return {
                "success": False,
                "error": (
                    "No se encontraron ligandos validos en el PDB. "
                    "La deteccion APO por MolPocket tampoco encontro "
                    "cavidades. Estructuras apo (sin ligando) requieren "
                    "coordenadas manuales del grid box."
                ),
                "warnings": warnings,
                "total_hetatm_groups": len(all_ligands),
            }

        # Sort by atom count (descending), report all found
        ranked = sorted(valid_ligands.items(), key=lambda kv: len(kv[1]), reverse=True)
        all_ligands_found = [
            {"id": rid, "name": _extract_res_name(rid), "atoms": len(coords)}
            for rid, coords in ranked[:10]
        ]

        # Pick the largest drug-like ligand
        best_id, coords = ranked[0]
        best_name = _extract_res_name(best_id)

        if len(ranked) > 1:
            warnings.append(
                f"Se encontraron {len(ranked)} ligandos potenciales. "
                f"Usando el mas grande: {best_name} ({len(coords)} atomos). "
                f"Alternativas: {', '.join(l['name'] for l in all_ligands_found[1:6])}"
            )

    # ── Guard clause ─────────────────────────────────────────────────
    if len(coords) == 0:
        return {"success": False, "error": f"Ligando {best_id} sin coordenadas.", "warnings": warnings}

    # ── Compute grid center and size ─────────────────────────────────
    xs, ys, zs = [c[0] for c in coords], [c[1] for c in coords], [c[2] for c in coords]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    cz = sum(zs) / len(zs)

    # More accurate radius using bounding box
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    span_z = max(zs) - min(zs)
    ligand_span = max(span_x, span_y, span_z)

    # Radius from centroid for spherical approximation
    max_dist = 0.0
    for c in coords:
        dist = math.sqrt((c[0] - cx)**2 + (c[1] - cy)**2 + (c[2] - cz)**2)
        if dist > max_dist:
            max_dist = dist

    # Adaptive grid: use the larger of radius+padding vs span+padding
    grid_half = max(GRID_MIN_HALF, min(GRID_MAX_HALF, max(max_dist, ligand_span / 2) + GRID_PADDING_A))
    gx = round(grid_half * 2, 1)
    gy = round(grid_half * 2, 1)
    gz = round(grid_half * 2, 1)

    # ── Chain detection ──────────────────────────────────────────────
    detected_chain = _detect_chain_from_ligand(receptor_atoms, coords)
    if not detected_chain:
        detected_chain = _detect_chain_by_atom_count(all_chain_atoms)
    if not detected_chain:
        detected_chain = target_chain or "A"

    if detected_chain != target_chain and target_chain != "A":
        warnings.append(
            f"La cadena detectada ({detected_chain}) difiere de la "
            f"esperada ({target_chain}). Se usara la detectada."
        )

    # ── Hotspot mining ───────────────────────────────────────────────
    hotspots = _mine_hotspots(receptor_atoms, coords)

    # ── Grid validation ──────────────────────────────────────────────
    grid_warnings = _validate_grid(gx, gy, gz, len(receptor_atoms))
    warnings.extend(grid_warnings)

    return {
        "success": True,
        "ligand_id": best_id,
        "ligand_name": best_name,
        "atom_count": len(coords),
        "ligand_radius": round(max_dist, 2),
        "ligand_span": round(ligand_span, 2),
        "grid_center": (round(cx, 2), round(cy, 2), round(cz, 2)),
        "grid_size": (gx, gy, gz),
        "suggested_hotspots": hotspots,
        "detected_chain": detected_chain,
        "all_ligands_found": all_ligands_found,
        "warnings": warnings,
    }


# ── Helper: Fallback APO (MolPocket) ─────────────────────────────────────


def _fallback_apo_pocket(
    pdb_content: str,
    warnings: list[str],
    target_chain: str = "A",
) -> dict | None:
    """Detecta pocket en estructura APO usando MolPocket (motor propio).

    Llamado cuando NO hay ligandos válidos (drug-like ni cofactores). Usa
    `detect_pockets` del módulo pocket_detector (reimplementación de fpocket
    en Python + scipy, validado sobre PDBbind v2020: mediana top1 ≈ 5-6 Å).

    Returns:
        dict con el mismo contrato de `discover_pocket_from_pdb` (success,
        grid_center, grid_size, suggested_hotspots, detected_chain,
        all_ligands_found, ligand_name="APO", ...) o None si no detecta nada.
    """
    try:
        from utils.pocket_detector import detect_pockets
    except Exception as exc:
        warnings.append(f"MolPocket no disponible: {exc}")
        return None

    try:
        pockets = detect_pockets(pdb_content, top_n=1)
    except Exception as exc:
        warnings.append(f"MolPocket falló: {exc}")
        return None

    if not pockets:
        warnings.append(
            "MolPocket no detectó cavidades en la estructura APO."
        )
        return None

    pocket = pockets[0]
    cx, cy, cz = (float(v) for v in pocket.center)

    # Grid adaptativa: radio del pocket + padding, dentro de límites
    # (misma lógica que la rama con ligando).
    grid_half = max(GRID_MIN_HALF, min(GRID_MAX_HALF, pocket.radius + GRID_PADDING_A))
    gx = round(grid_half * 2, 1)
    gy = round(grid_half * 2, 1)
    gz = round(grid_half * 2, 1)

    # Cadena: detectar por átomos (no hay ligando para proximidad)
    chain_atoms: dict[str, int] = {}
    for line in pdb_content.splitlines():
        if not line.startswith("ATOM"):
            continue
        chain = (line[21:22].strip() or "A").upper()
        chain_atoms[chain] = chain_atoms.get(chain, 0) + 1
    detected_chain = max(chain_atoms, key=chain_atoms.get) if chain_atoms else target_chain

    hotspots = pocket.hotspots if isinstance(pocket.hotspots, list) else []

    grid_warnings = _validate_grid(gx, gy, gz, sum(chain_atoms.values()))
    warnings.extend(grid_warnings)
    warnings.append(
        "Estructura APO (sin ligando): se uso MolPocket para detectar el "
        f"pocket (score={pocket.score:.2f}, dr={pocket.druggability:.2f}, "
        f"esferas={pocket.n_spheres}). Verifica el grid box manualmente."
    )

    return {
        "success": True,
        "ligand_id": "APO",
        "ligand_name": "APO",
        "atom_count": 0,
        "ligand_radius": round(float(pocket.radius), 2),
        "ligand_span": round(float(pocket.radius) * 2, 2),
        "grid_center": (round(cx, 2), round(cy, 2), round(cz, 2)),
        "grid_size": (gx, gy, gz),
        "suggested_hotspots": hotspots,
        "detected_chain": detected_chain,
        "all_ligands_found": [
            {"id": "APO", "name": "APO", "atoms": 0,
             "detail": "Pocket detectado por MolPocket (sin ligando)"}
        ],
        "warnings": warnings,
        "apo_molpocket": True,
    }


# ── Helper: Chain Detection ──────────────────────────────────────────────

def _detect_chain_from_ligand(
    receptor_atoms: list[tuple[str, str, tuple[float, float, float]]],
    ligand_coords: list[tuple[float, float, float]],
) -> str:
    """Detect which chain contains the binding site by proximity to ligand."""
    chain_scores: dict[str, float] = {}
    cutoff_sq = CHAIN_CONTACT_CUTOFF_A ** 2

    for res_id, res_name, (rx, ry, rz) in receptor_atoms:
        chain = res_id[0] if ":" in res_id else "A"
        # Check ALL ligand atoms for proximity (not just 20)
        min_dist_sq = float("inf")
        for lx, ly, lz in ligand_coords:
            d2 = (rx - lx)**2 + (ry - ly)**2 + (rz - lz)**2
            if d2 < min_dist_sq:
                min_dist_sq = d2
        if min_dist_sq < cutoff_sq:
            # Weight by inverse distance (closer = stronger signal)
            weight = 1.0 / (math.sqrt(min_dist_sq) + 0.1)
            chain_scores[chain] = chain_scores.get(chain, 0.0) + weight

    if chain_scores:
        return max(chain_scores, key=chain_scores.get)
    return ""


def _detect_chain_by_atom_count(chain_atoms: dict[str, int]) -> str:
    """Fallback: pick chain with most atoms."""
    if chain_atoms:
        return max(chain_atoms, key=chain_atoms.get)
    return ""


# ── Helper: Hotspot Mining ───────────────────────────────────────────────


def _mine_hotspots(
    receptor_atoms: list[tuple[str, str, tuple[float, float, float]]],
    ligand_coords: list[tuple[float, float, float]],
) -> list[dict]:
    """Score receptor residues by proximity to ligand atoms."""
    cutoff_sq = HOTSPOT_CUTOFF_A ** 2
    close_sq = HOTSPOT_CLOSE_CUTOFF_A ** 2
    residue_scores: dict[str, float] = {}

    for res_id, res_name, (rx, ry, rz) in receptor_atoms:
        contacts = 0
        min_dist_sq = float("inf")

        for lx, ly, lz in ligand_coords:
            d2 = (rx - lx)**2 + (ry - ly)**2 + (rz - lz)**2
            if d2 < cutoff_sq:
                contacts += 1
                if d2 < min_dist_sq:
                    min_dist_sq = d2

        if contacts > 0:
            bonus = 2.0 if min_dist_sq < close_sq else 1.0
            residue_scores[res_id] = residue_scores.get(res_id, 0.0) + contacts * bonus

    if not residue_scores:
        return []

    sorted_scores = sorted(residue_scores.items(), key=lambda x: x[1], reverse=True)
    max_score = sorted_scores[0][1]
    return [
        {
            "name": res_id,
            "importance": round(0.5 + (score / max_score) * 0.5, 2),
        }
        for res_id, score in sorted_scores[:15]
    ]


# ── Helper: Grid Validation ──────────────────────────────────────────────


def _validate_grid(gx: float, gy: float, gz: float, receptor_atom_count: int) -> list[str]:
    """Validate that grid box dimensions are physically reasonable."""
    warnings: list[str] = []
    if gx < 15 or gy < 15 or gz < 15:
        warnings.append(f"Grid muy pequeno ({gx:.0f}x{gy:.0f}x{gz:.0f} A). Considera aumentarlo manualmente.")
    if gx > 50 or gy > 50 or gz > 50:
        warnings.append(f"Grid muy grande ({gx:.0f}x{gy:.0f}x{gz:.0f} A). El docking sera mas lento.")
    if receptor_atom_count < 20:
        warnings.append(f"Receptor con pocos atomos ({receptor_atom_count}). Verifica que el PDB sea valido.")
    return warnings


# ── Helper: Residue Name Extraction ──────────────────────────────────────


def _extract_res_name(res_id: str) -> str:
    """Extract the 3-letter residue/ligand code from 'A:HEM123' style IDs.

    El res_id se construye como `chain:resname+seq` (p. ej. "A:HEM123" →
    resname="HEM", seq="123"; "A:D16414" → resname="D16", seq="414").
    El seq es un número de residuo (1..~1500) que se concatena al código.
    Estrategia: el código son los primeros 3 caracteres del name_part SI
    producen un código HETATM plausible; si el name_part empieza con letras
    seguidas de dígitos sin separación, los primeros 3 chars son el código
    (p. ej. "LIG" en "LIG100", "HEM" en "HEM123", "D16" en "D16414").
    Para códigos que empiezan con dígito (3PO, 1PE) se toma el prefijo
    alfanumérico completo hasta el seq.
    """
    if ":" in res_id:
        name_part = res_id.split(":")[1]
        # Si empieza con dígito: código = dígitos + letras (p. ej. "3PO42")
        if name_part and name_part[0].isdigit():
            m = re.match(r"^(\d+[A-Za-z]+)", name_part)
            if m:
                return m.group(1)
            return name_part
        # Si tiene >= 3 chars: el código son los primeros 3 (HEM123 → HEM,
        # LIG100 → LIG, D16414 → D16, UMP314 → UMP).
        if len(name_part) >= 3:
            return name_part[:3]
        return name_part
    return res_id


# ── Public utilities ─────────────────────────────────────────────────────


def normalize_hotspots(hotspots: object) -> list[dict]:
    """Normaliza el campo hotspots del target a una lista de dicts.

    El campo se guarda en una columna JSONB que en SQLite se compila a TEXT.
    Dependiendo del camino de lectura puede llegar como:
      - list[dict]  (lo ideal, tras deserializar)
      - str JSON    ('[{"name": ...}]' — el string ya serializado)
      - None / "null" / "[]" / ""
    Esta función garantiza que los consumidores reciban SIEMPRE list[dict]
    (vacía si no hay datos válidos), sin que el pipeline se rompa al iterar
    un string carácter a carácter.
    """
    if hotspots is None:
        return []
    if isinstance(hotspots, list):
        return [h for h in hotspots if isinstance(h, dict)]
    if isinstance(hotspots, str):
        s = hotspots.strip()
        if s in ("", "null", "[]"):
            return []
        try:
            import json as _json
            parsed = _json.loads(s)
            if isinstance(parsed, list):
                return [h for h in parsed if isinstance(h, dict)]
            # Doble-escape: el string contiene otro string JSON
            if isinstance(parsed, str):
                inner = _json.loads(parsed)
                if isinstance(inner, list):
                    return [h for h in inner if isinstance(h, dict)]
            return []
        except Exception:
            return []
    return []


def detect_binding_site_chain(
    pdb_content: str,
    ligand_coords: list[tuple[float, float, float]],
) -> str:
    """
    Public API: Detect receptor chain by ligand proximity.
    Uses ALL ligand atoms for maximum accuracy.
    """
    receptor_atoms: list[tuple[str, str, tuple[float, float, float]]] = []
    for line in pdb_content.splitlines():
        if not line.startswith("ATOM"):
            continue
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        res_name = line[17:20].strip().upper()
        chain = (line[21:22].strip() or "A").upper()
        res_seq = line[22:26].strip()
        res_id = f"{chain}:{res_name}{res_seq}"
        receptor_atoms.append((res_id, res_name, (x, y, z)))

    return _detect_chain_from_ligand(receptor_atoms, ligand_coords) or "A"


def validate_hotspots_in_pdb(pdb_path: str | Path, hotspots: list[dict]) -> dict:
    """
    Verifica si los residuos definidos como hotspots existen en el archivo PDB/PDBQT.
    Retorna un diccionario con el estado de cada hotspot.
    """
    pdb_path = Path(pdb_path)
    if not pdb_path.exists():
        return {"error": f"Archivo {pdb_path.name} no encontrado", "valid": False}

    found_residues = set()
    with open(pdb_path, "r") as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                res_name = line[17:20].strip().upper()
                chain = line[21].strip().upper()
                res_seq = line[22:26].strip()
                found_residues.add(f"{res_name}{res_seq}")
                if chain:
                    found_residues.add(f"{chain}:{res_name}{res_seq}")

    report = []
    all_valid = True
    for h in hotspots:
        h_name = h["name"].upper()
        if h_name in found_residues:
            report.append({"name": h_name, "status": "FOUND"})
        else:
            all_valid = False
            if ":" in h_name:
                parts = h_name.split(":", 1)
                amino = re.sub(r'\d+', '', parts[1])
                prefix = parts[0] + ":"
            else:
                amino = re.sub(r'\d+', '', h_name)
                prefix = ""
            candidates = [r for r in found_residues if prefix + amino in r or amino in r]
            report.append({
                "name": h_name, "status": "MISSING", "suggestions": candidates[:5],
            })

    return {
        "valid": all_valid,
        "hotspots_checked": len(hotspots),
        "found_count": sum(1 for r in report if r["status"] == "FOUND"),
        "report": report,
    }


def get_residue_coordinates(
    pdb_path: str | Path,
    residue_names: list[str],
    chain: str | None = None,
) -> dict[str, tuple[float, float, float]]:
    """
    Lee un archivo PDB y encuentra las coordenadas del átomo CA (C-alpha)
    para cada residuo especificado en residue_names.
    Si no hay CA, toma el primer átomo del residuo.

    Filtro por cadena (fidelidad estructural): en complejos multicadena
    (GPCR + proteína G, anticuerpos, etc.) el mismo número de residuo puede
    existir en varias cadenas. Se filtra por el prefijo del nombre
    ("A:LEU221" → cadena A) y, para los nombres sin prefijo, por la cadena del
    receptor (`chain`). Sin ninguna de las dos → primera coincidencia.

    CORRECCIÓN (doc 72). Este parseo tenía las dos mitades intercambiadas:
    `"A:ARG76".partition(":")` deja `"A"` a la izquierda y `"ARG76"` a la
    derecha, y el código tomaba la IZQUIERDA como nombre de residuo y la
    DERECHA como cadena. Como el bucle construye `res_id = "ARG76"`, la clave
    registrada (`"A"`) no coincidía nunca y la función **devolvía un diccionario
    vacío para todo hotspot con prefijo de cadena** — es decir, para los 385
    receptores del catálogo, que los llevan todos. Comprobado sobre 1AJ6:
    `["A:ARG76"]` → `{}`, `["ARG76"]` → coordenadas.

    El efecto era silencioso: `list_targets` no fallaba, sólo omitía las
    coordenadas, y el visor las recalculaba por su cuenta parseando el PDB en el
    navegador. Nadie lo notó porque el que las necesitaba se las arreglaba solo.
    """
    pdb_path = Path(pdb_path)
    if not pdb_path.exists():
        return {}

    coords: dict[str, tuple[float, float, float]] = {}
    # {res_id: cadena esperada o None (sin filtro)}
    expected_chain: dict[str, str | None] = {}
    fallback_chain = (chain or "").strip().upper() or None
    for r in residue_names:
        clean = r.strip().upper()
        if ":" in clean:
            ch, _, name_clean = clean.partition(":")
            expected_chain[name_clean.strip()] = ch.strip() or None
        else:
            expected_chain[clean] = fallback_chain

    with open(pdb_path, "r") as f:
        for line in f:
            if not line.startswith(("ATOM", "HETATM")):
                continue
            res_name = line[17:20].strip().upper()
            res_seq = line[22:26].strip()
            res_id = f"{res_name}{res_seq}"
            if res_id not in expected_chain:
                continue
            want_chain = expected_chain[res_id]
            if want_chain and line[21].strip().upper() != want_chain:
                continue
            atom_name = line[12:16].strip().upper()
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            if res_id not in coords or atom_name == "CA":
                coords[res_id] = (x, y, z)
    return coords

"""
scoring/ums.py — el adaptador de ZINC de la familia M5.

═══════════════════════════════════════════════════════════════════════════
SE LLAMA «UNIVERSAL» Y NO LO ES
═══════════════════════════════════════════════════════════════════════════

`docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md` §6 define M5 como una
familia con un adaptador por metal. Este archivo es el adaptador de zinc, y el
nombre «Universal Metal Score» es anterior a esa decisión.

Los siete warheads que detecta son grupos de unión a ZINC: sulfonamida,
sulfonamida primaria, hidroxámico, tiol, carboxilato, fosfonato y N-hidroxi. El
paper los valida sobre CA2 (sulfonamida), MMP9 (hidroxámico) y ACE
(carboxilato/tiol) — las tres, enzimas de zinc.

Algunos solapan con otros metales: el hidroxámico también quela Fe(III), el
carboxilato quela casi todo. Pero el ORDEN de preferencia cambia con el metal, y
una sulfonamida primaria —quelante de Zn de primer orden— es un mal ligando de
magnesio. Los pesos (`0.60·warhead + 0.20·donor + 0.20·molchamb`), el
`0.85 + 0.10·min(n/3, 1)` del componente de warhead y el divisor 30 de donores
salen todos del ajuste sobre dianas de zinc.

Lo que sí es común a cualquier metal —detectar el ion en la estructura,
conservarlo, registrar su procedencia, saber si hay adaptador y abstenerse si
no— vive en `services/pipeline/protocols/m5/base.py`.

El nombre de las funciones se conserva porque está en artefactos sellados y en
el manuscrito. Lo que cambia es que aquí se dice de qué metal habla.

---

Universal Metal Score (UMS) — portado desde scripts/universal_metal_score.py
al runtime del backend (2026-08-03).

Enfoque cheminformático: detecta warheads canónicos de quelación de Zn2+
directamente desde SMILES (sin docking, sin pose, sin GPU), los combina con
el MolChamb quantum score (opcional, precomputado) y con el conteo de átomos
donadores (N+O+S). Es el componente w5 del M5_gated descrito en
docs/PAPER_UMS.md (bootstrap_ci.py:80-107 usa pesos w5 = 0.25-0.40 para
metaloenzimas).

Features (todas ligand-only, NO se requiere docking):
  - warheads dict       : 7 patrones SMARTS -> bool
  - any_warhead         : 0/1 si existe cualquier warhead
  - n_warheads          : suma de warheads detectados
  - donor_count         : átomos N + O + S (heavy)
  - molchamb_score      : score cuántico MolChamb (precomputado, default 0.5)
  - universal_metal_score: score combinado heurístico [0..1]

DIFERENCIA CON metal_features (services/chemistry/protein_surgery.py):
  - metal_features es count-based (substruct counts) y hoy solo hace log en
    queue_handler.py:664-676; NO alimenta el stacking.
  - Este módulo produce el score continuo [0..1] del paper y SÍ alimenta el
    stacking engine (scoring/engine.py) como `ums_score` para metaloenzimas.
  Ambos son complementarios; no se reemplazan mutuamente.

NORMALIZACIÓN DE FAMILIA (gotcha crítico):
  El código y stacking_weights.json usan "metaloenzyme" (1 L), pero
  scripts/reclassify_targets.py:89 normaliza a "metalloenzyme" (2 L) en la DB.
  Este módulo y el gate en engine.py normalizan ambas grafías vía
  _is_metalloenzyme_family().
"""

from __future__ import annotations

from utils.logger import get_logger

log = get_logger(__name__)

# ── Warhead detection patterns ──
# Se usa substructure matching con RDKit SMARTS, NO regex sobre el string
# SMILES: el mismo substructure químico puede tener múltiples SMILES
# canónicos (ej: C(=O)NO vs O=C(NO)); SMARTS es químicamente consciente.

_WARHEAD_SMARTS = {
    "sulfonamide": [
        "S(=O)(=O)[N;!$(N-C=O)]",          # sulfonamida S(=O)(=O)N, excluye amidas
        "O=S(=O)[N;!$(N-C=O)]",            # orientación inversa
    ],
    "primary_sulfonamide": [
        "S(=O)(=O)[NH2]",                   # sulfonamida primaria
        "O=S(=O)[NH2]",
    ],
    "hydroxamic": [
        "[C;$(C(=O))]N[O;$(O-*)]",          # C(=O)NOH — vorinostat, marimastat, batimastat
        "C(=O)NO",                           # explícito
    ],
    "thiol": [
        "[SH]",                              # notación explícita [SH]
    ],
    "carboxylate": [
        "C(=O)[O-]",                         # carboxilato desprotonado
        "C(=O)[OH1]",                        # ácido carboxílico protonado (OH con 1 H)
    ],
    "phosphonate": [
        "P(=O)(O)(O)",                       # ácido fosfónico
        "P(=O)(O)([O-])",                    # desprotonado
    ],
    "n_hydroxy": [
        "[N]-[OH1]",                         # enlace simple N-OH, tipo hidroxilamina
        "N(O)",                              # notación explícita N-óxido
    ],
}

# Lista ordenada de claves de warhead para estabilidad del vector de features
WARHEAD_KEYS = [
    "sulfonamide",
    "primary_sulfonamide",
    "hydroxamic",
    "thiol",
    "carboxylate",
    "phosphonate",
    "n_hydroxy",
]

#: Dónde se midió este adaptador. Fuera de estas tres dianas no hay medición
#: que respalde la transferencia, y el resultado debe marcarse REVIEW. Ver
#: `services/pipeline/protocols/m5/base.py::ADAPTADORES`.
DOMINIO_MEDIDO_ZN = ("CA2", "MMP9", "ACE")


# ── Grafía canónica ──────────────────────────────────────────────────────
#
# `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md` §6 fija la identidad canónica:
#
#     metalloenzyme
#
# Es la forma inglesa estándar y la que usa el catálogo curado. `metaloenzyme`
# —una sola L— se acepta SÓLO al leer entradas antiguas, y se normaliza.
#
# POR QUÉ NO SE PODÍA ARREGLAR ANTES. La clave de `stacking_weights.json` era
# `metaloenzyme` con la política genérica `clgnn=1.0`, y el catálogo escribe
# `metalloenzyme`. Los tres receptores de esa familia caían a `default` por la
# discrepancia. Corregir sólo el nombre habría activado esa política genérica,
# que no reproduce ninguno de los tres perfiles validados. Por eso el ADR exige
# desplegar la normalización y los pesos nuevos EN EL MISMO CAMBIO, y por eso
# la entrada genérica se retira en este mismo commit.
#
# La clasificación es por igualdad exacta tras normalizar. Nunca por
# coincidencia difusa tipo `"metal" in family`: `metalloprotease` y
# `metallothionein` no son esto.
FAMILIA_CANONICA_METAL = "metalloenzyme"

#: Alias de LECTURA. Sólo para abrir expedientes antiguos sin reescribir su
#: historia (§6.6 del ADR). Nada nuevo se persiste con estas grafías.
ALIAS_DE_LECTURA = {"metaloenzyme": FAMILIA_CANONICA_METAL}

METALLOENZYME_FAMILIES = frozenset({FAMILIA_CANONICA_METAL, *ALIAS_DE_LECTURA})


def normalizar_familia(familia: str | None) -> str | None:
    """La grafía canónica de una familia, o la que venga si no hay alias.

    Devuelve `None` para entrada vacía. No adivina: sólo aplica el mapa exacto.
    """
    if not familia:
        return None
    limpia = familia.strip().lower()
    return ALIAS_DE_LECTURA.get(limpia, limpia)


def _is_metalloenzyme_family(target_family: str | None) -> bool:
    """True si target_family (posiblemente con typos/grafías) es metaloenzima."""
    if not target_family:
        return False
    return target_family.strip().lower() in METALLOENZYME_FAMILIES


def detect_warheads(smiles: str) -> dict:
    """Devuelve dict warhead_key -> bool usando RDKit SMARTS.

    SMILES inválido o excepción -> todos False (fallo silencioso, consistente
    con la convención del resto del backend).
    """
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return dict.fromkeys(WARHEAD_KEYS, False)
    except Exception:
        return dict.fromkeys(WARHEAD_KEYS, False)

    result = {}
    for key, smarts_list in _WARHEAD_SMARTS.items():
        found = False
        for smarts in smarts_list:
            pat = Chem.MolFromSmarts(smarts)
            if pat and mol.HasSubstructMatch(pat):
                found = True
                break
        result[key] = found

    # Caso especial: detección de tiol infiriendo H implícito en S.
    # El SMARTS-only pierde tioles escritos como 'S' simple (sin [SH]).
    if not result.get("thiol"):
        try:
            for a in mol.GetAtoms():
                if a.GetSymbol() == "S" and a.GetTotalNumHs() == 1:
                    result["thiol"] = True
                    break
        except Exception:
            pass

    return result


def count_donor_atoms(smiles: str) -> int:
    """Cuenta átomos heavy N, O, S desde SMILES (RDKit); fallback regex simple."""
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            return sum(1 for a in mol.GetAtoms()
                       if a.GetAtomicNum() in (7, 8, 16))  # N, O, S
    except Exception:
        pass
    # Fallback: contar patrones N, O, S en el string SMILES
    count = 0
    for ch in smiles:
        if ch in ('N', 'O', 'S') and ch != 'H':
            count += 1
    return count


def compute_universal_metal_score(
    smiles: str,
    molchamb_score: float = 0.5,
    target_family: str | None = None,
) -> tuple[float, dict]:
    """Computa el universal metal score [0..1] y todas las sub-features.

    Args:
        smiles: SMILES del ligando
        molchamb_score: score MolChamb precomputado (0-1), o 0.5 si desconocido
        target_family: familia opcional. "metaloenzyme"/"metalloenzyme" activa
                       la ruta metal (warheads dominan). Cualquier otra familia
                       produce un score conservador (pull hacia 0.5) para no
                       penalizar targets no-metal.

    Returns:
        (universal_metal_score, features_dict)
        universal_metal_score: score combinado [0..1]
        features_dict: todos los componentes para transparencia
    """
    warheads = detect_warheads(smiles)
    donor_count = count_donor_atoms(smiles)
    any_warhead = int(any(warheads.values()))

    # Vector de warheads: 1 si presente por tipo
    wh_vec = {k: int(warheads.get(k, False)) for k in WARHEAD_KEYS}
    n_warheads = sum(wh_vec.values())

    # Si NO es metaloenzima: score conservador (solo MolChamb, que es neutral
    # en targets no-metal). Se usa _is_metalloenzyme_family para tolerar la
    # grafía con 1L o 2L.
    if not _is_metalloenzyme_family(target_family):
        score = 0.3 * molchamb_score + 0.7 * 0.5  # pull hacia 0.5
        score = max(0.0, min(1.0, score))
        return round(score, 4), {
            "any_warhead": any_warhead,
            "n_warheads": n_warheads,
            "donor_count": donor_count,
            "molchamb_score": round(molchamb_score, 4),
            "is_metalloenzyme": False,
            "universal_metal_score": round(score, 4),
            "warheads": wh_vec,
        }

    # Metaloenzima: combinar señales
    # Componente warhead: si hay CUALQUIER warhead, score alto; si no, 0
    if any_warhead:
        warhead_component = 0.85 + 0.10 * min(n_warheads / 3.0, 1.0)  # 0.85-0.95
    else:
        warhead_component = 0.0

    # Componente donor: normalizar por max esperado (~50 N+O+S, divisor 30)
    donor_component = min(1.0, donor_count / 30.0)

    # Componente MolChamb: score crudo
    mc_component = molchamb_score

    # Combinar: warhead domina (señal primaria), donor + molchamb afinan
    score = 0.60 * warhead_component + 0.20 * donor_component + 0.20 * mc_component
    score = max(0.0, min(1.0, score))

    features = {
        "any_warhead": any_warhead,
        "n_warheads": n_warheads,
        "donor_count": donor_count,
        "molchamb_score": round(molchamb_score, 4),
        "is_metalloenzyme": True,
        "universal_metal_score": round(score, 4),
        "warheads": wh_vec,
    }

    return round(score, 4), features


def compute_all(smiles_list: list[str],
                molchamb_scores: list[float] | None = None,
                target_family: str | None = None
                ) -> list[tuple[float, dict]]:
    """Computa universal metal scores en batch."""
    if molchamb_scores is None:
        molchamb_scores = [0.5] * len(smiles_list)
    return [
        compute_universal_metal_score(smi, mc, target_family)
        for smi, mc in zip(smiles_list, molchamb_scores)
    ]

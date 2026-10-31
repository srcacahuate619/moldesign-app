"""
services/docking/preflight.py

Comprobación previa FACTUAL de una corrida de docking. No ejecuta docking.

# Qué es

Responde, antes de gastar un minuto de cómputo: *qué receptor, qué cadena, qué
caja, qué forma química y qué política de preparación van a entrar en la
corrida*, y qué de eso **no se puede saber todavía**.

# Qué NO es

No es un veredicto científico. No dice si la molécula es buena, no produce una
nota 0-100 y no convierte una afinidad en una probabilidad. Cada control
termina en uno de cuatro estados y nada más:

    pasa · advertencia · bloquea · no_evaluado

`no_evaluado` es un resultado de primera clase. Un control que no pudo
ejecutarse **nunca** se reporta como `pasa`: eso convertiría una ausencia de
información en una afirmación, que es el modo de fallo que este módulo existe
para impedir.

# La regla que gobierna el archivo entero

**Todo dato sale de la ruta real de ejecución.** El diff se calcula llamando a
`preparer.filter_pdb_content`, que es literalmente la misma función que usará
la corrida; los hashes se calculan sobre los archivos reales en disco; la
política de heteroátomos se lee de las constantes vivas del preparador y del
sitio de llamada real (`vina_service.run_docking`). No hay una segunda
implementación que pueda divergir, y no se infiere un diff a partir de listas
teóricas.

# Lo que este módulo NO hace, a propósito

- **No descarga nada.** Si la fuente todavía no está en disco, el control
  bloquea la corrida: no se puede sellar una estructura que aún no se leyó.
  Un preflight que se va a la red deja de ser barato y predecible sin conexión.
- **No ejecuta meeko.** El receptor preparado se inspecciona sólo si ya existe.
- **No escribe artefactos de producción.** Sólo lee.

# Rutas

Ninguna ruta absoluta del disco del usuario sale en la respuesta. Se publican
`*_available` y hashes; la ubicación es un detalle del equipo, no evidencia.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from core.config import get_settings
from chem.validator import validate_smiles
from services.docking import preparer
from services.docking.search_policy import BOX_VOLUME_WARNING_A3, box_volume
from utils.local_storage import path_for
from utils.file_handlers import StoragePath
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

PREFLIGHT_SCHEMA_VERSION = 4

#: Identificador de la ruta de ejecución inspeccionada. La política de
#: heteroátomos difiere entre docking y MM-GBSA (docs/53 §6.2), así que el
#: resultado no significa nada sin decir de qué ruta habla.
EXECUTION_ROUTE = "docking_vina"

#: Límites de la caja de búsqueda que la ejecución admite (SOL-13). La interfaz
#: los espeja en `frontend/lib/limitesCaja.ts` y una prueba lee este archivo
#: para que no se separen: un tope de interfaz más estrecho que éste recorta
#: en silencio lo que el usuario pidió. El origen de coordenadas lo fija la
#: estructura, así que el centro sólo se exige finito y acotado.
CAJA_LADO_MIN_A = 5.0
CAJA_LADO_MAX_A = 80.0
CAJA_CENTRO_MAX_A = 10000.0

ControlState = Literal["pasa", "advertencia", "bloquea", "no_evaluado"]


# ── Estructuras ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Control:
    """
    Un hecho comprobado sobre la corrida que se va a lanzar.

    `observation` es lo que se midió; `reason` explica por qué importa;
    `provenance` dice de dónde salió el dato. Los tres son obligatorios para
    que ningún control pueda presentarse sin decir en qué se apoya.
    """

    code: str
    state: ControlState
    title: str
    observation: str
    reason: str
    provenance: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "state": self.state,
            "title": self.title,
            "observation": self.observation,
            "reason": self.reason,
            "provenance": self.provenance,
        }


@dataclass
class _SpeciesCount:
    """Recuento de especies de un PDB, por clase, según las listas vivas."""

    atom_records: int = 0
    hetatm_records: int = 0
    waters: int = 0
    metals: int = 0
    organic_cofactors: int = 0
    other_hetatm: int = 0
    chains: set[str] = field(default_factory=set)
    hetatm_residues: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "atom_records": self.atom_records,
            "hetatm_records": self.hetatm_records,
            "waters": self.waters,
            "metals": self.metals,
            "organic_cofactors": self.organic_cofactors,
            "other_hetatm": self.other_hetatm,
            "chains": sorted(self.chains),
        }


#: `preparer.METAL_COFACTORS` es la lista de RETENCIÓN (qué se conserva sólo vía
#: `cofactors_whitelist`) y mete con los metales un haluro y dos gases nobles.
#: Para rotular una especie no vale: un cloruro junto a la caja salía como
#: «metal», el diff de 3F75 contaba 2 metales que no tiene y Preparación
#: bloqueaba la corrida (QA-027). Se usa la misma lista viva sin los que no son
#: metales; la retención no cambia.
_NO_SON_METALES = frozenset({"CL", "XE", "KR"})


def _es_metal(residue: str) -> bool:
    return residue in preparer.METAL_COFACTORS and residue not in _NO_SON_METALES


#: Cofactores orgánicos que la receta de hoy RETIRA —no tienen plantilla local— y que son cofactores, no aditivos de
#: cristalización: la forma reducida del NADP (NDP, NADPH) y del NAD (NAI, NADH). Sin esto un NDP retirado junto al sitio se
#: contaba como «otra especie» y pedía revisión, como un sulfato, cuando es lo mismo que un NAP retirado: abstención.
#: Aparte de `ORGANIC_COFACTORS_KEPT` a propósito: conservarlos exige una plantilla, y la biblioteca de plantillas entra en el
#: hash de la receta de los 381 receptores (`receptor_recipe_hash`). Decisión del propietario, no una corrección mecánica.
COFACTORES_RECONOCIDOS_QUE_LA_RECETA_RETIRA = frozenset({"NDP", "NAI"})


def _es_cofactor_organico(residue: str) -> bool:
    """Un cofactor orgánico: el que la receta conserva o el que reconoce y retira."""
    return residue in preparer.ORGANIC_COFACTORS_KEPT or residue in COFACTORES_RECONOCIDOS_QUE_LA_RECETA_RETIRA


def _species_category(residue: str) -> str:
    """Categoría estable de API; los nombres internos no llegan a la UI."""

    if residue in preparer.WATER_RESIDUES:
        return "water"
    if _es_metal(residue):
        return "metal"
    if _es_cofactor_organico(residue):
        return "organic_cofactor"
    return "other_heteroatom"


def _removed_species(source: _SpeciesCount, route_input: _SpeciesCount) -> list[dict[str, Any]]:
    """Especies concretas retiradas, expresadas como registros atómicos PDB."""

    removed: list[dict[str, Any]] = []
    for residue_code, source_atoms in sorted(source.hetatm_residues.items()):
        atom_count = source_atoms - route_input.hetatm_residues.get(residue_code, 0)
        if atom_count > 0:
            removed.append(
                {
                    "residue_code": residue_code or "DESCONOCIDO",
                    "atom_count": atom_count,
                    "category": _species_category(residue_code),
                }
            )
    return removed


# ── Utilidades puras ─────────────────────────────────────────────────


def sha256_of(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def count_species(pdb_content: str) -> _SpeciesCount:
    """
    Cuenta átomos y heteroátomos por clase usando las listas VIVAS del
    preparador.

    La clasificación no se reimplementa: `preparer.WATER_RESIDUES`,
    `preparer.METAL_COFACTORS` y `preparer.ORGANIC_COFACTORS_KEPT` son las
    mismas referencias que decide el filtro real. Si mañana alguien añade un
    cofactor a la lista del producto, este recuento cambia con ella. La única
    excepción es el rótulo «metal»: el cloruro y los gases nobles de la lista de
    retención cuentan como otros heteroátomos (ver `_es_metal`).
    """
    counts = _SpeciesCount()
    for line in pdb_content.splitlines():
        record = line[:6].strip()
        if record not in {"ATOM", "HETATM"}:
            continue
        residue = line[17:20].strip()
        chain = (line[21:22].strip() or "A") if len(line) > 21 else "A"
        counts.chains.add(chain)
        if record == "ATOM":
            counts.atom_records += 1
            continue
        counts.hetatm_records += 1
        counts.hetatm_residues[residue] = counts.hetatm_residues.get(residue, 0) + 1
        if residue in preparer.WATER_RESIDUES:
            counts.waters += 1
        elif _es_metal(residue):
            counts.metals += 1
        elif _es_cofactor_organico(residue):
            counts.organic_cofactors += 1
        else:
            counts.other_hetatm += 1
    return counts


def _el_canonico_cambia_el_tautomero(smiles: str) -> bool:
    """¿El canónico de RDKit acoplaría otro tautómero que el escrito? Ante la duda, sí."""
    try:
        from rdkit import Chem, RDLogger
        from rdkit.Chem.MolStandardize import rdMolStandardize

        RDLogger.DisableLog("rdApp.*")
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return True
        parametros = rdMolStandardize.CleanupParameters()
        parametros.tautomerRemoveSp3Stereo = False      # los mismos que `chem/conformer.py`
        parametros.tautomerRemoveBondStereo = False
        canonico = rdMolStandardize.TautomerEnumerator(parametros).Canonicalize(mol)
        return (Chem.MolToSmiles(canonico, isomericSmiles=False)
                != Chem.MolToSmiles(mol, isomericSmiles=False))
    except Exception:  # noqa: BLE001 — sin poder comprobarlo, la huella lo distingue
        return True


def _tautomero_en_la_huella(
    smiles: str, pipeline_config: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """El modo de tautómero, tal como entra en la huella: sólo si cambia lo que se acopla.

    Hasta el 2026-10-10 el valor por defecto era `canonico` y se firmaba sin clave;
    `entrada` se firmaba dentro de `pipeline_config`. Ahora el defecto es `entrada`.
    Firmar siempre el modo convertiría en «corrida anterior» todos los casos
    guardados, aunque su molécula no tenga otro tautómero que acoplar. Así que la
    clave sólo aparece cuando el modo efectivo es `entrada` y el canónico de RDKit
    cambiaría la molécula: la misma codificación de antes para lo que ya existía, y
    una huella distinta para una corrida que ahora acopla otra especie que antes.
    Devuelve la configuración normalizada y, sin `pipeline_config`, la clave suelta.
    """
    import copy

    from services.docking.protocolo import resolver_modo_tautomero

    conformer = ((pipeline_config or {}).get("stage_params") or {}).get("conformer")
    modo = resolver_modo_tautomero(conformer if isinstance(conformer, dict) else None)
    config = copy.deepcopy(pipeline_config) if pipeline_config else None
    anidado = ((config or {}).get("stage_params") or {}).get("conformer")
    if isinstance(anidado, dict):
        anidado.pop("tautomero", None)
    if modo != "entrada" or not _el_canonico_cambia_el_tautomero(smiles):
        return config, None
    if config is None:
        return None, "entrada"
    stage_params = config.setdefault("stage_params", {})
    conformer_params = stage_params.get("conformer")
    if not isinstance(conformer_params, dict):
        conformer_params = stage_params["conformer"] = {}
    conformer_params["tautomero"] = "entrada"
    return config, None


def canonical_input_document(
    *,
    smiles_for_hash: str,
    target_pdb_id: str,
    chain: str,
    grid_center: tuple[float, float, float] | None,
    grid_size: tuple[float, float, float] | None,
    custom_hotspots: list[str] | None,
    docking_engine: str,
    exhaustiveness: int,
    num_poses: int,
    seed: int,
    source_sha256: str | None,
    prepared_sha256: str | None,
    receptor_recipe_hash: str | None = None,
    site_chains: list[str] | None = None,
    cofactors_whitelist: list[str] | None = None,
    conformers: int = 1,
    pipeline_config: dict[str, Any] | None = None,
) -> str:
    """
    Documento canónico del que se deriva el fingerprint.

    **Sólo entra lo que puede cambiar la corrida.** No entra la hora, no entra
    el usuario y no entra nada que varíe entre dos llamadas con los mismos
    inputs: si entrara, el fingerprint dejaría de poder demostrar que la
    corrida corresponde al preflight que se enseñó.

    Los flotantes se redondean a 3 decimales antes de serializar. Sin eso,
    `22.5` y `22.500000000000004` —que producen exactamente la misma caja—
    darían fingerprints distintos y el botón de ejecutar se bloquearía solo.
    """

    def _grid(value: tuple[float, float, float] | None) -> list[float] | None:
        if value is None:
            return None
        return [round(float(v), 3) for v in value]

    document = {
        "schema": PREFLIGHT_SCHEMA_VERSION,
        "route": EXECUTION_ROUTE,
        "smiles": smiles_for_hash,
        "target_pdb_id": target_pdb_id.strip().upper(),
        "chain": chain,
        "grid_center": _grid(grid_center),
        "grid_size": _grid(grid_size),
        # Ordenados: el mismo conjunto de hotspots en otro orden es la misma
        # corrida.
        # SOL-08: `[]` (decisión de no usar referencias) firma distinto que
        # la clave ausente (nunca se abrió Opciones). Antes el truthy
        # colapsaba ambas en la misma huella.
        "custom_hotspots": sorted(custom_hotspots) if custom_hotspots is not None else None,
        "docking_engine": docking_engine,
        "exhaustiveness": int(exhaustiveness),
        "num_poses": int(num_poses),
        "seed": int(seed),
        # Si cambia el artefacto estructural, los mismos campos visibles ya no
        # describen la misma corrida. Los hashes pertenecen por ello a la
        # identidad de la preparación, no sólo a la sección de procedencia.
        "source_sha256": source_sha256,
        "prepared_sha256": prepared_sha256,
        "receptor_recipe_hash": receptor_recipe_hash,
        "site_chains": sorted(site_chains) if site_chains else None,
        "cofactors_whitelist": sorted(cofactors_whitelist or []),
    }
    # `conformers` entra SOLO cuando hay ensemble.
    #
    # Es deliberado y no una omision. Anadir la clave siempre cambiaria el
    # fingerprint de TODOS los casos ya guardados —incluidos los que corrieron
    # con el protocolo por defecto, que no ha cambiado—, y el producto los
    # declararia «corrida anterior»: los inputs no cambiaron, cambio el formato
    # del documento. Con K=1 el protocolo es el mismo de siempre, asi que su
    # identidad tambien.
    if int(conformers or 1) > 1:
        document["conformers"] = int(conformers)
    pipeline_config, tautomero_suelto = _tautomero_en_la_huella(smiles_for_hash, pipeline_config)
    if tautomero_suelto:
        document["tautomero"] = tautomero_suelto
    if pipeline_config:
        # La configuración PRO forma parte de la identidad de la corrida. Se
        # conserva dentro del documento canónico para que activar selectividad,
        # MM/GBSA, precisión GNN o una etapa distinta invalide el preflight.
        document["pipeline_config"] = pipeline_config
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint_of(document: str) -> str:
    return sha256_of(document.encode("utf-8"))


# ── Localización de artefactos (sin red, sin escribir) ───────────────


def _source_pdb_path(pdb_id: str) -> Path | None:
    """Fuente local que usaría prepare_target, sin descargar de la red."""
    return preparer.receptor_source_path_no_network(pdb_id)


def _prepared_pdbqt_path(pdb_id: str, recipe_hash: str | None) -> Path | None:
    if recipe_hash is None:
        return None
    logical = StoragePath.target_prepared(pdb_id, recipe_hash)
    prepared = path_for(logical)
    report = path_for(preparer._meeko_report_path(logical))
    if not prepared.is_file() or not report.is_file():
        return None
    try:
        evidence = json.loads(report.read_text(encoding="utf-8"))
        if (evidence.get("recipe_hash") != recipe_hash
            or evidence.get("receptor_sha256") != hashlib.sha256(prepared.read_bytes()).hexdigest()
            or "protonation_templates" not in evidence):
            return None
    except (OSError, ValueError):
        return None
    return prepared


# ── Núcleo ───────────────────────────────────────────────────────────


def build_preflight(
    *,
    smiles: str,
    target_pdb_id: str,
    chain: str,
    target_origin: str,
    target_reference: str | None,
    grid_center: tuple[float, float, float] | None,
    grid_size: tuple[float, float, float] | None,
    custom_hotspots: list[str] | None,
    catalog_grid_center: tuple[float, float, float] | None,
    catalog_grid_size: tuple[float, float, float] | None,
    catalog_hotspots: list[str] | None,
    cofactors_whitelist: list[str] | None,
    site_chains: list[str] | None = None,
    site_ligand: str | None = None,
    calibracion: dict[str, Any] | None = None,
    docking_engine: str = "vina",
    exhaustiveness: int | None = None,
    num_poses: int | None = None,
    conformers: int | None = None,
    pipeline_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Construye el informe de preparación. Función pura respecto de FastAPI y de
    la base de datos: el router resuelve el target y le pasa datos planos, para
    que las pruebas puedan invocar esto sin levantar una app ni una DB.
    """
    controls: list[Control] = []

    # ── Ligando ──────────────────────────────────────────────────────
    #
    # Se usa `validate_smiles`, exactamente el mismo validador que ejecuta
    # `/evaluation/submit`. La variante que NO lanza: un SMILES inválido tiene
    # que producir un bloqueante legible, no un 422 sin informe.
    validation = validate_smiles(smiles)
    canonical = validation.canonical_smiles
    smiles_hash = validation.smiles_hash

    if validation.is_valid and canonical:
        controls.append(
            Control(
                code="LIGANDO_SMILES_VALIDO",
                state="pasa",
                title="Forma química del ligando",
                observation=(
                    f"SMILES canónico {canonical} · fórmula "
                    f"{validation.molecular_formula or 'no evaluada'} · "
                    f"{validation.heavy_atom_count} átomos pesados."
                ),
                reason="La corrida se ejecuta sobre el SMILES canónico, no sobre el texto introducido.",
                provenance="chem.validator.validate_smiles (mismo validador que /evaluation/submit)",
            )
        )
    else:
        controls.append(
            Control(
                code="LIGANDO_SMILES_VALIDO",
                state="bloquea",
                title="Forma química del ligando",
                observation="; ".join(validation.errors) or "El SMILES no se pudo interpretar.",
                reason="Sin una molécula interpretable no hay nada que acoplar: la corrida fallaría igual, más tarde.",
                provenance="chem.validator.validate_smiles (mismo validador que /evaluation/submit)",
            )
        )

    # Compatibilidad de átomos con Vina. En `strict_science_mode` el validador
    # ya lo convierte en error —y entonces el control de arriba bloquea—, así
    # que aquí sólo queda el caso en que la corrida SÍ se ejecutaría con un
    # score poco fiable: eso es una advertencia, no un bloqueo.
    unsupported = _unsupported_vina_atoms(validation.warnings, validation.errors)
    # OJO al orden: si se detectó un elemento sin parámetros, ESO es lo que se
    # reporta, aunque el validador haya rechazado la molécula y no exista
    # canónico. `no_evaluado` significa «no se pudo mirar», no «se miró y hay
    # un problema»; confundirlos escondería la causa real detrás de un hueco.
    if unsupported:
        controls.append(
            Control(
                code="LIGANDO_ATOMOS_VINA",
                state="bloquea" if not validation.is_valid else "advertencia",
                title="Átomos soportados por el campo de fuerza",
                observation=f"Elementos sin parámetros fiables en Vina: {', '.join(unsupported)}.",
                reason="Vina no tiene parámetros para esos elementos; la energía que devuelva no es comparable.",
                provenance="chem.validator._check_atoms",
            )
        )
    elif canonical:
        controls.append(
            Control(
                code="LIGANDO_ATOMOS_VINA",
                state="pasa",
                title="Átomos soportados por el campo de fuerza",
                observation="Todos los elementos tienen parámetros en el campo de fuerza de Vina.",
                reason="Un elemento sin parámetros produce una energía que no se puede comparar con las demás.",
                provenance="chem.validator._check_atoms",
            )
        )
    else:
        controls.append(
            Control(
                code="LIGANDO_ATOMOS_VINA",
                state="no_evaluado",
                title="Átomos soportados por el campo de fuerza",
                observation="No evaluado: el SMILES no se pudo interpretar.",
                reason="Sin molécula no hay átomos que comprobar.",
                provenance="chem.validator._check_atoms",
            )
        )

    # Advertencias químicas restantes del validador real (fragmentos, tamaño,
    # carga…). Se transcriben; no se reinterpretan ni se puntúan.
    for warning in validation.warnings:
        if _is_atom_warning(warning):
            continue
        controls.append(
            Control(
                code="LIGANDO_REVISION_QUIMICA",
                state="advertencia",
                title="Revisión química del ligando",
                observation=warning,
                reason="El validador de producción lo señaló sin impedir la ejecución.",
                provenance="chem.validator.validate_smiles (warnings)",
            )
        )

    # ── Receptor: artefactos reales ──────────────────────────────────
    pdb_id = target_pdb_id.strip().upper()
    site_ligand = site_ligand or preparer.ligando_del_sitio(pdb_id)
    source_path = _source_pdb_path(pdb_id)
    # Un receptor propio que la persona subió ya preparado se evalúa tal cual: el
    # catálogo no tiene perfil, así que `perfil_propio` es None y nada de lo que
    # sigue cambia para él.
    perfil_propio = preparer.distinto_del_automatico(pdb_id)
    es_pdbqt = perfil_propio is not None and perfil_propio["modo"] == "pdbqt"
    # Una estructura que el equipo ya preparó se respeta: no se retiran sus aguas ni sus metales.
    es_respetar = perfil_propio is not None and perfil_propio["modo"] == "respetar"
    pdbqt_texto: str | None = None
    pdbqt_sha: str | None = None
    if es_pdbqt:
        try:
            pdbqt_bytes = path_for(perfil_propio["almacen"]["receptor"]).read_bytes()
            pdbqt_sha = sha256_of(pdbqt_bytes)
            pdbqt_texto = pdbqt_bytes.decode("utf-8", errors="replace")
        except (OSError, KeyError):
            pdbqt_texto = None
    prepared_path: Path | None = None
    source_original_text: str | None = None
    cadenas_del_sitio = {str(c).strip() for c in (site_chains or []) if str(c).strip()}
    cadenas = cadenas_del_sitio if len(cadenas_del_sitio) > 1 else {chain.strip()}
    # Lo que se ENSEÑA tiene que ser lo que se prepara: en modo multicadena el
    # receptor lleva todas las cadenas del sitio, no sólo `chain` (1HSG decía
    # «sólo conserva 'A'» mientras conservaba A y B).
    varias = len(cadenas) > 1
    etiqueta_cadenas = "+".join(sorted(cadenas))

    source_sha: str | None = None
    source_counts: _SpeciesCount | None = None
    source_text: str | None = None

    if source_path is not None:
        try:
            source_bytes = source_path.read_bytes()
            source_sha = sha256_of(source_bytes)
            source_original_text = (source_bytes.decode("utf-8", errors="replace")
                                    .replace("\r\n", "\n").replace("\r", "\n"))
            from services.chemistry.ensamblaje_biologico import generar_unidad_biologica
            # Un receptor ya preparado se usa tal como viene: no se genera su unidad biológica.
            source_text = (source_original_text if es_respetar
                           else generar_unidad_biologica(source_original_text, pdb_id=pdb_id).pdb)
            source_counts = count_species(source_text)
            controls.append(
                Control(
                    code="RECEPTOR_FUENTE_DISPONIBLE",
                    state="pasa",
                    title="Fuente del receptor",
                    observation=(
                        f"{pdb_id}: {source_counts.atom_records} registros ATOM y "
                        f"{source_counts.hetatm_records} HETATM · cadenas "
                        f"{', '.join(sorted(source_counts.chains)) or 'ninguna'}."
                    ),
                    reason=(
                        "Es la estructura de origen del PDBQT: sólo se usa para auditarlo; el receptor "
                        "de la corrida es el PDBQT tal como se subió."
                        if es_pdbqt else
                        "Es el archivo exacto que leerá la preparación de la corrida."
                    ),
                    provenance=f"{source_path.name} · {source_sha}",
                )
            )
        except OSError as exc:
            source_path = None
            controls.append(
                Control(
                    code="RECEPTOR_FUENTE_DISPONIBLE",
                    state="bloquea",
                    title="Fuente del receptor",
                    observation=f"El archivo existe pero no se pudo leer: {exc.strerror or exc}.",
                    reason="Sin leer la fuente no se puede afirmar nada sobre lo que entra en la corrida.",
                    provenance="lectura local del PDB de origen",
                )
            )
    elif es_pdbqt:
        # El PDBQT se evalúa tal cual; lo que falta es poder AUDITARLO. No bloquea la
        # evaluación, pero tampoco se calla: Preparación pedirá la estructura de origen.
        controls.append(
            Control(
                code="RECEPTOR_FUENTE_DISPONIBLE",
                state="advertencia",
                title="Fuente del receptor",
                observation=(
                    f"{pdb_id} se subió como PDBQT sin estructura de origen"
                    + (f" (SHA-256 {pdbqt_sha[7:]})" if pdbqt_sha else "")
                    + ": se evaluará exactamente ese archivo."
                ),  # plantilla en core/i18n_receptores_propios.py
                reason=(
                    "Sin la estructura de origen no se puede saber qué se retiró al preparar el PDBQT "
                    "(aguas, metales, cofactores, residuos, huecos). Súbela junto al PDBQT para auditar."
                ),
                provenance="PDBQT subido por el investigador",
            )
        )
    else:
        controls.append(
            Control(
                code="RECEPTOR_FUENTE_DISPONIBLE",
                state="bloquea",
                title="Fuente del receptor",
                observation=(
                    f"El PDB de {pdb_id} todavía no está en disco y no se pudo sellar su contenido."
                ),
                reason=(
                    "La comprobación previa no descarga nada: importa o prepara el receptor y "
                    "repite el control para calcular su hash y lo que la preparación retirará."
                ),
                provenance="almacenamiento local (data/targets, biblioteca y caché)",
            )
        )

    # ── Diff fuente → preparado, con la función REAL ─────────────────
    diff: dict[str, Any]
    filtered_counts: _SpeciesCount | None = None
    filtered_text: str | None = None
    chain_error: str | None = None

    if es_pdbqt:
        # El receptor de la corrida es el PDBQT subido: sus átomos son «lo que entra».
        from services.docking.preparer_propio import pdbqt_como_pdb

        if pdbqt_texto is not None:
            filtered_text = pdbqt_como_pdb(pdbqt_texto, con_hidrogenos=True)
            filtered_counts = count_species(filtered_text)
            etiqueta_cadenas = "+".join(sorted(filtered_counts.chains)) or etiqueta_cadenas
        if source_counts is not None and filtered_counts is not None:
            diff = _build_diff(source_counts, filtered_counts, etiqueta_cadenas)
        else:
            diff = _diff_not_evaluated(
                "Sin la estructura de origen no se puede saber qué se retiró al preparar el PDBQT: "
                "súbela para auditar."
            )
    elif source_text is None or source_counts is None:
        diff = _diff_not_evaluated(
            "No hay fuente en disco que comparar. Se calculará cuando la corrida la descargue."
        )
    else:
        try:
            # LA MISMA función que ejecuta la corrida, con LOS MISMOS
            # argumentos que usa `vina_service.run_docking`.
            if es_respetar:
                # LA MISMA función que ejecuta la corrida (preparer_respetando), con la caja provisional
                # que se conoce aquí: la efectiva se resuelve más abajo.
                from services.docking import preparer_respetando as respetando

                traducido, _ = respetando.traducir_residuos(source_text)
                caja_provisional = (
                    tuple(float(v) for v in (grid_center or catalog_grid_center or (0.0, 0.0, 0.0))),
                    tuple(float(v) for v in (grid_size or catalog_grid_size or (20.0, 20.0, 20.0))),
                )
                filtered_text, _ = respetando.filtrar_respetando(traducido, cadenas, *caja_provisional)
                source_counts = count_species(traducido)
            else:
                filtered_text = preparer.filter_pdb_content(
                    source_text,
                    chain_id=cadenas,
                    keep_hetatm=True,
                    cofactors_whitelist=cofactors_whitelist,
                    site_ligand=site_ligand,
                )
            filtered_counts = count_species(filtered_text)
            diff = _build_diff(source_counts, filtered_counts, etiqueta_cadenas)
        except Exception as exc:  # ProteinPreparationError y cualquier otro fallo real
            chain_error = str(getattr(exc, "detail", None) or exc)
            diff = _diff_not_evaluated(
                "El filtrado de la cadena falló, así que no hay preparado con el que comparar."
            )

    if es_pdbqt:
        declaradas = sorted(filtered_counts.chains) if filtered_counts else []
        cadena_pedida = chain.strip()
        if filtered_counts is None:
            estado_cadena, obs_cadena = "no_evaluado", "No se pudo leer el PDBQT subido."
        elif cadena_pedida and cadena_pedida not in declaradas and declaradas:
            estado_cadena = "advertencia"
            obs_cadena = (f"La cadena declarada '{cadena_pedida}' no aparece en el PDBQT, que contiene "
                          f"{', '.join(declaradas)}. Se acopla contra lo que contiene.")
        else:
            estado_cadena = "pasa"
            obs_cadena = (f"El PDBQT aporta {filtered_counts.atom_records} átomos de las cadenas "
                          f"{', '.join(declaradas) or 'sin identificar'} al receptor de la corrida.")
        controls.append(
            Control(
                code="RECEPTOR_CADENA_PRESENTE",
                state=estado_cadena,
                title="Cadena del receptor",
                observation=obs_cadena,
                reason="El receptor es el PDBQT tal como se subió: no se filtra ninguna cadena.",
                provenance="PDBQT subido por el investigador",
            )
        )
    elif chain_error is not None:
        controls.append(
            Control(
                code="RECEPTOR_CADENA_PRESENTE",
                state="bloquea",
                title="Cadena del receptor",
                observation=(
                    f"Filtrar {'las cadenas' if varias else 'la cadena'} '{etiqueta_cadenas}' "
                    "no dejó ningún átomo de proteína."
                ),
                reason=(
                    "La corrida ejecutaría este mismo filtro y fallaría en la preparación. "
                    "Revisa el identificador de cadena del receptor."
                ),
                provenance="preparer.filter_pdb_content (la función que ejecuta la corrida)",
            )
        )
    elif filtered_counts is not None:
        controls.append(
            Control(
                code="RECEPTOR_CADENA_PRESENTE",
                state="pasa",
                title="Cadena del receptor",
                observation=(
                    f"Las cadenas '{etiqueta_cadenas}' aportan {filtered_counts.atom_records} "
                    "átomos de proteína al receptor de la corrida: el sitio se forma entre ellas."
                    if varias else
                    f"La cadena '{etiqueta_cadenas}' aporta {filtered_counts.atom_records} átomos "
                    "de proteína al receptor de la corrida."
                ),
                reason=(
                    "Son las cadenas que se acoplarán juntas; el resto de la estructura no entra."
                    if varias else
                    "Es la cadena que se acoplará; el resto de la estructura no entra."
                ),
                provenance="preparer.filter_pdb_content (la función que ejecuta la corrida)",
            )
        )
    else:
        controls.append(
            Control(
                code="RECEPTOR_CADENA_PRESENTE",
                state="no_evaluado",
                title="Cadena del receptor",
                observation=f"No evaluado: sin la fuente en disco no se puede comprobar la cadena '{etiqueta_cadenas}'.",
                reason="La comprobación exige el archivo real.",
                provenance="preparer.filter_pdb_content (la función que ejecuta la corrida)",
            )
        )

    # ── Política de heteroátomos de ESTA ruta ────────────────────────
    controles_heteroatomos = _heteroatom_controls(
        source_counts=source_counts,
        filtered_counts=filtered_counts,
        cofactors_whitelist=cofactors_whitelist,
    )
    if es_pdbqt:
        # La política del catálogo (aguas fuera, lista blanca de metales) no se aplica a un
        # PDBQT que la persona preparó: se enseña lo que realmente pasa.
        controles_heteroatomos[0] = Control(
            code="POLITICA_HETEROATOMOS",
            state="pasa",
            title="Política de heteroátomos de esta ruta",
            observation=(
                "El PDBQT se usa tal cual: MolDesign no retira aguas, metales ni cofactores. "
                "Lo que contiene es lo que decidió quien lo preparó."
            ),
            reason="Un resultado no se puede comparar con otro sin declarar la política de cada ruta.",
            provenance="PDBQT subido por el investigador",
        )
    if es_respetar:
        controles_heteroatomos[0] = Control(
            code="POLITICA_HETEROATOMOS",
            state="pasa",
            title="Política de heteroátomos de esta ruta",
            observation=(
                "Receptor ya preparado por el usuario: se conservan las aguas, los metales y los cofactores "
                "que trae el archivo (sin lista blanca). Sólo se retiran, y se declaran, las especies de otras "
                "cadenas y las que Meeko no puede representar lejos del sitio."
            ),
            reason="Un resultado no se puede comparar con otro sin declarar la política de cada ruta.",
            provenance="preparer_respetando.filtrar_respetando (la función que ejecuta la corrida)",
        )
    controls.extend(controles_heteroatomos)

    if es_respetar and filtered_text is not None:
        from services.docking import preparer_respetando as respetando

        sin_representacion = respetando.especies_sin_representacion(filtered_text, *caja_provisional)
        cerca = [f for f in sin_representacion if f["distance_to_box_A"] <= preparer.MARGEN_SITIO_A]
        if sin_representacion:
            etiquetas = ", ".join(respetando._etiqueta(f) for f in sin_representacion[:6])
            controls.append(Control(
                code="ESPECIES_SIN_REPRESENTACION",
                state="bloquea" if cerca else "advertencia",
                title="Especies que Meeko no puede representar",
                observation=(
                    f"{len(sin_representacion)} especie(s) del archivo no tienen plantilla en Meeko o no se "
                    f"pueden tipar para Vina: {etiquetas}."
                ),
                reason=(
                    "Junto al sitio la preparación se abstiene: ni se adivinan ni se retiran en silencio. "
                    "Lejos de él se retiran y se declaran."
                ),
                provenance="preparer_respetando.especies_sin_representacion",
            ))
    from chem.conformer_ensemble import normalizar_k

    # K declarado en el nivel superior del request. La resolución efectiva la
    # hace `_effective_configuration` con el resolutor único (SOL-02): el
    # anidado gobierna y este valor sólo sirve para declarar el conflicto si
    # el cliente envía los dos y no coinciden.
    conformaciones = normalizar_k(conformers if conformers is not None else 1)

    effective, grid_controls = _effective_configuration(
        grid_center=grid_center,
        grid_size=grid_size,
        catalog_grid_center=catalog_grid_center,
        catalog_grid_size=catalog_grid_size,
        custom_hotspots=custom_hotspots,
        catalog_hotspots=catalog_hotspots,
        cofactors_whitelist=cofactors_whitelist,
        filtered_text=(filtered_text if es_pdbqt else
                       preparer.source_for_dynamic_box(
                           source_text, cadenas, site_ligand, preparer.catalog_site_center(pdb_id))
                       if source_text is not None else None),
        prepared_chains=sorted(filtered_counts.chains) if filtered_counts else [],
        docking_engine=docking_engine,
        exhaustiveness=exhaustiveness,
        num_poses=num_poses,
        conformers=conformaciones,
        pipeline_config=pipeline_config,
    )
    controls.extend(grid_controls)

    # ── Cofactores sin plantilla: la MISMA regla que prepare_target ──
    #
    # Antes bastaba un HETATM orgánico conservado para bloquear: el hemo, el FMN, el ADP y los
    # fosforresiduos, que tienen plantilla local, y hasta la MET que sale de una MSE. Eran 18 de los
    # 381 receptores del catálogo y en los 18 era el único bloqueante: la corrida se rechazaba (409)
    # aunque prepare_target la preparaba (auditoría de receptores, 2026-10-10). Se consulta la misma
    # función, con el mismo ensamblaje, cadenas, ligando de referencia, lista blanca y CAJA EFECTIVA
    # (overrides y caja dinámica incluidos). Un receptor propio ya preparado o un PDBQT tienen sus
    # propios controles: no pasan por la preparación automática.
    cofactor_check: dict[str, Any] = {"state": "no_evaluado"}
    if not (es_pdbqt or es_respetar) and source_text is not None:
        box_center = tuple(float(v) for v in effective["grid_center"])
        box_size = tuple(float(v) for v in effective["grid_size"])
        if all(math.isfinite(v) for v in (*box_center, *box_size)) and all(v > 0 for v in box_size):
            en_el_sitio, fuera_del_sitio = preparer.cofactores_sin_plantilla(
                source_text, cadenas=cadenas, site_ligand=site_ligand,
                cofactors_whitelist=cofactors_whitelist, center=box_center, size=box_size,
            )
            cofactor_check = {
                "state": "evaluado",
                "margin_A": preparer.MARGEN_SITIO_A,
                "box_center": list(box_center),
                "box_size": list(box_size),
                "missing_near_site": en_el_sitio,
                "missing_outside_site": fuera_del_sitio,
                "local_templates_sha256": preparer._plantillas_sha256(),
            }

            def _instancias(filas: list[dict[str, Any]]) -> str:
                return ", ".join(
                    f"{f['name']} {f['chain']}:{f['residue_number']}{f['insertion_code']} "
                    f"({f['distance_to_box_A']} Å)" for f in filas
                )

            if en_el_sitio:
                controls.append(Control(
                    code="COFACTOR_TEMPLATE_NO_DISPONIBLE",
                    state="bloquea",
                    title="Plantilla local de cofactor",
                    observation=(
                        f"Sin plantilla Meeko local a {preparer.MARGEN_SITIO_A:g} Å o menos de la caja: "
                        f"{_instancias(en_el_sitio)}."
                    ),
                    reason="La preparación se abstiene antes de consultar CCD por red o retirar el cofactor.",
                    provenance="preparer.cofactores_sin_plantilla · caja efectiva de la corrida, la misma regla que prepare_target",
                ))
            if fuera_del_sitio:
                controls.append(Control(
                    code="COFACTORES_SIN_PLANTILLA_FUERA_DEL_SITIO",
                    state="advertencia",
                    title="Cofactores sin plantilla fuera del margen",
                    observation=(
                        f"La preparación retirará {_instancias(fuera_del_sitio)}: "
                        f"a más de {preparer.MARGEN_SITIO_A:g} Å de la caja."
                    ),
                    reason=(
                        "Quedan fuera del margen geométrico de preparación; esa distancia no demuestra "
                        "irrelevancia química."
                    ),
                    provenance="preparer.cofactores_sin_plantilla · caja efectiva de la corrida, la misma regla que prepare_target",
                ))
                # prepare_target los retira antes de filtrar: el diff y la política de heteroátomos
                # tienen que contar lo que de verdad entra, no lo que había antes de retirarlos.
                if filtered_text is not None and source_counts is not None:
                    filtered_text = preparer.retirar_cofactores_fuera_del_sitio(filtered_text, fuera_del_sitio)
                    filtered_counts = count_species(filtered_text)
                    diff = _build_diff(source_counts, filtered_counts, etiqueta_cadenas)
                    rehechos = _heteroatom_controls(
                        source_counts=source_counts,
                        filtered_counts=filtered_counts,
                        cofactors_whitelist=cofactors_whitelist,
                    )
                    inicio = next(i for i, c in enumerate(controls) if c is controles_heteroatomos[0])
                    controls[inicio:inicio + len(controles_heteroatomos)] = rehechos

    if es_pdbqt:
        from services.docking.preparer_propio import receta_pdbqt

        recipe_hash = receta_pdbqt(
            perfil_propio, tuple(effective["grid_center"]), tuple(effective["grid_size"]))
        # El receptor preparado ES el PDBQT que se subió: existe desde la ingesta.
        prepared_path = path_for(perfil_propio["almacen"]["receptor"]) if pdbqt_texto is not None else None
    elif es_respetar:
        from services.docking import preparer_respetando as respetando

        recipe_hash = (
            respetando.receta_respetando(
                source_original_text, cadenas, tuple(effective["grid_center"]), tuple(effective["grid_size"]))
            if source_original_text is not None else None
        )
        prepared_path = _prepared_pdbqt_path(pdb_id, recipe_hash)
    else:
        recipe_hash = (
            preparer.receptor_recipe_hash(
                source_original_text,
                chains=cadenas,
                cofactors_whitelist=cofactors_whitelist,
                center=tuple(effective["grid_center"]),
                size=tuple(effective["grid_size"]),
                site_ligand=site_ligand,
            )
            if source_original_text is not None else None
        )
        prepared_path = _prepared_pdbqt_path(pdb_id, recipe_hash)

    # ── Receptor preparado ───────────────────────────────────────────
    prepared_sha: str | None = None
    prepared_sha_for_run: str | None = None
    prepared_compatible: bool | None = None
    prepared_chains: list[str] = []
    if es_pdbqt and pdbqt_texto is not None:
        prepared_sha = pdbqt_sha
        prepared_sha_for_run = pdbqt_sha
        prepared_compatible = True
        prepared_chains = sorted(preparer.prepared_receptor_chains(pdbqt_texto))
        controls.append(
            Control(
                code="RECEPTOR_PREPARADO_DISPONIBLE",
                state="pasa",
                title="Receptor preparado",
                observation=(
                    f"El receptor es el PDBQT que subiste, sin cambios "
                    f"({sum(1 for l in pdbqt_texto.splitlines() if l.startswith(('ATOM', 'HETATM')))} átomos)."
                ),
                reason="La corrida lo usa tal cual; su hash entra en la huella.",
                provenance=f"PDBQT subido · {pdbqt_sha}",
            )
        )
    elif prepared_path is not None:
        try:
            prepared_bytes = prepared_path.read_bytes()
            prepared_sha = sha256_of(prepared_bytes)
            prepared_text = prepared_bytes.decode("utf-8", errors="replace")
            prepared_chains = sorted(preparer.prepared_receptor_chains(prepared_text))
            prepared_compatible = preparer.prepared_receptor_matches_chain(
                prepared_text,
                cadenas,
            )
            prepared_atoms = sum(
                1
                for line in prepared_text.splitlines()
                if line.startswith(("ATOM", "HETATM"))
            )
            if prepared_compatible:
                prepared_sha_for_run = prepared_sha
                controls.append(
                    Control(
                        code="RECEPTOR_PREPARADO_DISPONIBLE",
                        state="pasa",
                        title="Receptor preparado",
                        observation=(
                            f"Existe un receptor preparado compatible con la cadena '{chain}' "
                            f"y {prepared_atoms} átomos."
                        ),
                        reason="La corrida lo reutilizará tal cual; la huella identifica la fuente y la receta.",
                        provenance=f"prepared.pdbqt · {prepared_sha}",
                    )
                )
            else:
                controls.append(
                    Control(
                        code="RECEPTOR_PREPARADO_OBSOLETO",
                        state="advertencia",
                        title="Receptor preparado incompatible",
                        observation=(
                            f"El PDBQT cacheado contiene la(s) cadena(s) "
                            f"{', '.join(prepared_chains) or 'no declaradas'}, no exclusivamente '{chain}'."
                        ),
                        reason=(
                            "La corrida no lo reutilizará: el preparador verifica la cadena y lo "
                            "regenerará desde la fuente antes de ejecutar Vina."
                        ),
                        provenance=f"prepared.pdbqt · {prepared_sha}",
                    )
                )
        except OSError:
            prepared_path = None

    if prepared_path is None:
        controls.append(
            Control(
                code="RECEPTOR_PREPARADO_DISPONIBLE",
                state="bloquea" if es_pdbqt else "no_evaluado",
                title="Receptor preparado",
                observation=("No se pudo leer el PDBQT que se subió; la corrida no tiene receptor."
                             if es_pdbqt else "Todavía no existe: la corrida lo generará con Meeko."),
                reason=(
                    "El hash del receptor preparado sólo puede calcularse sobre un archivo que exista. "
                    "Prepararlo aquí convertiría la comprobación previa en trabajo de corrida."
                ),
                provenance="almacenamiento local de targets preparados",
            )
        )

    if es_pdbqt and prepared_compatible:
        controls.append(Control(
            code="RECEPTOR_PROTONACION_DECLARADA", state="advertencia",
            title="Protonación del receptor",
            observation="La declara quien preparó el PDBQT; MolDesign no la comprueba ni la modifica.",
            reason=(
                "Un PDBQT no lleva el JSON de plantillas de Meeko, así que no se puede atribuir una "
                "protonación concreta a cada residuo. El hash del archivo identifica lo que se acopla."
            ),
            provenance="PDBQT subido por el investigador",
        ))
    elif prepared_path is not None and prepared_compatible:
        try:
            prep_report = json.loads(path_for(preparer._meeko_report_path(
                StoragePath.target_prepared(pdb_id, recipe_hash)
            )).read_text(encoding="utf-8"))
            templates = prep_report["protonation_templates"]
            histidines = sorted(
                f"{resid}={row['template']}" for resid, row in templates.items()
                if row.get("input_resname") in {"HIS", "HID", "HIE", "HIP"}
            )
            declarada = prep_report.get("protonacion_declarada")
            if declarada:
                controls.append(Control(
                    code="RECEPTOR_PROTONACION_DECLARADA", state="advertencia",
                    title="Protonación del receptor",
                    observation=(
                        f"La declara quien preparó el archivo: {declarada.get('plantillas_declaradas', 0)} "
                        "residuo(s) con protonación en el nombre, y Meeko aplicó exactamente esas plantillas."
                        + (" Plantillas de histidina: " + ", ".join(histidines) + "." if histidines else "")
                    ),
                    reason="MolDesign no fija un pH ni decide la protonación: la responsabilidad es de quien preparó el receptor.",
                    provenance="informe Meeko del receptor preparado",
                ))
            else:
                controls.append(Control(
                    code="RECEPTOR_PROTONACION_DECLARADA", state="advertencia",
                    title="Protonación del receptor",
                    observation=("Plantillas de histidina de Meeko: "
                                 + (", ".join(histidines) if histidines else "ninguna") + "."),
                    reason="El template elegido está registrado; el microestado experimental no está validado.",
                    provenance="informe Meeko del receptor preparado",
                ))
        except (OSError, ValueError, KeyError, TypeError):
            controls.append(Control(
                code="RECEPTOR_PROTONACION_DECLARADA", state="bloquea",
                title="Protonación del receptor",
                observation="El receptor preparado carece del resumen de plantillas de Meeko.",
                reason="No se puede atribuir una protonación concreta a un PDBQT sin este registro.",
                provenance="informe Meeko del receptor preparado",
            ))
    elif source_text is not None:
        controls.append(Control(
            code="RECEPTOR_PROTONACION_DECLARADA", state="no_evaluado",
            title="Protonación del receptor",
            observation="Meeko aún no ha preparado el receptor; la plantilla elegida no se conoce.",
            reason="El preflight no ejecuta Meeko ni adivina HIE/HID/HIP desde un PDB sin hidrógenos.",
            provenance="Meeko 0.7.1 · selección de plantillas",
        ))

    # ── Herramientas del runtime ─────────────────────────────────────
    controls.extend(
        _toolchain_controls(
            docking_engine,
            receptor_prepared=prepared_compatible is True,
        )
    )

    # ── Configuración efectiva ───────────────────────────────────────
    # ── Protocolo de generacion 3D ───────────────────────────────────
    #
    # Vive con exhaustividad, poses y semilla porque es lo mismo: un parametro
    # que cambia lo que se ejecuta, se congela con el caso y se imprime en el
    # dossier. Un valor imposible cae al defecto en vez de bloquear: el
    # preflight informa, no rechaza por una cifra mal escrita.
    # Se expone junto a la configuración efectiva para que el cliente pueda
    # persistir el mismo protocolo y reenviarlo en /evaluation/submit.
    if pipeline_config:
        effective["pipeline_config"] = pipeline_config

    # ── Deudas declaradas ────────────────────────────────────────────
    controls.extend(_declared_debts())
    controls.extend(_calibration_controls(calibracion))

    # ── Fingerprint ──────────────────────────────────────────────────
    #
    # Sobre el SMILES CANÓNICO cuando existe: dos textos distintos de la misma
    # molécula son la misma corrida. Si no se pudo canonicalizar, se usa el
    # texto crudo para que el fingerprint siga cambiando cuando el usuario
    # corrige el SMILES.
    document = canonical_input_document(
        smiles_for_hash=canonical or smiles.strip(),
        target_pdb_id=pdb_id,
        chain=chain,
        grid_center=tuple(effective["grid_center"]),
        grid_size=tuple(effective["grid_size"]),
        custom_hotspots=list(effective["hotspots"]),
        docking_engine=docking_engine,
        exhaustiveness=int(effective["exhaustiveness"]),
        num_poses=int(effective["num_poses"]),
        seed=int(effective["seed"]),
        source_sha256=source_sha,
        # El PDBQT subido es una entrada, no un producto de una receta: su hash
        # debe firmarse. Para otros receptores, la identidad sigue siendo fuente
        # y receta: que aparezca una caché tras la primera corrida no debe cambiar
        # la huella de una hipótesis que no cambió.
        prepared_sha256=prepared_sha_for_run if es_pdbqt else None,
        receptor_recipe_hash=recipe_hash,
        site_chains=sorted(cadenas) if len(cadenas) > 1 else None,
        cofactors_whitelist=cofactors_whitelist,
        conformers=int(effective["conformers"]),
        pipeline_config=pipeline_config,
    )

    report = {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_route": EXECUTION_ROUTE,
        "input_fingerprint": fingerprint_of(document),
        "input_document": document,
        "receptor": {
            "reference": target_reference,
            "pdb_id": pdb_id,
            "chain": chain,
            "origin": target_origin,
            "source_available": source_path is not None,
            "source_sha256": source_sha,
            "prepared_available": prepared_path is not None,
            "prepared_sha256": prepared_sha,
            "recipe_hash": recipe_hash,
            "site_chains": sorted(cadenas),
            "site_ligand_removed": site_ligand,
            "cofactor_template_check": cofactor_check,
            "prepared_compatible": prepared_compatible,
            "prepared_chains": prepared_chains,
            # SC-9: el respaldo científico del receptor viaja con el informe,
            # no se deduce en cada pantalla. Ver `services/targets/calibracion.py`.
            "calibracion": calibracion,
        },
        "ligand": {
            "input_smiles": smiles,
            "canonical_smiles": canonical,
            "smiles_hash": smiles_hash,
            "molecular_formula": validation.molecular_formula,
            "heavy_atom_count": validation.heavy_atom_count,
            "error": None if validation.is_valid else "; ".join(validation.errors),
            "vina_atom_compatibility": {
                "evaluated": canonical is not None,
                "supported": canonical is not None and not unsupported,
                "unsupported_elements": sorted(unsupported),
            },
        },
        "effective_config": effective,
        "preparation_diff": diff,
        "controls": [control.as_dict() for control in controls],
        "technical_blockers": [c.code for c in controls if c.state == "bloquea"],
        "warnings": [c.code for c in controls if c.state == "advertencia"],
        "not_evaluated": [c.code for c in controls if c.state == "no_evaluado"],
    }
    if perfil_propio:
        # Sólo un receptor propio con otro modo de preparación lo trae: el informe del
        # catálogo no cambia. Dice qué se hizo con el archivo que subió la persona.
        report["receptor"]["modo_de_preparacion"] = (
            perfil_propio.get("modo_detallado") or perfil_propio["modo"])
    return report


# ── Piezas ───────────────────────────────────────────────────────────


def _calibration_controls(calibracion: dict[str, Any] | None) -> list[Control]:
    """SC-9: el respaldo del receptor es un control del preflight, no un adorno.

    Es siempre `advertencia`, nunca `bloquea`: la falta de calibración no impide
    ejecutar —el investigador puede querer explorar— pero sí cambia lo que el
    resultado permite afirmar, y por eso tiene que leerse ANTES de lanzar.

    Sin dato de calibración se declara `no_evaluado`, no «todo bien»: no saber
    qué respaldo tiene un receptor no es lo mismo que saber que lo tiene.
    """
    if not calibracion:
        return [
            Control(
                code="CALIBRACION_RECEPTOR",
                state="no_evaluado",
                title="Respaldo científico del receptor",
                observation="No se pudo determinar el estado de calibración.",
                reason=(
                    "Sin este dato no se puede saber si el ranking del motor "
                    "está respaldado para este receptor."
                ),
                provenance="services/targets/calibracion.py",
            )
        ]

    nivel = calibracion.get("nivel", "sin_curar")
    respaldo = calibracion.get("respaldo")
    # SCI-D-001: un «calibrado» sin su medida (n, IC, panel, protocolo) no
    # suprime la reserva, venga de donde venga el diccionario.
    respaldado = (
        nivel == "calibrado"
        and isinstance(respaldo, dict)
        and all(respaldo.get(k) not in (None, "", []) for k in ("rho", "ic95", "n", "panel", "protocolo"))
    )
    requiere = bool(calibracion.get("requiere_advertencia", True)) or not respaldado
    observacion = calibracion.get("resumen", "")
    if respaldado:
        ic = respaldo["ic95"]
        observacion = (
            f"{observacion} (ρ = {respaldo['rho']:.2f}, IC 95 % [{ic[0]:.2f}; {ic[1]:.2f}], "
            f"n = {respaldo['n']}, panel {respaldo['panel']})"
        )
    if respaldado:
        protocolo = respaldo["protocolo"]
        razon = (
            "El ranking del motor se calibró para este receptor con exhaustividad "
            f"{protocolo.get('exhaustiveness')}, {protocolo.get('num_poses')} poses y semilla "
            f"{protocolo.get('semilla')}; la medida describe corridas con esos parámetros."
        )
    else:
        razon = calibracion.get("advertencia") or (
            "No hay una medida de calibración con n, intervalo y protocolo para este "
            "receptor: el ranking no está respaldado aquí."
        )
    return [
        Control(
            code="CALIBRACION_RECEPTOR",
            state="advertencia" if requiere else "pasa",
            title="Respaldo científico del receptor",
            observation=observacion,
            reason=razon,
            provenance=(
                f"receptores_verificados.json + familia estructural ({nivel}); "
                "services/targets/calibracion.py"
            ),
        )
    ]


def _is_atom_warning(warning: str) -> bool:
    return "AutoDock Vina no tiene parámetros" in warning or "Átomos no soportados" in warning


def _unsupported_vina_atoms(warnings: list[str], errors: list[str]) -> list[str]:
    """
    Extrae los elementos señalados por el validador real.

    Se leen de sus mensajes en vez de recalcularse: recalcular significaría
    tener una segunda lista de elementos soportados que puede divergir de la
    que decide el comportamiento.
    """
    found: list[str] = []
    for message in [*errors, *warnings]:
        if not _is_atom_warning(message):
            continue
        start = message.find("[")
        end = message.find("]", start)
        if start == -1 or end == -1:
            continue
        for chunk in message[start + 1 : end].split(","):
            element = chunk.strip().strip("'\"")
            if element and element not in found:
                found.append(element)
    return found


def _diff_not_evaluated(reason: str) -> dict[str, Any]:
    return {
        "state": "no_evaluado",
        "reason": reason,
        "source": None,
        "route_input": None,
        "removed": None,
        "removed_species": None,
        "preserved": None,
    }


def _build_diff(
    source: _SpeciesCount, route_input: _SpeciesCount, chain: str
) -> dict[str, Any]:
    """
    Diff comparable entre la fuente y el PDB filtrado que recibirá Meeko.

    Los recuentos de la fuente son de la estructura ENTERA; los de
    ``route_input``, de la cadena elegida antes de convertirla a PDBQT. No se
    llama «receptor preparado»: Meeko puede añadir o transformar átomos y ese
    artefacto sólo se cuenta si ya existe por separado.
    """
    same_chain_note = (
        f"La fuente incluye {len(source.chains)} cadena(s); el receptor de la corrida sólo "
        f"conserva '{chain}'."
    )
    return {
        "state": "evaluado",
        "reason": same_chain_note,
        "source": source.as_dict(),
        "route_input": route_input.as_dict(),
        "removed": {
            "waters": source.waters - route_input.waters,
            "metals": source.metals - route_input.metals,
            "organic_cofactors": source.organic_cofactors - route_input.organic_cofactors,
            "other_hetatm": source.other_hetatm - route_input.other_hetatm,
        },
        "removed_species": _removed_species(source, route_input),
        "preserved": {
            "atom_records": route_input.atom_records,
            "organic_cofactors": route_input.organic_cofactors,
            "metals": route_input.metals,
            "waters": route_input.waters,
        },
    }


def _instancias_hetatm(
    pdb_content: str,
) -> dict[tuple[str, str, str, str], list[tuple[float, float, float]]]:
    """Posiciones de cada instancia HETATM, por (cadena, número, inserción, nombre)."""
    instancias: dict[tuple[str, str, str, str], list[tuple[float, float, float]]] = {}
    for line in pdb_content.splitlines():
        if not line.startswith("HETATM") or len(line) < 54:
            continue
        try:
            pos = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except ValueError:
            continue
        key = (line[21:22].strip() or "A", line[22:26].strip(), line[26:27].strip(),
               line[17:20].strip())
        instancias.setdefault(key, []).append(pos)
    return instancias


def diff_de_especies_de_la_corrida(
    fuente: str,
    entrada_meeko: str,
    *,
    cadenas: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    site_ligand: str | None,
) -> dict[str, Any]:
    """El diff de heteroátomos que la corrida GUARDA en el informe del receptor.

    ``preparer.prepare_target`` lo llama con el ensamblaje del que parte y con
    el PDB exacto que entrega a Meeko; ``vina_service`` lo copia a
    ``execution_provenance.receptor_prep.species_diff``. Los recuentos son los
    de :func:`_build_diff` —la misma semántica que enseña el preflight—, y se
    añade lo que un recuento global no puede decir: qué instancias estaban a
    ``MARGEN_SITIO_A`` o menos de la caja y si llegaron a Meeko. Un zinc
    catalítico retirado y un sulfato a 40 Å cuentan igual en ``removed``;
    en ``near_site`` no.

    Una instancia cuenta como conservada si su residuo (cadena, número,
    inserción) llega a Meeko con cualquier registro: la selenometionina entra
    como MET y lo declara ``converted_to``. Lo que Meeko borre después va en
    ``removed_residues`` del mismo informe, no aquí.

    ``protein_residues_removed`` cuenta, por cadena, los residuos de proteína
    que tocan la caja y no llegan a Meeko: cadenas que el receptor excluye.
    """
    diff = _build_diff(count_species(fuente), count_species(entrada_meeko), cadenas)
    ligando = (site_ligand or "").strip().upper()
    en_meeko: dict[tuple[str, str, str], str] = {}
    for line in entrada_meeko.splitlines():
        if line.startswith(("ATOM", "HETATM")) and len(line) >= 27:
            en_meeko.setdefault(
                (line[21:22].strip() or "A", line[22:26].strip(), line[26:27].strip()),
                line[17:20].strip(),
            )
    retiradas: list[dict[str, Any]] = []
    conservadas: list[dict[str, Any]] = []
    instancias = _instancias_hetatm(fuente)
    # El ligando del cristal es UNA copia: la más cercana al centro de la caja, como la referencia de
    # `contexto_estructural`. Las otras con el mismo código se retiran igual, pero se declaran como otra
    # especie. FEP-06-PRE-2 (6SXC): OHT A:307, a 3,3 Å de OHT A:305, desaparecía como «el ligando» y la
    # auditoría decía que no se había retirado nada a 6 Å o menos.
    copias = [clave for clave in instancias if ligando and clave[3] == ligando]
    referencia = min(copias, key=lambda c: min(math.dist(p, center) for p in instancias[c]), default=None)
    for (cadena, numero, insercion, nombre), posiciones in sorted(instancias.items()):
        distancia = min(preparer.distancia_a_caja(p, center, size) for p in posiciones)
        if distancia > preparer.MARGEN_SITIO_A:
            continue
        fila: dict[str, Any] = {
            "chain": cadena,
            "residue_number": numero,
            "insertion_code": insercion,
            "name": nombre,
            "category": "site_ligand" if (cadena, numero, insercion, nombre) == referencia
            else "other_heteroatom" if ligando and nombre == ligando
            else _species_category(nombre),
            "distance_to_box_A": round(distancia, 3),
        }
        if ligando and nombre == ligando and (cadena, numero, insercion, nombre) != referencia:
            fila["site_ligand_copy"] = True
        destino = en_meeko.get((cadena, numero, insercion))
        if destino is None:
            retiradas.append(fila)
            continue
        if destino != nombre:
            fila["converted_to"] = destino
        conservadas.append(fila)
    # Proteína que no llega a Meeko y toca la caja: una cadena vecina que el
    # receptor excluye. En 1C3R la caja de 30 Å encierra 48 residuos de la
    # cadena B mientras `site_chains` dice sólo A.
    proteina: dict[str, set[tuple[str, str]]] = {}
    for line in fuente.splitlines():
        if not line.startswith("ATOM") or len(line) < 54:
            continue
        cadena = line[21:22].strip() or "A"
        clave = (line[22:26].strip(), line[26:27].strip())
        if (cadena, *clave) in en_meeko or clave in proteina.get(cadena, ()):
            continue
        try:
            pos = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except ValueError:
            continue
        if preparer.distancia_a_caja(pos, center, size) <= preparer.MARGEN_SITIO_A:
            proteina.setdefault(cadena, set()).add(clave)
    diff["site_ligand"] = ligando or None
    diff["near_site"] = {
        "margin_A": preparer.MARGEN_SITIO_A,
        "removed": retiradas,
        "preserved": conservadas,
        "protein_residues_removed": {c: len(r) for c, r in sorted(proteina.items())},
    }
    return diff


def _heteroatom_controls(
    *,
    source_counts: _SpeciesCount | None,
    filtered_counts: _SpeciesCount | None,
    cofactors_whitelist: list[str] | None,
) -> list[Control]:
    """
    Declara la política REAL de esta ruta y lo que le cuesta a esta estructura.

    La whitelist del target viaja en PipelineParams y llega a `prepare_target`
    en la ruta de docking. Se publica junto con la política para que conservar
    un metal o cofactor sea una decisión verificable, no una promesa de UI.
    """
    whitelist_declared = sorted(cofactors_whitelist or [])
    policy_observation = (
        "Ruta de docking: se eliminan TODAS las aguas; los metales sólo se conservan "
        "si el receptor los declara explícitamente; "
        f"se conservan los cofactores orgánicos reconocidos "
        f"({', '.join(sorted(preparer.ORGANIC_COFACTORS_KEPT))})."
    )
    if whitelist_declared:
        policy_observation += (
            f" La corrida aplicará la lista de conservación del receptor "
            f"({', '.join(whitelist_declared)})."
        )

    controls = [
        Control(
            code="POLITICA_HETEROATOMOS",
            state="pasa",
            title="Política de heteroátomos de esta ruta",
            observation=policy_observation,
            reason=(
                "MM-GBSA y otros métodos pueden aplicar políticas distintas. "
                "Un resultado no se puede comparar con otro sin declarar la política de cada ruta."
            ),
            provenance="preparer.filter_pdb_content + sitio de llamada en vina_service.run_docking",
        )
    ]

    if source_counts is None or filtered_counts is None:
        controls.append(
            Control(
                code="ESPECIES_DEL_SITIO_RETIRADAS",
                state="no_evaluado",
                title="Especies retiradas de la estructura",
                observation="No evaluado: sin la fuente en disco no hay nada que comparar.",
                reason="El recuento sale de comparar archivos reales, no de una lista teórica.",
                provenance="preparer.filter_pdb_content",
            )
        )
        return controls

    removed_waters = source_counts.waters - filtered_counts.waters
    removed_metals = source_counts.metals - filtered_counts.metals
    removed_cofactors = source_counts.organic_cofactors - filtered_counts.organic_cofactors
    removed_other = source_counts.other_hetatm - filtered_counts.other_hetatm
    removed_species = _removed_species(source_counts, filtered_counts)
    removed_metal_species = [
        item for item in removed_species if item["category"] == "metal"
    ]
    total_removed = removed_waters + removed_metals + removed_cofactors + removed_other

    if total_removed == 0:
        controls.append(
            Control(
                code="ESPECIES_DEL_SITIO_RETIRADAS",
                state="pasa",
                title="Especies retiradas de la estructura",
                observation="La preparación no retira ningún heteroátomo de esta estructura.",
                reason="Nada que decidir: no hay especies en disputa.",
                provenance="preparer.filter_pdb_content sobre el PDB de origen",
            )
        )
    else:
        parts = []
        if removed_waters:
            parts.append(f"{removed_waters} átomos de agua")
        if removed_metals:
            parts.append(f"{removed_metals} átomos metálicos")
        if removed_cofactors:
            parts.append(f"{removed_cofactors} átomos de cofactor orgánico")
        if removed_other:
            parts.append(f"{removed_other} otros heteroátomos (ligandos, lípidos, aditivos)")
        controls.append(
            Control(
                code="ESPECIES_DEL_SITIO_RETIRADAS",
                # Advertencia, no bloqueo: retirar especies es la política
                # declarada del producto, no un error. Lo que no es aceptable
                # es que ocurra sin que nadie lo vea.
                state="advertencia",
                title="Especies retiradas de la estructura",
                observation="La preparación retira " + ", ".join(parts) + ".",
                reason=(
                    "Si alguna de esas especies pertenece al sitio de unión, la corrida acopla "
                    "contra un sitio distinto del cristalográfico. La decisión es tuya; el sistema "
                    "no la toma ni la corrige."
                ),
                provenance="preparer.filter_pdb_content sobre el PDB de origen",
            )
        )

    if removed_metals > 0:
        metal_detail = ", ".join(
            f"{item['residue_code']} ({item['atom_count']} átomo"
            f"{'s' if item['atom_count'] != 1 else ''})"
            for item in removed_metal_species
        )
        controls.append(
            Control(
                code="METALES_ELIMINADOS",
                state="advertencia",
                title="Metales del receptor",
                observation=(
                    f"Se eliminan {removed_metals} átomos metálicos antes del acoplamiento"
                    f": {metal_detail}."
                    if metal_detail
                    else f"Se eliminan {removed_metals} átomos metálicos antes del acoplamiento."
                ),
                reason=(
                    "En una metaloenzima el metal suele ser parte del sitio catalítico. "
                    "Sólo se conservan los metales declarados explícitamente para este receptor."
                ),
                provenance="Comparación entre la estructura PDB de origen y la entrada preparada para la corrida.",
            )
        )

    return controls


def _toolchain_controls(
    docking_engine: str,
    *,
    receptor_prepared: bool = False,
) -> list[Control]:
    """
    Herramientas que la corrida necesita. Su ausencia es un fallo técnico
    verificable AHORA, y por eso puede bloquear: la corrida fallaría igual,
    sólo que después de que el usuario espere.
    """
    controls: list[Control] = []

    requested_engine = docking_engine.strip().lower()
    if requested_engine not in {"vina", "qvina2"}:
        return [
            Control(
                code="RUTA_PREFLIGHT_SOPORTADA",
                state="bloquea",
                title="Ruta de docking comprobable",
                observation=(
                    f"El motor '{docking_engine}' no usa la ruta Vina que inspecciona "
                    "esta comprobación previa."
                ),
                reason=(
                    "Ejecutar con un informe de otra ruta atribuiría controles que no se "
                    "realizaron al motor seleccionado."
                ),
                provenance="services.pipeline.runner · services.docking.vina_service",
            )
        ]

    vina_path = Path(settings.vina_executable_path)
    vina_found = bool(
        vina_path.exists() or preparer.resolve_executable(settings.vina_executable_path)
    )
    qvina_found = bool(preparer.resolve_executable(settings.qvina2_executable_path))
    executable_found = qvina_found if requested_engine == "qvina2" else vina_found
    actual_label = "QuickVina 2" if requested_engine == "qvina2" else "AutoDock Vina"
    controls.append(
        Control(
            code="MOTOR_DOCKING_DISPONIBLE",
            state="pasa" if executable_found else "bloquea",
            title="Motor de docking",
            observation=(
                f"{actual_label} disponible."
                if executable_found
                else f"No se encontró el ejecutable de {actual_label}."
            ),
            reason=(
                "Sin el ejecutable solicitado no se puede afirmar que la corrida corresponde "
                "al motor inspeccionado. El fallback silencioso no forma parte del contrato del caso."
            ),
            provenance=(
                "core.config.settings.qvina2_executable_path"
                if requested_engine == "qvina2"
                else "core.config.settings.vina_executable_path"
            ),
        )
    )

    meeko_found = preparer.resolve_executable(settings.meeko_prepare_receptor_path)
    receptor_preparation_available = bool(meeko_found or receptor_prepared)
    controls.append(
        Control(
            code="PREPARADOR_RECEPTOR_DISPONIBLE",
            state="pasa" if receptor_preparation_available else "bloquea",
            title="Preparador del receptor",
            observation=(
                "Meeko (mk_prepare_receptor) disponible."
                if meeko_found
                else "No hace falta regenerar el receptor: existe un PDBQT compatible y sellado en la huella."
                if receptor_prepared
                else "No se encontró 'mk_prepare_receptor'. El receptor no se puede preparar."
            ),
            reason=(
                "La corrida reutiliza el receptor preparado sólo cuando la cadena coincide; "
                "si debe regenerarlo, exige Meeko en vez de inventar la preparación."
            ),
            provenance="core.config.settings.meeko_prepare_receptor_path",
        )
    )

    # El bundle incluye Open Babel como programa independiente. Su estado sigue
    # siendo útil para diagnosticar la instalación y artefactos históricos, pero
    # la ruta de docking actual se abstiene si Meeko no exporta un SDF válido.
    # El preflight sólo inspecciona manifiesto y hash: no lanza subprocesos.
    from services.external_tools import open_babel

    conversor = open_babel.estado_actual(verificar_version=False)
    if conversor.disponible:
        observacion = (
            f"Open Babel {conversor.version_declarada} presente con el hash declarado "
            f"({conversor.ruta_relativa}, sha256 {(conversor.sha256 or '')[:12]}…). "
            "No se ejecutó para comprobarlo: esta comprobación previa no lanza procesos."
        )
    else:
        observacion = f"[{conversor.estado.value}] {conversor.detalle}"
    controls.append(
        Control(
            code="CONVERSOR_ESTRUCTURAL_DISPONIBLE",
            state="pasa" if conversor.disponible else "advertencia",
            title="Herramienta estructural incluida",
            observation=observacion,
            reason=(
                "Open Babel viaja como programa independiente (GPL-2.0-only) y "
                "se conserva para operaciones y artefactos históricos. La ruta "
                "de docking actual exige el SDF exportado por Meeko: si falla, "
                "se abstiene sin reconstruir química desde el PDBQT de Vina. "
                "La inspección de este control no busca ejecutables en PATH."
            ),
            provenance="services.external_tools.open_babel · tools/openbabel/openbabel-manifest.json",
        )
    )
    return controls


def _mismo_triple(
    a: tuple[float, float, float],
    b: tuple[float, float, float] | list[float] | None,
    tolerancia: float = 1e-3,
) -> bool:
    """`a` es el triple del catálogo `b` (a 3 decimales, el redondeo que usa el documento canónico)."""
    if b is None or len(a) != len(b):
        return False
    return all(abs(float(x) - float(y)) <= tolerancia for x, y in zip(a, b))


def _effective_configuration(
    *,
    grid_center: tuple[float, float, float] | None,
    grid_size: tuple[float, float, float] | None,
    catalog_grid_center: tuple[float, float, float] | None,
    catalog_grid_size: tuple[float, float, float] | None,
    custom_hotspots: list[str] | None,
    catalog_hotspots: list[str] | None,
    cofactors_whitelist: list[str] | None,
    filtered_text: str | None,
    prepared_chains: list[str],
    docking_engine: str,
    exhaustiveness: int | None,
    num_poses: int | None,
    conformers: int = 1,
    pipeline_config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[Control]]:
    """
    Resuelve la caja igual que lo hará la corrida.

    Dos capas, en el orden REAL:
      1. `PipelineParams.effective_grid_*`: el override del usuario gana sobre
         el catálogo — incluido el override (0,0,0), que es lo que envía la
         interfaz mientras nadie abra «Opciones».
      2. `prepare_target`: si el centro resultante es (0,0,0), lo sustituye por
         una caja derivada del PDB filtrado con `compute_dynamic_box`.

    La segunda capa se reproduce aquí con la misma función y sobre el mismo
    artefacto, así que el centro que se enseña es el que se va a usar.
    """
    controls: list[Control] = []

    # QA1-007. Un valor recibido NO es por eso «elegido por el usuario»: la interfaz
    # guarda en el caso la caja del catálogo al elegir el receptor y la envía en cada
    # comprobación, y el preflight la presentaba como «origen: elegido por ti» sin que
    # la investigadora hubiera tocado nada. Si coincide con el catálogo, el origen es
    # el catálogo; sólo lo que difiere es decisión suya.
    if grid_center is not None:
        center = tuple(float(v) for v in grid_center)
        center_origin = (
            "catalogo_target"
            if _mismo_triple(center, catalog_grid_center)
            else "override_usuario"
        )
    elif catalog_grid_center is not None:
        center = tuple(float(v) for v in catalog_grid_center)
        center_origin = "catalogo_target"
    else:
        center = (0.0, 0.0, 0.0)
        center_origin = "sin_definir"

    if grid_size is not None:
        size = tuple(float(v) for v in grid_size)
        size_origin = (
            "catalogo_target"
            if _mismo_triple(size, catalog_grid_size)
            else "override_usuario"
        )
    elif catalog_grid_size is not None:
        size = tuple(float(v) for v in catalog_grid_size)
        size_origin = "catalogo_target"
    else:
        size = (0.0, 0.0, 0.0)
        size_origin = "sin_definir"

    derived: dict[str, Any] | None = None
    if center == (0.0, 0.0, 0.0):
        derived = _derive_dynamic_box(filtered_text)
        if derived is not None:
            center = derived["center"]
            size = (derived["size"], derived["size"], derived["size"])
            center_origin = "derivado_dinamico"
            size_origin = "derivado_dinamico"
            controls.append(
                Control(
                    code="GRID_EFECTIVO",
                    state=("bloquea" if "PROTEIN_ATOM_FALLBACK" in derived["source"]
                           else "advertencia"),
                    title="Caja de búsqueda",
                    observation=(
                        f"La configuración enviada tiene centro (0, 0, 0), así que la corrida "
                        f"derivará la caja del propio PDB: centro {_fmt(center)}, "
                        f"lado {derived['size']} Å (origen: {derived['source']})."
                    ),
                    reason=(
                        "Si sólo se halló el centroide proteico, la corrida se abstiene. "
                        "Una caja derivada de un heteroátomo tampoco es una hipótesis "
                        "de sitio validada experimentalmente."
                    ),
                    provenance=(
                        "preparer.resolve_effective_docking_box · "
                        "services.chemistry.protein_surgery.compute_dynamic_box"
                    ),
                )
            )
        else:
            controls.append(
                Control(
                    code="GRID_EFECTIVO",
                    state="bloquea",
                    title="Caja de búsqueda",
                    observation=(
                        "El centro enviado es (0, 0, 0) y no se pudo derivar una caja reproducible "
                        "del PDB filtrado."
                    ),
                    reason=(
                        "La corrida tampoco debe continuar con coordenadas cero: hay que disponer "
                        "de la estructura o declarar una caja explícita."
                    ),
                    provenance="preparer.resolve_effective_docking_box",
                )
            )
    else:
        invalid_size = any(
            not math.isfinite(v) or not CAJA_LADO_MIN_A <= v <= CAJA_LADO_MAX_A for v in size
        )
        invalid_center = any(not math.isfinite(v) or abs(v) > CAJA_CENTRO_MAX_A for v in center)
        controls.append(
            Control(
                code="GRID_EFECTIVO",
                state="bloquea" if invalid_size or invalid_center else "pasa",
                title="Caja de búsqueda",
                observation=(
                    f"Centro {_fmt(center)} · origen: "
                    f"{'elegido por ti' if center_origin == 'override_usuario' else 'catálogo del receptor'}; "
                    f"tamaño {_fmt(size)} Å · origen: "
                    f"{'elegido por ti' if size_origin == 'override_usuario' else 'catálogo del receptor'}."
                ),
                reason=(f"Caja fuera de los límites de ejecución: lados entre {CAJA_LADO_MIN_A:g} y "
                        f"{CAJA_LADO_MAX_A:g} Å, centro finito entre -{CAJA_CENTRO_MAX_A:g} y "
                        f"{CAJA_CENTRO_MAX_A:g} Å."
                        if invalid_size or invalid_center else
                        "Es la caja exacta que recibirá el acoplamiento."),
                provenance="PipelineParams.effective_grid_center/size",
            )
        )

    # ── SOL-07: la relación geométrica caja/receptor/sitio ────────────
    #
    # El rango numérico de GRID_EFECTIVO no dice nada de PERTINENCIA: una
    # caja en (9999, 9999, 9999) pasaba como válida contra un receptor en el
    # origen. La auditoría lo midió con la API real. La distancia se MIDE
    # sobre el PDB filtrado de la ruta real, y la decisión de buscar lejos
    # del receptor queda registrada — no se bloquea, porque explorar fuera
    # del sitio puede ser intencional; se declara.
    extension_receptor, separacion = _geometria_caja_receptor(center, size, filtered_text)
    if extension_receptor is None or separacion is None:
        controls.append(Control(
            code="CAJA_VS_RECEPTOR",
            state="no_evaluado",
            title="Caja y receptor",
            observation="No hay estructura del receptor disponible para comparar la caja.",
            reason=(
                "Sin el PDB de la ruta no se puede medir la relación geométrica "
                "entre la caja y el receptor; no se inventa."
            ),
            provenance="PDB filtrado de la ruta real",
        ))
    elif separacion > 0:
        detalle_sitio = ""
        if catalog_grid_center is not None:
            distancia_sitio = math.dist(
                tuple(float(v) for v in center),
                tuple(float(v) for v in catalog_grid_center),
            )
            detalle_sitio = (
                f" El centro del sitio declarado por el catálogo queda a "
                f"{distancia_sitio:,.1f} Å de esta caja."
            )
        controls.append(Control(
            code="CAJA_VS_RECEPTOR",
            state="advertencia",
            title="Caja y receptor",
            observation=(
                f"Caja en {_fmt(center)} · tamaño {_fmt(size)} Å: NO abarca ningún "
                f"átomo del receptor. Separación medida de {separacion:,.1f} Å con la "
                f"extensión del receptor "
                f"({_fmt(extension_receptor[0])} a {_fmt(extension_receptor[1])} Å)."
                f"{detalle_sitio} La búsqueda ocurrirá en espacio vacío salvo que "
                "buscar lejos del receptor sea tu intención; queda registrado aquí."
            ),
            reason=(
                "Una caja sin intersección con el receptor acopla contra espacio "
                "vacío: el score que salga no describirá ningún bolsillo. La decisión "
                "de explorar fuera es del investigador; lo que no puede ser invisible."
            ),
            provenance="PDB filtrado de la ruta real · geometría de la caja de búsqueda efectiva",
        ))
    else:
        controls.append(Control(
            code="CAJA_VS_RECEPTOR",
            state="pasa",
            title="Caja y receptor",
            observation=(
                f"La caja abarca volumen con átomos del receptor "
                f"(extensión {_fmt(extension_receptor[0])} a {_fmt(extension_receptor[1])} Å)."
            ),
            reason="La búsqueda tiene estructura delante; la pertinencia del sitio se lee en los residuos de referencia.",
            provenance="PDB filtrado de la ruta real · geometría de la caja de búsqueda efectiva",
        ))

    # ── Protocolo efectivo (SOL-02) ───────────────────────────────────
    # Una sola resolución para preflight, fingerprint, revalidación de submit
    # y runner. Los campos de nivel superior del request son espejos de la
    # UI: si contradicen lo que la ejecución hará con `pipeline_config`, se
    # declara el conflicto — no se ejecuta en silencio.
    from services.docking.protocolo import resolver_parametros_docking

    resuelto = resolver_parametros_docking(
        pipeline_config=pipeline_config,
        size=tuple(size),
        docking_engine=docking_engine,
        exhaustiveness_declarada=exhaustiveness,
        num_poses_declarado=num_poses,
        conformers_declarado=conformers,
    )

    volume = box_volume(size)
    if volume > BOX_VOLUME_WARNING_A3:
        effective_exh = resuelto["exhaustiveness"]
        controls.append(Control(
            code="GRID_VOLUMEN_AMPLIO",
            state="advertencia",
            title="Volumen de búsqueda amplio",
            observation=f"Caja de {volume:.0f} Å³; exhaustividad efectiva {effective_exh}.",
            reason=("El umbral de 27 000 Å³ y el escalón 32 son una política "
                    "conservadora pendiente de benchmark de convergencia; "
                    "no garantizan una pose correcta."),
            provenance="services.docking.search_policy · tamaño efectivo de caja",
        ))

    # SOL-08: `[]` es una decisión («no quiero residuos de referencia»), no
    # una ausencia. La UI ya viaja con la distinción (`null` vs `[]`);
    # colapsarla aquí devolvía el catálogo a quien acababa de desmarcarlo
    # todo, y el origen le atribuía la elección al catálogo.
    if custom_hotspots is None:
        hotspots = sorted(catalog_hotspots or [])
        hotspots_origin = "catalogo_target" if catalog_hotspots else "ninguno"
        seleccion_vacia = False
    else:
        hotspots = sorted(custom_hotspots)
        hotspots_origin = "seleccion_usuario" if hotspots else "seleccion_vacia"
        seleccion_vacia = not hotspots
    controls.extend(_hotspot_chain_controls(hotspots, prepared_chains))
    controls.append(
        Control(
            code="HOTSPOTS_EFECTIVOS",
            state="pasa" if hotspots or seleccion_vacia else "no_evaluado",
            title="Residuos de referencia",
            observation=(
                f"{len(hotspots)} residuo(s): {', '.join(hotspots)}."
                if hotspots
                else (
                    "0 residuos por decisión del investigador: esta corrida no usa "
                    "residuos de referencia; el análisis de contactos viajará sin lista."
                    if seleccion_vacia
                    else "El receptor no declara residuos de referencia y no has seleccionado ninguno."
                )
            ),
            reason=(
                "Los hotspots no restringen el acoplamiento; se usan para describir el sitio y "
                "para el análisis posterior."
            ),
            provenance="PipelineParams.effective_hotspots",
        )
    )

    if resuelto["conflictos"]:
        detalle = "; ".join(
            f"{c['campo']}: declarado {c['declarado']}, efectivo {c['efectivo']}"
            for c in resuelto["conflictos"]
        )
        controls.append(Control(
            code="PROTOCOLO_DECLARADO_CONFLICTIVO",
            state="advertencia",
            title="Protocolo declarado y protocolo ejecutable distintos",
            observation=(
                f"Campos de nivel superior ignorados frente a pipeline_config — {detalle}. "
                "La corrida ejecuta los valores de pipeline_config.stage_params."
            ),
            reason=(
                "El protocolo que puede ejecutarse viaja en pipeline_config: las puertas "
                "de ejecución no llevan esos campos de nivel superior. Declararlos como "
                "efectivos firmaría una corrida que no ocurriría; para cambiar el "
                "protocolo hay que declararlo en stage_params."
            ),
            provenance="services.docking.protocolo.resolver_parametros_docking",
        ))

    effective = {
        "grid_center": [round(v, 3) for v in center],
        "grid_size": [round(v, 3) for v in size],
        "grid_center_origin": center_origin,
        "grid_size_origin": size_origin,
        "derived_box": derived,
        "hotspots": hotspots,
        "hotspots_origin": hotspots_origin,
        "docking_engine": docking_engine.strip().lower(),
        "exhaustiveness": resuelto["exhaustiveness"],
        "num_poses": resuelto["num_poses"],
        "seed": resuelto["seed"],
        # Conformaciones de entrada. 1 = confórmero único, el protocolo por
        # defecto. K > 1 activa el ensemble, que amplía cobertura geométrica y
        # cuesta K veces el tiempo de docking sin mejorar, por sí solo, el top-1.
        "conformers": resuelto["conformers"],
        "heteroatom_policy": {
            "route": EXECUTION_ROUTE,
            "waters": "eliminadas",
            "metals": "conservados_solo_whitelist",
            "organic_cofactors": "bloqueados_sin_plantilla_local",
            "organic_cofactors_kept": sorted(preparer.ORGANIC_COFACTORS_KEPT),
            "cofactors_whitelist_declared": sorted(cofactors_whitelist or []),
            "cofactors_whitelist_applied": True,
            "source": "Política de preparación aplicada a la estructura de esta corrida.",
        },
    }
    return effective, controls


def _geometria_caja_receptor(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    filtered_text: str | None,
) -> tuple[tuple[tuple[float, float, float], tuple[float, float, float]] | None, float | None]:
    """La extensión del receptor y la separación entre la caja y esa extensión.

    SOL-07. Devuelve `(None, None)` cuando no hay estructura que comparar o
    el texto no contiene coordenadas interpretables: la relación geométrica
    no se inventa. La separación es 0.0 cuando la caja y el receptor se tocan
    o solapan — la forma canónica de decir que la búsqueda tiene algo delante.

    Coordenadas por columnas fijas del formato PDB (x 31-38, y 39-46, z
    47-54, 1-indexadas): la misma convención que lee la ruta de preparación.
    """
    if not filtered_text:
        return None, None
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for line in filtered_text.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            try:
                xs.append(float(line[30:38]))
                ys.append(float(line[38:46]))
                zs.append(float(line[46:54]))
            except ValueError:
                continue
    if not xs:
        return None, None
    extension = (
        (min(xs), min(ys), min(zs)),
        (max(xs), max(ys), max(zs)),
    )
    # Separación por eje entre el ortoedro de la caja y el del receptor; 0
    # cuando se solapan. La distancia es la norma euclídea de los huecos.
    gaps = []
    for axis in range(3):
        box_min = float(center[axis]) - float(size[axis]) / 2.0
        box_max = float(center[axis]) + float(size[axis]) / 2.0
        gaps.append(max(
            extension[0][axis] - box_max,
            box_min - extension[1][axis],
            0.0,
        ))
    return extension, math.sqrt(sum(g * g for g in gaps))


def _hotspot_chain_controls(hotspots: list[str], prepared_chains: list[str]) -> list[Control]:
    """
    ¿Los residuos que describen el sitio están en el receptor que se acopla?

    Sale de un hallazgo real: en 7E2Y el catálogo declara quince hotspots y
    doce están en la cadena `R`, mientras el receptor de docking conserva sólo
    la `A`. El sitio que describen esos residuos no existe en la estructura
    contra la que se va a acoplar, y hasta ahora nada lo decía.

    Sólo se pronuncia cuando los nombres traen prefijo de cadena (`R:TYR400`).
    Sin prefijo no hay forma de saber a qué cadena pertenecen, y adivinarlo
    sería inventar la comprobación.
    """
    if not hotspots or not prepared_chains:
        return []

    prefixed = [h for h in hotspots if ":" in h]
    if not prefixed:
        return [
            Control(
                code="HOTSPOTS_FUERA_DEL_RECEPTOR",
                state="no_evaluado",
                title="Cadena de los residuos de referencia",
                observation="Los residuos declarados no indican cadena, así que no se puede comprobar.",
                reason="Sin la cadena en el nombre no hay forma de saber si están en el receptor.",
                provenance="hotspots del catálogo · cadenas del receptor filtrado",
            )
        ]

    kept = set(prepared_chains)
    outside = sorted({h.split(":", 1)[0] for h in prefixed} - kept)
    if not outside:
        return [
            Control(
                code="HOTSPOTS_FUERA_DEL_RECEPTOR",
                state="pasa",
                title="Cadena de los residuos de referencia",
                observation=f"Todos los residuos declarados están en la(s) cadena(s) {', '.join(sorted(kept))}.",
                reason="Describen el sitio de la estructura que efectivamente se acopla.",
                provenance="hotspots del catálogo · cadenas del receptor filtrado",
            )
        ]

    affected = [h for h in prefixed if h.split(":", 1)[0] in outside]
    return [
        Control(
            code="HOTSPOTS_FUERA_DEL_RECEPTOR",
            state="advertencia",
            title="Cadena de los residuos de referencia",
            observation=(
                f"{len(affected)} de {len(hotspots)} residuos declarados están en la(s) cadena(s) "
                f"{', '.join(outside)}, que NO entran en el receptor (se conserva "
                f"{', '.join(sorted(kept))}): {', '.join(affected[:6])}"
                + ("…" if len(affected) > 6 else "")
            ),
            reason=(
                "El sitio que describen esos residuos no existe en la estructura contra la que se "
                "va a acoplar. Puede que la cadena elegida no sea la del sitio de unión."
            ),
            provenance="hotspots del catálogo · cadenas del receptor filtrado",
        )
    ]


def _derive_dynamic_box(filtered_text: str | None) -> dict[str, Any] | None:
    return preparer.derive_dynamic_box(filtered_text)


def _declared_debts() -> list[Control]:
    """
    Deudas DECLARADAS, no huecos silenciosos.

    Cada una es algo que docs/53 §6.1 pide y que la ruta actual no conserva.
    Aparecen como `no_evaluado` con su causa para que nadie las lea como
    «comprobado y correcto».
    """
    return [
        Control(
            code="LIGANDO_PROTONACION_TAUTOMERO",
            state="no_evaluado",
            title="Protonación y tautómero del ligando",
            observation="No evaluado antes de ejecutar.",
            reason=(
                "La forma protonada y el tautómero los fija la etapa de conformación durante la "
                "corrida. Anticiparlos aquí sería inventar una decisión que todavía no se ha tomado."
            ),
            provenance="deuda declarada · docs/53 §6.1",
        ),
        Control(
            code="ASSEMBLY_BIOLOGICA",
            state="no_evaluado",
            title="Unidad asimétrica frente a assembly biológica",
            observation="No evaluado: el catálogo no registra qué assembly representa el archivo.",
            reason=(
                "Acoplar contra la unidad asimétrica cuando el sitio se forma entre cadenas produce "
                "un sitio incompleto. El dato no existe todavía en el modelo."
            ),
            provenance="deuda declarada · docs/53 §6.1",
        ),
        Control(
            code="HUECOS_CERCA_DEL_SITIO",
            state="no_evaluado",
            title="Residuos faltantes cerca del sitio",
            observation="No evaluado: la ruta no conserva un mapa de huecos del receptor preparado.",
            reason=(
                "Un hueco junto al sitio cambia la forma del bolsillo. Requiere un análisis que "
                "esta comprobación previa todavía no hace."
            ),
            provenance="deuda declarada · docs/53 §6.1",
        ),
    ]


def _fmt(values: tuple[float, ...]) -> str:
    return "(" + ", ".join(f"{v:.2f}" for v in values) + ")"

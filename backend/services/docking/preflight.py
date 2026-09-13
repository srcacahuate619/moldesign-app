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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from core.config import get_settings
from chem.validator import validate_smiles
from services.docking import preparer
from utils.local_storage import path_for
from utils.file_handlers import StoragePath
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

PREFLIGHT_SCHEMA_VERSION = 3

#: Identificador de la ruta de ejecución inspeccionada. La política de
#: heteroátomos difiere entre docking y MM-GBSA (docs/53 §6.2), así que el
#: resultado no significa nada sin decir de qué ruta habla.
EXECUTION_ROUTE = "docking_vina"

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


def _species_category(residue: str) -> str:
    """Categoría estable de API; los nombres internos no llegan a la UI."""

    if residue in preparer.WATER_RESIDUES:
        return "water"
    if residue in preparer.METAL_COFACTORS:
        return "metal"
    if residue in preparer.ORGANIC_COFACTORS_KEPT:
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
    cofactor a la lista del producto, este recuento cambia con ella.
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
        elif residue in preparer.METAL_COFACTORS:
            counts.metals += 1
        elif residue in preparer.ORGANIC_COFACTORS_KEPT:
            counts.organic_cofactors += 1
        else:
            counts.other_hetatm += 1
    return counts


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
        "custom_hotspots": sorted(custom_hotspots) if custom_hotspots else None,
        "docking_engine": docking_engine,
        "exhaustiveness": int(exhaustiveness),
        "num_poses": int(num_poses),
        "seed": int(seed),
        # Si cambia el artefacto estructural, los mismos campos visibles ya no
        # describen la misma corrida. Los hashes pertenecen por ello a la
        # identidad de la preparación, no sólo a la sección de procedencia.
        "source_sha256": source_sha256,
        "prepared_sha256": prepared_sha256,
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
    """
    Fuente que leería `prepare_target`, con su MISMA precedencia.

    `prepare_target` prefiere el PDB compartido (`get_target_pdb_path`) y sólo
    cae al crudo descargado si aquél no existe. Aquí se replica esa
    precedencia y se detiene ahí: si no hay nada en disco, se devuelve `None`
    y el control correspondiente sale `no_evaluado` — nunca se descarga.
    """
    shared = Path(preparer.get_target_pdb_path(pdb_id))
    if shared.exists():
        return shared
    raw = path_for(StoragePath.target_raw(pdb_id))
    if raw.exists():
        return raw
    # Ultimo recurso ANTES de rendirse: materializar la estructura que viaja en
    # el instalador. La siembra del arranque tarda decenas de segundos en copiar
    # las 407, y quien acaba de instalar pregunta dentro de ese hueco. Copiar un
    # archivo del bundle no es descargar: la regla de este modulo —no tocar la
    # red— sigue intacta.
    from services.semilla_estructuras import sembrar_una

    return sembrar_una(pdb_id)


def _prepared_pdbqt_path(pdb_id: str) -> Path | None:
    prepared = path_for(StoragePath.target_prepared(pdb_id))
    return prepared if prepared.exists() else None


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
    source_path = _source_pdb_path(pdb_id)
    prepared_path = _prepared_pdbqt_path(pdb_id)

    source_sha: str | None = None
    source_counts: _SpeciesCount | None = None
    source_text: str | None = None

    if source_path is not None:
        try:
            source_bytes = source_path.read_bytes()
            source_sha = sha256_of(source_bytes)
            source_text = source_bytes.decode("utf-8", errors="replace")
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
                    reason="Es el archivo exacto que leerá la preparación de la corrida.",
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

    if source_text is None or source_counts is None:
        diff = _diff_not_evaluated(
            "No hay fuente en disco que comparar. Se calculará cuando la corrida la descargue."
        )
    else:
        try:
            # LA MISMA función que ejecuta la corrida, con LOS MISMOS
            # argumentos que usa `vina_service.run_docking`.
            filtered_text = preparer.filter_pdb_content(
                source_text,
                chain_id=chain,
                keep_hetatm=True,
                cofactors_whitelist=cofactors_whitelist,
            )
            filtered_counts = count_species(filtered_text)
            diff = _build_diff(source_counts, filtered_counts, chain)
        except Exception as exc:  # ProteinPreparationError y cualquier otro fallo real
            chain_error = str(getattr(exc, "detail", None) or exc)
            diff = _diff_not_evaluated(
                "El filtrado de la cadena falló, así que no hay preparado con el que comparar."
            )

    if chain_error is not None:
        controls.append(
            Control(
                code="RECEPTOR_CADENA_PRESENTE",
                state="bloquea",
                title="Cadena del receptor",
                observation=f"Filtrar la cadena '{chain}' no dejó ningún átomo de proteína.",
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
                    f"La cadena '{chain}' aporta {filtered_counts.atom_records} átomos de proteína "
                    f"al receptor de la corrida."
                ),
                reason="Es la cadena que se acoplará; el resto de la estructura no entra.",
                provenance="preparer.filter_pdb_content (la función que ejecuta la corrida)",
            )
        )
    else:
        controls.append(
            Control(
                code="RECEPTOR_CADENA_PRESENTE",
                state="no_evaluado",
                title="Cadena del receptor",
                observation=f"No evaluado: sin la fuente en disco no se puede comprobar la cadena '{chain}'.",
                reason="La comprobación exige el archivo real.",
                provenance="preparer.filter_pdb_content (la función que ejecuta la corrida)",
            )
        )

    # ── Política de heteroátomos de ESTA ruta ────────────────────────
    controls.extend(
        _heteroatom_controls(
            source_counts=source_counts,
            filtered_counts=filtered_counts,
            cofactors_whitelist=cofactors_whitelist,
        )
    )

    # ── Receptor preparado ───────────────────────────────────────────
    prepared_sha: str | None = None
    prepared_sha_for_run: str | None = None
    prepared_compatible: bool | None = None
    prepared_chains: list[str] = []
    if prepared_path is not None:
        try:
            prepared_bytes = prepared_path.read_bytes()
            prepared_sha = sha256_of(prepared_bytes)
            prepared_text = prepared_bytes.decode("utf-8", errors="replace")
            prepared_chains = sorted(preparer.prepared_receptor_chains(prepared_text))
            prepared_compatible = preparer.prepared_receptor_matches_chain(
                prepared_text,
                chain,
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
                        reason="La corrida lo reutilizará tal cual; su hash entra en la huella.",
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
                state="no_evaluado",
                title="Receptor preparado",
                observation="Todavía no existe: la corrida lo generará con Meeko.",
                reason=(
                    "El hash del receptor preparado sólo puede calcularse sobre un archivo que exista. "
                    "Prepararlo aquí convertiría la comprobación previa en trabajo de corrida."
                ),
                provenance="almacenamiento local de targets preparados",
            )
        )

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
    from chem.conformer_ensemble import normalizar_k

    conformaciones = normalizar_k(conformers if conformers is not None else 1)

    effective, grid_controls = _effective_configuration(
        grid_center=grid_center,
        grid_size=grid_size,
        catalog_grid_center=catalog_grid_center,
        catalog_grid_size=catalog_grid_size,
        custom_hotspots=custom_hotspots,
        catalog_hotspots=catalog_hotspots,
        cofactors_whitelist=cofactors_whitelist,
        filtered_text=filtered_text,
        prepared_chains=sorted(filtered_counts.chains) if filtered_counts else [],
        docking_engine=docking_engine,
        exhaustiveness=exhaustiveness,
        num_poses=num_poses,
        conformers=conformaciones,
    )
    controls.extend(grid_controls)
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
        prepared_sha256=prepared_sha_for_run,
        conformers=conformaciones,
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
    requiere = bool(calibracion.get("requiere_advertencia", True))
    rho = calibracion.get("spearman_rho")
    observacion = calibracion.get("resumen", "")
    if rho is not None:
        observacion = f"{observacion} (ρ = {rho})"
    return [
        Control(
            code="CALIBRACION_RECEPTOR",
            state="advertencia" if requiere else "pasa",
            title="Respaldo científico del receptor",
            observation=observacion,
            reason=(
                calibracion.get("advertencia")
                or "El ranking del motor está calibrado para este receptor."
            ),
            provenance=(
                f"targets.spearman_rho + familia estructural ({nivel}); "
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

    # ── El conversor estructural de respaldo ─────────────────────────────
    #
    # Open Babel viaja DENTRO del instalador, así que su ausencia o su
    # alteración no describen una función que el usuario no compró: describen
    # una instalación dañada. Se comprueba aquí, que es barato, en vez de
    # descubrirlo a mitad de una corrida.
    #
    # No bloquea. Si Meeko exporta un SDF utilizable —el camino normal— Open
    # Babel no llega a ejecutarse, y bloquear una corrida que iba a funcionar
    # sería convertir una comprobación en un estorbo. Lo que no puede pasar es
    # que la corrida NECESITE el respaldo, no lo tenga y siga en silencio: de
    # eso se encarga `vina_service`, que en ese caso deja el aviso
    # `CONVERSOR_ESTRUCTURAL_NO_DISPONIBLE` con severidad crítica.
    #
    # `verificar_version=False` A PROPÓSITO. El presupuesto entero de este
    # módulo es cero subprocesos y cero modelos —lo fija
    # `test_preflight_never_runs_docking_or_expensive_models`— y comprobar la
    # versión exige lanzar `obabel -V`. Aquí se comprueba lo que se puede
    # comprobar leyendo el disco: que el programa está y que su hash es el
    # declarado. La versión la verifican `/health` y el verificador del bundle,
    # que sí pueden gastar un proceso.
    #
    # El control DICE cuál de las dos cosas comprobó. Un informe que dijera
    # «verificado» tras mirar sólo el hash afirmaría de más.
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
            title="Conversor estructural de respaldo",
            observation=observacion,
            reason=(
                "Cuando la exportación de Meeko no produce un SDF utilizable, la "
                "evidencia estructural se rescata convirtiendo el PDBQT de Vina con "
                "Open Babel, un programa independiente (GPL-2.0-only) que MolDesign "
                "invoca como herramienta de línea de órdenes. Sin él, esa corrida se "
                "abstiene en vez de entregar poses incompletas. No se busca en el "
                "PATH: un binario ajeno produciría un resultado que el informe "
                "atribuiría a la versión declarada."
            ),
            provenance="services.external_tools.open_babel · tools/openbabel/openbabel-manifest.json",
        )
    )
    return controls


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

    if grid_center is not None:
        center = tuple(float(v) for v in grid_center)
        center_origin = "override_usuario"
    elif catalog_grid_center is not None:
        center = tuple(float(v) for v in catalog_grid_center)
        center_origin = "catalogo_target"
    else:
        center = (0.0, 0.0, 0.0)
        center_origin = "sin_definir"

    if grid_size is not None:
        size = tuple(float(v) for v in grid_size)
        size_origin = "override_usuario"
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
                    state="advertencia",
                    title="Caja de búsqueda",
                    observation=(
                        f"La configuración enviada tiene centro (0, 0, 0), así que la corrida "
                        f"derivará la caja del propio PDB: centro {_fmt(center)}, "
                        f"lado {derived['size']} Å (origen: {derived['source']})."
                    ),
                    reason=(
                        "El centro derivado depende de los heteroátomos del archivo. No es una "
                        "hipótesis de sitio confirmada por nadie."
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
        controls.append(
            Control(
                code="GRID_EFECTIVO",
                state="pasa",
                title="Caja de búsqueda",
                observation=(
                    f"Centro {_fmt(center)}, tamaño {_fmt(size)} Å · origen: "
                    f"{'elegido por ti' if center_origin == 'override_usuario' else 'catálogo del receptor'}."
                ),
                reason="Es la caja exacta que recibirá el acoplamiento.",
                provenance="PipelineParams.effective_grid_center/size",
            )
        )

    hotspots = sorted(custom_hotspots) if custom_hotspots else sorted(catalog_hotspots or [])
    hotspots_origin = (
        "seleccion_usuario" if custom_hotspots else ("catalogo_target" if catalog_hotspots else "ninguno")
    )
    controls.extend(_hotspot_chain_controls(hotspots, prepared_chains))
    controls.append(
        Control(
            code="HOTSPOTS_EFECTIVOS",
            state="pasa" if hotspots else "no_evaluado",
            title="Residuos de referencia",
            observation=(
                f"{len(hotspots)} residuo(s): {', '.join(hotspots)}."
                if hotspots
                else "El receptor no declara residuos de referencia y no has seleccionado ninguno."
            ),
            reason=(
                "Los hotspots no restringen el acoplamiento; se usan para describir el sitio y "
                "para el análisis posterior."
            ),
            provenance="PipelineParams.effective_hotspots",
        )
    )

    effective = {
        "grid_center": [round(v, 3) for v in center],
        "grid_size": [round(v, 3) for v in size],
        "grid_center_origin": center_origin,
        "grid_size_origin": size_origin,
        "derived_box": derived,
        "hotspots": hotspots,
        "hotspots_origin": hotspots_origin,
        "docking_engine": docking_engine.strip().lower(),
        "exhaustiveness": int(
            exhaustiveness
            if exhaustiveness is not None
            else (4 if docking_engine.strip().lower() == "qvina2" else settings.vina_exhaustiveness)
        ),
        "num_poses": int(num_poses if num_poses is not None else settings.vina_num_poses),
        "seed": int(settings.vina_seed),
        # Conformaciones de entrada. 1 = confórmero único, el protocolo por
        # defecto. K > 1 activa el ensemble, que amplía cobertura geométrica y
        # cuesta K veces el tiempo de docking sin mejorar, por sí solo, el top-1.
        "conformers": int(conformers or 1),
        "heteroatom_policy": {
            "route": EXECUTION_ROUTE,
            "waters": "eliminadas",
            "metals": "conservados_solo_whitelist",
            "organic_cofactors": "conservados_lista_producto",
            "organic_cofactors_kept": sorted(preparer.ORGANIC_COFACTORS_KEPT),
            "cofactors_whitelist_declared": sorted(cofactors_whitelist or []),
            "cofactors_whitelist_applied": True,
            "source": "Política de preparación aplicada a la estructura de esta corrida.",
        },
    }
    return effective, controls


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

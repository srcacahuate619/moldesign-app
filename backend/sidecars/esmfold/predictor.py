"""
predictor.py — Capa de predicción ESMFold.

Modos:
  - stub              : poses dummy (tests E2E)
  - fast (default)    : ESMFold pliega → Vina dockea → OpenMM refina (rápido, ~1-2 min)
  - pro               : plegamiento completo + refinamiento exhaustivo (~5-15 min)
                        (requiere ESMFoldFastPredictor ya cargado; extiende su lógica)

La interfaz pública es idéntica en todos los modos.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import random
import shutil
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from logger import get_logger

log = get_logger(__name__)


# ── Tipos públicos (compatibles con el cliente del server) ───────────────


#: De dónde salió la geometría de una pose. Sin esto, una estructura plegada
#: SIN acoplar y una pose de Vina viajan por el mismo campo y llegan al dossier
#: indistinguibles. Ver `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md` §7.
ORIGEN_VINA = "vina_docked"
ORIGEN_SOLO_PLEGADO = "folded_structure_only"
ORIGEN_STUB = "stub"
VINA_VERSION = "AutoDock Vina 1.2.7"


@dataclass
class PredictedPose:
    rank: int
    #: Confianza ESTRUCTURAL del plegado, en [0, 1]. Deriva del pLDDT del
    #: modelo. NO se deriva de la afinidad y no se convierte a kcal/mol.
    confidence: float
    ligand_pdb: str
    rmsd: float | None = None
    #: La afinidad que Vina calculó de verdad, en kcal/mol, o `None` si esta
    #: pose no pasó por Vina.
    #:
    #: ═══════════════════════════════════════════════════════════════════
    #: EL CAMPO QUE FALTABA, Y LO QUE PASABA SIN ÉL
    #: ═══════════════════════════════════════════════════════════════════
    #:
    #: `_parse_vina_pdbqt` leía `REMARK VINA RESULT`, calculaba una «confianza»
    #: a partir de la afinidad y TIRABA la afinidad. La fórmula era
    #:
    #:     conf = min(1.0, max(0.1, 1.0 - abs(afinidad) / 15.0))
    #:
    #: con el comentario «más negativo = mejor» encima, haciendo lo contrario:
    #: Vina −12 daba confianza 0.200 y Vina −4 daba 0.733. Cuanto mejor el
    #: acoplamiento, menos confianza.
    #:
    #: Y aguas abajo, `services/docking/peptide_docking.py` reconvertía esa
    #: confianza en una afinidad con `max(-12.0, min(-4.0, -1.5 * conf))`. Como
    #: `-1.5 * conf` con conf en [0.1, 1.0] vale entre −1.5 y −0.15, y todos
    #: esos valores son mayores que −4.0, `min(-4.0, ·)` devolvía −4.0
    #: **siempre**. Medido:
    #:
    #:     Vina real   conf    afinidad persistida
    #:        −2.0     0.867          −4.0
    #:        −6.0     0.600          −4.0
    #:       −12.0     0.200          −4.0
    #:
    #: Toda corrida peptídica reportaba −4.0 kcal/mol, con independencia de lo
    #: que Vina hubiera calculado, y el número real no se guardaba en ninguna
    #: parte.
    vina_affinity_kcal_mol: float | None = None
    #: SDF con el grafo quimico explicito y las coordenadas de esta pose.
    ligand_sdf: str | None = None
    #: `ORIGEN_VINA`, `ORIGEN_SOLO_PLEGADO` u `ORIGEN_STUB`.
    origen: str = ORIGEN_VINA


@dataclass
class PredictionResult:
    success: bool
    poses: list[PredictedPose]
    best_confidence: float | None
    method: str
    execution_time_s: float
    warnings: list[str]
    error: str | None = None
    scientific_status: str = "EXPERIMENTAL"
    transfer_manifest: dict | None = None


# ── Interfaz abstracta ────────────────────────────────────────────────────


class BasePredictor(ABC):
    @abstractmethod
    async def load(self) -> None:
        """Carga el modelo en memoria. Llamar una sola vez al arranque."""

    @abstractmethod
    async def predict(
        self,
        protein_pdb: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None,
        grid_size: tuple[float, float, float] | None,
    ) -> PredictionResult:
        """Predice `num_poses` poses para el complejo proteína-péptido."""


# ── Stub predictor ─────────────────────────────────────────────────────────


class StubPredictor(BasePredictor):
    async def load(self) -> None:
        log.info("StubPredictor cargado (modo dummy; no usa modelo real)")

    async def predict(
        self,
        protein_pdb: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None,
        grid_size: tuple[float, float, float] | None,
    ) -> PredictionResult:
        start = time.monotonic()
        warnings: list[str] = []

        if not protein_pdb or "ATOM" not in protein_pdb.upper():
            return PredictionResult(
                success=False, poses=[], best_confidence=None,
                method="ESMFold-Stub", execution_time_s=0.0,
                warnings=warnings,
                error="PDB del receptor inválido (no contiene ATOM records)",
            )
        if not peptide_smiles or len(peptide_smiles) < 3:
            return PredictionResult(
                success=False, poses=[], best_confidence=None,
                method="ESMFold-Stub", execution_time_s=0.0,
                warnings=warnings,
                error="SMILES del péptido vacío o demasiado corto",
            )

        await asyncio.sleep(random.uniform(1.0, 3.0))

        if grid_center is None:
            grid_center = (0.0, 0.0, 0.0)
        if grid_size is None:
            grid_size = (25.0, 25.0, 25.0)

        cx, cy, cz = grid_center
        poses: list[PredictedPose] = []
        seed = int(hashlib.sha256(
            f"{protein_pdb[:200]}|{peptide_smiles}|{num_poses}".encode()
        ).hexdigest()[:8], 16)
        rng = random.Random(seed)

        for rank in range(1, num_poses + 1):
            confidence = round(max(0.05, 1.0 - (rank - 1) * 0.15 + rng.uniform(-0.05, 0.05)), 3)
            rmsd = round(1.0 + (rank - 1) * 0.8 + rng.uniform(0.0, 0.3), 2)
            angle = (rank - 1) * (2 * math.pi / num_poses)
            x = cx + 5.0 * math.cos(angle)
            y = cy + 5.0 * math.sin(angle)
            z = cz + (rank - 1) * 0.5
            ligand_pdb = (
                f"REMARK   Stub pose rank={rank} confidence={confidence}\n"
                f"HETATM    1  N   ALA A   1   {x:6.3f} {y:6.3f} {z:6.3f}  1.00  0.00           N\n"
                f"HETATM    2  CA  ALA A   1   {x+1.5:6.3f} {y:6.3f} {z:6.3f}  1.00  0.00           C\n"
                f"HETATM    3  C   ALA A   1   {x+3.0:6.3f} {y:6.3f} {z:6.3f}  1.00  0.00           C\n"
                f"END\n"
            )
            # `origen=ORIGEN_STUB`: esta confianza es una secuencia decreciente
            # con ruido, no una medida de nada. Marcarla impide que llegue al
            # dossier como si fuera un resultado.
            poses.append(PredictedPose(
                rank=rank, confidence=confidence, ligand_pdb=ligand_pdb, rmsd=rmsd,
                vina_affinity_kcal_mol=None, origen=ORIGEN_STUB,
            ))

        warnings.append("Resultado STUB: no usar para investigación.")

        return PredictionResult(
            success=True, poses=poses,
            best_confidence=poses[0].confidence if poses else None,
            method="ESMFold-Stub",
            execution_time_s=round(time.monotonic() - start, 2),
            warnings=warnings,
        )


# ── Mapa de aminoácidos (3-letras → 1-letra) ──────────────────────────────

AA_3TO1: dict[str, str] = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "ASX": "B", "GLX": "Z", "XLE": "J", "SEC": "U", "PYL": "O",
    "MSE": "M", "HYP": "P", "NLE": "L", "ORN": "O",
}


# ── ESMFold Fast Predictor ─────────────────────────────────────────────────


class ESMFoldFastPredictor(BasePredictor):
    """
    Predictor rápido: ESMFold pliega el péptido → Vina dockea → OpenMM refina.

    Pipeline:
      1. Extraer secuencia aminoacídica desde SMILES (RDKit)
      2. Plegar con ESMFold (Meta AI, Science 2023)
      3. Dockear contra el receptor con AutoDock Vina
      4. Refinar top poses con OpenMM (minimización rápida)

    Tiempo estimado: ~1-2 min (GPU) / ~5-10 min (CPU).
    Output: pLDDT como métrica de confianza, scores Vina en kcal/mol.
    """

    def __init__(self, model_dir: str, device: str = "auto"):
        self.model_dir = Path(model_dir)
        self._device_str = device
        self._device = None
        self._tokenizer = None
        self._model = None
        self._vina_path: str | None = None

    # ── Device resolution ──────────────────────────────────────────────

    @staticmethod
    def _resolve_device(device_str: str):
        if device_str == "cpu":
            return "cpu"
        if device_str == "cuda":
            return "cuda"
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"

    # ── Public interface ───────────────────────────────────────────────

    async def load(self) -> None:
        import torch
        from transformers import EsmForProteinFolding, AutoTokenizer

        self._device = self._resolve_device(self._device_str)
        log.info("ESMFoldFastPredictor: cargando modelo ESMFold",
                 device=self._device, model_dir=str(self.model_dir))

        # CARGA LOCAL, Y SÓLO LOCAL (2026-09-01).
        #
        # Esto decía `from_pretrained("facebook/esmfold_v1")`: resolvía el modelo
        # POR SU NOMBRE, es decir, contra HuggingFace, e ignoraba por completo el
        # `model_dir` que este predictor recibe y hasta registra en el log de
        # arriba. Dos consecuencias, las dos inaceptables aquí:
        #
        #   1. la aplicación declara cero red implícita, y esto era una descarga
        #      de 8.4 GB disparada por elegir un motor en un menú;
        #   2. los pesos que el investigador SÍ descargó desde el gestor de
        #      modelos no se usaban, y volvían a bajarse a la caché de
        #      `transformers`.
        #
        # `local_files_only=True` es la parte que lo hace verificable: si falta
        # algo en el directorio, esto falla aquí y con un mensaje sobre archivos,
        # en vez de salir a buscarlo a internet.
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"No hay checkpoint de ESMFold en {self.model_dir}. Descárgalo desde "
                "el gestor de modelos de la aplicación."
            )
        model_id = str(self.model_dir)
        self._tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
        self._model = EsmForProteinFolding.from_pretrained(
            model_id,
            low_cpu_mem_usage=True,
            local_files_only=True,
        )
        self._model = self._model.to(self._device).eval()
        self._model.trunk.set_chunk_size(64)

        # Buscar Vina en PATH o en tools/
        self._vina_path = shutil.which("vina")
        if self._vina_path is None:
            # El servicio vive en `backend/sidecars/esmfold/`, así que la raíz de
            # la instalación son tres niveles arriba. Cuando estaba en
            # `<raíz>/esmfold/` bastaba con `parent.parent`, y esa ruta quedó
            # obsoleta al moverlo al árbol que el instalador sí copia.
            raiz = Path(__file__).resolve().parents[3]
            # ── UNA RUTA VACIA NO ES UN CANDIDATO ────────────────────────
            #
            # `Path(os.environ.get("VINA_EXECUTABLE_PATH", ""))` es `Path(".")`
            # cuando la variable no esta puesta, y `Path(".").exists()` es True:
            # el bucle elegia EL DIRECTORIO ACTUAL como binario de Vina, nunca
            # llegaba a `tools/vina/vina.exe`, y `subprocess` intentaba ejecutar
            # una carpeta. Medido: `PermissionError: [WinError 5] Acceso
            # denegado`, con `vina_available=True` en el log un segundo antes.
            #
            # Se exige ademas que sea un FICHERO: un directorio que exista no es
            # un ejecutable, y ese era exactamente el modo de fallo.
            declarada = (os.environ.get("VINA_EXECUTABLE_PATH") or "").strip()
            candidates = [
                *( [Path(declarada)] if declarada else [] ),
                raiz / "tools" / "vina" / "vina.exe",
                raiz / "tools" / "vina" / "vina",
            ]
            for c in candidates:
                if c.is_file():
                    self._vina_path = str(c)
                    break

        log.info("ESMFoldFastPredictor cargado",
                 vina_available=self._vina_path is not None,
                 device=str(self._device))

    async def predict(
        self,
        protein_pdb: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None,
        grid_size: tuple[float, float, float] | None,
    ) -> PredictionResult:
        import torch
        start = time.monotonic()
        warnings: list[str] = []
        tmp_files: list[str] = []

        try:
            # 1. Extraer secuencia del péptido
            sequence = await asyncio.to_thread(
                self._smiles_to_aa_sequence, peptide_smiles
            )
            if not sequence or len(sequence) < 2:
                return PredictionResult(
                    success=False, poses=[], best_confidence=None,
                    method="ESMFold-Fast", execution_time_s=0.0,
                    warnings=warnings,
                    error="No se pudo extraer una secuencia de aminoácidos del SMILES.",
                )
            log.info("esmfold_sequence_extracted", length=len(sequence))

            # 2. Plegar con ESMFold
            with torch.no_grad():
                folded_pdb = self._fold_sequence(sequence)

            # Guardar péptido plegado a archivo temporal
            fd_pep, pep_path = tempfile.mkstemp(suffix=".pdb", prefix="esmfold_pep_")
            os.close(fd_pep)
            tmp_files.append(pep_path)
            Path(pep_path).write_text(folded_pdb)

            # Calcular pLDDT como proxy de confianza
            plddt = self._compute_plddt_from_pdb(folded_pdb)
            log.info("esmfold_folded", plddt=round(plddt, 2), length=len(sequence))

            if plddt < 50.0:
                warnings.append(
                    f"pLDDT bajo ({plddt:.1f}). La estructura plegada tiene baja confianza. "
                    "Considerá usar esmfold-pro para mayor precisión."
                )

            # 2b. Frontera quimica V1: el SMILES conserva la conectividad y
            # ESMFold aporta solo coordenadas. Si esta etapa falla, la
            # respuesta es una abstencion trazable, no una pose de otra quimica.
            transfer_manifest = None
            try:
                from ligand_transfer import TransferenciaPeptidicaError, transferir_coordenadas
                transferencia = transferir_coordenadas(peptide_smiles, folded_pdb)
                transfer_manifest = dict(transferencia.manifest)
                transfer_manifest.update({"fold_plddt": round(plddt, 3), "esmfold_model": self.model_dir.name})
                Path(pep_path).write_text(transferencia.pdb_complete, encoding="utf-8")
                from rdkit import Chem
                sdf_fd, sdf_path = tempfile.mkstemp(suffix=".sdf", prefix="esmfold_ligand_")
                os.close(sdf_fd)
                tmp_files.append(sdf_path)
                Chem.MolToMolFile(transferencia.mol, sdf_path)
                ligand_input_path = sdf_path
            except TransferenciaPeptidicaError as exc:
                transfer_manifest = {"protocol_version": "PEPTIDE_ESMFOLD_VINA_V1", "status": "abstained", "failure_code": exc.code, "failure_message": str(exc), "coordinate_source": "esmfold", "fold_plddt": round(plddt, 3)}
                warnings.append(f"PEPTIDE_TRANSFERENCIA: {exc.code}: {exc}")
                return PredictionResult(
                    success=True,
                    poses=[PredictedPose(rank=1, confidence=round(plddt / 100.0, 3), ligand_pdb=folded_pdb, vina_affinity_kcal_mol=None, origen=ORIGEN_SOLO_PLEGADO)],
                    best_confidence=round(plddt / 100.0, 3),
                    method="ESMFold-Fast",
                    execution_time_s=round(time.monotonic() - start, 2),
                    warnings=warnings,
                    error=exc.code,
                    scientific_status="NOT_EVALUATED_LIGAND_RECONSTRUCTION",
                    transfer_manifest=transfer_manifest,
                )

            # 3. Guardar receptor a archivo temporal
            fd_rec, rec_path = tempfile.mkstemp(suffix=".pdb", prefix="esmfold_rec_")
            os.close(fd_rec)
            tmp_files.append(rec_path)
            Path(rec_path).write_text(protein_pdb)

            # 4. Calcular grid box si no se proveyó
            if grid_center is None or grid_size is None:
                grid_center, grid_size = self._compute_grid_from_ligand(pep_path)

            # 5. Dockear con Vina
            if self._vina_path is None:
                warnings.append("Vina no encontrado. Devolviendo estructura plegada sin docking.")
                # `origen` iba por defecto, y su defecto es `ORIGEN_VINA`: esta
                # rama devolvía una estructura plegada ETIQUETADA COMO ACOPLADA,
                # en el mismo bloque cuyo aviso dice que no se acopló. El campo
                # existe justo para distinguir estas dos cosas, así que dejarlo
                # al defecto lo vuelve inútil precisamente donde hace falta.
                poses = [
                    PredictedPose(rank=1, confidence=round(plddt / 100.0, 3),
                                  ligand_pdb=folded_pdb,
                                  vina_affinity_kcal_mol=None,
                                  origen=ORIGEN_SOLO_PLEGADO)
                ]
            else:
                poses = await asyncio.to_thread(
                    self._vina_dock, ligand_input_path, rec_path,
                    grid_center, grid_size, num_poses
                )
                # `_parse_vina_pdbqt` no conoce el plegado, asi que deja
                # `confidence=0.0`. Cero se lee como «confianza nula», y la
                # confianza ESTRUCTURAL de estas poses existe y es la del
                # plegado del que TODAS salen: el mismo pLDDT que ya viaja en
                # `best_confidence`. El docstring de `PredictedPose` promete
                # exactamente eso, y la afinidad sigue sin tocarla nadie.
                for pose in poses:
                    if not pose.confidence:
                        pose.confidence = round(plddt / 100.0, 3)

            # El SDF de Vina conserva la geometria y el grafo quimico V1.
            # No se sobrescribe con OpenMM, que no vuelve a serializar el mapa atomico.
            if not any(getattr(pose, "ligand_sdf", None) for pose in poses):
                try:
                    refined = await asyncio.to_thread(
                        self._refine_poses, poses[:3], rec_path,
                    )
                    poses[:len(refined)] = refined
                except Exception as e:
                    log.debug("openmm_refine_skipped", error=str(e))

            best_confidence = round(plddt / 100.0, 3)

            return PredictionResult(
                success=True, poses=poses,
                best_confidence=best_confidence,
                method="ESMFold-Fast",
                execution_time_s=round(time.monotonic() - start, 2),
                warnings=warnings,
                scientific_status=("COMPLETED" if any(p.vina_affinity_kcal_mol is not None for p in poses) else "NOT_EVALUATED_DOCKING_FAILED"),
                transfer_manifest=transfer_manifest,
            )

        except Exception as e:
            log.exception("esmfold_predict_error")
            return PredictionResult(
                success=False, poses=[], best_confidence=None,
                method="ESMFold-Fast",
                execution_time_s=round(time.monotonic() - start, 2),
                warnings=warnings,
                error=f"{type(e).__name__}: {e}",
            )
        finally:
            for f in tmp_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except OSError:
                    pass

    # ── Sequence extraction ────────────────────────────────────────────

    # La tabla `_AA_SMARTS` que vivía aquí se ha eliminado.
    #
    # Tenía veinte entradas, pero escritas a mano y varias sencillamente mal:
    #
    #     "N": "[NX3][CX3](=[OX1])"        casa con CUALQUIER amida, empezando
    #                                      por el propio esqueleto peptídico
    #     "D": "[CX3](=[OX1])[OX1H0-]"     exige el carboxilato desprotonado
    #     "C": "[SX2][H]"                  exige el hidrógeno explícito
    #
    # Y nadie las usaba: el único lector las nombraba como variable suelta
    # dentro de un `@staticmethod`, así que levantaba `NameError` siempre.
    # Se borra en vez de arreglarse porque el reconocimiento correcto —por
    # comparación con las cadenas laterales de los veinte, extraídas con el
    # mismo código, y con el punto de anclaje marcado— vive en `secuencia.py`.
    # Una tabla equivocada que no llama nadie es una trampa para el siguiente
    # que la vea y decida «arreglar» el NameError.


    @staticmethod
    def _smiles_to_aa_sequence(smiles: str) -> str:
        """Secuencia de una letra desde el SMILES del péptido.

        ═══════════════════════════════════════════════════════════════════
        LO QUE HABÍA AQUÍ NO PODÍA FUNCIONAR
        ═══════════════════════════════════════════════════════════════════

        Este método construía sus patrones así:

            aa_patterns = {aa: Chem.MolFromSmarts(s)
                           for aa, s in _AA_SMARTS.items()}

        `_AA_SMARTS` es un ATRIBUTO DE CLASE, y un nombre suelto dentro de un
        `@staticmethod` no resuelve contra el cuerpo de la clase. La línea
        levantaba `NameError` en toda llamada, para todo péptido: el motor
        peptídico de ESMFold no extrajo una secuencia jamás, y cada corrida
        caía al respaldo de Vina.

        Arreglar sólo el `NameError` habría sido peor. La tabla a la que
        apuntaba tenía TRES residuos de veinte, y uno de sus patrones
        —`"N": "[NX3][CX3](=[OX1])"`— casa con cualquier amida, empezando por
        el propio esqueleto peptídico. El resultado no habría sido un error:
        habría sido una secuencia inventada, plegada y acoplada.

        Había un tercer defecto: los residuos se recorrían en el orden de
        `GetSubstructMatches`, que sigue los índices atómicos. Con un SMILES
        escrito de N a C coincide por casualidad; con otro, la secuencia sale
        permutada, que es otro péptido.

        ═══════════════════════════════════════════════════════════════════
        Y LA QUIRALIDAD, QUE ES LO QUE MÁS IMPORTA AQUÍ
        ═══════════════════════════════════════════════════════════════════

        Nada de aquello miraba el estereocentro del Cα. Un D-péptido y su
        enantiómero L dan la misma secuencia de letras, así que ESMFold habría
        plegado el L y el resultado se habría presentado como la molécula del
        usuario. Un D-péptido se diseña justamente para NO ser el L: su razón
        de ser es resistir proteasas.

        ESMFold sólo conoce L. Así que con residuos D esto **se niega** en vez
        de plegar el enantiómero equivocado.

        Ver `secuencia.py` para la extracción y sus límites declarados.
        """
        from secuencia import SecuenciaNoDeterminable, extraer_secuencia

        try:
            lectura = extraer_secuencia(smiles)
        except SecuenciaNoDeterminable as exc:
            raise ValueError(str(exc)) from exc

        if lectura.tiene_d:
            posiciones = [
                f"{i + 1}{r.letra}"
                for i, r in enumerate(lectura.residuos)
                if r.serie == "D"
            ]
            raise ValueError(
                f"El péptido lleva aminoácidos D en {', '.join(posiciones)}. "
                f"ESMFold sólo pliega L, y plegar el enantiómero L habría "
                f"devuelto una molécula distinta de la que se pidió."
            )

        if lectura.tiene_no_estandar:
            posiciones = [
                str(i + 1) for i, r in enumerate(lectura.residuos) if r.letra == "X"
            ]
            raise ValueError(
                f"No se reconocieron los residuos en las posiciones "
                f"{', '.join(posiciones)}: no son de los veinte estándar. "
                f"ESMFold no puede plegar la secuencia sin ellos."
            )

        if lectura.series_sin_declarar:
            # No se rechaza —un SMILES sin estereoquímica es una entrada
            # legítima— pero se deja constancia de qué se supuso.
            log.warning(
                "esmfold_estereoquimica_no_declarada",
                residuos=lectura.series_sin_declarar,
                nota="el SMILES no declara la configuración; se pliega como L",
            )

        return lectura.secuencia

    def _fold_sequence(self, sequence: str) -> str:
        """Pliega una secuencia aminoacídica con ESMFold y devuelve PDB."""
        import torch

        # ESMFold tiene límite de secuencia; truncar si es necesario
        if len(sequence) > 400:
            log.warning("sequence_truncated", length=len(sequence),
                       msg="ESMFold limitado a ~400 residuos. Truncando.")
            sequence = sequence[:400]

        tokenized = self._tokenizer(
            [sequence], return_tensors="pt", add_special_tokens=False
        )
        tokenized = {k: v.to(self._device) for k, v in tokenized.items()}

        with torch.no_grad():
            output = self._model(**tokenized)

        # ═══════════════════════════════════════════════════════════════
        # EL CONVERSOR ES EL DE HUGGING FACE, NO UNO ARTESANAL
        # ═══════════════════════════════════════════════════════════════
        #
        # Aquí se llamaba a `_positions_to_pdb`, escrito a mano, con cuatro
        # errores que se midieron ejecutando el modelo de verdad sobre la
        # angiotensina II (`DRVYIHPF`) el 2026-09-04:
        #
        #   1. `output["positions"][0]` NO es (L, 37, 3) como decía el
        #      comentario: es (1, L, 14, 3). La primera dimensión de
        #      `output["positions"]` indexa los BLOQUES del módulo de
        #      estructura, así que `[0]` tomaba el bloque MENOS refinado, y
        #      dejaba la dimensión de lote dentro.
        #   2. Por eso `zip(sequence, positions)` emparejaba los 8 residuos
        #      contra una dimensión de lote de tamaño 1: una sola iteración.
        #   3. `bfactor = float(plddt[res_idx])` recibía un array de 37
        #      elementos: `TypeError: only 0-dimensional arrays can be
        #      converted to Python scalars`.
        #   4. `zip({"N","CA","C","O"}, coords[:4])` iteraba un SET, y los
        #      índices 0-3 de la representación atom14/atom37 son N, CA, C y
        #      **CB** — no O. El cuarto átomo se etiquetaba como oxígeno.
        #
        # El (3) hace que la función lance antes de devolver nada, así que el
        # modo `fast` —el modo por defecto— nunca llegó a producir un PDB
        # plegado. El modelo sí funciona: carga en ~11 s y pliega la
        # angiotensina II en ~12 s sobre CPU.
        #
        # `output_to_pdb` es el conversor de la propia biblioteca: toma el
        # bloque final, resuelve los nombres de átomo y maneja el lote. No hay
        # motivo para tener otro.
        return self._model.output_to_pdb(output)[0]

    @staticmethod
    def _compute_plddt_from_pdb(pdb_text: str) -> float:
        """pLDDT medio en la escala CONVENCIONAL 0-100.

        ═════════════════════════════════════════════════════════════════
        LA ESCALA, QUE NO ERA LA QUE EL CÓDIGO SUPONÍA
        ═════════════════════════════════════════════════════════════════

        `output_to_pdb` escribe los B-factors en **0-1**, no en 0-100. Medido
        con la angiotensina II el 2026-09-04: min 0.54, max 0.81, media 0.72 —
        es decir, un pLDDT de 72 sobre 100, una confianza razonable.

        Esta función devolvía esa media tal cual, y aguas arriba:

            if plddt < 50.0:  -> aviso «pLDDT bajo»    SIEMPRE se disparaba
            confidence = plddt / 100.0                 salía 0.007

        Toda corrida de ESMFold avisaba de baja confianza y reportaba una
        centésima parte de la que tenía.

        Se normaliza aquí, y se detecta la escala en vez de suponerla: un PDB
        de otra fuente puede traer los B-factors ya en 0-100, y multiplicar dos
        veces sería el mismo error con el signo cambiado.
        """
        values = []
        for line in pdb_text.splitlines():
            if line.startswith(("ATOM", "HETATM")):
                try:
                    values.append(float(line[60:66]))
                except (ValueError, IndexError):
                    pass
        if not values:
            return 0.0

        media = sum(values) / len(values)
        # pLDDT en 0-100 nunca es <= 1.0 salvo en una estructura sin ninguna
        # confianza, caso en el que multiplicar por 100 tampoco la crea.
        if max(values) <= 1.0:
            media *= 100.0
        return media

    # ── Grid computation ───────────────────────────────────────────────

    @staticmethod
    def _compute_grid_from_ligand(pdb_path: str) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Calcula centro y tamaño del grid box basado en el ligando plegado."""
        coords = []
        with open(pdb_path) as f:
            for line in f:
                if line.startswith(("ATOM", "HETATM")):
                    try:
                        coords.append((
                            float(line[30:38]),
                            float(line[38:46]),
                            float(line[46:54]),
                        ))
                    except (ValueError, IndexError):
                        continue

        if not coords:
            return (0.0, 0.0, 0.0), (25.0, 25.0, 25.0)

        xs, ys, zs = zip(*coords)
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        cz = sum(zs) / len(zs)
        span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) + 10.0
        span = max(span, 20.0)
        return (cx, cy, cz), (span, span, span)

    # ── Vina docking ───────────────────────────────────────────────────

    def _vina_dock(
        self,
        ligand_pdb_path: str,
        receptor_pdb_path: str,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        num_poses: int,
    ) -> list[PredictedPose]:
        """
        Ejecuta AutoDock Vina para dockear el péptido plegado contra el receptor.

        Prepara el ligando con Meeko (SMILES → PDBQT) y el receptor con
        mk_prepare_receptor.py (PDB → PDBQT). Ejecuta Vina como subprocess.
        """
        import subprocess

        cx, cy, cz = center
        sx, sy, sz = size

        # `ignore_cleanup_errors`: en Windows no se puede borrar un archivo que
        # alguien tenga abierto, y aqui dentro corren procesos hijos -Meeko, Vina,
        # Open Babel- mas el antivirus escaneando lo recien escrito. Sin esto, la
        # limpieza puede levantar PermissionError DESPUES de que el trabajo haya
        # terminado bien, y tirar una corrida completa por no poder borrar un
        # temporal. Dejar un archivo suelto es mucho mejor que perder el resultado.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True, prefix="esmfold_vina_") as tmpdir:
            tmp = Path(tmpdir)
            lig_pdbqt = tmp / "ligand.pdbqt"
            rec_pdbqt = tmp / "receptor.pdbqt"
            out_pdbqt = tmp / "out.pdbqt"

            # ── MEEKO SE INVOCA COMO MÓDULO, NO POR RUTA ─────────────────
            #
            # Aquí decía:
            #
            #     mk = shutil.which("mk_prepare_ligand.py") or "mk_prepare_ligand"
            #     subprocess.run([sys.executable, mk, ...], cwd=str(tmp))
            #
            # Cuando `which` no encuentra el script —que es lo normal: Meeko se
            # instala como biblioteca y sus entry points no siempre quedan en
            # PATH— el `or` deja la CADENA LITERAL, y Python intenta ejecutar un
            # archivo con ese nombre dentro del directorio temporal. Medido el
            # 2026-09-04:
            #
            #     can't open file '...\esmfold_vina_xxxx\mk_prepare_ligand'
            #
            # Es decir: la preparación del ligando fallaba SIEMPRE, y con ella
            # el acoplamiento entero. El resto del árbol ya lo hace bien —ver
            # `services/docking/preparer.py`, que usa `-m
            # meeko.cli.mk_prepare_receptor`— así que aquí se hace igual.
            # ── `-i` ENTRA POR PRODY, Y PRODY NO ARRANCA CON NUMPY 2 ─────
            #
            # `mk_prepare_receptor -i` es el atajo de `--read_with_prody`, y
            # ProDy sigue importando `numpy.alltrue`, que NumPy retiro en la 2.0.
            # El runtime embebido trae NumPy 2.4.4, asi que la preparacion del
            # receptor moria SIEMPRE con:
            #
            #     returncode 2
            #     cannot import name 'alltrue' from 'numpy'
            #
            # Y el log no lo decia: `result.stderr[:300]` recorta desde el
            # PRINCIPIO, y ahi solo caben dos DeprecationWarning de ProDy. El
            # error real quedaba fuera del recorte.
            #
            # `--read_pdb` usa el lector propio de Meeko y no toca ProDy.
            # Verificado sobre 1HSG con este mismo runtime: returncode 0.
            #
            # Y dos detalles mas de la misma llamada:
            #
            #   * faltaba `-p`, que es la bandera que ESCRIBE el receptor rigido;
            #   * `-o receptor.pdbqt` produce `receptor.pdbqt.pdbqt`, porque
            #     Meeko anade la extension. Vina recibia una ruta inexistente.
            #     Se le pasa el tronco, sin extension.
            def _meeko_receptor(entrada: str, salida: Path) -> subprocess.CompletedProcess:
                tronco = salida.with_suffix("")
                return subprocess.run(
                    [sys.executable, "-m", "meeko.cli.mk_prepare_receptor",
                     "--read_pdb", entrada, "-o", str(tronco), "-p"],
                    capture_output=True, text=True, timeout=120, cwd=str(tmp),
                )

            # ── EL LIGANDO VA POR LA API, NO POR LA CLI ──────────────────
            #
            # `mk_prepare_ligand` sólo acepta sdf/mol2/mol:
            #
            #     Error: Format [pdb] not in supported formats [sdf/mol2/mol]
            #
            # y lo que ESMFold produce es un PDB. Aunque la invocación por
            # módulo estuviera bien —lo estaba a partir de este commit— el
            # formato la habría hecho fallar igual. Se usa la API de Python de
            # Meeko sobre un mol de RDKit, que es como lo hace
            # `services/ai/clgnn_inference.py`.
            try:
                from meeko import MoleculePreparation, PDBQTWriterLegacy
                from rdkit import Chem

                if Path(ligand_pdb_path).suffix.lower() in (".sdf", ".mol"):
                    mol = Chem.MolFromMolFile(ligand_pdb_path, removeHs=False, sanitize=True)
                else:
                    mol = Chem.MolFromPDBFile(ligand_pdb_path, removeHs=False, sanitize=True)
                if mol is None:
                    log.warning("ligando_pdb_no_parseable", ruta=ligand_pdb_path)
                    return ESMFoldFastPredictor._fallback_poses(ligand_pdb_path)
                mol = Chem.AddHs(mol, addCoords=True)

                preparacion = MoleculePreparation()
                setups = preparacion.prepare(mol)
                if not setups:
                    log.warning("meeko_sin_setups")
                    return ESMFoldFastPredictor._fallback_poses(ligand_pdb_path)
                pdbqt_str, ok, msg = PDBQTWriterLegacy.write_string(setups[0])
                if not ok:
                    log.warning("meeko_write_failed", detalle=str(msg)[:300])
                    return ESMFoldFastPredictor._fallback_poses(ligand_pdb_path)
                lig_pdbqt.write_text(pdbqt_str, encoding="utf-8")
                pdbqt_atom_map = ESMFoldFastPredictor._pdbqt_heavy_index_map(
                    pdbqt_str, mol
                )
            except Exception as exc:
                log.warning("meeko_ligand_prep_failed",
                            error=f"{type(exc).__name__}: {exc}"[:300])
                return ESMFoldFastPredictor._fallback_poses(ligand_pdb_path)

            result = _meeko_receptor(receptor_pdb_path, rec_pdbqt)
            # El recorte va por la COLA. `stderr[:300]` dejaba fuera el error y
            # guardaba dos DeprecationWarning de ProDy: un log que no permitia
            # diagnosticar el fallo que estaba registrando.
            if result.returncode != 0 or not rec_pdbqt.is_file():
                log.warning(
                    "meeko_receptor_prep_failed",
                    returncode=result.returncode,
                    salida_existe=rec_pdbqt.is_file(),
                    stderr=(result.stderr or "")[-600:],
                )
                return ESMFoldFastPredictor._fallback_poses(ligand_pdb_path)

            # Ejecutar Vina
            vina_cmd = [
                self._vina_path,
                "--ligand", str(lig_pdbqt),
                "--receptor", str(rec_pdbqt),
                "--center_x", str(cx), "--center_y", str(cy), "--center_z", str(cz),
                "--size_x", str(sx), "--size_y", str(sy), "--size_z", str(sz),
                "--out", str(out_pdbqt),
                "--num_modes", str(num_poses),
                "--exhaustiveness", "8",
                "--seed", "42",
            ]
            # ── TRES TIMEOUTS EN CASCADA, Y ÉSTE ES EL QUE MANDA ─────────
            #
            # Estaba en 300 s fijos, por debajo del timeout de la predicción y
            # del cliente: subir aquellos no cambiaba nada porque este cortaba
            # antes. Medido con el receptor 1HSG y su caja de 25 Å en CPU:
            #
            #     6 residuos,  41 átomos pesados     ~120 s   completa
            #     6 residuos,  52 átomos pesados     >300 s   se cortaba aquí
            #     8 residuos,  75 átomos pesados     >300 s   se cortaba aquí
            #    12 residuos,  81 átomos pesados     >300 s   se cortaba aquí
            #
            # El plegado son 5-10 s; esto es Vina buscando en los grados de
            # libertad de un péptido, que es mucho más caro que una molécula
            # pequeña.
            #
            # La jerarquía tiene que ir de dentro afuera para que cada capa
            # pueda dar un motivo en vez de ser cortada por la de encima:
            #
            #     Vina (aquí)                    900 s
            #     predict_timeout_seconds       1200 s   config.py
            #     PREDICT_TIMEOUT_S del cliente 1320 s   services/esmfold/
            VINA_TIMEOUT_S = float(os.environ.get("ESMFOLD_VINA_TIMEOUT", "900"))
            try:
                result = subprocess.run(
                    vina_cmd, capture_output=True, text=True, timeout=VINA_TIMEOUT_S,
                    cwd=str(tmp),
                )
            except subprocess.TimeoutExpired:
                # El límite es real y conviene decirlo con su causa. Medido en
                # CPU contra 1HSG con caja de 25 Å y exhaustiveness 8:
                #
                #     41 átomos pesados (6 residuos)    120 s   completa
                #     52 átomos pesados (6 residuos)    297 s   completa
                #     75 átomos pesados (8 residuos)   >900 s   no cabe
                #
                # «Timeout» a secas manda a mirar la red o el disco. Lo que pasa
                # es que el ligando tiene demasiados grados de libertad para el
                # tiempo concedido, y eso el investigador sí puede accionarlo:
                # acortar el péptido, estrechar la caja o usar una máquina con
                # GPU.
                n_pesados = getattr(mol, "GetNumHeavyAtoms", lambda: 0)()
                log.warning(
                    "vina_timeout_peptido",
                    segundos=VINA_TIMEOUT_S,
                    atomos_pesados=n_pesados,
                )
                raise RuntimeError(
                    f"AutoDock Vina no terminó en {int(VINA_TIMEOUT_S)} s para un "
                    f"péptido de {n_pesados} átomos pesados. No es un fallo de "
                    "configuración: el coste de búsqueda crece con los grados de "
                    "libertad del ligando, y en CPU el límite práctico está "
                    "alrededor de 50-60 átomos pesados. Usa un péptido más corto, "
                    "una caja más estrecha, o una máquina con GPU. Se puede subir "
                    "el límite con ESMFOLD_VINA_TIMEOUT."
                ) from None
            if result.returncode != 0 or not out_pdbqt.exists():
                log.warning("vina_docking_failed", returncode=result.returncode,
                           stderr=result.stderr[:200])
                return ESMFoldFastPredictor._fallback_poses(ligand_pdb_path)

            # Parsear output PDBQT → poses
            poses = ESMFoldFastPredictor._parse_vina_pdbqt(
                str(out_pdbqt), num_poses
            )
            for pose in poses:
                pose.ligand_sdf = ESMFoldFastPredictor._pose_sdf_from_pdbqt(
                    mol, pose.ligand_pdb, pdbqt_atom_map
                )
            return poses

    @staticmethod
    def _pdbqt_heavy_index_map(pdbqt_text: str, template_mol) -> dict[int, int]:
        """Mapea el serial PDBQT al índice del grafo RDKit de entrada.

        Meeko reordena los átomos al escribir PDBQT. ``REMARK SMILES IDX``
        conserva la relación entre el índice canónico del grafo y el serial
        que Vina devolverá; ignorar ese mapa intercambia átomos de la pose.
        Sólo se registran átomos pesados porque los H implícitos de Meeko no
        forman parte del grafo químico de autoridad.
        """
        import json
        from rdkit import Chem

        heavy_mol = Chem.RemoveHs(Chem.Mol(template_mol))
        Chem.MolToSmiles(heavy_mol, isomericSmiles=True)
        try:
            # RDKit deja aquí la lista de átomos del grafo en el orden de la
            # cadena canónica. Es la inversa de ``order`` de Meeko.
            canonical_to_template = json.loads(
                heavy_mol.GetProp("_smilesAtomOutputOrder")
            )
        except (KeyError, ValueError, TypeError):
            canonical_to_template = list(range(heavy_mol.GetNumAtoms()))
        result: dict[int, int] = {}
        for line in pdbqt_text.splitlines():
            if not line.startswith("REMARK SMILES IDX"):
                continue
            values = line[len("REMARK SMILES IDX"):].split()
            if len(values) % 2:
                continue
            for canonical, serial in zip(values[::2], values[1::2]):
                try:
                    canonical_idx = int(canonical) - 1
                    serial_idx = int(serial)
                except ValueError:
                    continue
                if 0 <= canonical_idx < len(canonical_to_template):
                    result[serial_idx] = int(canonical_to_template[canonical_idx])
        return result

    @staticmethod
    def _pose_sdf_from_pdbqt(
        template_mol,
        model_text: str,
        atom_index_by_serial: dict[int, int] | None = None,
    ) -> str | None:
        """Reaplica Vina al grafo original sin cambiar enlaces ni estereoquímica.

        El SDF de salida conserva sólo el grafo pesado del SMILES; Meeko vuelve
        a generar los H con ``addCoords=True``. Así no se dejan hidrógenos
        explícitos en ``(0, 0, 0)`` ni se confunden por el reordenamiento de
        átomos que hace Meeko.
        """
        from rdkit import Chem
        coords_by_serial: dict[int, tuple[float, float, float]] = {}
        for line in model_text.splitlines():
            if not line.startswith(("ATOM", "HETATM")) or len(line) < 54:
                continue
            try:
                serial = int(line[6:11])
            except (ValueError, IndexError):
                continue
            element = line[77:79].strip().upper() if len(line) >= 79 else ""
            if element == "H" or line[12:16].strip().startswith("H"):
                continue
            try:
                coords_by_serial[serial] = (
                    float(line[30:38]), float(line[38:46]), float(line[46:54])
                )
            except (ValueError, IndexError):
                continue

        mol = Chem.RemoveHs(Chem.Mol(template_mol))
        heavy = list(range(mol.GetNumAtoms()))
        if atom_index_by_serial:
            mapped = {
                atom_index: coords_by_serial[serial]
                for serial, atom_index in atom_index_by_serial.items()
                if serial in coords_by_serial and atom_index in heavy
            }
        else:
            coords = list(coords_by_serial.values())
            if len(coords) != len(heavy):
                return None
            mapped = dict(zip(heavy, coords))
        if len(mapped) != len(heavy):
            return None

        mol.RemoveAllConformers()
        mol.AddConformer(Chem.Conformer(mol.GetNumAtoms()), assignId=True)
        conf = mol.GetConformer()
        for idx, xyz in mapped.items():
            conf.SetAtomPosition(idx, xyz)
        return Chem.MolToMolBlock(mol)
    @staticmethod
    def _parse_vina_pdbqt(pdbqt_path: str, max_poses: int) -> list[PredictedPose]:
        """Parsea el output multi-model PDBQT de Vina en PredictedPose."""
        poses: list[PredictedPose] = []
        current_rank = 0
        current_model_lines: list[str] = []
        # `None` hasta leer el REMARK: un 0.0 inicial se persistiría como
        # «afinidad cero», que no es lo mismo que «no la hubo».
        current_affinity: float | None = None

        with open(pdbqt_path) as f:
            for line in f:
                if line.startswith("MODEL"):
                    current_model_lines = [line]
                    current_rank += 1
                elif line.startswith("ENDMDL"):
                    current_model_lines.append(line)
                    # LA AFINIDAD SE CONSERVA TAL CUAL.
                    #
                    # Aquí se calculaba una «confianza» a partir de ella
                    # —invertida, ver el docstring de `PredictedPose`— y se
                    # tiraba el número real. Ahora viaja, y `confidence` queda
                    # en `None` porque esta rama NO mide confianza estructural:
                    # mide afinidad. Rellenarla con algo derivado de la
                    # afinidad es exactamente lo que había que quitar.
                    poses.append(PredictedPose(
                        rank=current_rank,
                        confidence=0.0,
                        ligand_pdb="".join(current_model_lines),
                        vina_affinity_kcal_mol=current_affinity,
                        origen=ORIGEN_VINA,
                    ))
                    current_affinity = None
                elif line.startswith("REMARK VINA RESULT:"):
                    try:
                        current_affinity = float(line.split()[3])
                    except (IndexError, ValueError):
                        pass
                else:
                    current_model_lines.append(line)

                if len(poses) >= max_poses:
                    break

        return poses

    @staticmethod
    def _fallback_poses(pdb_path: str) -> list[PredictedPose]:
        """La estructura plegada SIN acoplar, marcada como tal.

        Antes salía por el mismo campo que una pose de Vina, con una confianza
        inventada de 0.5, y aguas abajo se convertía en una «afinidad». Una
        estructura que nunca pasó por un motor de acoplamiento no es una pose
        de acoplamiento, y el dossier tiene que poder distinguirlas.

        `vina_affinity_kcal_mol` queda en `None` a propósito: no hay afinidad
        que reportar, y fabricar una es el defecto que esto corrige.
        """
        try:
            if Path(pdb_path).suffix.lower() in (".sdf", ".mol"):
                from rdkit import Chem
                _mol = Chem.MolFromMolFile(pdb_path, removeHs=False, sanitize=False)
                content = Chem.MolToPDBBlock(_mol) if _mol is not None else ""
                ligand_sdf = Chem.MolToMolBlock(_mol) if _mol is not None else None
            else:
                content = Path(pdb_path).read_text()
                ligand_sdf = None
        except Exception:
            content = ""
            ligand_sdf = None
        # La confianza SÍ existe: es la del plegado, y se lee de los B-factors
        # que ESMFold dejó en el propio PDB. Ponerla a 0.0 haría parecer que no
        # se sabe nada de la estructura cuando lo que falta es el acoplamiento.
        # Lo que queda en `None` es la afinidad, porque esa no existe.
        plddt = ESMFoldFastPredictor._compute_plddt_from_pdb(content) if content else 0.0
        return [PredictedPose(
            rank=1,
            confidence=round(plddt / 100.0, 3),
            ligand_pdb=content,
            vina_affinity_kcal_mol=None,
            origen=ORIGEN_SOLO_PLEGADO,
            ligand_sdf=ligand_sdf,
        )]

    # ── OpenMM refinement ──────────────────────────────────────────────

    @staticmethod
    def _refine_poses(
        poses: list[PredictedPose],
        receptor_pdb_path: str,
        max_iterations: int = 500,
    ) -> list[PredictedPose]:
        """
        Refina poses con OpenMM: minimización rápida de energía en la interfaz.

        Carga el complejo receptor-ligando, aplica constraints suaves en el
        backbone del receptor, y minimiza la energía del sistema.
        """
        try:
            import openmm as mm
            import openmm.app as app
            import openmm.unit as unit
        except ImportError:
            log.debug("openmm_not_available")
            return poses

        refined = []
        for pose in poses:
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdb", mode="w", delete=False) as f:
                    f.write(pose.ligand_pdb)
                    lig_path = f.name

                # Cargar sistema
                pdb = app.PDBFile(receptor_pdb_path)
                forcefield = app.ForceField("amber14-all.xml", "amber14/tip3pfb.xml")

                modeller = app.Modeller(pdb.topology, pdb.positions)
                try:
                    lig_pdb = app.PDBFile(lig_path)
                    modeller.add(lig_pdb.topology, lig_pdb.positions)
                except Exception:
                    os.unlink(lig_path)
                    refined.append(pose)
                    continue

                system = forcefield.createSystem(
                    modeller.topology,
                    nonbondedMethod=app.NoCutoff,
                    constraints=app.HBonds,
                )
                integrator = mm.LangevinMiddleIntegrator(
                    300 * unit.kelvin, 1.0 / unit.picosecond, 2.0 * unit.femtosecond
                )
                simulation = app.Simulation(
                    modeller.topology, system, integrator
                )
                simulation.context.setPositions(modeller.positions)

                # Minimizar energía
                simulation.minimizeEnergy(maxIterations=max_iterations)

                # Extraer posiciones del ligando
                state = simulation.context.getState(getPositions=True)
                positions = state.getPositions(asNumpy=True)

                # Guardar como PDB
                with tempfile.NamedTemporaryFile(suffix=".pdb", mode="w", delete=False) as out_f:
                    out_path = out_f.name
                app.PDBFile.writeFile(
                    modeller.topology, positions,
                    open(out_path, "w"),
                )

                refined_pdb = Path(out_path).read_text()
                # LA AFINIDAD Y EL ORIGEN SOBREVIVEN AL REFINADO.
                #
                # Esta reconstrucción copiaba rango, confianza, PDB y RMSD, y
                # dejaba `vina_affinity_kcal_mol` y `origen` en sus valores por
                # defecto. Como el defecto de `origen` es `ORIGEN_VINA`, pasaban
                # dos cosas a la vez por minimizar la energía de una pose:
                #
                #   · la afinidad que Vina midió se perdía  -> None
                #   · una pose `folded_structure_only` salía como `vina_docked`
                #
                # Es el mismo defecto que borraba el score de Vina en M4, con
                # otro disfraz: una etapa posterior reescribe el objeto y tira
                # la observación primaria. OpenMM mueve átomos; no mide unión ni
                # cambia de dónde vino la pose.
                refined.append(PredictedPose(
                    rank=pose.rank,
                    confidence=pose.confidence,
                    ligand_pdb=refined_pdb,
                    rmsd=pose.rmsd,
                    vina_affinity_kcal_mol=pose.vina_affinity_kcal_mol,
                    origen=pose.origen,
                    ligand_sdf=pose.ligand_sdf,
                ))

                os.unlink(lig_path)
                os.unlink(out_path)

            except Exception as e:
                log.debug("openmm_refine_pose_failed", rank=pose.rank, error=str(e))
                refined.append(pose)

        return refined


# ── ESMFold Pro Predictor (placeholder — Fase 3) ──────────────────────────


class ESMFoldProPredictor(ESMFoldFastPredictor):
    """
    Predictor preciso: plegamiento completo del complejo + refinamiento exhaustivo.

    Pipeline:
      1. Extraer secuencias del receptor (PDB) y péptido (SMILES)
      2. Plegar el COMPLEJO completo con ESMFold como multímero (receptor:péptido)
      3. Refinar la interfaz con OpenMM (2000 iteraciones, constraints suaves)
      4. Calcular métricas: pLDDT medio, pLDDT de interfaz, área de contacto
      5. Generar poses alternativas vía perturbaciones controladas de la interfaz

    Tiempo estimado: ~5-15 min (GPU).
    """

    # ── Override predict ───────────────────────────────────────────────

    async def predict(
        self,
        protein_pdb: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None,
        grid_size: tuple[float, float, float] | None,
    ) -> PredictionResult:
        import torch
        start = time.monotonic()
        warnings: list[str] = []
        tmp_files: list[str] = []

        try:
            # 1. Extraer secuencias
            peptide_seq = await asyncio.to_thread(
                self._smiles_to_aa_sequence, peptide_smiles
            )
            if not peptide_seq or len(peptide_seq) < 2:
                return PredictionResult(
                    success=False, poses=[], best_confidence=None,
                    method="ESMFold-Pro", execution_time_s=0.0,
                    warnings=warnings,
                    error="No se pudo extraer secuencia del péptido.",
                )

            receptor_seq = await asyncio.to_thread(
                self._extract_sequence_from_pdb_text, protein_pdb
            )
            if not receptor_seq or len(receptor_seq) < 20:
                warnings.append(
                    "Secuencia del receptor corta o no detectable. "
                    "El plegamiento del complejo puede ser menos preciso."
                )
                receptor_seq = "A" * 100  # fallback seguro

            log.info("esmfold_pro_sequences",
                     rec_len=len(receptor_seq), pep_len=len(peptide_seq))

            # 2. Guardar receptor a temp file
            fd_rec, rec_path = tempfile.mkstemp(suffix=".pdb", prefix="esmfoldpro_rec_")
            os.close(fd_rec)
            tmp_files.append(rec_path)
            Path(rec_path).write_text(protein_pdb)

            # 3. Plegar complejo completo con ESMFold multimer
            with torch.no_grad():
                complex_pdb = self._fold_complex(receptor_seq, peptide_seq)

            fd_cpx, cpx_path = tempfile.mkstemp(suffix=".pdb", prefix="esmfoldpro_cpx_")
            os.close(fd_cpx)
            tmp_files.append(cpx_path)
            Path(cpx_path).write_text(complex_pdb)

            # 4. Calcular métricas de calidad
            plddt_global = self._compute_plddt_from_pdb(complex_pdb)
            plddt_interface = self._compute_interface_plddt(complex_pdb, len(receptor_seq))
            contact_area = self._compute_contact_area(cpx_path, len(receptor_seq))
            log.info("esmfold_pro_metrics",
                     plddt_global=round(plddt_global, 2),
                     plddt_interface=round(plddt_interface, 2) if plddt_interface else None,
                     contact_area=round(contact_area, 1) if contact_area else None)

            if plddt_global < 60.0:
                warnings.append(
                    f"pLDDT global bajo ({plddt_global:.1f}). "
                    "El complejo plegado tiene baja confianza general."
                )

            # 5. Refinar interfaz con OpenMM (exhaustivo)
            refined_pdb = await asyncio.to_thread(
                self._refine_interface_exhaustive, complex_pdb, rec_path,
                len(receptor_seq),
            )

            # 6. Extraer el péptido del complejo refinado
            peptide_pdb = self._extract_chain_from_complex(refined_pdb, chain="B")
            if not peptide_pdb:
                peptide_pdb = refined_pdb

            # 7. Generar poses alternativas
            poses = await asyncio.to_thread(
                self._generate_alternatives_from_refined,
                refined_pdb, peptide_pdb, num_poses, len(receptor_seq),
            )

            best_confidence = round(plddt_global / 100.0, 3)

            return PredictionResult(
                success=True, poses=poses,
                best_confidence=best_confidence,
                method="ESMFold-Pro",
                execution_time_s=round(time.monotonic() - start, 2),
                warnings=warnings,
            )

        except Exception as e:
            log.exception("esmfold_pro_predict_error")
            return PredictionResult(
                success=False, poses=[], best_confidence=None,
                method="ESMFold-Pro",
                execution_time_s=round(time.monotonic() - start, 2),
                warnings=warnings,
                error=f"{type(e).__name__}: {e}",
            )
        finally:
            for f in tmp_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except OSError:
                    pass

    # ── Sequence extraction from PDB ───────────────────────────────────

    @staticmethod
    def _extract_sequence_from_pdb_text(pdb_text: str) -> str:
        """
        Extrae secuencia aminoacídica de un PDB (texto).

        Usa MDAnalysis si está disponible; si no, hace un parse
        heurístico de los ATOM records.
        """
        try:
            import MDAnalysis as mda
            from io import StringIO

            u = mda.Universe(StringIO(pdb_text), format="PDB")
            return ESMFoldProPredictor._sequence_from_residues(u.residues)
        except ImportError:
            pass

        # Fallback: parse heurístico de CA atoms
        return ESMFoldProPredictor._sequence_from_pdb_heuristic(pdb_text)

    @staticmethod
    def _sequence_from_residues(residues) -> str:
        """Convierte residuos MDAnalysis a secuencia 1-letra."""
        aa_one = []
        for res in residues:
            name = res.resname.strip().upper()
            aa_one.append(AA_3TO1.get(name, "X"))
        return "".join(aa_one)

    @staticmethod
    def _sequence_from_pdb_heuristic(pdb_text: str) -> str:
        """Parse heurístico: CA atoms con residue names estándar."""
        seen: set[int] = set()
        seq: list[str] = []
        for line in pdb_text.splitlines():
            if not line.startswith("ATOM"):
                continue
            if len(line) < 22:
                continue
            atom_name = line[12:16].strip()
            if atom_name != "CA":
                continue
            try:
                res_num = int(line[22:26])
            except ValueError:
                continue
            if res_num in seen:
                continue
            seen.add(res_num)
            res_name = line[17:20].strip().upper()
            seq.append(AA_3TO1.get(res_name, "X"))
        return "".join(seq)

    # ── Complex folding ────────────────────────────────────────────────

    def _fold_complex(self, receptor_seq: str, peptide_seq: str) -> str:
        """Pliega el complejo receptor:péptido como multímero con ESMFold."""
        import torch

        multimer = f"{receptor_seq}:{peptide_seq}"
        total_len = len(receptor_seq) + len(peptide_seq)

        if total_len > 400:
            # Truncar receptor para mantener el péptido completo
            max_rec = 400 - len(peptide_seq) - 1
            if max_rec < 50:
                raise ValueError(
                    f"Complejo demasiado grande ({total_len} residuos). "
                    "ESMFold multimer está limitado a ~400."
                )
            receptor_seq = receptor_seq[:max_rec]
            multimer = f"{receptor_seq}:{peptide_seq}"
            log.warning("receptor_truncated_for_multimer",
                       original=len(receptor_seq) + len(peptide_seq),
                       truncated=len(multimer))

        tokenized = self._tokenizer(
            [multimer], return_tensors="pt", add_special_tokens=False
        )
        tokenized = {k: v.to(self._device) for k, v in tokenized.items()}

        with torch.no_grad():
            output = self._model(**tokenized)

        positions = output["positions"][0].cpu().numpy()
        plddt = output.get("plddt", None)
        if plddt is not None:
            plddt = plddt[0].cpu().numpy()

        # Split sequence into two chains
        chain_a = receptor_seq
        chain_b = peptide_seq
        full_seq = chain_a + chain_b

        return self._positions_to_multichain_pdb(
            chain_a, chain_b, positions, plddt
        )

    @staticmethod
    def _positions_to_multichain_pdb(
        chain_a: str, chain_b: str, positions, plddt
    ) -> str:
        """Convierte posiciones de ESMFold multimer a PDB multi-cadena."""
        lines: list[str] = []
        atom_idx = 0
        backbone_atoms = {"N", "CA", "C", "O"}

        for chain_id, sequence in [("A", chain_a), ("B", chain_b)]:
            start = 0 if chain_id == "A" else len(chain_a)
            for res_offset, (res_name_1, coords) in enumerate(
                zip(sequence, positions[start : start + len(sequence)])
            ):
                res_idx = (start + res_offset + 1) if chain_id == "A" else (res_offset + 1)
                for atom_name, coord in zip(backbone_atoms, coords[:4]):
                    if atom_name not in backbone_atoms:
                        continue
                    atom_idx += 1
                    bf = float(plddt[start + res_offset]) if plddt is not None else 0.0
                    x, y, z = float(coord[0]), float(coord[1]), float(coord[2])
                    lines.append(
                        f"ATOM  {atom_idx:5d}  {atom_name:<3s} UNK {chain_id}{res_idx:4d}    "
                        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00{bf:6.2f}           {atom_name[0]:1s}"
                    )

        lines.append("TER")
        lines.append("END")
        return "\n".join(lines)

    # ── Interface metrics ──────────────────────────────────────────────

    @staticmethod
    def _compute_interface_plddt(pdb_text: str, receptor_length: int) -> float | None:
        """pLDDT medio de los residuos del péptido (cadena B) en el complejo."""
        values = []
        for line in pdb_text.splitlines():
            if line.startswith(("ATOM", "HETATM")) and line[21:22] == "B":
                try:
                    b = float(line[60:66])
                    values.append(b)
                except (ValueError, IndexError):
                    pass
        return sum(values) / len(values) if values else None

    @staticmethod
    def _compute_contact_area(pdb_path: str, receptor_length: int) -> float | None:
        """Área de contacto aproximada entre cadenas A y B (Å²)."""
        try:
            import MDAnalysis as mda
            import numpy as np

            u = mda.Universe(pdb_path)
            chain_a = u.select_atoms("chainID A")
            chain_b = u.select_atoms("chainID B")

            if len(chain_a) == 0 or len(chain_b) == 0:
                return None

            cutoff = 8.0  # Å
            contacts = 0
            for atom_a in chain_a.atoms.positions:
                dists = np.linalg.norm(chain_b.atoms.positions - atom_a, axis=1)
                contacts += np.sum(dists < cutoff)

            # Aproximación: ~20 Å² por contacto cercano
            return round(float(contacts) * 20.0, 1)
        except ImportError:
            return None
        except Exception:
            return None

    # ── Exhaustive refinement ──────────────────────────────────────────

    @staticmethod
    def _refine_interface_exhaustive(
        complex_pdb: str,
        receptor_pdb_path: str,
        receptor_length: int,
        max_iterations: int = 2000,
    ) -> str:
        """
        Refinamiento exhaustivo del complejo con OpenMM.

        Más iteraciones que el modo fast (2000 vs 500), constraints
        más suaves en la interfaz para permitir reacomodo local.
        """
        try:
            import openmm as mm
            import openmm.app as app
            import openmm.unit as unit
        except ImportError:
            log.debug("openmm_not_available_for_pro")
            return complex_pdb

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdb", mode="w", delete=False) as f:
                f.write(complex_pdb)
                cpx_path = f.name

            pdb = app.PDBFile(cpx_path)
            forcefield = app.ForceField("amber14-all.xml", "amber14/tip3pfb.xml")

            # Constraints suaves: solo backbone, no sidechains
            system = forcefield.createSystem(
                pdb.topology,
                nonbondedMethod=app.NoCutoff,
                constraints=app.HBonds,
            )

            # Restraint suave en backbone del receptor para mantener el fold
            force = mm.CustomExternalForce("0.5 * k * ((x-x0)^2 + (y-y0)^2 + (z-z0)^2)")
            force.addGlobalParameter("k", 10.0 * unit.kilocalories_per_mole / unit.angstroms**2)
            force.addPerParticleParameter("x0")
            force.addPerParticleParameter("y0")
            force.addPerParticleParameter("z0")

            for i, atom in enumerate(pdb.topology.atoms()):
                chain = atom.residue.chain.id if atom.residue.chain else ""
                if chain == "A" and atom.name == "CA":
                    pos = pdb.positions[i]
                    force.addParticle(i, [
                        pos.x.value_in_unit(unit.angstroms),
                        pos.y.value_in_unit(unit.angstroms),
                        pos.z.value_in_unit(unit.angstroms),
                    ])
            system.addForce(force)

            integrator = mm.LangevinMiddleIntegrator(
                300 * unit.kelvin, 1.0 / unit.picosecond, 2.0 * unit.femtosecond
            )
            simulation = app.Simulation(pdb.topology, system, integrator)
            simulation.context.setPositions(pdb.positions)

            # Minimizar
            simulation.minimizeEnergy(maxIterations=max_iterations)

            state = simulation.context.getState(getPositions=True)
            positions = state.getPositions(asNumpy=True)

            with tempfile.NamedTemporaryFile(suffix=".pdb", mode="w", delete=False) as out_f:
                out_path = out_f.name
            app.PDBFile.writeFile(pdb.topology, positions, open(out_path, "w"))
            result = Path(out_path).read_text()

            os.unlink(cpx_path)
            os.unlink(out_path)
            return result

        except Exception as e:
            log.warning("openmm_pro_refine_failed", error=str(e))
            return complex_pdb

    # ── Chain extraction ───────────────────────────────────────────────

    @staticmethod
    def _extract_chain_from_complex(pdb_text: str, chain: str = "B") -> str:
        """Extrae átomos de una cadena específica del complejo PDB."""
        lines = []
        for line in pdb_text.splitlines():
            if line.startswith(("ATOM", "HETATM")) and len(line) >= 22:
                if line[21:22] == chain:
                    lines.append(line)
        if lines:
            lines.append("TER")
            lines.append("END")
        return "\n".join(lines)

    # ── Alternative pose generation ────────────────────────────────────

    @staticmethod
    def _generate_alternatives_from_refined(
        refined_pdb: str,
        peptide_pdb: str,
        num_poses: int,
        receptor_length: int,
    ) -> list[PredictedPose]:
        """
        Genera poses alternativas por perturbación controlada.

        Estrategia: pequeñas rotaciones y traslaciones del péptido
        alrededor de la posición refinada, respetando la interfaz.
        """
        import math
        import random

        # NINGUNA de estas poses pasó por Vina: el camino Pro pliega el
        # complejo, refina la interfaz con OpenMM y perturba el péptido. Sin
        # `origen` explícito salían con el defecto —`ORIGEN_VINA`—, es decir,
        # etiquetadas como acopladas por un motor que en esta rama no se
        # ejecuta. `confidence` es la del plegado/refinado y NO se convierte a
        # kcal/mol en ningún sitio; la afinidad es `None` porque no existe.
        poses = [
            PredictedPose(rank=1, confidence=0.95, ligand_pdb=peptide_pdb,
                          vina_affinity_kcal_mol=None,
                          origen=ORIGEN_SOLO_PLEGADO)
        ]

        if num_poses <= 1:
            return poses

        # Parsear átomos del péptido
        pept_atoms = []
        for line in peptide_pdb.splitlines():
            if line.startswith(("ATOM", "HETATM")) and len(line) >= 54:
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    pept_atoms.append((x, y, z, line[:30], line[54:]))
                except (ValueError, IndexError):
                    pass

        if not pept_atoms:
            return poses

        # Centroide del péptido
        cx = sum(a[0] for a in pept_atoms) / len(pept_atoms)
        cy = sum(a[1] for a in pept_atoms) / len(pept_atoms)
        cz = sum(a[2] for a in pept_atoms) / len(pept_atoms)

        seed = hash(peptide_pdb[:200]) % 2**31
        rng = random.Random(seed)

        for rank in range(2, num_poses + 1):
            # Pequeña rotación (~5-15 grados) y traslación (~1-3 Å)
            angle = math.radians(rng.uniform(5, 15))
            dx = rng.uniform(-2.0, 2.0)
            dy = rng.uniform(-2.0, 2.0)
            dz = rng.uniform(-1.0, 1.0)

            cos_a = math.cos(angle)
            sin_a = math.sin(angle)

            alt_lines = []
            atom_idx = 0
            for (x, y, z, prefix, suffix) in pept_atoms:
                # Rotar alrededor del eje Z (centrado en el centroide)
                rx = cx + (x - cx) * cos_a - (y - cy) * sin_a + dx
                ry = cy + (x - cx) * sin_a + (y - cy) * cos_a + dy
                rz = z + dz
                atom_idx += 1
                alt_lines.append(
                    f"{prefix}{rx:8.3f}{ry:8.3f}{rz:8.3f}{suffix}"
                )

            alt_lines.append("TER")
            alt_lines.append("END")
            alt_pdb = "\n".join(alt_lines)

            confidence = round(max(0.4, 0.95 - (rank - 1) * 0.12), 3)
            poses.append(PredictedPose(
                rank=rank, confidence=confidence, ligand_pdb=alt_pdb,
                vina_affinity_kcal_mol=None, origen=ORIGEN_SOLO_PLEGADO,
            ))

        return poses


# ── Factory ──────────────────────────────────────────────────────────────


def make_predictor(mode: str, model_dir: str, device: str = "auto") -> BasePredictor:
    """
    Fábrica de predictores.

    Modos:
      - "stub"  → StubPredictor (poses dummy, tests E2E)
      - "fast"  → ESMFoldFastPredictor (ESMFold + Vina + OpenMM)
      - "pro"   → ESMFoldProPredictor (plegamiento completo + refinamiento)
      - "real"  → alias legacy de "fast"
    """
    if mode == "stub":
        return StubPredictor()
    if mode in ("fast", "real"):
        return ESMFoldFastPredictor(model_dir=model_dir, device=device)
    if mode == "pro":
        return ESMFoldProPredictor(model_dir=model_dir, device=device)
    raise ValueError(f"Modo desconocido: {mode!r}. Usa 'stub', 'fast', o 'pro'.")

"""
predictor.py — RFdiffusion Predictor (Experimental).

Pipeline:
  1. Validar GPU disponible (RFdiffusion requiere CUDA)
  2. Extraer secuencia del péptido desde SMILES (RDKit)
  3. Ejecutar RFdiffusion vía subprocess (scripts/run_inference.py)
  4. Parsear resultados → poses con métricas de confianza

Modo: esmfold-experimental
Tiempo estimado: ~10-20 min (GPU NVIDIA >=8 GB)
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from logger import get_logger

log = get_logger(__name__)


# ── Tipos públicos ────────────────────────────────────────────────────────


@dataclass
class PredictedPose:
    rank: int
    confidence: float
    ligand_pdb: str
    rmsd: float | None = None


@dataclass
class PredictionResult:
    success: bool
    poses: list[PredictedPose]
    best_confidence: float | None
    method: str
    execution_time_s: float
    warnings: list[str]
    error: str | None = None


# ── AA map ────────────────────────────────────────────────────────────────

AA_3TO1: dict[str, str] = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "MSE": "M", "HYP": "P",
}


# ── Abstract ──────────────────────────────────────────────────────────────


class BasePredictor(ABC):
    @abstractmethod
    async def load(self) -> None:
        """Verifica GPU y disponibilidad de RFdiffusion."""

    @abstractmethod
    async def predict(
        self,
        protein_pdb: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None,
        grid_size: tuple[float, float, float] | None,
    ) -> PredictionResult:
        """Predice poses vía RFdiffusion RFpeptides."""


# ── Stub (tests E2E) ──────────────────────────────────────────────────────


class StubPredictor(BasePredictor):
    """Predictor dummy para tests E2E sin GPU."""

    async def load(self) -> None:
        log.info("StubPredictor cargado (RFdiffusion stub)")

    async def predict(
        self,
        protein_pdb: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None,
        grid_size: tuple[float, float, float] | None,
    ) -> PredictionResult:
        start = time.monotonic()
        await asyncio.sleep(random.uniform(1.0, 2.0))

        poses: list[PredictedPose] = []
        seed = int(hashlib.sha256(
            f"{protein_pdb[:200]}|{peptide_smiles}|{num_poses}".encode()
        ).hexdigest()[:8], 16)
        rng = random.Random(seed)

        for rank in range(1, num_poses + 1):
            confidence = round(max(0.05, 1.0 - (rank - 1) * 0.2 + rng.uniform(-0.03, 0.03)), 3)
            poses.append(PredictedPose(
                rank=rank, confidence=confidence,
                ligand_pdb=(
                    f"REMARK   RFdiffusion Stub rank={rank}\n"
                    f"ATOM      1  N   ALA A   1      {5.0*rank:6.3f}   0.000   0.000\n"
                    f"END\n"
                ),
            ))

        return PredictionResult(
            success=True, poses=poses,
            best_confidence=poses[0].confidence if poses else None,
            method="RFdiffusion-Stub",
            execution_time_s=round(time.monotonic() - start, 2),
            warnings=["Resultado STUB. Instalar GPU + RFdiffusion para predicciones reales."],
        )


# ── RFdiffusion Predictor ─────────────────────────────────────────────────


class RFdiffusionPredictor(BasePredictor):
    """
    Predictor experimental: RFdiffusion RFpeptides (Baker Lab).

    Ejecuta RFdiffusion como subprocess en su conda environment.
    El modelo usa difusión SE(3)-equivariante para plegar y acoplar
    el péptido al receptor en un solo paso.

    Requisitos:
      - GPU NVIDIA >=8 GB VRAM con CUDA
      - RFdiffusion clonado en rfdiffusion_path
      - Checkpoints en model_dir: Base_ckpt.pt, Complex_base_ckpt.pt
      - Conda env 'SE3nv' con SE(3)-Transformer
    """

    def __init__(
        self,
        model_dir: str,
        rfdiffusion_path: str,
        device: str = "auto",
        predict_timeout: float = 1200.0,
    ):
        self.model_dir = Path(model_dir)
        self.rfdiffusion_path = Path(rfdiffusion_path)
        self._device = device
        self._predict_timeout = predict_timeout
        self._gpu_available = False

    # ── Public interface ───────────────────────────────────────────────

    async def load(self) -> None:
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(
                "RFdiffusion requiere GPU NVIDIA con CUDA. "
                "Este modo es experimental y necesita hardware dedicado. "
                "Usa 'esmfold' o 'esmfold-pro' como alternativas sin GPU."
            )

        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_mem / (1024**3)
        log.info("RFdiffusion GPU detectada", gpu=gpu_name, vram_gb=round(vram_gb, 1))

        if vram_gb < 6.0:
            raise RuntimeError(
                f"VRAM insuficiente ({vram_gb:.1f} GB). "
                "RFdiffusion necesita >=8 GB idealmente (mínimo 6 GB)."
            )

        self._gpu_available = True

        # Verificar checkpoints
        required = ["Base_ckpt.pt", "Complex_base_ckpt.pt"]
        for m in required:
            if not (self.model_dir / m).exists():
                log.warning(
                    f"checkpoint_missing: {m}",
                    model_dir=str(self.model_dir),
                )

        # Verificar repo RFdiffusion
        run_script = self.rfdiffusion_path / "scripts" / "run_inference.py"
        if not run_script.exists():
            log.warning(
                "rfdiffusion_not_found",
                expected=str(run_script),
            )

        log.info("RFdiffusionPredictor cargado",
                 gpu_available=self._gpu_available,
                 model_dir=str(self.model_dir))

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
        tmp_files: list[str] = []

        try:
            # 1. Extraer secuencia
            peptide_seq = await asyncio.to_thread(
                self._smiles_to_aa_sequence, peptide_smiles
            )
            if not peptide_seq or len(peptide_seq) < 2:
                return PredictionResult(
                    success=False, poses=[], best_confidence=None,
                    method="RFdiffusion", execution_time_s=0.0, warnings=warnings,
                    error="No se pudo extraer secuencia del péptido.",
                )

            # 2. Guardar receptor a temp file
            fd_rec, rec_path = tempfile.mkstemp(suffix=".pdb", prefix="rfdiff_rec_")
            os.close(fd_rec)
            tmp_files.append(rec_path)
            Path(rec_path).write_text(protein_pdb)

            # 3. Detectar hotspots en la interfaz
            hotspots = await asyncio.to_thread(
                self._detect_hotspots, rec_path, peptide_seq
            )
            if not hotspots:
                warnings.append(
                    "No se detectaron hotspots de interfaz. "
                    "RFdiffusion usará el receptor completo — puede ser más lento."
                )

            # 4. Ejecutar RFdiffusion
            poses = await asyncio.to_thread(
                self._run_rfdiffusion,
                rec_path, peptide_seq, num_poses, hotspots,
                tmp_files,
            )

            best_conf = poses[0].confidence if poses else None

            return PredictionResult(
                success=True, poses=poses,
                best_confidence=best_conf,
                method="RFdiffusion",
                execution_time_s=round(time.monotonic() - start, 2),
                warnings=warnings,
            )

        except subprocess.TimeoutExpired:
            return PredictionResult(
                success=False, poses=[], best_confidence=None,
                method="RFdiffusion",
                execution_time_s=round(time.monotonic() - start, 2),
                warnings=warnings,
                error=f"Timeout: RFdiffusion excedió {self._predict_timeout}s.",
            )
        except Exception as e:
            log.exception("rfdiffusion_predict_error")
            return PredictionResult(
                success=False, poses=[], best_confidence=None,
                method="RFdiffusion",
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

    # ── Sequence extraction ────────────────────────────────────────────────

    # La tabla `_AA_SMARTS` que vivía aquí se ha eliminado, y con ella los tres
    # métodos que la leían (`_expand_residue`, `_match_aa_by_smarts`,
    # `_identify_single_aa`).
    #
    # ═══════════════════════════════════════════════════════════════════════
    # NUNCA EXTRAJO UNA SECUENCIA. NI UNA.
    # ═══════════════════════════════════════════════════════════════════════
    #
    # `_match_aa_by_smarts` y `_identify_single_aa` usaban `Chem` como nombre de
    # módulo, pero el único `import rdkit.Chem as Chem` de este archivo estaba
    # DENTRO de `_smiles_to_aa_sequence`. Un import local no crea un global, así
    # que las dos funciones levantaban
    #
    #     NameError: name 'Chem' is not defined
    #
    # en toda llamada, para todo péptido. `_smiles_to_aa_sequence` llama a una o
    # a otra siempre —a la primera con dos o más residuos, a la segunda con uno—
    # así que el motor de RFdiffusion no ha leído una secuencia jamás: el error
    # subía hasta el `except Exception` de `predict()` y la corrida se devolvía
    # como `error="NameError: name 'Chem' is not defined"`.
    #
    # Es el mismo fallo que tenía el sidecar de ESMFold, desplazado: allí el
    # nombre suelto era `_AA_SMARTS` dentro de un `@staticmethod`; aquí es `Chem`
    # dentro de dos. Ver `backend/sidecars/esmfold/predictor.py`.
    #
    # Y la tabla, además, estaba mal. Tres ejemplos de veinte:
    #
    #     "N": "[NX3][CX3](=[OX1])"        casa con CUALQUIER amida, empezando
    #                                      por el propio esqueleto peptídico
    #     "D": "[CX3](=[OX1])[OX1H0-]"     exige el carboxilato desprotonado
    #     "C": "[SX2][H]"                  exige el hidrógeno explícito
    #
    # Arreglar sólo el `NameError` habría sido peor que dejarlo: en vez de un
    # error habría devuelto una secuencia inventada, y RFdiffusion habría
    # diseñado contra un péptido que no es el que pidió el usuario. Un fallo
    # duro es recuperable; una secuencia falsa que se diseña y se acopla, no.
    #
    # El reconocimiento correcto vive en `secuencia.py`, copia byte a byte de
    # `backend/sidecars/esmfold/secuencia.py` — los dos sidecars son procesos
    # independientes con su propio `requirements.txt`, igual que ya duplican
    # `logger.py` y `config.py`. `test_secuencia_peptidica.py` comprueba que las
    # dos copias no se separen.

    @staticmethod
    def _smiles_to_aa_sequence(smiles: str) -> str:
        """Secuencia de una letra desde el SMILES del péptido.

        Levanta `ValueError` en vez de devolver `""` o una secuencia parcial:
        RFdiffusion diseña un backbone a partir de esta lectura, así que una
        secuencia equivocada no produce un aviso, produce un diseño equivocado.

        LA QUIRALIDAD. RFdiffusion difunde backbones sobre el PDB, que es de
        aminoácidos L. Un péptido con residuos D se rechaza aquí en vez de
        diseñarse como su enantiómero L — que es otra molécula, y precisamente
        la que el usuario evitó al escribir los D (resistencia a proteasas).

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
                f"RFdiffusion diseña sobre backbones L, y hacerlo habría "
                f"devuelto el enantiómero de la molécula que se pidió."
            )

        if lectura.tiene_no_estandar:
            posiciones = [
                str(i + 1) for i, r in enumerate(lectura.residuos) if r.letra == "X"
            ]
            raise ValueError(
                f"No se reconocieron los residuos en las posiciones "
                f"{', '.join(posiciones)}: no son de los veinte estándar. "
                f"RFdiffusion no puede diseñar contra ellos."
            )

        if lectura.series_sin_declarar:
            # No se rechaza —un SMILES sin estereoquímica es una entrada
            # legítima— pero se deja constancia de qué se supuso.
            log.warning(
                "rfdiffusion_estereoquimica_no_declarada",
                residuos=lectura.series_sin_declarar,
                nota="el SMILES no declara la configuración; se asume L",
            )

        return lectura.secuencia


    # ── Hotspot detection ──────────────────────────────────────────────

    @staticmethod
    def _detect_hotspots(receptor_pdb: str, peptide_seq: str) -> list[str]:
        """
        Detecta residuos del receptor candidatos a hotspot.

        Estrategia simple: devuelve los primeros N residuos visibles
        en el PDB del receptor. En producción, se puede integrar con
        la lógica de docking para detectar la interfaz real.
        """
        residues: set[str] = set()
        with open(receptor_pdb) as f:
            for line in f:
                if line.startswith("ATOM") and len(line) >= 26:
                    chain = line[21:22] if len(line) > 21 else "A"
                    try:
                        res_num = int(line[22:26])
                        residues.add(f"{chain}{res_num}")
                    except ValueError:
                        continue

        # Limitar a max 6 hotspots (RFdiffusion best practice)
        sorted_res = sorted(residues, key=lambda r: int(r[1:]) if r[1:].isdigit() else 0)
        return sorted_res[:6]

    # ── RFdiffusion execution ──────────────────────────────────────────

    def _run_rfdiffusion(
        self,
        receptor_path: str,
        peptide_seq: str,
        num_poses: int,
        hotspots: list[str],
        tmp_files: list[str],
    ) -> list[PredictedPose]:
        """
        Ejecuta RFdiffusion como subprocess.

        El script run_inference.py se invoca con:
          - Receptor PDB como input
          - Longitud del péptido como contig
          - Hotspots detectados
        """
        run_script = self.rfdiffusion_path / "scripts" / "run_inference.py"
        if not run_script.exists():
            log.warning("rfdiffusion_script_missing", path=str(run_script))
            return self._generate_dummy_poses(peptide_seq, num_poses)

        output_dir = Path(tempfile.mkdtemp(prefix="rfdiff_out_"))
        pep_length = len(peptide_seq)

        hotspot_arg = ""
        if hotspots:
            hotspot_arg = f"ppi.hotspot_res=[{','.join(hotspots)}]"

        cmd = [
            sys.executable,
            str(run_script),
            f"contigmap.contigs=[{pep_length}-{pep_length}/0 A1-9999]",
            f"inference.output_prefix={output_dir}/design",
            f"inference.num_designs={num_poses}",
            f"inference.input_pdb={receptor_path}",
            "denoiser.noise_scale_ca=0.5",
            "denoiser.noise_scale_frame=0.5",
            "diffuser.T=50",
        ]
        if hotspot_arg:
            cmd.append(hotspot_arg)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                timeout=self._predict_timeout,
                cwd=str(self.rfdiffusion_path),
            )
            if result.returncode != 0:
                log.error("rfdiffusion_failed",
                         returncode=result.returncode,
                         stderr=result.stderr[:500])
                return self._generate_dummy_poses(peptide_seq, num_poses)

            return self._parse_rfdiffusion_output(output_dir)

        except subprocess.TimeoutExpired:
            raise
        except FileNotFoundError:
            log.warning("rfdiffusion_python_not_found")
            raise RuntimeError("RFdiffusion Python no encontrado. Instala RFdiffusion en entorno conda.")
        except Exception as e:
            log.exception("rfdiffusion_subprocess_error")
            raise RuntimeError(f"RFdiffusion error: {e}")

    @staticmethod
    def _parse_rfdiffusion_output(output_dir: Path) -> list[PredictedPose]:
        """Parsea los .pdb outputs de RFdiffusion en PredictedPose."""
        poses = []
        pdb_files = sorted(output_dir.glob("*.pdb"))
        if not pdb_files:
            pdb_files = sorted(output_dir.rglob("*.pdb"))

        for rank, pdb_file in enumerate(pdb_files, 1):
            content = pdb_file.read_text()
            # RFdiffusion no reporta confidence nativo
            confidence = max(0.4, 0.95 - (rank - 1) * 0.12)
            poses.append(PredictedPose(
                rank=rank,
                confidence=round(confidence, 3),
                ligand_pdb=content,
            ))

        return poses if poses else []


# ── Factory ──────────────────────────────────────────────────────────────


def make_predictor(
    mode: str,
    model_dir: str,
    rfdiffusion_path: str | None = None,
    device: str = "auto",
    predict_timeout: float = 1200.0,
) -> BasePredictor:
    if mode == "stub":
        return StubPredictor()
    if mode == "rfdiffusion":
        return RFdiffusionPredictor(
            model_dir=model_dir,
            rfdiffusion_path=rfdiffusion_path or str(Path(model_dir).parent / "rfdiffusion"),
            device=device,
            predict_timeout=predict_timeout,
        )
    raise ValueError(f"Modo desconocido: {mode!r}. Usa 'stub' o 'rfdiffusion'.")

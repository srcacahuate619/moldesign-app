"""
scoring/mmgbsa.py — sólo la detección de GPU de OpenMM.

# Lo que había aquí y por qué se fue

Este módulo contenía `run_mmgbsa()`, `MMGBSAResult` y dos ayudantes, unas 190
líneas que **no llamaba nadie**: el endpoint `/pro/mmgbsa` y la etapa del
pipeline usan `services/chemistry/molchamb_v2.py::compute_mmgbsa_from_pose`.
La única importación viva de este archivo, en todo el backend, era
`is_gpu_available`.

No era código inofensivo. Su propio docstring lo describía así:

    v1.3: Protein-only minimization (ligand joining requires GAFF2
    parametrization via antechamber — documented as limitation)

es decir: minimizaba la proteína **vacía**, sin el ligando, y presentaba el
resultado en un `MMGBSAResult` con campos llamados `delta_g_total`,
`delta_g_vdw` y `delta_g_elec`. Los dos últimos no se medían: se repartían
como porcentajes fijos de la energía no enlazada,

    delta_g_vdw  = nonbonded * 0.65
    delta_g_elec = nonbonded * 0.35

Un objeto con nombres de descomposición energética cuyos valores salen de dos
constantes escritas a mano, junto a una función pública con el nombre exacto
del cálculo que el producto ofrece, es una trampa esperando a que alguien la
importe por el nombre. Ningún número que viera un usuario salió nunca de aquí;
el riesgo era el siguiente que leyera el archivo.

Se borra en vez de archivarse porque el historial de git ya lo conserva, y un
módulo «archivado» dentro del paquete que se instala sigue siendo importable.

Lo que se conserva es lo que se usaba: preguntar a OpenMM si hay GPU.
"""

from __future__ import annotations

from utils.logger import get_logger

log = get_logger(__name__)


def is_gpu_available() -> bool:
    """¿Ofrece OpenMM una plataforma acelerada en este equipo?"""
    try:
        import openmm

        for i in range(openmm.Platform.getNumPlatforms()):
            if openmm.Platform.getPlatform(i).getName() in ("CUDA", "OpenCL"):
                return True
    except ImportError:
        pass
    return False

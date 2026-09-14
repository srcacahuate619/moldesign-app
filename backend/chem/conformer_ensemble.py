"""
Ensemble conformacional: K conformaciones de entrada en vez de una.

# Qué compra, y qué NO compra

El ensemble amplía la **cobertura geométrica**: sube la probabilidad de que
*alguna* de las conformaciones que entran a Vina se parezca a la real. Es lo que
midió MF-33 (26/33).

Lo que NO compra es acierto en el top-1. La medición interna es explícita: la
ventaja del ensemble no llega a la primera pose — el cuello de botella se
desplaza a la SELECCIÓN. Por eso este módulo no se presenta como «modo mejor»
ni se activa por defecto: es un parámetro de protocolo, declarado, con su coste
dicho en voz alta.

# Por qué vive aparte de `chem/conformer.py`

`generate_conformer` es el camino por defecto y el que ha corrido en todas las
evaluaciones existentes. Meterle un parámetro `k` y ramificar por dentro habría
puesto el camino nuevo en la ruta crítica del viejo. Aquí K=1 DELEGA en él
literalmente, así que el protocolo por defecto ejecuta exactamente el mismo
código que antes de que este archivo existiera.

# Determinismo

Las semillas se derivan de un valor base fijo (`SEMILLA_BASE + i * PASO`), como
ya hacía el generador de un solo confórmero. Dos corridas con el mismo SMILES y
el mismo K producen el mismo ensemble, que es lo que permite que el paquete
reproducible siga siéndolo.
"""

from __future__ import annotations

from typing import Any

from utils.file_handlers import StoragePath
from utils.local_storage import write_text
from utils.logger import get_logger

log = get_logger(__name__)

#: Confórmeros por defecto. UNO: el protocolo por defecto no cambia por existir
#: este módulo. El ensemble se pide explícitamente o no ocurre.
CONFORMEROS_POR_DEFECTO = 1

#: Techo duro. Cada confórmero es una corrida completa de Vina, así que K alto
#: multiplica el tiempo de la etapa cara. Un usuario puede pedir menos; no más.
CONFORMEROS_MAXIMO = 64

#: Misma progresión de semillas que el generador de un solo confórmero, para
#: que el primero del ensemble sea el mismo que produciría el camino por defecto.
SEMILLA_BASE = 42
SEMILLA_PASO = 137


def hash_de_conformero(smiles_hash: str, indice: int) -> str:
    """
    Identificador de almacenamiento de la conformación `indice`.

    El índice 0 devuelve el hash REAL, sin sufijo: con K=1 todo —el `.sdf`, el
    `.pdbqt` preparado y la caché de docking— cae exactamente en las mismas
    rutas que antes de que este módulo existiera, así que el protocolo por
    defecto ni siquiera pierde los aciertos de caché que ya tenía.

    Para el resto se deriva `<hash>__cNN`. Es deliberado que sea un sufijo del
    hash y no un directorio aparte: toda la cadena de docking indexa por
    `smiles_hash`, así que derivarlo aísla cada conformación en su propia caché
    sin tocar una sola línea de `vina_service`.
    """
    if indice == 0:
        return smiles_hash
    return f"{smiles_hash}__c{indice:02d}"


def conformer_path_de(smiles_hash: str, indice: int) -> str:
    """Ruta del `.sdf` de la conformación `indice`."""
    return StoragePath.ligand_conformer(hash_de_conformero(smiles_hash, indice))


def normalizar_k(valor: Any) -> int:
    """K efectivo. Un valor imposible cae al defecto, no revienta la corrida."""
    try:
        k = int(valor)
    except (TypeError, ValueError):
        return CONFORMEROS_POR_DEFECTO
    if k < 1:
        return CONFORMEROS_POR_DEFECTO
    return min(k, CONFORMEROS_MAXIMO)


async def generate_conformer_ensemble(
    smiles: str,
    k: Any = CONFORMEROS_POR_DEFECTO,
    ph: float | None = None,
) -> dict:
    """
    Genera K conformaciones y devuelve sus rutas, en orden.

    Returns:
        dict con lo MISMO que `generate_conformer` más:
          conformers: lista de dicts {indice, conformer_path, energia, semilla}
          conformers_requested: K pedido
          conformers_generated: cuántos se consiguieron de verdad
          conformer_warnings: por qué faltan los que faltan

    NUNCA lanza por un confórmero que no embebe: si al menos uno sale, la
    corrida sigue con los que haya y declara la diferencia. Abortar la
    evaluación entera porque la conformación 17 de 30 no convergió sería
    perder 16 conformaciones válidas por una que no lo es.
    """
    from chem.conformer import generate_conformer

    k = normalizar_k(k)

    # ── K = 1: el camino de siempre, sin desviarse ───────────────────
    # El mismo pH que el resto de la corrida: el ensemble varia la
    # CONFORMACION, no la especie protonada.
    base = await generate_conformer(smiles, ph)
    if k == 1:
        return {
            **base,
            "conformers": [{
                "indice": 0,
                "smiles_hash": base["smiles_hash"],
                "conformer_path": base["conformer_path"],
                "energia": None,
                "semilla": SEMILLA_BASE,
            }],
            "conformers_requested": 1,
            "conformers_generated": 1,
            "conformer_warnings": [],
        }

    # ── K > 1: el resto se embebe con semillas derivadas ─────────────
    from rdkit import Chem
    from rdkit.Chem import AllChem

    from chem.conformer import _get_etkdg_params

    smiles_hash = base["smiles_hash"]
    conformeros: list[dict[str, Any]] = [{
        "indice": 0,
        "smiles_hash": base["smiles_hash"],
        "conformer_path": base["conformer_path"],
        "energia": None,
        "semilla": SEMILLA_BASE,
    }]
    avisos: list[str] = []

    # Se parte del SDF que ya se escribió: así el grafo, la protonación y la
    # forma química del ensemble son los MISMOS que los del confórmero 0. Volver
    # a canonicalizar aquí podría producir un ensemble de otra molécula.
    plantilla = None
    try:
        plantilla = Chem.MolFromMolBlock(base.get("sdf_content") or "", removeHs=False)
    except Exception as exc:                                       # noqa: BLE001
        avisos.append(f"no se pudo releer el confórmero base: {type(exc).__name__}")

    if plantilla is None:
        avisos.append(
            "El ensemble no se pudo generar: el confórmero base no se pudo releer. "
            "La corrida sigue con una sola conformación."
        )
        return {
            **base,
            "conformers": conformeros,
            "conformers_requested": k,
            "conformers_generated": 1,
            "conformer_warnings": avisos,
        }

    for indice in range(1, k):
        semilla = SEMILLA_BASE + indice * SEMILLA_PASO
        try:
            copia = Chem.RWMol(plantilla)
            params = _get_etkdg_params(random_seed=semilla)
            if AllChem.EmbedMolecule(copia, params) != 0:
                avisos.append(f"conformación {indice} no embebió (semilla {semilla})")
                continue
            molecula = copia.GetMol()
            energia = None
            try:
                campo = AllChem.MMFFGetMoleculeForceField(
                    molecula, AllChem.MMFFGetMoleculeProperties(molecula)
                )
                if campo is not None:
                    campo.Minimize(maxIts=200)
                    energia = float(campo.CalcEnergy())
            except Exception:                                      # noqa: BLE001
                # Sin minimizar es una conformación peor, no una inválida: entra
                # igual y su energía se declara ausente.
                avisos.append(f"conformación {indice} sin minimizar (MMFF no disponible)")

            ruta = conformer_path_de(smiles_hash, indice)
            await write_text(ruta, Chem.MolToMolBlock(molecula))
            conformeros.append({
                "indice": indice,
                "smiles_hash": hash_de_conformero(smiles_hash, indice),
                "conformer_path": ruta,
                "energia": energia,
                "semilla": semilla,
            })
        except Exception as exc:                                   # noqa: BLE001
            avisos.append(f"conformación {indice} falló: {type(exc).__name__}")

    if len(conformeros) < k:
        avisos.append(
            f"Se pidieron {k} conformaciones y se generaron {len(conformeros)}. "
            f"La cobertura del ensemble es menor que la solicitada."
        )

    log.info(
        "ensemble_conformacional",
        pedidos=k,
        generados=len(conformeros),
        smiles_hash=smiles_hash[:12],
    )
    return {
        **base,
        "conformers": conformeros,
        "conformers_requested": k,
        "conformers_generated": len(conformeros),
        "conformer_warnings": avisos,
    }

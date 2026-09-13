"""
services/docking/preparer.py

Preparación del receptor para AutoDock Vina usando una estrategia explícita:

1. Descargar PDB raw del RCSB si no existe en el almacenamiento local.
2. Filtrar la cadena objetivo y eliminar aguas evidentes.
3. Ejecutar preparación real a PDBQT mediante Meeko si está disponible.

Importante:
Este módulo NO simula preparación química. Si la herramienta necesaria no está
disponible, falla con un error explícito para no introducir falsa ciencia.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

from core.config import get_settings
from core.exceptions import ProteinPreparationError
from utils.file_handlers import (
    StoragePath,
    download_pdb_from_rcsb,
    validate_pdbqt_content,
)
from utils.local_storage import exists, read_text, write_file, write_text
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)

_WATER_RESIDUES = {"HOH", "WAT", "DOD"}

# Residuos HETATM que NUNCA deben incluirse en el receptor.
# Incluye aguas, ligandos comunes co-cristalizados, lípidos y detergentes.
# Si un HETATM no está en esta lista pero tampoco es un aminoácido estándar,
# se excluye igualmente (ver _filter_pdb_content).
_STANDARD_RESIDUES = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    # Variantes comunes de protonación / modificación que Meeko maneja
    "HID", "HIE", "HIP", "CYX", "ASH", "GLH",
    # Residuos modificados frecuentes en cryo-EM
    "MSE",  # selenometionina → tratada como MET
    "SEP", "TPO", "PTR",  # fosfo-residuos
    # Cofactores orgánicos esenciales (grupos prostéticos). Los METALES (ZN,
    # MG, NI...) NO van aquí: se conservan SOLO si el target los declara en
    # su cofactors_whitelist (metaloenzimas), porque un metal cristalográfico
    # accidental (Ni, Pt) rompe meeko ("no covalent radius") y contamina el
    # sitio en targets no-metálicos.
    "HEM", "HEC", "FAD", "NAD", "NAP", "FMN", "ATP", "ADP", "SAM",
    "SF4", "FES", "F3S",  # iron-sulfur clusters
}

# Metales que se conservan SOLO vía cofactors_whitelist (metaloenzimas).
_METAL_COFACTORS = {
    "ZN", "MG", "CA", "MN", "FE", "CU", "CO", "NI", "K", "NA", "CL",
    "AU", "HG", "PT", "CD", "GD", "XE", "KR", "SR", "PB", "IR", "OS",
}


def _resolve_executable(path_or_name: str) -> str | None:
    candidate = Path(path_or_name)
    if candidate.exists():
        return str(candidate)

    found = shutil.which(path_or_name)
    if found:
        return found

    scripts_dir = Path(sys.executable).resolve().parent

    # Try scripts_dir / path_or_name directly (e.g. for files with extensions in the bin/scripts folder)
    direct_candidate = scripts_dir / path_or_name
    if direct_candidate.exists():
        return str(direct_candidate)

    windows_candidate = scripts_dir / f"{path_or_name}.exe"
    if windows_candidate.exists():
        return str(windows_candidate)

    py_candidate = scripts_dir / f"{path_or_name}.py"
    if py_candidate.exists():
        return str(py_candidate)

    # En modo DESKTOP o cuando usamos python -m, el script esta dentro
    # de site-packages. Verificamos que el modulo se puede importar.
    if path_or_name in ("mk_prepare_receptor.py", "mk_prepare_receptor"):
        import importlib.util
        if importlib.util.find_spec("meeko.cli.mk_prepare_receptor"):
            return "mk_prepare_receptor.py"  # dummy, se usa python -m

    # Buscar en site-packages del usuario (Windows: AppData\Roaming\Python)
    try:
        import site
        user_site = site.getusersitepackages()
        if user_site:
            candidate = Path(user_site) / path_or_name
            if candidate.exists():
                return str(candidate)
    except Exception:
        pass

    return None


def _convert_mse_to_met(line: str) -> str | None:
    """Convierte un HETATM de selenometionina (MSE) a metionina (MET).

    RDKit no tiene radio covalente para Se, por lo que Meeko falla con
    "Element Se doesn't have an implemented covalent radius". La práctica
    estándar en preparación de receptores es convertir MSE → MET:
      - Residuo:  MSE → MET
      - Átomo SE  → SD, elemento SE → S  (el S de la metionina)

    Conserva la geometría y el esqueleto; solo cambia el nombre/átomo.
    Devuelve None si la línea no es convertible (no debería ocurrir).
    """
    try:
        if len(line) < 78:
            return None
        # Nombre de residuo (cols 18-20, 1-indexed → 17:20 en 0-indexed)
        new = line[:17] + "MET" + line[20:]
        # Átomo SE (cols 13-16 → 12:16) → SD; elemento SE (cols 77-78 → 76:78) → S
        atom_name = new[12:16]
        element = new[76:78].strip()
        if element == "SE":
            new = new[:76] + "S "
        if " SE" in new[12:16]:
            new = new[:12] + new[12:16].replace(" SE", " SD") + new[16:]
        return new
    except Exception:
        return None


def _filter_pdb_content(
    pdb_content: str,
    chain_id: str | set[str] | list[str] | tuple[str, ...],
    keep_hetatm: bool = False,
    cofactors_whitelist: list[str] | None = None,
) -> str:
    """
    Filtra la(s) cadena(s) de interés para preparación del receptor.

    `chain_id` admite una cadena o un conjunto de ellas. **Varias no significa
    "el oligómero entero"**: cuando el sitio de unión se forma ENTRE cadenas
    —la proteasa del VIH es el caso de libro—, conservar una sola deja al ligando
    acoplando contra media cavidad (doc 71, modo de fallo C). Quien pasa un
    conjunto es `prepare_target` en modo multicadena, y allí este filtro va
    SIEMPRE seguido de un recorte al sitio: sin ese recorte se reintroduciría el
    receptor de 10 MB que la v1.6 eliminó.

    Estrategia de filtrado (ortodoxo para docking molecular):
    1. Solo conserva la(s) cadena(s) especificada(s) (auth chain ID, col. 22).
    2. Elimina aguas (HOH, WAT, DOD).
    3. Por defecto, elimina TODOS los registros HETATM — ligandos co-cristalizados,
       colesterol, detergentes, iones, etc. NO deben estar en el receptor.
    4. Solo conserva ATOM records (aminoácidos estándar de la proteína).

    Si keep_hetatm=True, conserva HETATM que sean residuos estándar modificados
    (MSE, SEP, TPO, PTR) que Meeko sabe reconvertir. Esto es útil para
    proteínas con selenometioninas de cristalografía.

    Justificación científica:
    - En docking rígido contra un GPCR, el receptor debe contener SOLO la proteína.
    - Incluir ligandos co-cristalizados (ej. serotonina en 7E2Y) contamina el
      binding site y produce afinidades artificiales.
    - Incluir colesterol/lípidos de la membrana crea una envolvente no fisiológica.
    - Meeko (mk_prepare_receptor) añade hidrógenos polares y cargas Gasteiger
      solo a residuos proteicos reconocidos.

    Referencia: Morris et al. (2009) J Comput Chem 30:2785-2791.
    """
    cadenas = ({chain_id.strip()} if isinstance(chain_id, str)
               else {str(c).strip() for c in chain_id})
    etiqueta_cadena = "+".join(sorted(cadenas))

    filtered_lines: list[str] = []
    excluded_hetatm: dict[str, int] = {}  # residue_name → count (para logging)

    # ── v1.8.1: Resolución de altlocs ──────────────────────────────────────
    # Algunos PDBs (ej. 5NN5, 6FBQ, 5TY1) contienen residuos con dos
    # conformaciones alternativas (altloc A/B/C) donde ciertos átomos solo
    # existen en una variante. Meeko falla con "Requested altlocs not found"
    # porque no puede reconstruir el residuo con conformaciones mezcladas.
    # Estrategia ortodoxa (pdb-tools/OpenBabel/obabel):
    #   1. Agrupar átomos ATOM/HETATM por (chain, resSeq, resName).
    #   2. Por residuo, elegir la variante altloc que tenga MÁS átomos.
    #   3. Conservar solo esa variante (o sin altloc si es la mayoritaria).
    _residue_atoms: dict[tuple, list[tuple]] = {}
    for line in pdb_content.splitlines():
        record = line[:6].strip()
        if record not in {"ATOM", "HETATM"}:
            continue
        try:
            altloc = line[16:17]
            res_name = line[17:20].strip()
            chain = line[21:22].strip() or "A"
            res_seq_raw = line[22:26].strip()
            res_seq = int(res_seq_raw) if res_seq_raw.strip().lstrip("-").isdigit() else 0
        except Exception:
            continue
        key = (chain, res_seq, res_name)
        variant = altloc or " "
        _residue_atoms.setdefault(key, []).append((variant, line))

    # Elegir la variante mayoritaria por residuo
    _chosen_altloc: dict[tuple, str] = {}
    for key, entries in _residue_atoms.items():
        counts: dict[str, int] = {}
        for variant, _ in entries:
            counts[variant] = counts.get(variant, 0) + 1
        # Variante sin altloc ( " " ) es la preferida si existe; si no, la más común
        if counts.get(" ", 0) >= max(counts.values()):
            chosen = " "
        else:
            chosen = max(counts, key=lambda v: (counts[v], v == " "))
        _chosen_altloc[key] = chosen
    # ────────────────────────────────────────────────────────────────────────

    for line in pdb_content.splitlines():
        record = line[:6].strip()
        if record not in {"ATOM", "HETATM", "TER", "END", "MODEL", "ENDMDL"}:
            continue

        if record in {"TER", "END", "MODEL", "ENDMDL"}:
            filtered_lines.append(line)
            continue

        residue_name = line[17:20].strip()
        current_chain = line[21].strip() or "A"

        residue_seq_raw = line[22:26].strip()
        try:
            residue_seq = int(residue_seq_raw)
        except ValueError:
            residue_seq = 0

        # --- Filtros básicos ---
        if residue_name in _WATER_RESIDUES:
            continue
        if current_chain not in cadenas:
            continue
        if residue_seq <= 0:
            continue

        # --- v1.8.1: Descartar átomos de la variante altloc no elegida ---
        # Si el residuo tiene altlocs, conservar SOLO la variante mayoritaria.
        # Sin esto, Meeko no puede armar residuos con conformaciones mezcladas
        # (fallo "Requested altlocs not found for: [...]" en 5NN5, 6FBQ, etc).
        if record in {"ATOM", "HETATM"}:
            try:
                altloc_variant = line[16:17]
            except IndexError:
                altloc_variant = " "
            chosen = _chosen_altloc.get((current_chain, residue_seq, residue_name), " ")
            if altloc_variant != chosen:
                continue

        # --- Filtro de HETATM: eliminar ligandos, lípidos, retener cofactores ---
        if record == "HETATM":
            is_metal = residue_name in _METAL_COFACTORS
            # v1.8.1: Selenometionina (MSE) → MET. El átomo SE no tiene radio
            # covalente en RDKit ("Element Se doesn't have an implemented
            # covalent radius") y rompe Meeko. La práctica estándar es
            # convertir la selenometionina a metionina (SE → SD, elemento S),
            # que Meeko sí parametriza. Se pierde el Se pero el esqueleto
            # proteico queda íntegro para docking rígido.
            if residue_name == "MSE":
                new_line = _convert_mse_to_met(line)
                if new_line:
                    filtered_lines.append(new_line)
                    continue
            if keep_hetatm and not is_metal and residue_name in _STANDARD_RESIDUES:
                # Residuo modificado reconocible (MSE, SEP, etc.) → conservar
                filtered_lines.append(line)
            elif cofactors_whitelist and (residue_name in cofactors_whitelist
                                          or (is_metal and residue_name in cofactors_whitelist)):
                # Cofactor orgánico o metal específico del receptor (whitelist
                # explícito del target) → conservar. Un metal NO whitelisted
                # se excluye (evita romper meeko en targets no-metálicos).
                filtered_lines.append(line)
            else:
                # Ligando, colesterol, solvente genérico, metal accidental → excluir
                excluded_hetatm[residue_name] = excluded_hetatm.get(residue_name, 0) + 1
            continue

        # ATOM records (aminoácidos estándar) → siempre conservar
        filtered_lines.append(line)

    # Logging de lo que se excluyó para trazabilidad
    if excluded_hetatm:
        log.info(
            "HETATM excluidos de la preparación del receptor",
            chain=etiqueta_cadena,
            excluded=excluded_hetatm,
            total_excluded=sum(excluded_hetatm.values()),
        )

    atom_count = sum(1 for l in filtered_lines if l.startswith("ATOM"))
    if atom_count == 0:
        raise ProteinPreparationError(
            pdb_id="unknown",
            step="chain_filtering",
            detail=(
                f"No quedaron átomos ATOM tras filtrar la cadena '{etiqueta_cadena}' "
                f"(HETATM excluidos: {excluded_hetatm or 'ninguno'}). "
                "Verifica el chain ID objetivo."
            ),
        )

    log.info(
        "PDB filtrado para preparación",
        chain=etiqueta_cadena,
        atom_records=atom_count,
        hetatm_excluded=sum(excluded_hetatm.values()),
    )

    return "\n".join(filtered_lines) + "\n"


def _recortar_al_sitio(
    filtered_content: str,
    *,
    pdb_id: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    cadenas: list[str],
) -> str:
    """Recorta un receptor multicadena al sitio, sin salir de memoria.

    Encadena `services/chemistry/protein_surgery.trim_to_pocket`, que ya está en
    producción para MM-GBSA y para la ventana de ProLIF, y que tiene las dos
    propiedades que hacen falta aquí: es **agnóstico a la cadena** —indexa por
    `(chain, resnum, inscode)`, así que conserva residuos de todas— y **nunca
    corta a mitad de residuo**, sin lo cual Meeko recibiría fragmentos de cadena
    principal y produciría basura.

    El radio NO es un parámetro: lo deriva `radio_para_caja` de la caja de este
    objetivo, de modo que ningún átomo que el ligando pueda tocar desde dentro
    de la caja se quede fuera del receptor. Ver su docstring para la medida.

    **El recorte es un paso de preparación, nunca una mutación del activo.** Se
    escribe en un temporal propio y el crudo del almacén no se toca; el receptor
    completo tiene que seguir intacto para el flujo de «crear variante», que
    parte de él.
    """
    from services.chemistry.protein_surgery import trim_to_pocket
    from services.docking.preparer_multichain import radio_para_caja

    radio = radio_para_caja(tuple(float(v) for v in size))
    atomos = [l for l in filtered_content.splitlines() if l.startswith(("ATOM", "HETATM"))]
    antes = len(atomos)

    # ── Cuantos atomos hay de verdad dentro del radio ───────────────────────
    #
    # Se mide AQUI y no se deduce del booleano de `trim_to_pocket`, porque ese
    # booleano es `n_kept > 0 and n_kept < n_total` y por tanto vale `False` en
    # DOS situaciones opuestas: cuando no hay nada cerca del centro -un defecto
    # real- y cuando TODO el receptor cabe dentro del radio, que no tiene nada
    # de malo. Confundirlas tumbaba la preparacion de los receptores pequeños:
    # 1C6X -proteasa del VIH, 1514 atomos, el centro exactamente sobre el
    # centroide de su ligando co-cristalizado y la cadena mas cercana a 4 Å-
    # moria con un mensaje que acusaba a la caja de estar mal.
    cx, cy, cz = (float(v) for v in center)
    dentro = 0
    for linea in atomos:
        try:
            dx = float(linea[30:38]) - cx
            dy = float(linea[38:46]) - cy
            dz = float(linea[46:54]) - cz
        except ValueError:
            continue
        if dx * dx + dy * dy + dz * dz <= radio * radio:
            dentro += 1
    if dentro == 0:
        raise ProteinPreparationError(
            pdb_id=pdb_id,
            step="trim_to_pocket",
            detail=(
                f"El centro {tuple(center)} no tiene ningún átomo de las cadenas "
                f"{'+'.join(cadenas)} a {radio:.1f} Å. O el centro del sitio está mal, "
                "o no corresponde a esta estructura. No se prepara un receptor a ciegas."
            ),
        )

    # `ignore_cleanup_errors`: en Windows no se puede borrar un archivo que
    # alguien tenga abierto, y aqui dentro corren procesos hijos -Meeko, Vina,
    # Open Babel- mas el antivirus escaneando lo recien escrito. Sin esto, la
    # limpieza puede levantar PermissionError DESPUES de que el trabajo haya
    # terminado bien, y tirar una corrida completa por no poder borrar un
    # temporal. Dejar un archivo suelto es mucho mejor que perder el resultado.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True, dir=settings.vina_temp_dir) as tmp:
        entrada = Path(tmp) / f"{pdb_id}_multicadena.pdb"
        salida = Path(tmp) / f"{pdb_id}_sitio.pdb"
        entrada.write_text(filtered_content, encoding="utf-8")
        # El segundo valor -«se recorto algo»- se ignora a proposito: vale
        # `False` tanto si no habia nada cerca del centro como si el receptor
        # entero cabia dentro del radio. Lo que decide ya se midio arriba.
        ruta, _ = trim_to_pocket(
            str(entrada), tuple(float(v) for v in center),
            radius=radio, output_pdb=str(salida),
            # SIN caps. PDBFixer reescribe el PDB por la topologia de OpenMM y
            # renombra las cadenas: sobre 6SX5 fundia A y su copia de simetria D
            # en una sola, y el receptor perdia media cavidad en silencio. Los
            # caps existen para MM-GBSA, donde un terminal roto falsea la
            # energia; aqui rompen la identidad de cadena de la que depende todo
            # lo demas.
            apply_caps=False,
        )
        contenido = Path(ruta).read_text(encoding="utf-8", errors="replace")

    despues = len([l for l in contenido.splitlines() if l.startswith(("ATOM", "HETATM"))])
    if despues == 0:
        # No deberia ocurrir habiendo atomos dentro del radio, pero un receptor
        # vacio es exactamente lo que Vina acoplaria contra el vacio sin
        # protestar.
        raise ProteinPreparationError(
            pdb_id=pdb_id,
            step="trim_to_pocket",
            detail=(
                f"El recorte al sitio dejó el receptor sin átomos pese a haber {dentro} "
                f"dentro de {radio:.1f} Å del centro."
            ),
        )
    conservadas = sorted({l[21].strip() for l in contenido.splitlines()
                          if l.startswith(("ATOM", "HETATM")) and len(l) > 21})
    log.info(
        "receptor_multicadena_recortado",
        pdb_id=pdb_id, radio_A=round(radio, 1), cadenas_pedidas=cadenas,
        cadenas_conservadas=conservadas, atomos_antes=antes, atomos_despues=despues,
        atomos_dentro_del_radio=dentro,
    )
    return contenido


def get_target_pdb_path(pdb_id: str) -> str:
    """Resuelve la ruta local al archivo PDB del target.
    
    Prioridad:
      1. Bundle del instalador: data/targets/{pdb_id}.pdb (offline, pre-cargado)
         o dentro de data/target_library/{area_key}/{pdb_id}.pdb
      2. ~MolDesign/data/targets/{pdb_id}.pdb (descargado/cacheado)
    """
    pdb_id_clean = pdb_id.strip()

    # 1. Bundle directory (ships with installer, highest priority)
    root_dir = Path(__file__).resolve().parent.parent.parent.parent

    # 1a. Standard target path
    bundle = root_dir / "data" / "targets" / f"{pdb_id_clean}.pdb"
    if bundle.exists():
        return str(bundle)

    # 1b. Search target_library subdirectories recursively
    library_dir = root_dir / "data" / "target_library"
    if library_dir.exists():
        for sub in library_dir.glob(f"**/{pdb_id_clean}.pdb"):
            if sub.exists():
                return str(sub)
        for sub in library_dir.glob(f"**/{pdb_id_clean.upper()}.pdb"):
            if sub.exists():
                return str(sub)
        for sub in library_dir.glob(f"**/{pdb_id_clean.lower()}.pdb"):
            if sub.exists():
                return str(sub)

    # 2. Cache del escritorio.
    local = Path(settings.local_data_dir) / "targets" / f"{pdb_id_clean}.pdb"
    if local.exists():
        return str(local)

    # Fallback search in local data dir recursively in case they are there.
    local_dir = Path(settings.local_data_dir)
    for sub in local_dir.glob(f"**/targets/**/{pdb_id_clean}*"):
        if sub.suffix.lower() == ".pdb" and sub.exists():
            return str(sub)

    # Return the path even if it doesn't exist yet (will be downloaded on demand).
    return str(local)


def prepared_receptor_chains(pdbqt_content: str) -> set[str]:
    """Devuelve las cadenas proteicas declaradas por un receptor PDBQT.

    El cache histórico de receptores se indexa sólo por PDB ID. Por eso esta
    comprobación no es decorativa: evita reutilizar, por ejemplo, una cadena R
    cuando la corrida solicitó la A. Los registros sin cadena no se convierten
    en ``A``; una ausencia de procedencia no demuestra compatibilidad.
    """

    chains: set[str] = set()
    for line in pdbqt_content.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        if len(line) > 21:
            chain = line[21:22].strip()
            if chain:
                chains.add(chain)
    return chains


def prepared_receptor_matches_chain(
    pdbqt_content: str,
    chain_id: str | set[str] | list[str] | tuple[str, ...],
) -> bool:
    """Indica si un PDBQT cacheado representa exactamente las cadenas pedidas.

    Es lo que impide servir un receptor de una sola cadena a una corrida que pide
    el sitio multicadena, y al revés. El modo se deriva del catálogo, así que un
    cambio de anotación tiene que invalidar la caché sin que nadie se acuerde de
    borrarla: aquí se acuerda.
    """
    pedidas = ({chain_id.strip()} if isinstance(chain_id, str)
               else {str(c).strip() for c in chain_id})
    return prepared_receptor_chains(pdbqt_content) == pedidas


def derive_dynamic_box(filtered_pdb_content: str) -> dict[str, object] | None:
    """Deriva la caja dinámica con el algoritmo vivo usado por producción.

    Se recibe el PDB *ya filtrado* para que preflight, preparación y Vina
    resuelvan exactamente el mismo artefacto. No ejecuta Meeko ni docking.
    """

    try:
        from services.chemistry.protein_surgery import compute_dynamic_box

        Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            suffix=".pdb",
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=settings.vina_temp_dir,
        ) as handle:
            handle.write(filtered_pdb_content)
            pdb_path = Path(handle.name)
        try:
            result = compute_dynamic_box(ligand_mol2=None, pdb_path=str(pdb_path))
        finally:
            pdb_path.unlink(missing_ok=True)
    except Exception as exc:
        log.warning("auto_box_derivation_failed", error=str(exc))
        return None

    center = tuple(float(value) for value in result.get("center", (0.0, 0.0, 0.0)))
    if center == (0.0, 0.0, 0.0):
        return None
    size = float(result["size"])
    return {
        "center": center,
        "size": size,
        "source": str(result.get("source", "unknown")),
    }


def resolve_effective_docking_box(
    *,
    pdb_id: str,
    chain_id: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Resuelve la caja que deben recibir tanto Meeko como Vina.

    Antes la caja dinámica se calculaba dentro de :func:`prepare_target`, pero
    ese valor local no regresaba al caller y Vina seguía recibiendo ``(0,0,0)``.
    Esta función hace explícita la resolución para que no existan dos cajas en
    una misma corrida.
    """

    normalized_center = tuple(float(value) for value in center)
    normalized_size = tuple(float(value) for value in size)
    if normalized_center != (0.0, 0.0, 0.0):
        return normalized_center, normalized_size

    source_path = Path(get_target_pdb_path(pdb_id))
    if not source_path.exists():
        raise ProteinPreparationError(
            pdb_id=pdb_id,
            step="dynamic_box_source",
            detail="No existe el PDB fuente necesario para derivar la caja de docking.",
        )
    source_content = source_path.read_text(encoding="utf-8", errors="replace")
    filtered_content = _filter_pdb_content(
        source_content,
        chain_id=chain_id,
        keep_hetatm=True,
        cofactors_whitelist=None,
    )
    derived = derive_dynamic_box(filtered_content)
    if derived is None:
        raise ProteinPreparationError(
            pdb_id=pdb_id,
            step="dynamic_box_derivation",
            detail=(
                "La caja no está definida y no pudo derivarse del receptor filtrado. "
                "La corrida se detiene antes de enviar un centro (0,0,0) a Vina."
            ),
        )
    derived_center = tuple(derived["center"])
    derived_size = float(derived["size"])
    return derived_center, (derived_size, derived_size, derived_size)


async def prepare_target(
    pdb_id: str,
    chain_id: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    force_reprepare: bool = False,
    cofactors_whitelist: list[str] | None = None,
    site_chains: list[str] | None = None,
) -> str:
    """
    Prepara un receptor para Vina y lo guarda en el almacenamiento local.

    Args:
        chain_id: la cadena que el catálogo declara. Sigue mandando cuando el
            sitio lo forma una sola.
        site_chains: las cadenas que FORMAN el sitio, medidas sobre el PDB del
            RCSB (`curated_targets.json:site_chains`). Con dos o más se prepara
            en **modo multicadena**: se conservan todas y después se recorta al
            sitio. Sin esto, `preparer` conservaría sólo `chain_id` y el ligando
            acoplaría contra media cavidad — el modo de fallo C del doc 71, con
            la proteasa del VIH como caso de libro.

    **El modo se DERIVA de `site_chains`; no hay un interruptor que ponga nadie.**
    Una política congelada en la tabla obligaría a reanotar 385 filas el día que
    cambie el umbral, y nadie sabría con qué criterio se puso cada una.

    Retorna la ruta lógica del archivo `.pdbqt` (resuelve a disco bajo
    settings.local_data_dir).
    """
    pdb_id = pdb_id.upper()

    # Las cadenas a conservar. `site_chains` con una sola —o ausente— deja el
    # comportamiento histórico intacto, byte a byte.
    cadenas_del_sitio = [c.strip() for c in (site_chains or []) if c and c.strip()]
    multicadena = len(set(cadenas_del_sitio)) > 1
    cadenas = set(cadenas_del_sitio) if multicadena else {chain_id.strip()}
    prepared_path = StoragePath.target_prepared(pdb_id)
    raw_path = StoragePath.target_raw(pdb_id)

    # La copia que consume el rescoring. `get_target_pdb_path` puede resolverla
    # al directorio del programa -de solo lectura en una instalacion-, asi que
    # la que este modulo escribe es SIEMPRE la del almacenamiento del usuario.
    # En produccion son la misma ruta: el bundle viaja en gzip y las dos ramas
    # anteriores de esa funcion no encuentran nada.
    shared_pdb_path = Path(get_target_pdb_path(pdb_id))
    compartido_local = Path(settings.local_data_dir) / "targets" / f"{pdb_id}.pdb"
    cadenas_compartidas = (
        prepared_receptor_chains(shared_pdb_path.read_text(encoding="utf-8", errors="replace"))
        if shared_pdb_path.exists()
        else set()
    )
    # Pendiente = falta, o le falta una cadena del sitio Y es nuestra, la del
    # usuario. Una copia del bundle a la que le falte algo no se toca: no se
    # puede escribir ahi, y colgar de eso el camino rapido dejaria a esta
    # maquina -donde `target_library` resuelve catorce de los quince- volviendo
    # a preparar el receptor en cada corrida.
    copia_pendiente = not shared_pdb_path.exists() or (
        not cadenas <= cadenas_compartidas and shared_pdb_path == compartido_local
    )

    # ── El camino rapido ────────────────────────────────────────────────────
    #
    # Es el de CADA acoplamiento a partir del segundo, asi que va antes de leer
    # y ensamblar el receptor: nada de eso hace falta para devolver un `.pdbqt`
    # que ya esta en disco y declara las cadenas pedidas.
    if not force_reprepare and not copia_pendiente and await exists(prepared_path):
        prepared_content = await read_text(prepared_path)
        if prepared_receptor_matches_chain(prepared_content, cadenas):
            return prepared_path
        log.warning(
            "prepared_receptor_chain_mismatch",
            pdb_id=pdb_id,
            requested_chain=sorted(cadenas),
            cached_chains=sorted(prepared_receptor_chains(prepared_content)),
            action="reprepare",
        )

    # ── El origen: el crudo depositado, y su unidad biologica ───────────────
    #
    # Un PDB deposita la unidad ASIMETRICA. Cuando el ensamblaje tiene simetria
    # interna que coincide con la del cristal, eso es solo una fraccion del
    # receptor y el resto se reconstruye con las matrices BIOMT del REMARK 350.
    #
    # Medido sobre el catalogo: 31 objetivos tenian atomos que faltaban DENTRO
    # de su caja de docking, y diez superaban el 40%. NavAb (5VB8) llegaba al
    # 80,5%: la caja apuntaba al eje del poro y tres cuartas partes de su pared
    # no existian en el archivo.
    #
    # EL ORIGEN ES SIEMPRE EL CRUDO DEPOSITADO cuando existe -el instalador lo
    # siembra para los 380 objetivos-. La copia compartida esta filtrada por
    # cadena y NO conserva los REMARK: leerla como origen borraba el ensamblaje,
    # y con el las cadenas que solo existen dentro de el. En esta maquina el
    # defecto no se veia porque `data/target_library` -que NO viaja en el
    # instalador- adelantaba una estructura completa; en una instalacion limpia,
    # 5VA1 preparaba la cadena A sola con el sitio declarado en A+B.
    from services.semilla_estructuras import sembrar_una

    if await exists(raw_path):
        origen = await read_text(raw_path)
    elif shared_pdb_path.exists():
        # Biblioteca offline precargada: no hay crudo depositado del que partir.
        origen = shared_pdb_path.read_text(encoding="utf-8", errors="replace")
    elif sembrar_una(pdb_id) is not None:
        # La estructura viaja en el instalador y la siembra del arranque -que
        # copia las 407 en un hilo de fondo- aun no habia llegado a ella. Ir al
        # RCSB aqui seria pedir RED para un receptor que ya esta en el disco.
        origen = await read_text(raw_path)
    else:
        origen = await download_pdb_from_rcsb(pdb_id)
        await write_text(raw_path, origen)

    # Va ANTES del filtro de cadena a proposito: las copias generadas traen
    # identificadores nuevos y `site_chains` -que se mide sobre el mismo
    # ensamblaje- ya los nombra. Cuando no hay nada que generar la funcion
    # devuelve la entrada intacta, que es el caso de 341 de los 380.
    from services.chemistry.ensamblaje_biologico import generar_unidad_biologica

    raw_content = generar_unidad_biologica(origen, pdb_id=pdb_id).pdb

    # --- Asegurar PDB en volumen compartido para Rescoring ---
    #
    # Se escribe DESDE el ensamblaje, no desde el archivo depositado: si el
    # rescoring puntuara sobre un receptor distinto del que acopla, la segunda
    # opinion no seria una segunda opinion. Y una copia anterior a la que le
    # falte una cadena del sitio se reescribe: es de antes de generar la unidad
    # biologica y describe media cavidad.
    if copia_pendiente:
        log.info(
            "asegurando_pdb_para_rescoring",
            pdb_id=pdb_id,
            existia=shared_pdb_path.exists(),
            cadenas_previas=sorted(cadenas_compartidas),
            cadenas_pedidas=sorted(cadenas),
        )
        compartido_local.parent.mkdir(parents=True, exist_ok=True)
        compartido_local.write_text(
            _filter_pdb_content(
                raw_content,
                chain_id=cadenas,
                keep_hetatm=True,
                cofactors_whitelist=cofactors_whitelist,
            ),
            encoding="utf-8",
        )
        log.info("pdb_persisted_for_rescoring", path=str(compartido_local))

    prepare_receptor_cmd = _resolve_executable(settings.meeko_prepare_receptor_path)
    if not prepare_receptor_cmd:
        raise ProteinPreparationError(
            pdb_id=pdb_id,
            step="prepare_receptor_executable",
            detail=(
                "No se encontró 'mk_prepare_receptor.py'. Instala Meeko o provee "
                "la ruta correcta en MEEKO_PREPARE_RECEPTOR_PATH. Sin esta herramienta "
                "no es científicamente defendible preparar el receptor para Vina."
            ),
        )

    try:
        filtered_content = _filter_pdb_content(
            raw_content,
            cadenas,
            keep_hetatm=True,  # v1.8: Conservar cofactores (metales, grupos prostéticos) para docking realista
            cofactors_whitelist=cofactors_whitelist,
        )
        if multicadena:
            # El recorte al sitio NO es opcional aquí: conservar los oligómeros
            # enteros reintroduciría los receptores de 5 y 10 MB que la v1.6
            # eliminó. `trim_to_pocket` es agnóstico a la cadena y nunca corta a
            # mitad de residuo, que son las dos propiedades que hacen falta.
            filtered_content = _recortar_al_sitio(
                filtered_content, pdb_id=pdb_id, center=center, size=size,
                cadenas=sorted(cadenas),
            )
            # Que falte una cadena del sitio NO puede seguir adelante. El
            # receptor quedaria con media cavidad y Vina devolveria una
            # afinidad igualmente: es el modo de fallo C del doc 71, y no
            # dispara ninguna alarma porque el numero sale con la misma cara
            # que uno bueno. Antes esto solo se veia en una linea de log.
            conservadas = prepared_receptor_chains(filtered_content)
            if conservadas != cadenas:
                raise ProteinPreparationError(
                    pdb_id=pdb_id,
                    step="site_chains_missing",
                    detail=(
                        f"El sitio se forma entre {sorted(cadenas)} y el receptor "
                        f"preparado solo contendria {sorted(conservadas)}. Se detiene "
                        "antes de acoplar contra media cavidad."
                    ),
                )
    except ProteinPreparationError as e:
        e.pdb_id = pdb_id
        raise

    Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)

    # `ignore_cleanup_errors`: en Windows no se puede borrar un archivo que
    # alguien tenga abierto, y aqui dentro corren procesos hijos -Meeko, Vina,
    # Open Babel- mas el antivirus escaneando lo recien escrito. Sin esto, la
    # limpieza puede levantar PermissionError DESPUES de que el trabajo haya
    # terminado bien, y tirar una corrida completa por no poder borrar un
    # temporal. Dejar un archivo suelto es mucho mejor que perder el resultado.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True, dir=settings.vina_temp_dir) as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        input_pdb = tmp_dir_path / f"{pdb_id}_{chain_id}.pdb"
        output_basename = tmp_dir_path / f"{pdb_id}_{chain_id}_prepared"

        input_pdb.write_text(filtered_content, encoding="utf-8")

        # ── [Bucket B] Dynamic box fallback ────────────────────────────────
        # If the caller did not specify a real center (origin sentinel),
        # derive one at runtime from the PDB's HETATM/protein atoms using the
        # same algorithm that scripts/recalibrate_all_386_targets.py applied
        # offline to the curated database.  Keeps the historical centers
        # consistent with on-the-fly preparation of new PDBs.
        if center == (0.0, 0.0, 0.0) or center == (0, 0, 0):
            derived = derive_dynamic_box(filtered_content)
            if derived is None:
                raise ProteinPreparationError(
                    pdb_id=pdb_id,
                    step="dynamic_box_derivation",
                    detail=(
                        "La caja no está definida y no pudo derivarse del receptor filtrado. "
                        "No se ejecutará Meeko con un centro (0,0,0)."
                    ),
                )
            center = tuple(derived["center"])
            derived_size_value = float(derived["size"])
            size = (derived_size_value, derived_size_value, derived_size_value)
            log.info(
                "auto_box_derived",
                pdb_id=pdb_id,
                center=center,
                size=derived_size_value,
                source=derived["source"],
            )
        # ────────────────────────────────────────────────────────────────

        center_x, center_y, center_z = center
        size_x, size_y, size_z = size


        # Usar exactamente el intérprete del backend instalado por el launcher.
        conda_python = sys.executable
        command = [
            conda_python,
            "-m", "meeko.cli.mk_prepare_receptor",
            "--read_pdb", str(input_pdb),
            "-o", str(output_basename),
            "-p",
            "-v",
            "-a",
            "--default_altloc", settings.meeko_default_altloc,
            "--box_size", str(size_x), str(size_y), str(size_z),
            "--box_center", str(center_x), str(center_y), str(center_z),
        ]

        log.debug(
            "Invocando mk_prepare_receptor.py",
            command=command,
            input_pdb=str(input_pdb),
            output_basename=str(output_basename),
            cwd=str(tmp_dir_path),
        )

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(tmp_dir_path),
        )
        stdout, stderr = await process.communicate()

        # ── v1.8.1: Degradación por glicanos / residuos no-templated ────────
        # Glicoproteínas (5NN5: NAG/FUC/MAN/BMA; 6MEO, 7CM4) rompen Meeko con
        # "Template generation failed for unknown residues". La recomendación
        # oficial de Meeko es --delete_residues para ignorarlos. Si la primera
        # pasada falla por residuos desconocidos, reintentamos eliminándolos
        # en vez de abortar la evaluación con un error crudo.
        if process.returncode != 0:
            stderr_txt = stderr.decode("utf-8", errors="replace")
            stdout_txt = stdout.decode("utf-8", errors="replace")
            # ⚠️ Meeko escribe el error FATAL ("Error: Creation of data structure
            # failed. Details: Requested altlocs not found...") en STDOUT, y los
            # warnings de templates en STDERR. Debemos revisar AMBOS para
            # detectar los casos de glicanos/altlocs/Se.
            combined = stderr_txt + "\n" + stdout_txt
            # Glicanos comunes que Meeko no parametriza y que NUNCA deben
            # estar en el receptor (azúcares de superficie, no del sitio activo).
            _GLYCAN_RESIDUES = ("NAG", "FUC", "BMA", "MAN", "GAL", "SIA", "BGC", "GLC")
            # Parsear residuos problemáticos del stderr/stdout (altlocs, unknown templates)
            problematic: list[str] = []
            import re as _re
            for m in _re.finditer(r"(['\"])([A-Za-z]):(\d+)\1", combined):
                chain, seq = m.group(2), m.group(3)
                res_id = f"{chain}:{seq}"
                if res_id not in problematic:
                    problematic.append(res_id)

            if any(m in combined for m in ("unknown residues", "Template generation failed",
                                              "doesn't have an implemented covalent radius",
                                              "Requested altlocs not found")):
                log.warning(
                    "mk_prepare_receptor_fallback_delete_residues",
                    pdb_id=pdb_id,
                    reason="glycan_or_altloc_or_unusual_residue",
                    detail=combined[-400:],
                    problematic=problematic[:20],
                )
                # Reintento con --delete_residues: elimina glicanos y residuos
                # problemáticos que Meeko no parametriza (NAG/FUC/MAN/BMA,
                # selenometioninas, altlocs rotos).
                retry_command = [a for a in command if a != "-a"]
                if problematic:
                    retry_command += ["--delete_residues", ",".join(problematic[:30])]
                else:
                    retry_command += ["--delete_residues", ",".join(_GLYCAN_RESIDUES)]
                try:
                    process2 = await asyncio.create_subprocess_exec(
                        *retry_command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(tmp_dir_path),
                    )
                    stdout2, stderr2 = await process2.communicate()
                except Exception as retry_err:
                    log.error("mk_prepare_receptor_retry_spawn_failed", pdb_id=pdb_id, error=str(retry_err))
                    stdout2, stderr2 = b"", b""
                    process2 = None

                if process2 is not None and process2.returncode == 0:
                    log.info("receptor preparado con degradación por glicanos", pdb_id=pdb_id, chain="+".join(sorted(cadenas)))
                    stdout, stderr = stdout2, stderr2
                    process = process2
                else:
                    stderr_txt2 = (stderr2 or b"").decode("utf-8", errors="replace")
                    stdout_txt2 = (stdout2 or b"").decode("utf-8", errors="replace")
                    log.error(
                        "mk_prepare_receptor_retry_tambien_fallo",
                        pdb_id=pdb_id,
                        stderr=stderr_txt2[-300:],
                        stdout=stdout_txt2[-300:],
                    )
                    raise ProteinPreparationError(
                        pdb_id=pdb_id,
                        step="mk_prepare_receptor_glycan_fallback",
                        detail=f"STDERR(1): {stderr_txt[-400:]}\nSTDOUT(1): {stdout_txt[-400:]}\nSTDERR(2): {stderr_txt2[-400:]}\nSTDOUT(2): {stdout_txt2[-400:]}\nCMD: {' '.join(command)}",
                    )

        if process.returncode != 0:
            log.error(
                "mk_prepare_receptor.py falló",
                returncode=process.returncode,
                stderr=stderr.decode("utf-8", errors="replace"),
                stdout=stdout.decode("utf-8", errors="replace"),
                command=command,
            )
            raise ProteinPreparationError(
                pdb_id=pdb_id,
                step="mk_prepare_receptor",
                detail=f"STDERR: {stderr.decode('utf-8', errors='replace')}\nSTDOUT: {stdout.decode('utf-8', errors='replace')}\nCMD: {' '.join(command)}",
            )

        output_pdbqt = Path(f"{output_basename}.pdbqt")
        if not output_pdbqt.exists():
            raise ProteinPreparationError(
                pdb_id=pdb_id,
                step="mk_prepare_receptor_output",
                detail="La preparación terminó sin generar el archivo receptor .pdbqt esperado.",
            )

        content = output_pdbqt.read_text(encoding="utf-8", errors="replace")
        is_valid, validation_error = validate_pdbqt_content(content)
        if not is_valid:
            raise ProteinPreparationError(
                pdb_id=pdb_id,
                step="validate_pdbqt",
                detail=validation_error,
            )

        # --- Validación de calidad del PDBQT resultante ---
        pdbqt_atom_count = sum(1 for l in content.splitlines() if l.startswith(("ATOM", "HETATM")))
        pdbqt_has_charges = any(
            len(l) >= 77 and l[70:77].strip() not in ("", "0.000")
            for l in content.splitlines()
            if l.startswith(("ATOM", "HETATM"))
        )

        if pdbqt_atom_count < 500:
            log.warning(
                "PDBQT tiene pocos átomos — puede indicar preparación incompleta",
                pdb_id=pdb_id,
                atom_count=pdbqt_atom_count,
                expected_min=2000,
            )

        log.info(
            "receptor PDBQT validado",
            pdb_id=pdb_id,
            chain="+".join(sorted(cadenas)),
            pdbqt_atoms=pdbqt_atom_count,
            has_gasteiger_charges=pdbqt_has_charges,
        )

        await write_file(output_pdbqt, prepared_path)

    log.info("receptor preparado para Vina", pdb_id=pdb_id, chain="+".join(sorted(cadenas)),
             multicadena=multicadena, path=prepared_path)
    return prepared_path


# ── Alias públicos para inspección (preflight) ───────────────────────
#
# El preflight NO puede tener su propia copia de la política de filtrado: si la
# tuviera, describiría una preparación que no es la que se ejecuta, que es
# exactamente el defecto que documenta docs/53 §6.2. Estos alias existen para
# que `preflight.py` use LA MISMA función y LAS MISMAS listas, sin tocar nada
# privado y sin duplicar una sola regla.
#
# Van al final del módulo a propósito: son referencias a objetos ya definidos.

filter_pdb_content = _filter_pdb_content
resolve_executable = _resolve_executable
WATER_RESIDUES = _WATER_RESIDUES
METAL_COFACTORS = _METAL_COFACTORS
STANDARD_RESIDUES = _STANDARD_RESIDUES

#: Cofactores orgánicos que sobreviven al filtro sin necesidad de whitelist.
#: Es `STANDARD_RESIDUES` menos los aminoácidos, sus variantes de protonación y
#: los residuos modificados — es decir, la lista positiva REAL del producto.
#: `docs/53 §6.2` la audita: no incluye UDP ni GSH. Se DERIVA de la constante
#: viva en vez de copiarse, para que no pueda quedar desincronizada.
_AMINO_ACIDS_AND_VARIANTS = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    "HID", "HIE", "HIP", "CYX", "ASH", "GLH",
    "MSE", "SEP", "TPO", "PTR",
}
ORGANIC_COFACTORS_KEPT = frozenset(_STANDARD_RESIDUES - _AMINO_ACIDS_AND_VARIANTS)

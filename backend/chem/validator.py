"""
chem/validator.py

Validación química de SMILES usando RDKit.

Este es el primer módulo del pipeline científico — nada pasa
al siguiente paso sin pasar primero por aquí.

Hay dos niveles de validación:

1. Validación estructural (errores fatales → is_valid=False):
   - SMILES no parseable por RDKit
   - Valencia inválida (carbono con 5 enlaces, etc.)
   - Anillos no cerrados
   - Átomos desconocidos

2. Validación de scope (warnings → is_valid=True pero con advertencias):
   - Molécula fuera del alcance por tamaño (ver `chem/regimenes.py`)
   - Molécula demasiado pequeña (< 5 átomos pesados)
   - Presencia de metales (docking con Vina no es confiable)
   - Fragmentos desconectados (mezclas, sales)

Por qué canonicalizar el SMILES:
   "CCO", "OCC", y "C(C)O" son el mismo etanol pero strings distintos.
   RDKit produce un SMILES canónico único para cada molécula.
   Todo el sistema trabaja con el canónico para que el cache y
   la detección de duplicados funcionen correctamente.
"""

import hashlib
from dataclasses import dataclass, field

from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import Descriptors, rdMolDescriptors, SaltRemover
from rdkit.Chem.rdchem import Mol

from core.config import get_settings
from core.exceptions import InvalidSMILES
from core.models import ValidationResult
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# Silencia los logs internos de RDKit — son muy verbosos y van a stderr.
# Los errores importantes los capturamos nosotros en el try/except.
RDLogger.DisableLog("rdApp.*")


# ── Átomos que Vina no maneja bien ───────────────────────────────────────────

# AutoDock Vina tiene parámetros de fuerza para átomos orgánicos comunes.
# Metales y elementos exóticos causan que Vina falle silenciosamente
# o produzca scores incorrectos.
_VINA_UNSUPPORTED_ATOMS = {
    # Metales de transición
    "Fe", "Cu", "Zn", "Mn", "Co", "Ni", "Cr", "V", "Ti", "Mo", "W",
    # Metales alcalinos/alcalinotérreos
    "Li", "Na", "K", "Mg", "Ca", "Ba",
    # Otros problemáticos
    "Si", "B", "Al", "Sn", "Pb", "As", "Se", "Te",
}

# Elementos válidos para drug-like molecules
_ALLOWED_ATOMS = {
    "C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "H",
}


# ── Resultado interno de validación ──────────────────────────────────────────

@dataclass
class _ValidationState:
    """
    Estado interno acumulado durante la validación.
    Se convierte a ValidationResult al final.
    """
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mol: Mol | None = None
    canonical_smiles: str | None = None
    smiles_hash: str | None = None
    heavy_atom_count: int | None = None
    molecular_formula: str | None = None
    #: Regimen de tamano (chem/regimenes.py). Lo fija `_check_size`.
    clasificacion: object | None = None

    def add_error(self, msg: str) -> None:
        self.is_valid = False
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


# ── Funciones de validación individuales ─────────────────────────────────────

def _parse_smiles(smiles: str, state: _ValidationState) -> None:
    """
    Paso 1: intenta parsear el SMILES con RDKit.

    RDKit retorna None (sin lanzar excepción) si el SMILES es inválido.
    La sanitización completa valida valencia, aromaticidad y estructura.
    """
    if not smiles or not smiles.strip():
        state.add_error("El SMILES no puede estar vacío")
        return

    mol = Chem.MolFromSmiles(smiles.strip(), sanitize=False)

    if mol is None:
        state.add_error(
            f"RDKit no puede parsear el SMILES '{smiles[:50]}'. "
            "Verifica la sintaxis: átomos entre corchetes [], "
            "anillos cerrados con números, aromaticidad con minúsculas."
        )
        return

    # Sanitización completa: valida valencia, aromaticidad, estereoquímica
    try:
        Chem.SanitizeMol(mol)
    except Chem.AtomValenceException as e:
        state.add_error(
            f"Valencia inválida: {e}. "
            "Ejemplo: carbono sp3 solo puede tener 4 enlaces."
        )
        return
    except Chem.KekulizeException:
        state.add_error(
            "No se puede kekulizar la molécula. "
            "El sistema aromático definido no es válido."
        )
        return
    except Exception as e:
        state.add_error(f"Error de sanitización: {str(e)}")
        return

    state.mol = mol


def _check_atoms(state: _ValidationState) -> None:
    """
    Paso 2: verifica que todos los átomos son compatibles con Vina.

    No bloqueamos moléculas con átomos problemáticos (is_valid sigue True)
    pero sí advertimos al usuario que el docking puede ser poco confiable.
    """
    if state.mol is None:
        return

    atoms_in_mol = {atom.GetSymbol() for atom in state.mol.GetAtoms()}

    # Átomos no soportados por Vina
    unsupported = atoms_in_mol & _VINA_UNSUPPORTED_ATOMS
    if unsupported:
        message = (
            f"La molécula contiene {sorted(unsupported)} — "
            "AutoDock Vina no tiene parámetros confiables para estos elementos."
        )
        if settings.strict_science_mode:
            state.add_error(message)
            return
        state.add_warning(f"{message} El score de docking puede ser impreciso.")

    # Átomos completamente desconocidos (ni en allowed ni en unsupported)
    unknown = atoms_in_mol - _ALLOWED_ATOMS - _VINA_UNSUPPORTED_ATOMS - {"*"}
    if unknown:
        message = f"Átomos no soportados detectados: {sorted(unknown)}."
        if settings.strict_science_mode:
            state.add_error(message)
            return
        state.add_warning(f"{message} Verifica que la molécula sea drug-like.")


def _check_chemical_plausibility(state: _ValidationState) -> None:
    """
    Paso adicional: reglas de plausibilidad química para evitar estructuras
    con alta probabilidad de ser no defendibles para el pipeline.
    """
    if state.mol is None or not state.is_valid:
        return

    total_formal_charge = 0
    for atom in state.mol.GetAtoms():
        atom_charge = atom.GetFormalCharge()
        total_formal_charge += atom_charge

        if abs(atom_charge) > settings.max_atom_formal_charge_abs:
            state.add_error(
                f"Carga formal atómica extrema ({atom.GetSymbol()}={atom_charge}). "
                f"Máximo permitido: ±{settings.max_atom_formal_charge_abs}."
            )
            return

        if atom.GetNumRadicalElectrons() > 0:
            state.add_error(
                "Se detectaron electrones radicales; el pipeline actual no acepta radicales "
                "por baja defendibilidad en docking estándar."
            )
            return

    if abs(total_formal_charge) > settings.max_total_formal_charge_abs:
        state.add_error(
            f"Carga formal neta extrema ({total_formal_charge}). "
            f"Máximo permitido: ±{settings.max_total_formal_charge_abs}."
        )
        return

    # v1.5: Detectar estereocentros no asignados (elige enantiomero arbitrario)
    unassigned = Chem.FindMolChiralCenters(state.mol, includeUnassigned=True)
    unassigned = [(i, tag) for i, tag in unassigned if tag == "?"]
    if unassigned:
        state.add_warning(
            f"Se detectaron {len(unassigned)} estereocentro(s) sin estereoquimica definida. "
            "RDKit elegira un enantiomero arbitrario para el docking 3D. "
            "Usa '@' o '@@' en el SMILES para especificar la quiralidad deseada."
        )


def _check_size(state: _ValidationState) -> None:
    """
    Paso 3: verifica que el tamaño de la molécula está en rango razonable.

    Moléculas muy pequeñas (< 5 átomos): no son drug-like, scores sin sentido.
    Moléculas muy grandes (> max_heavy_atoms): el docking es computacionalmente
    prohibitivo y los resultados de Vina son poco confiables.
    """
    if state.mol is None or not state.is_valid:
        return

    heavy_atoms = state.mol.GetNumHeavyAtoms()
    state.heavy_atom_count = heavy_atoms

    if heavy_atoms < 5:
        state.add_error(
            f"La molécula tiene solo {heavy_atoms} átomo(s) pesado(s). "
            "El mínimo para evaluación farmacológica es 5."
        )
        return

    # ═══════════════════════════════════════════════════════════════════
    # EL TECHO LO PONE LA LITERATURA, NO ESTE PROYECTO
    # ═══════════════════════════════════════════════════════════════════
    #
    # Aquí había `heavy_atoms > settings.mol_max_heavy_atoms` con un máximo de
    # 80, y más abajo un aviso de MW por encima de 800 Da. Ninguno de los dos
    # números corresponde a un criterio publicado: eran umbrales propios
    # decidiendo qué entra al producto y cuál es el mensaje.
    #
    # Ahora la frontera es la de la química medicinal —Rule of Five, bRo5y el
    # rango de átomos de Ghose— y vive en `chem/regimenes.py` con su
    # referencia. Ver ese módulo para las citas y para la conversión medida
    # entre masa y átomos pesados.
    from chem.regimenes import clasificar

    peso = Descriptors.MolWt(state.mol)
    clasificacion = clasificar(peso, heavy_atoms)
    state.clasificacion = clasificacion

    if clasificacion.bloquea:
        state.add_error(
            f"{clasificacion.etiqueta}: {peso:.0f} Da y {heavy_atoms} átomos "
            f"pesados. {clasificacion.criterio}. {clasificacion.implicacion}"
        )
        return

    if clasificacion.regimen.value == "bro5":
        state.add_warning(
            f"{clasificacion.etiqueta} ({peso:.0f} Da). {clasificacion.criterio}. "
            f"{clasificacion.implicacion}"
        )

    if clasificacion.discrepancia:
        state.add_warning(clasificacion.discrepancia)


def _check_molecular_weight(state: _ValidationState) -> None:
    """
    Paso 4: verifica que el peso molecular está en rango drug-like.

    El techo lo decide `_check_size` con los regímenes publicados
    (`chem/regimenes.py`). Aquí sólo queda el extremo bajo, citado a Ghose.
    """
    if state.mol is None or not state.is_valid:
        return

    mw = Descriptors.MolWt(state.mol)

    # El techo lo decide `_check_size` con los regímenes publicados. Aquí sólo
    # queda el extremo BAJO, y con la cita de la única regla implementada que
    # lo define: Ghose et al. 1999 empieza en 160 Da y 20 átomos pesados. Por
    # debajo de ahí ninguno de los filtros de drug-likeness del producto
    # (Lipinski, Veber, Ghose, Egan, Muegge) está evaluando lo que dice
    # evaluar, y eso se declara en vez de compararlo con un mínimo propio de
    # 100 Da que no salía de ninguna parte.
    from chem.properties import GhoseRule

    if mw < GhoseRule.MW_RANGE[0]:
        state.add_warning(
            f"Masa molecular por debajo del rango de las reglas de "
            f"drug-likeness ({mw:.1f} Da). El filtro de Ghose et al. 1999 "
            f"empieza en {GhoseRule.MW_RANGE[0]:.0f} Da y {GhoseRule.ATOM_RANGE[0]} "
            "átomos pesados: a este tamaño esos filtros, y los umbrales de "
            "eficiencia de ligando, no están evaluando lo que dicen evaluar. "
            "El acoplamiento se ejecuta igual."
        )


def _check_fragments(state: _ValidationState) -> None:
    """
    Paso 5: detecta moléculas desconectadas (sales, mezclas).

    Un SMILES como "CC.OCC" representa dos fragmentos separados.
    Vina no puede dockar una mezcla — solo trabaja con una molécula.
    Advertimos al usuario para que use el fragmento principal.
    """
    if state.mol is None or not state.is_valid:
        return

    fragments = Chem.GetMolFrags(state.mol)
    if len(fragments) > 1:
        if settings.strict_single_fragment_only:
            state.add_error(
                f"La molécula contiene {len(fragments)} fragmentos desconectados. "
                "En modo científico estricto se rechazan sales/mezclas para evitar "
                "ambigüedad en docking y scoring."
            )
            return

        state.add_warning(
            f"La molécula tiene {len(fragments)} fragmentos desconectados "
            "(posiblemente una sal o mezcla). "
            "Solo se evaluará el fragmento más grande. "
            "Considera usar únicamente la parte activa."
        )
        # Automáticamente seleccionamos el fragmento más grande
        largest = max(
            Chem.GetMolFrags(state.mol, asMols=True),
            key=lambda m: m.GetNumHeavyAtoms(),
        )
        state.mol = largest
        # Actualizar heavy_atom_count tras selección de fragmento
        state.heavy_atom_count = largest.GetNumHeavyAtoms()
        state.add_warning(
            f"Usando fragmento de {largest.GetNumHeavyAtoms()} átomos "
            "para la evaluación."
        )

def _desalinate_and_clean_fragments(state: _ValidationState) -> None:
    """
    Realiza la desalinización automática (contraion stripping) y
    selección del fragmento principal (en caso de mezclas o solventes).
    """
    if state.mol is None or not state.is_valid:
        return

    # 1. Aplicar SaltRemover de RDKit
    try:
        remover = SaltRemover.SaltRemover()
        stripped = remover.StripMol(state.mol)
    except Exception as e:
        log.warning("Error en SaltRemover, continuando con la molécula original", error=str(e))
        stripped = state.mol

    # Si se removió todo (ej. entrada era solo sal/contraiones inorgánicos),
    # conservar la molécula original para que los siguientes validadores reporten el error apropiadamente
    if stripped is None or stripped.GetNumAtoms() == 0:
        stripped = state.mol

    # Verificar si hubo cambios por desalinización
    was_desalinated = stripped.GetNumAtoms() < state.mol.GetNumAtoms()

    # 2. Manejar múltiples fragmentos si quedan después de la desalinización
    fragments = Chem.GetMolFrags(stripped, asMols=True)
    if len(fragments) > 1:
        if settings.strict_single_fragment_only:
            state.add_error(
                f"La molécula contiene {len(fragments)} fragmentos desconectados. "
                "En modo científico estricto se rechazan sales/mezclas para evitar "
                "ambigüedad en docking y scoring."
            )
            return

        # Seleccionar el fragmento más grande por número de átomos pesados
        largest = max(fragments, key=lambda m: m.GetNumHeavyAtoms())

        # Verificar si la desalinización ocurrió y reportar advertencias
        if was_desalinated:
            state.add_warning(
                "La molécula contiene contraiones/sales que fueron removidos automáticamente. "
                f"Adicionalmente, se detectaron múltiples fragmentos y se seleccionó el fragmento orgánico más grande "
                f"de {largest.GetNumHeavyAtoms()} átomos pesados."
            )
        else:
            state.add_warning(
                f"La molécula contiene {len(fragments)} fragmentos desconectados (posiblemente una sal o mezcla). "
                f"Se seleccionó el fragmento más grande de {largest.GetNumHeavyAtoms()} átomos pesados "
                "para la evaluación."
            )
        state.mol = largest
    else:
        if was_desalinated:
            state.add_warning(
                "La molécula contiene contraiones/sales que fueron removidos automáticamente (desalinización)."
            )
        state.mol = stripped

    # Actualizar el heavy atom count inicial
    state.heavy_atom_count = state.mol.GetNumHeavyAtoms()


def _canonicalize(state: _ValidationState) -> None:
    """
    Paso 6: genera el SMILES canónico y su hash SHA-256.

    El SMILES canónico es la representación estándar de RDKit:
    única, determinista, y reproducible en cualquier instalación de RDKit.

    El hash SHA-256 del canónico es la identidad de la molécula en el sistema:
    - Key del estado efímero local
    - Identificador de duplicados en SQLite
    - Lo que se registra en Solana (no el SMILES raw del usuario)
    """
    if state.mol is None or not state.is_valid:
        return

    canonical = Chem.MolToSmiles(state.mol, canonical=True)
    state.canonical_smiles = canonical

    # SHA-256 del canónico en UTF-8
    state.smiles_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # Fórmula molecular (ej. "C9H8O4" para aspirina)
    state.molecular_formula = rdMolDescriptors.CalcMolFormula(state.mol)

    log.debug(
        "SMILES canonicalizado",
        canonical=canonical,
        formula=state.molecular_formula,
        hash_prefix=state.smiles_hash[:8],
    )


# ── Función principal de validación ──────────────────────────────────────────

def validate_smiles(smiles: str) -> ValidationResult:
    """
    Valida un SMILES y retorna un ValidationResult completo.

    Esta es la única función que los módulos externos deben llamar.
    Los pasos internos (_parse_smiles, _check_atoms, etc.) son
    detalles de implementación.

    El resultado siempre es un ValidationResult — nunca lanza excepción.
    Si quieres que lance excepción en caso de error, usa
    validate_smiles_or_raise().

    Ejemplo:
        result = validate_smiles("CC(=O)Oc1ccccc1C(=O)O")
        if not result.is_valid:
            print(result.errors)
        else:
            print(result.canonical_smiles)  # SMILES canónico de la aspirina
    """
    log.debug("iniciando validación de SMILES", smiles_preview=smiles[:30])

    state = _ValidationState()

    # Pipeline de validación en orden — cada paso puede agregar
    # errores/warnings y modificar state.mol
    _parse_smiles(smiles, state)

    # Los pasos siguientes solo corren si el parseo fue exitoso
    if state.is_valid and state.mol is not None:
        _desalinate_and_clean_fragments(state)
        if state.is_valid and state.mol is not None:
            _check_atoms(state)
            _check_chemical_plausibility(state)
            _check_size(state)
            _check_molecular_weight(state)
            # _check_fragments ya cubierto por _desalinate_and_clean_fragments (linea 442)
            _canonicalize(state)

    result = ValidationResult(
        is_valid=state.is_valid,
        canonical_smiles=state.canonical_smiles,
        smiles_hash=state.smiles_hash,
        errors=state.errors,
        warnings=state.warnings,
        heavy_atom_count=state.heavy_atom_count,
        molecular_formula=state.molecular_formula,
        # El régimen viaja con el resultado: decide para qué está calibrado el
        # resto del pipeline, y recalcularlo en cada consumidor invita a que
        # dos partes usen fronteras distintas.
        regimen=state.clasificacion.regimen.value if state.clasificacion else None,
        regimen_etiqueta=state.clasificacion.etiqueta if state.clasificacion else None,
        regimen_criterio=state.clasificacion.criterio if state.clasificacion else None,
        cumple_ro3=state.clasificacion.cumple_ro3 if state.clasificacion else None,
    )

    if result.is_valid:
        log.info(
            "SMILES válido",
            formula=result.molecular_formula,
            heavy_atoms=result.heavy_atom_count,
            warnings=len(result.warnings),
            hash_prefix=result.smiles_hash[:8] if result.smiles_hash else None,
        )
    else:
        log.warning(
            "SMILES inválido",
            smiles_preview=smiles[:30],
            errors=result.errors,
        )

    return result


def validate_smiles_or_raise(smiles: str) -> ValidationResult:
    """
    Valida un SMILES y lanza InvalidSMILES si no es válido.

    Úsalo en los routers de FastAPI donde una molécula inválida
    debe cortar el flujo inmediatamente con HTTP 422.

    Uso en chem/router.py:
        result = validate_smiles_or_raise(data.smiles)
        # Si llegamos aquí, result.is_valid == True garantizado
        return result
    """
    result = validate_smiles(smiles)

    if not result.is_valid:
        # Tomamos el primer error como razón principal
        primary_error = result.errors[0] if result.errors else "SMILES inválido"
        raise InvalidSMILES(
            smiles=smiles,
            reason=primary_error,
            detail="; ".join(result.errors[1:]) if len(result.errors) > 1 else None,
        )

    return result


# ── Utilidades adicionales ────────────────────────────────────────────────────

def smiles_to_canonical(smiles: str) -> str:
    """
    Convierte un SMILES a su forma canónica.

    Versión simplificada para uso interno cuando ya sabes que el
    SMILES es válido (ej. al recuperar de la DB).
    Lanza ValueError si el SMILES no es válido.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"SMILES inválido: {smiles}")
    return Chem.MolToSmiles(mol, canonical=True)


def smiles_to_hash(smiles: str) -> str:
    """
    Retorna el hash SHA-256 del SMILES desalinado y canónico.

    La desalinización asegura que "CCO.Cl" y "CCO" produzcan el mismo hash,
    evitando dockings duplicados en la DB (ver auditoría Julio 2026).
    """
    from rdkit.Chem import MolFromSmiles, MolToSmiles, GetMolFrags
    from rdkit.Chem.SaltRemover import SaltRemover

    mol = MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"SMILES inválido: {smiles}")

    # Desalinar: remover contraiones (Cl, Na, etc.)
    remover = SaltRemover()
    stripped = remover.StripMol(mol)
    if stripped is None or stripped.GetNumAtoms() == 0:
        stripped = mol

    # Si quedan múltiples fragmentos, tomar el más grande
    frags = GetMolFrags(stripped, asMols=True)
    if len(frags) > 1:
        stripped = max(frags, key=lambda m: m.GetNumHeavyAtoms())

    canonical = MolToSmiles(stripped, canonical=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def are_same_molecule(smiles_a: str, smiles_b: str) -> bool:
    """
    Compara dos SMILES para determinar si representan la misma molécula.

    Más confiable que comparar strings directamente porque dos SMILES
    distintos pueden representar la misma estructura.

    Uso en db/repository.py para detectar duplicados:
        if are_same_molecule(new_smiles, existing.smiles):
            return existing  # devuelve el resultado ya calculado
    """
    try:
        return smiles_to_hash(smiles_a) == smiles_to_hash(smiles_b)
    except ValueError:
        return False

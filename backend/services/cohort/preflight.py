"""
Comprobación previa de una cohorte. Pura, determinista, sin efectos.

# Qué hace y qué NO hace

Lee el archivo, normaliza cada fila contra el vocabulario del contrato, decide
si la cohorte puede ejecutarse y firma su identidad. **No** ejecuta docking, no
llama a ML, GNN, MolGraph, PoseBusters ni a ningún servicio externo, no lanza
tareas de fondo, no guarda nada y no calcula ningún score.

Tampoco calcula EF, ROC-AUC ni enriquecimiento. Podría —hay etiquetas `active`—
y sería exactamente el error: un enriquecimiento antes de ejecutar mide el
archivo, no el cribado.

# Qué significa `eligible`

Que la fila **puede entrar en la corrida común de esta cohorte**: la estructura
se lee y el validador del producto la acepta para evaluación. Nada más.

No significa que la molécula se una al receptor, ni que sea un buen fármaco, ni
que la cohorte vaya a producir un resultado interpretable. Superar la
comprobación previa no es evidencia de nada científico: es la condición mínima
para empezar a producirla.

# Las dos formas de no ser elegible, separadas a propósito

    SMILES_ILEGIBLE       RDKit no puede leer la estructura → arregla el texto
    SMILES_NO_ADMISIBLE   se lee, y la política química del producto la rechaza
                          para evaluación → la molécula está bien escrita y este
                          producto no la evalúa

Colapsarlas en «inválida» le diría a alguien que su SMILES está mal escrito
cuando lo que pasa es que su molécula es demasiado pequeña para el pipeline.

# Determinismo

Con la misma entrada, la misma salida — salvo `generated_at`, que es lo único
que depende del reloj y por eso está fuera del fingerprint.
"""

from __future__ import annotations

from datetime import datetime, timezone

from services.cohort.fingerprint import FingerprintRow, cohort_fingerprint
from services.cohort.parser import ParsedFile, RawRow, read_cohort_file
from services.cohort.schemas import (
    CohortPreflightResult,
    CohortRow,
    CohortStudy,
    CohortSummary,
)
from services.cohort.taxonomy import (
    CAJA_NO_DECLARADA,
    COHORTE_VACIA,
    CONTROL_ROLES,
    DUPLICADOS_CANONICOS,
    ELIGIBLE,
    ETIQUETA_ACTIVE_INVALIDA,
    FILAS_INVALIDAS,
    INVALID_INPUT,
    MOLECULA_CON_AVISOS_QUIMICOS,
    NOMBRE_AUSENTE,
    ROL_CONTROL_INVALIDO,
    ROLE_NONE,
    SEMILLA_NO_DECLARADA,
    SIN_CONTROLES_DECLARADOS,
    SIN_ETIQUETAS_ACTIVE,
    SIN_MOLECULAS_ELEGIBLES,
    SMILES_AUSENTE,
    SMILES_DUPLICADO,
    SMILES_ILEGIBLE,
    SMILES_NO_ADMISIBLE,
    VALIDADOR_NO_DISPONIBLE,
    decide,
)

#: Vocabulario de la etiqueta `active`. Lista blanca: cualquier otra cosa es una
#: etiqueta que no se entiende, y se declara como tal en vez de adivinarla.
_ACTIVE_TRUE = frozenset({"1", "true", "yes", "y", "si", "sí", "active", "activo"})
_ACTIVE_FALSE = frozenset({"0", "false", "no", "n", "inactive", "inactivo"})


def _rdkit_disponible() -> bool:
    try:
        from rdkit import Chem  # noqa: F401
    except ImportError:
        return False
    return True


def _interpretar_active(raw: str | None) -> tuple[bool | None, tuple[str, ...]]:
    """Etiqueta binaria, o ausencia declarada. Nunca un valor por defecto."""
    if raw is None:
        return None, ()
    valor = raw.strip().lower()
    if not valor:
        return None, ()
    if valor in _ACTIVE_TRUE:
        return True, ()
    if valor in _ACTIVE_FALSE:
        return False, ()
    return None, (ETIQUETA_ACTIVE_INVALIDA,)


def _interpretar_rol(raw: str | None) -> tuple[str, tuple[str, ...]]:
    """
    Papel de control declarado. Sin inferencia de ningún tipo.

    Un valor fuera del vocabulario NO se aproxima al más parecido: cae a `none`
    con aviso. «reference_compound» podría querer decir `reference`, y
    suponerlo convertiría una errata en un control que nadie declaró.
    """
    if raw is None:
        return ROLE_NONE, ()
    valor = raw.strip().lower()
    if not valor:
        return ROLE_NONE, ()
    if valor in CONTROL_ROLES:
        return valor, ()
    return ROLE_NONE, (ROL_CONTROL_INVALIDO,)


def _evaluar_molecula(smiles: str) -> tuple[str | None, str | None, tuple[str, ...]]:
    """
    Canónico, razón de rechazo y avisos químicos de UN SMILES.

    Dos pasos deliberadamente separados:

    1. **¿Se lee?** `Chem.MolFromSmiles`. Si no, `SMILES_ILEGIBLE` y no hay
       canónico que enseñar.
    2. **¿La evalúa este producto?** `validate_smiles`, el MISMO validador que
       usa `/evaluation/submit`. Si dijera que sí aquí y que no allí, la
       comprobación previa no comprobaría nada.

    El canónico se devuelve aunque el paso 2 rechace: sirve para que el lector
    vea de qué molécula se habla y para detectar duplicados.
    """
    from chem.validator import validate_smiles
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    try:
        mol = Chem.MolFromSmiles(smiles)
    except Exception:
        mol = None
    finally:
        RDLogger.EnableLog("rdApp.*")

    if mol is None:
        return None, SMILES_ILEGIBLE, ()

    canonico = Chem.MolToSmiles(mol)
    resultado = validate_smiles(smiles)
    avisos = (MOLECULA_CON_AVISOS_QUIMICOS,) if resultado.warnings else ()
    if not resultado.is_valid:
        return canonico, SMILES_NO_ADMISIBLE, avisos
    return (resultado.canonical_smiles or canonico), None, avisos


def _normalizar_fila(raw: RawRow, *, validador: bool) -> CohortRow:
    """Una fila cruda pasa a fila declarada. Ninguna se pierde por el camino."""
    razones: list[str] = list(raw.reasons)
    avisos: list[str] = list(raw.warnings)

    activo, avisos_activo = _interpretar_active(raw.active_raw)
    avisos.extend(avisos_activo)
    rol, avisos_rol = _interpretar_rol(raw.control_role_raw)
    avisos.extend(avisos_rol)

    if raw.source_name is None:
        avisos.append(NOMBRE_AUSENTE)

    smiles = raw.input_smiles.strip()
    canonico: str | None = None

    if razones:
        # La ingesta ya la invalidó (registro corrupto). No se vuelve a
        # diagnosticar: se respeta lo que dijo quien leyó el archivo.
        pass
    elif not smiles:
        razones.append(SMILES_AUSENTE)
    elif not validador:
        # Sin RDKit no se puede afirmar nada sobre la molécula. La fila NO se
        # marca ilegible —no lo sabemos— y el bloqueante de la cohorte explica
        # por qué no hay veredicto.
        pass
    else:
        canonico, razon, avisos_quimicos = _evaluar_molecula(smiles)
        if razon:
            razones.append(razon)
        avisos.extend(avisos_quimicos)

    elegible = validador and not razones
    return CohortRow(
        row_index=raw.row_index,
        source_name=raw.source_name,
        input_smiles=smiles,
        canonical_smiles=canonico,
        eligibility=ELIGIBLE if elegible else INVALID_INPUT,
        reasons=razones,
        warnings=avisos,
        active_label=activo,
        control_role=rol,
    )


def _marcar_duplicados(rows: list[CohortRow]) -> int:
    """
    Señala cada repetición con la PRIMERA fila equivalente.

    Se mira sobre todas las filas que tienen canónico, elegibles o no: una fila
    que el producto no evalúa sigue siendo la misma molécula que otra, y ocultar
    esa coincidencia dejaría al lector creyendo que su cohorte tiene más
    diversidad de la que tiene.

    Lo que NO se hace es excluirlas. Qué peso llevan en las métricas es una
    decisión de 5B; tomarla aquí, en silencio, cambiaría el denominador de todo
    lo que venga después.
    """
    primera: dict[str, int] = {}
    duplicadas = 0
    for indice, fila in enumerate(rows):
        canonico = fila.canonical_smiles
        if not canonico:
            continue
        if canonico in primera:
            duplicadas += 1
            rows[indice] = fila.model_copy(
                update={
                    "duplicate_of_row": primera[canonico],
                    "warnings": [*fila.warnings, SMILES_DUPLICADO],
                }
            )
        else:
            primera[canonico] = fila.row_index
    return duplicadas


def _resumen(rows: list[CohortRow], duplicadas: int) -> CohortSummary:
    total = len(rows)
    elegibles = [fila for fila in rows if fila.eligibility == ELIGIBLE]
    unicos = {fila.canonical_smiles for fila in elegibles if fila.canonical_smiles}

    def _controles(rol: str) -> int:
        return sum(1 for fila in elegibles if fila.control_role == rol)

    # Cobertura: `null` sin denominador. `0.0` afirmaría un 0 % medido, y no se
    # ha medido nada; NaN o ±Infinity no serían siquiera JSON válido.
    cobertura = round(len(elegibles) / total, 6) if total else None

    return CohortSummary(
        total_rows=total,
        eligible_rows=len(elegibles),
        invalid_rows=total - len(elegibles),
        unique_canonical_ligands=len(unicos),
        duplicate_rows=duplicadas,
        explicit_reference_controls=_controles("reference"),
        explicit_positive_controls=_controles("positive"),
        explicit_negative_controls=_controles("negative"),
        input_coverage=cobertura,
        input_coverage_denominator=total,
    )


def _avisos_de_cohorte(study: CohortStudy, summary: CohortSummary) -> list[str]:
    """Avisos de cohorte. Ninguno bloquea; si bloqueara, sería un bloqueante."""
    avisos: list[str] = []
    if summary.invalid_rows:
        avisos.append(FILAS_INVALIDAS)
    if summary.duplicate_rows:
        avisos.append(DUPLICADOS_CANONICOS)
    controles = (
        summary.explicit_reference_controls
        + summary.explicit_positive_controls
        + summary.explicit_negative_controls
    )
    if controles == 0:
        # No se inventa ninguno. Sin control declarado, el resultado de la
        # cohorte no tendrá contra qué contrastarse, y eso hay que decirlo antes
        # de ejecutar, no después.
        avisos.append(SIN_CONTROLES_DECLARADOS)
    if study.config.grid_center is None or study.config.grid_size is None:
        avisos.append(CAJA_NO_DECLARADA)
    if study.config.seed is None:
        avisos.append(SEMILLA_NO_DECLARADA)
    return avisos


def build_cohort_preflight(
    *,
    study: CohortStudy,
    filename: str,
    content: bytes,
    generated_at: datetime | None = None,
    parsed: ParsedFile | None = None,
) -> CohortPreflightResult:
    """
    Comprobación previa completa de una cohorte.

    `parsed` existe para las pruebas: permite inyectar una lectura ya hecha sin
    fabricar un archivo. En producción se deja en `None` y se lee de verdad.
    """
    momento = generated_at or datetime.now(timezone.utc)
    lectura = parsed if parsed is not None else read_cohort_file(filename, content)

    validador = _rdkit_disponible()
    blockers: list[str] = list(lectura.blockers)
    if not validador:
        blockers.append(VALIDADOR_NO_DISPONIBLE)

    rows = [_normalizar_fila(raw, validador=validador) for raw in lectura.rows]
    duplicadas = _marcar_duplicados(rows)
    summary = _resumen(rows, duplicadas)

    if summary.total_rows == 0:
        if COHORTE_VACIA not in blockers:
            blockers.append(COHORTE_VACIA)
    elif summary.eligible_rows == 0 and SIN_MOLECULAS_ELEGIBLES not in blockers:
        blockers.append(SIN_MOLECULAS_ELEGIBLES)

    avisos = _avisos_de_cohorte(study, summary)
    if not any(fila.active_label is not None for fila in rows):
        avisos.append(SIN_ETIQUETAS_ACTIVE)

    huella = cohort_fingerprint(
        study,
        [
            FingerprintRow(
                # El canónico cuando se pudo leer; si no, lo que la persona
                # escribió. Una fila ilegible sigue definiendo esta cohorte.
                molecule=fila.canonical_smiles or fila.input_smiles,
                active_label=fila.active_label,
                control_role=fila.control_role,
            )
            for fila in rows
        ],
    )

    return CohortPreflightResult(
        generated_at=momento.isoformat(),
        cohort_fingerprint=huella,
        normalized_study=study,
        decision=decide(blockers),
        blockers=blockers,
        warnings=avisos,
        summary=summary,
        rows=rows,
    )

"""Declaración del estado tautomérico de un ligando, para FEP (paso 1 de la cartera H).

# Qué problema resuelve

`chem/conformer.py` acopla el tautómero **canónico de RDKit** y hasta ahora sólo
registraba cuántas alternativas había. Para un cálculo de energía libre eso no
basta: el tautómero decide qué átomos donan y cuáles aceptan puentes de
hidrógeno, y un tautómero que en disolución tiene un 1 % de población, tratado
como si costara cero, ya mete del orden de 2,7 kcal/mol (−RT ln p).

El canónico de RDKit **no** es una predicción del estado dominante: su fin es dar
siempre la misma representación. Así que aquí RDKit hace de **generador de
candidatos**, no de árbitro.

# Los tres estados

    RESUELTO_UNICO          el enumerador encuentra un solo tautómero.
    MULTIESTADO_REQUERIDO   hay varios, la enumeración es completa y ninguno se
                            descarta: no hay un modelo de poblaciones validado.
                            Un paquete FEP tiene que llevarlos todos, o alguien
                            tiene que elegir uno con evidencia y decirlo.
    NO_RESUELTO             la enumeración falló o se cortó en el tope: el
                            conjunto de candidatos está incompleto.

Ninguno de los tres dice que el tautómero acoplado sea el correcto. Dicen qué se
sabe y qué no.

# Lo que no hace

No cambia lo que el producto acopla. No estima poblaciones ni descarta
candidatos: eso requiere un modelo energético validado, y cuando exista entrará
como capa aparte, con su evidencia y su versión.
"""

from __future__ import annotations

from typing import Any

#: El mismo tope que la auditoría FEP-01 (`scripts/analisis_fep01_integridad.py`).
MAX_TAUTOMEROS = 32
VERSION = 1

RESUELTO_UNICO = "RESUELTO_UNICO"
MULTIESTADO_REQUERIDO = "MULTIESTADO_REQUERIDO"
NO_RESUELTO = "NO_RESUELTO"


def _enumerador():
    from rdkit.Chem.MolStandardize import rdMolStandardize

    parametros = rdMolStandardize.CleanupParameters()
    # Igual que `chem/conformer.py`: el valor por defecto (True) borra la
    # estereoquímica sp3 implicada en el sistema tautomérico, y los dos
    # enantiómeros de la talidomida salían siendo la misma molécula.
    parametros.tautomerRemoveSp3Stereo = False
    parametros.maxTautomers = MAX_TAUTOMEROS
    return rdMolStandardize.TautomerEnumerator(parametros)


def declarar_tautomeros(smiles: str) -> dict[str, Any]:
    """Declaración serializable (JSON) del estado tautomérico de `smiles`.

    Nunca lanza: un fallo es un estado (`NO_RESUELTO`) con su motivo.
    """
    import rdkit
    from rdkit import Chem, RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize

    motor = (f"RDKit rdMolStandardize.TautomerEnumerator {rdkit.__version__} "
             f"(tautomerRemoveSp3Stereo=False, maxTautomers={MAX_TAUTOMEROS})")
    base: dict[str, Any] = {
        "version": VERSION,
        "motor": motor,
        "smiles_entrada": smiles,
        "smiles_canonico": None,
        "candidatos": [],
        "n_candidatos": None,
        "enumeracion_completa": False,
        "atomos_tautomericos": [],
        "estado": NO_RESUELTO,
        "motivo": None,
        "poblaciones": None,
        "poblaciones_motivo": ("Sin modelo de poblaciones validado: no se descarta ningún "
                               "candidato. El canónico de RDKit es una representación "
                               "reproducible, no el estado dominante."),
    }
    RDLogger.DisableLog("rdApp.*")
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            base["motivo"] = "SMILES_INVALIDO"
            return base
        te = _enumerador()
        resultado = te.Enumerate(mol)
        canonico = Chem.MolToSmiles(te.Canonicalize(mol))
        entrada = Chem.MolToSmiles(mol)
        smiles_candidatos = sorted({Chem.MolToSmiles(t) for t in resultado.tautomers})
        completa = resultado.status == rdMolStandardize.TautomerEnumeratorStatus.Completed
    except Exception as exc:  # noqa: BLE001 — un fallo de enumeración es un estado, no una excepción
        base["motivo"] = f"ENUMERACION_FALLO: {type(exc).__name__}: {exc}"[:300]
        return base

    base["smiles_canonico"] = canonico
    base["enumeracion_completa"] = bool(completa)
    base["n_candidatos"] = len(smiles_candidatos)
    base["atomos_tautomericos"] = sorted(int(i) for i in resultado.modifiedAtoms)
    # Identificadores estables: el orden es el alfabético del SMILES canónico de
    # cada candidato, no el del enumerador, para que no dependa de la versión.
    base["candidatos"] = [
        {"id": f"T{k}", "smiles": s, "es_canonico": s == canonico, "es_entrada": s == entrada}
        for k, s in enumerate(smiles_candidatos)
    ]
    if not completa:
        base["motivo"] = f"ENUMERACION_INCOMPLETA: {resultado.status.name}"
    elif len(smiles_candidatos) <= 1:
        base["estado"] = RESUELTO_UNICO
    else:
        base["estado"] = MULTIESTADO_REQUERIDO
        base["motivo"] = (f"{len(smiles_candidatos)} tautómeros enumerados y ninguno descartado "
                          "con evidencia; el acoplamiento usa el canónico de RDKit")
    return base


def resumen_para_humanos(declaracion: dict[str, Any] | None) -> str | None:
    """Una línea para el dossier. `None` si no hay declaración."""
    if not isinstance(declaracion, dict) or not declaracion.get("estado"):
        return None
    estado = declaracion["estado"]
    n = declaracion.get("n_candidatos")
    if estado == RESUELTO_UNICO:
        return "Un solo tautómero enumerable"
    if estado == MULTIESTADO_REQUERIDO:
        return (f"{n} tautómeros candidatos, ninguno descartado con evidencia; "
                "se acopló el canónico de RDKit, que no es una predicción de población")
    return f"No resuelto: {declaracion.get('motivo') or 'enumeración incompleta'}"

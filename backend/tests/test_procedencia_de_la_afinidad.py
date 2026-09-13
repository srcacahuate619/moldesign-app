"""`affinity_kcal` es el score de Vina. De nadie más.

Auditoría del 2026-09-04, §2. Los dos ejecutores hacían, tras el rescoring:

    corrected_kcal = -1.36 * pki_a          # pki_a: regresión de XGBoost
    docking.best_affinity = corrected_kcal

y `repository.upsert_evaluation_result` guarda
`affinity_kcal = docking.best_affinity`. Es decir: el número que se persiste,
se certifica en Solana y se imprime en el certificado PDF no era el score de
Vina. En una corrida real Vina dio −5.885 kcal/mol y lo guardado fue −5.305.

Tres cosas mal a la vez:

1. **El dato primario se destruía.** No se guardaba en ninguna otra parte, así
   que no había forma de recuperarlo ni de comparar las dos predicciones.
2. **El aviso posterior seguía llamándolo «escala de Vina»** — y el comentario
   sobre ese aviso en `utils/scientific.py` explica con cuidado cómo NO
   sobreleer un score de Vina, aplicado a un número que ya no lo era.
3. **La sustitución ocurría fuera del dominio de aplicabilidad.** Medido en una
   corrida: distancia de Mahalanobis 52.6 contra un umbral de 16.2, y el pKi
   reemplazaba a Vina igual.

No son la misma cantidad. La función de Vina es empírica y está entrenada para
ORDENAR poses; una regresión de pKi es otra medida, con otro error y otro
dominio de validez. Compartir la unidad kcal/mol no las hace intercambiables.

Ahora conviven: `affinity_kcal` es Vina y `ml_pki` es XGBoost, con
`ml_pki_aplicada` diciendo si el modelo estaba en dominio.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
EJECUTORES = {
    "queue_handler": BACKEND / "services" / "docking" / "queue_handler.py",
    "runner_pro": BACKEND / "services" / "pipeline" / "runner.py",
}

# La regresión convertida a kcal: `-1.36 * <lo que sea>`.
#
# La comprobación es deliberadamente estrecha. Asignar `best_affinity` es
# legítimo —el acoplamiento lo hace desde `poses[0].affinity`, y la ruta
# peptídica lo deriva de la confianza del plegado—; lo que no puede volver es
# que lo escriba el rescoring de ML.
_CONVERSION_PKI = re.compile(r"-\s*1\.36\s*\*")


def _lineas_de_codigo(ruta: Path) -> list[str]:
    return [
        linea.strip()
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if not linea.strip().startswith("#")
    ]


@pytest.mark.parametrize("nombre,ruta", EJECUTORES.items(), ids=list(EJECUTORES))
def test_ningun_ejecutor_escribe_la_afinidad_desde_el_rescoring_de_ml(
    nombre: str, ruta: Path
):
    culpables = [
        linea
        for linea in _lineas_de_codigo(ruta)
        if "best_affinity" in linea
        and "=" in linea
        and (
            _CONVERSION_PKI.search(linea)
            or "corrected_kcal" in linea
            or "pki" in linea.lower()
        )
    ]
    assert not culpables, (
        f"{nombre} vuelve a escribir la afinidad desde el rescoring de ML: "
        f"{culpables}. Ese campo se persiste como `affinity_kcal` y tiene que "
        "seguir siendo el score de Vina."
    )


@pytest.mark.parametrize("nombre,ruta", EJECUTORES.items(), ids=list(EJECUTORES))
def test_los_dos_ejecutores_guardan_la_prediccion_de_ml_aparte(nombre: str, ruta: Path):
    """No basta con dejar de pisar: el pKi tiene que conservarse."""
    fuente = ruta.read_text(encoding="utf-8")
    assert "ml_pki" in fuente, (
        f"{nombre} ya no registra `ml_pki`. Dejar de sobrescribir sin guardar "
        "la predicción sólo cambia un dato perdido por otro."
    )


@pytest.mark.parametrize("nombre,ruta", EJECUTORES.items(), ids=list(EJECUTORES))
def test_fuera_del_dominio_de_aplicabilidad_se_avisa(nombre: str, ruta: Path):
    fuente = ruta.read_text(encoding="utf-8")
    assert "ML_FUERA_DE_DOMINIO" in fuente, (
        f"{nombre} no emite aviso cuando la regresión cae fuera del dominio de "
        "aplicabilidad. Un pKi extrapolado y uno interpolado no se pueden "
        "presentar igual."
    )
    assert "in_applicability_domain" in fuente, (
        f"{nombre} dejó de leer `in_applicability_domain` del resultado de ML"
    )


def test_el_esquema_tiene_donde_guardar_las_dos_predicciones():
    from core.models import EvaluationResultORM

    columnas = {c.name for c in EvaluationResultORM.__table__.columns}
    for columna in ("affinity_kcal", "ml_pki", "ml_pki_aplicada"):
        assert columna in columnas, f"falta la columna {columna}"


def test_el_repositorio_escribe_affinity_kcal_solo_desde_el_acoplamiento():
    """La otra mitad del trato: nadie más puede tocar esa columna."""
    escrituras = [
        linea
        for linea in _lineas_de_codigo(BACKEND / "db" / "repository.py")
        if "result.affinity_kcal" in linea and "=" in linea
    ]
    # `= None` es la ruta de error, que limpia los scores previos para no dejar
    # datos rancios de una corrida anterior.
    permitidas = {
        "result.affinity_kcal = float(docking.best_affinity)",
        "result.affinity_kcal = None",
    }
    intrusas = [e for e in escrituras if e not in permitidas]
    assert not intrusas, f"`affinity_kcal` se escribe desde un sitio nuevo: {intrusas}"
    assert "result.affinity_kcal = float(docking.best_affinity)" in escrituras, (
        "el acoplamiento dejó de escribir `affinity_kcal`"
    )


def test_el_bump_de_esquema_declara_que_lo_viejo_no_es_comparable():
    """Las evaluaciones anteriores pueden tener un XGBoost en esa columna."""
    import re

    fuente = (BACKEND / "core" / "database.py").read_text(encoding="utf-8")
    # La versión sigue subiendo con el tiempo; lo que no puede bajar de 16 es el
    # sello, porque 16 es donde `ml_pki` empezó a existir. Fijar el número
    # exacto convertía cada bump posterior en un fallo de esta prueba, que no es
    # lo que vigila.
    version = re.search(r"^SCHEMA_VERSION = (\d+)", fuente, re.M)
    assert version, "no se encuentra SCHEMA_VERSION"
    assert int(version.group(1)) >= 16, (
        f"el esquema está en v{version.group(1)}: la separación de `ml_pki` "
        "entró en v16 y no puede desaparecer"
    )
    # Normalizando espacios: el texto va en un docstring justificado y un salto
    # de línea en medio de la frase la escondería.
    plano = " ".join(fuente.lower().split())
    assert "no son comparables" in plano, (
        "el bump no declara que las evaluaciones anteriores pueden llevar en "
        "`affinity_kcal` un valor de XGBoost. Sin esa nota, un lector compara "
        "números que no miden lo mismo."
    )

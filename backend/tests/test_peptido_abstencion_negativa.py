"""El golden negativo: la abstención peptídica, y que −4.0 no vuelve.

`docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md` §7 y §8.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ UN GOLDEN NEGATIVO ES UN GOLDEN
═══════════════════════════════════════════════════════════════════════════

`peptide_con_sidecar` documenta una corrida REAL, con los pesos de 8.44 GB
sobre CPU, que llega a:

    origen                   = folded_structure_only
    fold_plddt               = 59.5   (valor observado, escala 0-100)
    vina_affinity_kcal_mol   = null

No es un caso a medias: es el resultado científicamente correcto del estado
actual. ESMFold pliega bien; lo que no existe todavía es la frontera entre su
PDB y un ligando que Vina pueda consumir —el PDB no trae OXT, así que no casa
con el grafo del SMILES—.

El ADR decide que ese golden NO se reemplaza. Cuando exista la transferencia se
añadirá `peptide_transferido_y_acoplado_v1` **al lado**, porque representan dos
estados distintos que el dossier tiene que saber explicar.

═══════════════════════════════════════════════════════════════════════════
LO QUE ESTE ARCHIVO IMPIDE
═══════════════════════════════════════════════════════════════════════════

Que vuelva la afinidad fabricada. Antes de esta sesión, esta misma corrida
reportaba **−4.0 kcal/mol**, siempre, para cualquier resultado real de Vina:

    conf = 1 - |afinidad|/15        (invertida: mejor afinidad, menos confianza)
    aff  = max(-12.0, min(-4.0, -1.5 * conf))   ->  −4.0 para todo conf en [0.1, 1]

La abstención sólo vale si es imposible sustituirla por un número. Estas
pruebas recorren el código de los dos ejecutores y del sidecar buscando
cualquier reaparición de esa aritmética.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GOLDEN = RAIZ / "backend" / "tests" / "goldens" / "peptide_con_sidecar.json"

#: Todo el código que puede producir una afinidad en la ruta peptídica.
RUTA_PEPTIDICA = (
    RAIZ / "backend" / "services" / "docking" / "peptide_docking.py",
    RAIZ / "backend" / "services" / "docking" / "queue_handler.py",
    RAIZ / "backend" / "sidecars" / "esmfold" / "predictor.py",
    RAIZ / "backend" / "services" / "esmfold" / "service.py",
)


def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _codigo(ruta: Path) -> list[str]:
    return [
        linea.strip()
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if not linea.strip().startswith("#")
    ]


# ── El golden negativo se conserva ───────────────────────────────────────

def test_el_golden_negativo_existe_y_documenta_una_corrida_real():
    d = _golden()
    assert d["medido_el"] == "2026-09-04", (
        "el golden dejó de declarar cuándo se midió: sin eso no se distingue "
        "una corrida real de un contrato escrito a mano"
    )
    assert d["plegado"]["ejecutado"] is True
    assert d["acoplamiento"]["ejecutado"] is False


def test_el_golden_negativo_separa_plegado_de_acoplamiento():
    """Las dos cosas ocurrieron por separado, y una no ocurrió."""
    d = _golden()
    assert d["plegado"]["plddt_0_100"] > 0, "el plegado sí produjo confianza"
    assert d["acoplamiento"]["vina_affinity_kcal_mol"] is None, (
        "sin acoplamiento no hay afinidad, y no se fabrica ninguna"
    )
    assert d["contrato"]["pose_origen"] == "folded_structure_only"


def test_el_golden_negativo_declara_por_que_se_detuvo():
    """Una abstención sin motivo no se puede revisar."""
    detalle = _golden()["acoplamiento"]["detalle"]
    assert "OXT" in detalle, (
        "el motivo tiene que nombrar la causa concreta: el PDB de ESMFold no "
        "trae OXT y por eso no casa con el grafo del SMILES"
    )


def test_el_golden_positivo_todavia_no_existe():
    """Y cuando exista, se añade AL LADO, no encima.

    Esta prueba falla el día que se implemente la transferencia. Ese fallo es
    la señal: hay que comprobar entonces que el negativo sigue ahí.
    """
    positivo = GOLDEN.parent / "peptide_transferido_y_acoplado_v1.json"
    if positivo.is_file():
        pytest.fail(
            "Apareció el golden positivo. Comprueba que `peptide_con_sidecar` "
            "sigue existiendo —el ADR 76 §7 dice que NO se reemplaza— y "
            "actualiza esta prueba."
        )


# ── El −4.0 no puede volver ──────────────────────────────────────────────

@pytest.mark.parametrize("ruta", RUTA_PEPTIDICA, ids=lambda r: r.name)
def test_ninguna_aritmetica_fabrica_una_afinidad(ruta: Path):
    """La reaparición se busca por la forma, no por el número.

    Un `-4.0` suelto puede ser cualquier cosa; lo que no puede volver es
    DERIVAR una afinidad de una confianza. Se buscan las tres formas concretas
    que existieron.
    """
    sospechosas = []
    for linea in _codigo(ruta):
        minuscula = linea.lower()
        deriva_de_confianza = (
            ("conf" in minuscula or "plddt" in minuscula or "iptm" in minuscula)
            and ("aff" in minuscula or "kcal" in minuscula)
            and any(op in linea for op in ("*", "-1.5", "-4.0", "8.0"))
        )
        if deriva_de_confianza and "=" in linea:
            sospechosas.append(linea)

    assert not sospechosas, (
        f"{ruta.name} vuelve a derivar una afinidad de una confianza: "
        f"{sospechosas}. pLDDT e ipTM describen el plegado; convertirlos a "
        "kcal/mol inventa una medida que nadie hizo."
    )


@pytest.mark.parametrize("ruta", RUTA_PEPTIDICA, ids=lambda r: r.name)
def test_no_reaparece_el_clamp_que_devolvia_menos_cuatro(ruta: Path):
    culpables = [
        l for l in _codigo(ruta)
        if "min(-4.0" in l.replace(" ", "") or "min(-4," in l.replace(" ", "")
    ]
    assert not culpables, (
        f"{ruta.name}: volvió `min(-4.0, ...)`. Con cualquier confianza en "
        "[0.1, 1.0] ese clamp devolvía −4.0 SIEMPRE."
    )


def test_la_abstencion_no_se_puede_rellenar_con_un_neutro():
    """`DockingResult` exige una afinidad real, y eso es lo correcto."""
    from core.models import DockingResult

    campo = DockingResult.model_fields["best_affinity"]
    assert campo.is_required(), (
        "`best_affinity` dejó de ser obligatorio. Antes ese contrato se "
        "cumplía rellenándolo con −4.0; la solución no es hacerlo opcional, "
        "es no construir un DockingResult cuando no hubo acoplamiento."
    )


# ── El dossier dice lo que el ADR manda decir ────────────────────────────

def test_el_dossier_usa_la_formulacion_del_adr():
    """§8: «estructura peptídica generada; docking no evaluado»."""
    fuente = (RAIZ / "backend" / "services" / "dossier" / "model.py").read_text(
        encoding="utf-8"
    )
    assert "Estructura peptídica generada; docking no evaluado" in fuente, (
        "el dossier dejó de usar la formulación que el ADR 76 §8 fija para "
        "este estado"
    )


def test_el_dossier_separa_solicitado_de_ejecutado():
    fuente = (RAIZ / "backend" / "services" / "dossier" / "model.py").read_text(
        encoding="utf-8"
    )
    assert "Motor solicitado frente a ejecutado" in fuente


def test_el_dossier_detecta_la_abstencion_por_los_hechos():
    """No por una bandera que alguien tenga que acordarse de poner."""
    fuente = (RAIZ / "backend" / "services" / "dossier" / "model.py").read_text(
        encoding="utf-8"
    )
    bloque = fuente[
        fuente.index("def _campos_de_protocolo_y_abstencion") :
        fuente.index("def _campos_de_eficiencia")
    ]
    assert "afinidad is None" in bloque, (
        "la abstención tiene que deducirse de que hubo estructura y no hubo "
        "afinidad, no de una bandera"
    )


# ── El producto no puede afirmar lo que no hace ──────────────────────────

def test_la_interfaz_no_afirma_que_esmfold_completa_el_acoplamiento():
    """Condición de release del ADR 76 §8, mientras no haya golden positivo."""
    vistas = (
        RAIZ / "frontend" / "components" / "interfaces" / "pro" / "DockingEnginePanel.tsx",
        RAIZ / "frontend" / "components" / "interfaces" / "pro" / "ProOptionsModal.tsx",
        RAIZ / "backend" / "services" / "motores" / "catalogo.py",
    )
    for ruta in vistas:
        texto = ruta.read_text(encoding="utf-8")
        # Fuera comentarios: explican el cambio citando la frase vieja.
        visible = "\n".join(
            l for l in texto.splitlines()
            if not l.strip().startswith(("//", "#"))
        )
        for afirmacion in (
            "y acopla con Vina",
            "acopla el resultado con AutoDock Vina",
            "docking peptídico completado",
        ):
            assert afirmacion not in visible, (
                f"{ruta.name} afirma «{afirmacion}». Mientras no exista el "
                "golden positivo, la formulación correcta es que ESMFold está "
                "operativo para plegamiento y la conversión a ligando "
                "acoplable no está soportada."
            )


def test_la_interfaz_dice_lo_que_si_hace():
    """No basta con quitar la afirmación: hay que decir el estado real."""
    ruta = RAIZ / "frontend" / "components" / "interfaces" / "pro" / "DockingEnginePanel.tsx"
    texto = ruta.read_text(encoding="utf-8")
    assert "no soportada" in texto and "plegamiento" in texto, (
        "se quitó la afirmación pero no se puso el estado real en su lugar"
    )


# ── Ninguna pose puede salir sin declarar de dónde vino ──────────────────
#
# `PredictedPose.origen` tiene por defecto `ORIGEN_VINA`, así que OMITIRLO NO ES
# NEUTRAL: etiqueta la pose como acoplada por Vina. Tres sitios lo omitían, y
# los tres producen estructuras que nunca pasaron por un motor de acoplamiento:
#
#   · la rama «Vina no encontrado» del camino Fast;
#   · `_refine_poses`, que reconstruía la pose tras minimizar con OpenMM y de
#     paso tiraba la afinidad medida —el mismo defecto que borraba el score de
#     Vina en M4, con otro disfraz—;
#   · `_generate_alternatives_from_refined`, que es la salida ENTERA del camino
#     Pro, donde Vina no se ejecuta nunca.
#
# Se comprueba sobre el árbol sintáctico y no con `grep` porque lo que importa
# es qué argumentos recibe la llamada, no qué texto hay cerca.


def _llamadas_a_pose() -> list:
    import ast

    fuente = (RAIZ / "backend" / "sidecars" / "esmfold" / "predictor.py").read_text(
        encoding="utf-8"
    )
    arbol = ast.parse(fuente)
    return [
        nodo for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Name)
        and nodo.func.id == "PredictedPose"
    ]


def test_toda_pose_declara_origen_y_afinidad():
    llamadas = _llamadas_a_pose()
    assert llamadas, "no se encontró ninguna construcción de PredictedPose"

    olvidos = []
    for llamada in llamadas:
        claves = {clave.arg for clave in llamada.keywords}
        faltan = {"origen", "vina_affinity_kcal_mol"} - claves
        if faltan:
            olvidos.append((llamada.lineno, sorted(faltan)))

    assert not olvidos, (
        f"construcciones de PredictedPose sin declarar {olvidos}. El defecto de "
        "`origen` es `vina_docked`: omitirlo publica una estructura plegada como "
        "si un motor de acoplamiento la hubiera producido."
    )


def test_el_refinado_no_borra_la_afinidad_ni_el_origen():
    """OpenMM mueve átomos; no mide unión ni cambia la procedencia.

    Los dos campos tienen que COPIARSE de la pose de entrada. Un literal —o el
    valor por defecto— convertiría el refinado en una etapa que destruye la
    observación primaria, que es exactamente lo que hacía.
    """
    import ast

    fuente = (RAIZ / "backend" / "sidecars" / "esmfold" / "predictor.py").read_text(
        encoding="utf-8"
    )
    arbol = ast.parse(fuente)
    refinar = next(
        n for n in ast.walk(arbol)
        if isinstance(n, ast.FunctionDef) and n.name == "_refine_poses"
    )
    llamadas = [
        n for n in ast.walk(refinar)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "PredictedPose"
    ]
    assert llamadas, "`_refine_poses` ya no construye poses; revisa esta prueba"

    for llamada in llamadas:
        argumentos = {clave.arg: clave.value for clave in llamada.keywords}
        for campo in ("vina_affinity_kcal_mol", "origen"):
            valor = argumentos.get(campo)
            assert isinstance(valor, ast.Attribute) and valor.attr == campo, (
                f"`_refine_poses` no propaga `{campo}` desde la pose de entrada "
                f"(línea {llamada.lineno}). Refinar la geometría no puede "
                "cambiar ni la afinidad medida ni de dónde salió la pose."
            )

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
import re
import tempfile
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
#
# Estos dos guardianes leían el `.tsx` con `in`. Funcionó hasta que la interfaz
# se tradujo: las frases dejaron de vivir en el componente y pasaron al
# diccionario, detrás de `t("auto_14578be07d4d")`. El de abajo se puso rojo —que
# es el fallo bueno— y el de arriba se quedó VERDE mirando un archivo donde ya
# no puede haber ninguna afirmación, que es el fallo malo: un guardián que
# recorre 167 archivos y anuncia «limpio» sobre un export sucio.
#
# Desde aquí los dos siguen la indirección: resuelven cada clave que el
# componente usa, en TODOS los idiomas, y miran el texto que el usuario lee.

_CLAVE_EN_USO = re.compile(r"""\bt\(\s*["']([A-Za-z_][A-Za-z0-9_.]*)["']""")
_ENTRADA_TRADUCIDA = re.compile(
    r"""^\s*(?:["']?)([A-Za-z_][A-Za-z0-9_.]*)(?:["']?)\s*:\s*["'](.*)["'],?\s*$"""
)

TRADUCCIONES = RAIZ / "frontend" / "context" / "traducciones"


def _diccionario() -> dict[str, list[str]]:
    """clave → todos los textos con los que se muestra, en todos los idiomas.

    No se distingue el idioma a propósito: la exigencia es que NINGUNA variante
    afirme de más. Si mañana entra un tercer idioma, entra también aquí sin
    tocar nada.
    """
    resuelto: dict[str, list[str]] = {}
    for archivo in sorted(TRADUCCIONES.glob("*.ts")):
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            encontrado = _ENTRADA_TRADUCIDA.match(linea)
            if encontrado:
                clave, texto = encontrado.groups()
                resuelto.setdefault(clave, []).append(texto)
    return resuelto


def _texto_que_ve_el_usuario(ruta: Path) -> str:
    """Lo que el componente escribe literalmente MÁS lo que resuelven sus claves.

    Fuera los comentarios: explican el cambio citando la frase vieja, y contarla
    haría fallar al guardián por la razón contraria a la que existe.
    """
    fuente = ruta.read_text(encoding="utf-8")
    visible = "\n".join(
        l for l in fuente.splitlines() if not l.strip().startswith(("//", "#"))
    )
    if ruta.suffix not in (".tsx", ".ts"):
        return visible
    catalogo = _diccionario()
    traducido = [
        texto
        for clave in _CLAVE_EN_USO.findall(visible)
        for texto in catalogo.get(clave, [])
    ]
    return "\n".join([visible, *traducido])


#: Las frases que el ADR 76 §8 prohíbe mientras no exista el golden positivo.
AFIRMACIONES_PROHIBIDAS = (
    "y acopla con Vina",
    "acopla el resultado con AutoDock Vina",
    "docking peptídico completado",
)

VISTAS_DEL_MOTOR = (
    RAIZ / "frontend" / "components" / "interfaces" / "pro" / "DockingEnginePanel.tsx",
    RAIZ / "frontend" / "components" / "interfaces" / "pro" / "ProOptionsModal.tsx",
    RAIZ / "backend" / "services" / "motores" / "catalogo.py",
)


def test_la_interfaz_no_afirma_que_esmfold_completa_el_acoplamiento():
    """Condición de release del ADR 76 §8, mientras no haya golden positivo."""
    for ruta in VISTAS_DEL_MOTOR:
        visible = _texto_que_ve_el_usuario(ruta)
        for afirmacion in AFIRMACIONES_PROHIBIDAS:
            assert afirmacion not in visible, (
                f"{ruta.name} afirma «{afirmacion}». Mientras no exista el "
                "golden positivo, la formulación correcta es que ESMFold está "
                "operativo para plegamiento y la conversión a ligando "
                "acoplable no está soportada."
            )


def test_la_interfaz_dice_lo_que_si_hace():
    """No basta con quitar la afirmación: hay que decir el estado real.

    El texto vive hoy en `t("auto_14578be07d4d")` y se muestra en español e
    inglés. Se exige en LOS DOS: una traducción que pierda la salvedad diría al
    usuario inglés que el acoplamiento se evaluó.
    """
    ruta = RAIZ / "frontend" / "components" / "interfaces" / "pro" / "DockingEnginePanel.tsx"
    fuente = ruta.read_text(encoding="utf-8")
    catalogo = _diccionario()

    claves = [c for c in _CLAVE_EN_USO.findall(fuente) if c in catalogo]
    textos = [t for c in claves for t in catalogo[c]] + [fuente]

    def dice_que_pliega(texto: str) -> bool:
        return "plegamiento" in texto or "folding" in texto.lower()

    def dice_que_no_acopla(texto: str) -> bool:
        return "no soportada" in texto or "not yet supported" in texto.lower()

    honestos = [t for t in textos if dice_que_pliega(t) and dice_que_no_acopla(t)]
    assert len(honestos) >= 2, (
        "se quitó la afirmación pero no se puso el estado real en su lugar, o "
        "sólo se puso en un idioma: el panel tiene que decir que ESMFold pliega "
        f"y que la conversión no está soportada. Encontrados: {len(honestos)}"
    )


def test_el_guardian_de_la_interfaz_demuestra_que_ve():
    """Un detector tiene que probar que detecta, y que no detecta de más.

    El guardián anterior recorría un `.tsx` donde, tras la traducción, ya no
    podía haber ninguna afirmación: habría anunciado «limpio» para siempre. Esta
    prueba fija las dos mitades sobre muestras construidas.
    """
    catalogo = _diccionario()

    # 1. Ve a través de la indirección: la clave del panel resuelve, y en más
    #    de un idioma. Si el diccionario dejara de cargarse, esto cae.
    assert len(catalogo.get("auto_14578be07d4d", [])) >= 2, (
        "el diccionario dejó de resolver la clave del panel de motores: el "
        "guardián estaría mirando un componente vacío de texto"
    )

    # 2. Detecta lo que tiene que detectar, aunque llegue por traducción.
    with tempfile.TemporaryDirectory() as tmp:
        señuelo = Path(tmp) / "Señuelo.tsx"
        clave = next(
            c for c, textos in catalogo.items()
            if any(AFIRMACIONES_PROHIBIDAS[0] in t for t in textos)
        ) if any(
            AFIRMACIONES_PROHIBIDAS[0] in t
            for textos in catalogo.values() for t in textos
        ) else None
        # No hay (ni debe haber) una clave prohibida en el catálogo real, así
        # que la muestra positiva se construye con el texto literal.
        assert clave is None, (
            "el diccionario de traducciones contiene una afirmación prohibida"
        )
        señuelo.write_text(
            'export const X = () => <p>ESMFold pliega y acopla con Vina</p>;',
            encoding="utf-8",
        )
        visible = _texto_que_ve_el_usuario(señuelo)
        assert AFIRMACIONES_PROHIBIDAS[0] in visible

        # 3. Y NO detecta de más: un comentario que cita la frase vieja para
        #    explicar por qué se quitó no puede volver a encender la alarma.
        señuelo.write_text(
            '// antes decía «y acopla con Vina»; se quitó por el ADR 76 §8\n'
            'export const X = () => <p>ESMFold pliega</p>;',
            encoding="utf-8",
        )
        assert AFIRMACIONES_PROHIBIDAS[0] not in _texto_que_ve_el_usuario(señuelo)


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

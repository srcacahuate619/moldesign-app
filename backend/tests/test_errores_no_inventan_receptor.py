"""Un mensaje de error no puede nombrar un receptor que no intervino.

# El fallo que vigila

Encontrado el 2026-09-02, probando el instalador en una máquina virtual. El
usuario evaluó contra **1TW7** y la aplicación respondió:

    LA EVALUACIÓN FALLÓ
    Docking falló para molécula '...' contra target '7E2Y' (Vina exit code: 1)

Dos datos falsos en una sola frase:

1. **El receptor.** `_prepare_ligand_pdbqt` no recibía el target, así que ponía
   `settings.default_target_pdb_id` — la constante `"7E2Y"`. El informe nombraba
   una estructura que no había intervenido en la corrida.

2. **La etapa.** El proceso que devolvió 1 era `mk_prepare_ligand` de Meeko, no
   Vina. El mensaje decía «Vina exit code: 1» sobre un fallo en el que Vina ni
   siquiera llegó a arrancar.

Juntos mandaron a investigar la estructura equivocada y la herramienta
equivocada. El coste no fue el error en sí: fue el tiempo perdido buscándolo
donde no estaba.

# Por qué esto importa más aquí que en otro programa

MolDesign existe para producir evidencia trazable. Un error que atribuye un
fallo a un receptor que no participó es la misma clase de defecto que ENG-003,
donde `diffpepdock` etiquetaba corridas de ESMFold con su propio nombre: una
afirmación falsa sobre qué produjo qué. Que ocurra en la ruta de error y no en
la de éxito no lo hace menos grave — es justo cuando alguien va a leerlo con
atención.

# Qué se comprueba

Que ninguna excepción de docking rellene `target_pdb_id` con el valor por
defecto. Cuando una etapa no sabe contra qué receptor corre, tiene que decirlo,
no suponerlo.
"""

from __future__ import annotations

import inspect
import re

from services.docking import vina_service


def _codigo_sin_documentacion(modulo) -> str:
    """El código que se ejecuta, sin docstrings ni comentarios.

    Este archivo explica el fallo citando la línea que lo causaba; sin este
    filtro, la guardia se leería su propia explicación y fallaría siempre. Es la
    cuarta guardia de este repositorio que necesita la distinción.
    """
    texto = inspect.getsource(modulo)
    sin_comentarios = "\n".join(
        linea.split("#", 1)[0] for linea in texto.splitlines()
        if not linea.strip().startswith("#")
    )
    return re.sub(r'"""[\s\S]*?"""', "", sin_comentarios)


def test_ninguna_excepcion_rellena_el_receptor_con_el_valor_por_defecto():
    codigo = _codigo_sin_documentacion(vina_service)
    ofensivas = re.findall(
        r"target_pdb_id\s*=\s*settings\.default_target_pdb_id", codigo
    )
    assert not ofensivas, (
        f"{len(ofensivas)} excepción(es) rellenan `target_pdb_id` con la constante "
        "por defecto. Un informe de error que nombra un receptor que no intervino "
        "envía a depurar la estructura equivocada: paso en la VM del 2026-09-02, "
        "con 1TW7 elegido y '7E2Y' en el mensaje. Si la etapa no conoce el "
        "receptor, se pasa como argumento o se declara desconocido."
    )


def test_la_preparacion_del_ligando_recibe_el_receptor():
    """El dato existe en el llamador: no hay excusa para inventarlo."""
    firma = inspect.signature(vina_service._prepare_ligand_pdbqt)
    assert "target_pdb_id" in firma.parameters, (
        "`_prepare_ligand_pdbqt` tiene que recibir el receptor para poder "
        "nombrarlo en sus errores. El llamador ya lo tiene en el ámbito."
    )


def test_un_fallo_de_meeko_no_se_atribuye_a_vina():
    """`vina_exit_code` es de Vina. Meeko tiene el suyo, y se dice cual es."""
    codigo = _codigo_sin_documentacion(vina_service)
    preparacion = codigo[
        codigo.index("async def _prepare_ligand_pdbqt"):
        codigo.index("async def _run_vina_subprocess")
    ]
    assert "vina_exit_code=process.returncode" not in preparacion, (
        "La preparación del ligando reporta el código de salida de Meeko como si "
        "fuera de Vina. Vina no ha llegado a ejecutarse en ese punto."
    )
    assert "PREPARACIÓN DEL LIGANDO" in preparacion, (
        "Los errores de esta etapa tienen que decir que son de la preparación "
        "del ligando y no del docking."
    )


# ---------------------------------------------------------------------------
# Los lanzadores de pip llevan incrustada la ruta del constructor
# ---------------------------------------------------------------------------
#
# Encontrado el 2026-09-02 depurando por que fallaba toda evaluacion en la VM.
# Los `.exe` que pip genera en Windows guardan dentro el interprete con el que
# se instalaron. Los 55 que viajan en el instalador dicen
#
#     D:\moldesign-build\python-embed\python.exe
#
# ...la ruta de la maquina de construccion. En el equipo del usuario no existe:
# el lanzador falla y devuelve 1. `mk_prepare_ligand.exe` estaba en el camino
# critico, asi que NINGUNA evaluacion podia completarse.
#
# En la maquina donde se construye funciona, que es lo que lo mantuvo invisible.
# `preparer.py` ya lo habia resuelto para el receptor -«usar exactamente el
# interprete del backend instalado por el launcher»- y esa leccion no habia
# llegado ni a la preparacion del ligando, ni al export, ni a OpenBabel.


def test_meeko_se_invoca_por_modulo_y_no_por_lanzador():
    """`sys.executable -m meeko.cli...` no depende de ninguna ruta ajena."""
    codigo = _codigo_sin_documentacion(vina_service)
    for modulo in ("meeko.cli.mk_prepare_ligand", "meeko.cli.mk_export"):
        assert modulo in codigo, (
            f"`{modulo}` tiene que invocarse como modulo con el interprete del "
            "backend. Un lanzador de Scripts/ apunta al interprete de la maquina "
            "donde se construyo el instalador, que en el equipo del usuario no "
            "existe."
        )


def test_openbabel_no_se_invoca_por_nombre_suelto():
    """Un nombre suelto lo resuelve el PATH, y ahi esta el lanzador roto.

    ACTUALIZADO el 2026-09-05. Esta prueba exigia `_obabel_del_bundle()`, que
    resolvia el binario dentro de `site-packages/openbabel/bin/`. Arreglaba el
    sintoma —el lanzador roto de pip— pero ataba produccion al ENTORNO PYTHON de
    Open Babel, y ademas conservaba un respaldo a `"obabel"` a secas que
    ejecutaba en silencio un binario ajeno del equipo del usuario.

    Open Babel es ahora un programa independiente en `tools/openbabel/`, fuera
    del entorno importable, y se invoca por un adaptador unico que verifica su
    hash antes de ejecutarlo. La leccion original sigue vigente y se comprueba
    igual: nada se resuelve por PATH. Ver `docs/79_ADR_FRONTERA_OPEN_BABEL.md` y
    `backend/tests/test_fallback_open_babel.py`.
    """
    codigo = _codigo_sin_documentacion(vina_service)
    assert '"obabel", "-ipdbqt"' not in codigo, (
        "OpenBabel se invoca por nombre suelto: el PATH lo resuelve al lanzador "
        "de pip en Scripts/, que apunta al interprete del constructor."
    )
    assert "_obabel_del_bundle" not in codigo, (
        "Vuelve la resolucion dentro de site-packages: eso ata produccion al "
        "entorno Python de Open Babel, que es justo la frontera que hay que "
        "mantener separada."
    )
    assert "services.external_tools" in codigo, (
        "Toda invocacion de Open Babel debe pasar por el adaptador unico "
        "`services.external_tools.open_babel`, que solo ejecuta el binario "
        "empaquetado y comprueba su hash."
    )

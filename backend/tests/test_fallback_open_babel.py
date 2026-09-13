"""Los dos defectos del respaldo de Open Babel en `vina_service`, y su arreglo.

# Por qué existe este archivo

El respaldo de Open Babel tenía dos fallos que nadie había visto. La razón, que
apareció al arreglarlos y está medida más abajo, es un tercer hecho: con entrada
de Vina la rama del respaldo nunca llega a producir poses, así que ninguno de los
dos defectos se alcanzaba. Eran defectos reales del código —el programa se
comportaría mal si se alcanzaran, y cualquier cambio en el parser los habría
despertado a la vez— pero decir que «pasaban en producción» sería falso.

**Defecto 1 — procedencia inválida.** Cuando Meeko exportaba un SDF zombi y Open
Babel rescataba la conversión, `vina_service` asignaba
`parsing_source = "openbabel"`. Pero `DockingResult.parsing_source` sólo admitía
`"sdf" | "pdbqt" | "vina_stdout"`, así que construir el resultado reventaba con
un `ValidationError` de Pydantic — **justo en el caso en que el respaldo había
funcionado**. El rescate exitoso terminaba en error.

**Defecto 2 — se persistía el archivo equivocado.** Open Babel escribía un SDF
válido en un temporal, se parseaban sus poses… y después se guardaba con
`write_file(output_sdf, poses_path)` el SDF **original de Meeko**, el inválido.
El temporal de Open Babel se borraba a continuación. Es decir: las afinidades
del informe venían de un archivo y el archivo entregado era otro. Un dossier que
dice «estas poses» junto a un archivo que no las contiene es peor que no
entregar nada.

# Qué prueba cada prueba

Las dos primeras reproducen los defectos sobre el contrato, no sobre el
recuerdo: si alguien vuelve a estrechar el `Literal` o vuelve a persistir el SDF
de Meeko, fallan. Las siguientes fijan el comportamiento corregido, incluida la
regla de que una ausencia de Open Babel se declara en vez de continuar en
silencio.
"""

from __future__ import annotations

import inspect
import io
import re
import tokenize
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.models import DockingPose, DockingResult
from services.docking import vina_service

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
FUENTE_VINA = (RAIZ_BACKEND / "services" / "docking" / "vina_service.py").read_text(
    encoding="utf-8"
)


def solo_codigo(fuente: str) -> str:
    """La fuente con los COMENTARIOS borrados y el resto intacto.

    Un guardián que lee comentarios no vigila el programa: vigila la prosa.
    `vina_service.py` describe en sus comentarios justo lo que prohíbe —invocar
    `"obabel"` a secas, persistir el SDF de Meeko sin mirar— así que buscar
    sobre el texto crudo da positivos que no son código.

    Se borra el texto del comentario y se conserva la posición de todo lo demás,
    para que las líneas sigan siendo las mismas y una aserción sobre una
    asignación literal siga funcionando.
    """
    lineas = fuente.splitlines(keepends=True)
    for token in tokenize.generate_tokens(io.StringIO(fuente).readline):
        if token.type is not tokenize.COMMENT:
            continue
        fila = token.start[0] - 1
        inicio, fin = token.start[1], token.end[1]
        linea = lineas[fila]
        lineas[fila] = linea[:inicio] + " " * (fin - inicio) + linea[fin:]
    return "".join(lineas)


CODIGO_VINA = solo_codigo(FUENTE_VINA)

# AUTOTEST del extractor: un guardián que no demuestra que ve no sirve.
# Ver el incidente del detector con un 0x08 dentro, en check-exported-api-url.js.
assert solo_codigo('x = 1  # "obabel"\n') .strip() == "x = 1", (
    "solo_codigo() no borra el comentario: las aserciones de este archivo "
    "estarían vigilando la prosa y no el programa."
)
assert '"obabel"' in solo_codigo('y = "obabel"\n'), (
    "solo_codigo() borra de más: se comería la asignación que debe vigilar."
)


def _pose() -> DockingPose:
    return DockingPose(rank=1, affinity=-8.4, rmsd_lb=0.0, rmsd_ub=0.0)


# ── Defecto 1: la procedencia que el respaldo asignaba no era válida ─────


def test_defecto_1_la_etiqueta_openbabel_a_secas_sigue_siendo_invalida():
    """`"openbabel"` NO es una procedencia válida, y debe seguir sin serlo.

    El arreglo no consiste en abrir el `Literal` a cualquier cadena: consiste en
    añadir **una** procedencia explícita y verificable. Si mañana alguien vuelve
    a escribir la etiqueta antigua, esta prueba lo detiene.
    """
    with pytest.raises(ValidationError):
        DockingResult(
            best_affinity=-8.4,
            poses=[_pose()],
            parsing_source="openbabel",  # type: ignore[arg-type]
        )


def test_defecto_1_arreglado_existe_una_procedencia_valida_para_open_babel():
    resultado = DockingResult(
        best_affinity=-8.4,
        poses=[_pose()],
        parsing_source="sdf_openbabel_cli",
    )
    assert resultado.parsing_source == "sdf_openbabel_cli"


def test_defecto_1_el_servicio_usa_la_procedencia_valida():
    """La etiqueta que asigna el servicio tiene que ser la que el modelo admite.

    Se mira el código y no sólo el modelo porque el defecto original era
    exactamente una discrepancia entre los dos: el modelo estaba bien y el
    servicio escribía otra cosa.
    """
    assert 'parsing_source = "openbabel"' not in CODIGO_VINA, (
        "vina_service vuelve a asignar la procedencia inválida `openbabel`, "
        "que revienta DockingResult con ValidationError justo cuando el "
        "respaldo funciona."
    )
    assert 'parsing_source = "sdf_openbabel_cli"' in CODIGO_VINA
    procedencias_asignadas = set(
        re.findall(r'parsing_source\s*=\s*"([a-z_]+)"', CODIGO_VINA)
    )
    admitidas = set(DockingResult.model_fields["parsing_source"].annotation.__args__)
    assert procedencias_asignadas <= admitidas, (
        "vina_service asigna procedencias que DockingResult no admite: "
        f"{sorted(procedencias_asignadas - admitidas)}"
    )


# ── Defecto 2: se persistía el SDF de Meeko, no el de Open Babel ─────────


def test_defecto_2_no_se_persiste_incondicionalmente_el_sdf_de_meeko():
    """El archivo entregado tiene que ser aquel del que salieron las poses.

    La forma original era literal:

        await write_file(output_sdf, poses_path)

    sin ninguna condición, después de que el respaldo hubiera parseado otro
    archivo. Escribir el SDF de Meeko sigue siendo correcto —es lo que hacen los
    caminos `sdf`, `pdbqt` y `vina_stdout`, y sus bytes no deben cambiar— pero
    ya no puede ser incondicional: tiene que estar en la rama que corresponde.
    """
    assert "sdf_a_persistir" in CODIGO_VINA, (
        "Debe existir una variable explícita que diga QUÉ SDF se entrega."
    )
    entrega = re.search(
        r"if sdf_a_persistir is not None:\s*"
        r"await write_text\(poses_path, sdf_a_persistir\)\s*"
        r"else:\s*"
        r"await write_file\(output_sdf, poses_path\)",
        CODIGO_VINA,
    )
    assert entrega, (
        "La persistencia del SDF de poses ya no está condicionada a de dónde "
        "salieron las poses. Si Open Babel rescató la conversión, el archivo "
        "entregado no contendría las poses del informe."
    )
    # Y la coherencia entre lo que se declara y lo que se entrega se comprueba
    # en caliente, no sólo aquí: el defecto original fue exactamente que la
    # procedencia decía una cosa y el archivo era otra.
    assert 'parsing_source == "sdf_openbabel_cli") != (sdf_a_persistir is not None)' in (
        CODIGO_VINA
    ), "Falta la comprobación de coherencia entre procedencia y archivo entregado."


def test_defecto_2_el_sdf_de_open_babel_no_se_borra_antes_de_persistirlo():
    """El temporal ya no es el dueño del contenido rescatado.

    En la versión anterior el SDF de Open Babel vivía en un
    `NamedTemporaryFile(delete=False)` que se borraba con `os.remove` unas
    líneas después. Ahora el adaptador devuelve el CONTENIDO y el temporal
    muere con su directorio, así que no hay ventana en la que el archivo bueno
    exista sólo en disco temporal.
    """
    assert "tmp_sdf" not in CODIGO_VINA and "tmp_pdbqt" not in CODIGO_VINA, (
        "El respaldo vuelve a manejar temporales a mano en vez de usar el "
        "adaptador `services.external_tools.open_babel`."
    )


# ── La frontera: una sola puerta, y sin PATH ────────────────────────────


def test_el_respaldo_pasa_por_el_adaptador_y_no_por_un_subprocess_a_mano():
    assert "_obabel_del_bundle" not in CODIGO_VINA, (
        "vina_service vuelve a resolver el ejecutable por su cuenta. Toda "
        "llamada de producción debe pasar por el adaptador único."
    )
    assert "from services.external_tools import open_babel" in CODIGO_VINA or (
        "services.external_tools.open_babel" in CODIGO_VINA
    )


def test_el_servicio_no_invoca_obabel_por_nombre_suelto():
    """Ni `"obabel"` a secas ni nada que lo resuelva por PATH.

    `shutil.which` sigue siendo legítimo en este archivo: `_resolve_executable`
    lo usa para localizar Vina y las herramientas de Meeko, que no tienen esta
    restricción. Lo que no puede aparecer es el nombre de Open Babel en ninguna
    forma resoluble por entorno.
    """
    assert "obabel" not in CODIGO_VINA.lower(), (
        "El nombre del ejecutable de Open Babel vuelve a aparecer en el código "
        "de vina_service. Localizarlo es responsabilidad exclusiva del "
        "adaptador, que sólo ejecuta el binario empaquetado y verificado."
    )
    assert "openbabel" not in CODIGO_VINA.replace(
        "services.external_tools", ""
    ).replace("open_babel", "").replace("sdf_openbabel_cli", "").replace(
        "OpenBabelNoDisponible", ""
    ).lower(), (
        "Aparece una referencia a Open Babel fuera del adaptador y de la "
        "etiqueta de procedencia."
    )


# ── Ausencia declarada, nunca silenciosa ────────────────────────────────


def test_la_ausencia_de_open_babel_no_se_convierte_en_continuar_en_silencio():
    """El `except Exception: log.debug(...)` original tragaba cualquier fallo.

    Con Open Babel viajando en el instalador, su ausencia es una instalación
    dañada. La corrida debe registrar el motivo —y el aviso científico— en vez
    de seguir como si el respaldo no hiciera falta.
    """
    assert "OpenBabelNoDisponible" in CODIGO_VINA, (
        "El respaldo debe capturar el error TIPADO del adaptador y declarar el "
        "estado, no un `except Exception` que convierte un bug en «no disponible»."
    )
    assert "CONVERSOR_ESTRUCTURAL_NO_DISPONIBLE" in CODIGO_VINA, (
        "La corrida debe dejar un aviso científico explícito cuando el respaldo "
        "se necesitó y Open Babel no estaba."
    )


# ── El tercer hecho: por qué los dos defectos no se habían visto ────────


@pytest.mark.skipif(
    not (
        RAIZ_BACKEND.parent / "tools" / "openbabel" / "bin" / "obabel.exe"
    ).is_file(),
    reason="tools/openbabel/ no está staged",
)
def test_open_babel_sdf_conserva_las_poses_y_sus_metadatos():
    """Open Babel conserva las moléculas y los metadatos de Vina en el SDF.

    MEDIDO el 2026-09-05 sobre un PDBQT de salida de Vina real, de seis poses:
    el conversor escribe una propiedad REMARK por molécula; el parser extrae
    esos tres valores y el servicio puede persistir exactamente el SDF que
    respalda el informe. Los valores se comparan con el parser PDBQT original.
"""
    import asyncio

    from services.external_tools import open_babel
    from utils.file_handlers import parse_vina_output_pdbqt, parse_vina_output_sdf

    muestra = (
        RAIZ_BACKEND.parent
        / "data"
        / "dmfhard_curve_work"
        / "1aaq"
        / "curve30_conf0.out.pdbqt"
    )
    if not muestra.is_file():
        pytest.skip("no está el PDBQT de referencia de 1aaq")
    pdbqt = muestra.read_text(encoding="utf-8", errors="replace")

    conversion = asyncio.run(open_babel.convertir_pdbqt_a_sdf(pdbqt))
    assert open_babel.sdf_es_valido(conversion.contenido)
    assert conversion.contenido.count("$$$$") == 6, "las seis poses se convierten"
    # Y ninguna ruta del disco de quien corrió viaja dentro del archivo.
    assert "AppData" not in conversion.contenido
    assert ":\\" not in conversion.contenido
    assert conversion.contenido.splitlines()[0] == open_babel.TITULO_DE_LA_POSE
    assert ">  <REMARK>" in conversion.contenido
    assert "VINA RESULT" in conversion.contenido

    desde_sdf = parse_vina_output_sdf(conversion.contenido)
    assert len(desde_sdf) == 6, "el SDF convertido conserva las seis poses"
    assert [round(p["affinity"], 3) for p in desde_sdf] == [
        -5.693, -5.086, -4.775, -4.660, -4.074, -2.926
    ]
    assert [p["rank"] for p in desde_sdf] == list(range(1, 7))

    desde_pdbqt = parse_vina_output_pdbqt(pdbqt)
    assert [round(p["affinity"], 3) for p in desde_pdbqt] == [
        -5.693, -5.086, -4.775, -4.660, -4.074, -2.926
    ], "las afinidades del camino real no cambian"
    assert [p["affinity"] for p in desde_sdf] == [p["affinity"] for p in desde_pdbqt]


def test_no_se_fabrican_poses_ni_afinidades_en_el_respaldo():
    """El respaldo convierte un archivo; no inventa números.

    Las afinidades del camino de Open Babel salen del mismo parser que las del
    camino de Meeko (`parse_vina_output_sdf`), y los bloques PDBQT originales se
    conservan tal cual para trazabilidad.
    """
    fuente_respaldo = inspect.getsource(vina_service.run_vina_docking)
    assert "parse_vina_output_sdf" in fuente_respaldo
    assert "pdbqt_pose_blocks" in fuente_respaldo

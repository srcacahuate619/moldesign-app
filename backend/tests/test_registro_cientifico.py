"""Guardas del registro cientifico publico (pestana Ciencia).

La vista `/ciencia` no lee los manifests: lee el JSON estatico que
`scripts/build_registro_cientifico.py` emite en `frontend/public/registro/`. Eso
significa que la pestana puede quedarse contando una realidad vieja sin que nada
falle, y que un paper puede afirmar sobre un experimento algo que su manifest
sellado ya no dice.

Estas pruebas cubren los tres modos de fallo que doc/61 §9 exige evitar en la
pestana Ciencia: contenido desincronizado de la implementacion real, claims sin
respaldo, y contradiccion con resultados sellados.
"""

from __future__ import annotations

import importlib.util
import json

from pathlib import Path
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "moldesign_build_registro", ROOT / "scripts" / "build_registro_cientifico.py"
)
assert SPEC and SPEC.loader
REGISTRO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REGISTRO)

PAPERS = ROOT / "docs" / "papers"
PUBLICADO = ROOT / "frontend" / "public" / "registro"


@pytest.fixture(scope="module")
def construido() -> Dict[str, Any]:
    indice, papers = REGISTRO.construir()
    return {"indice": indice, "papers": papers}


@pytest.fixture(scope="module")
def taxonomia() -> Dict[str, Any]:
    return json.loads((REGISTRO.ARTEFACTOS / "_taxonomia.json").read_text(encoding="utf-8"))


def test_el_registro_publicado_esta_al_dia(construido: Dict[str, Any]) -> None:
    """Sellar un experimento o escribir un paper sin reconstruir deja la pestana mintiendo."""
    publicado = json.loads((PUBLICADO / "index.json").read_text(encoding="utf-8"))
    esperado = construido["indice"]

    viejo = {k: v for k, v in publicado.items() if k != "generado_en"}
    nuevo = {k: v for k, v in esperado.items() if k != "generado_en"}
    assert viejo == nuevo, (
        "frontend/public/registro/index.json esta desactualizado: "
        "corre python scripts/build_registro_cientifico.py"
    )


def test_cada_paper_publicado_tiene_su_json(construido: Dict[str, Any]) -> None:
    for exp_id in construido["papers"]:
        p = PUBLICADO / "papers" / f"{exp_id}.json"
        assert p.exists(), f"falta {p.relative_to(ROOT)}; reconstruye el registro"


def test_sin_deuda_editorial_en_las_columnas_protagonistas(
    construido: Dict[str, Any], taxonomia: Dict[str, Any]
) -> None:
    """Hallazgos y refutaciones son las dos columnas que sostienen claims: van con paper.

    `no-paper-standalone` es una decision editorial declarada, no una deuda.
    """
    sin_deuda = set(taxonomia.get("etiquetas", {}).get("no-paper-standalone", []))
    faltan = sorted(
        e["id"]
        for e in construido["indice"]["experimentos"]
        if not e["tiene_paper"]
        and e["categoria"] in ("hallazgo", "refutacion")
        and e["id"] not in sin_deuda
    )
    assert not faltan, f"hallazgos/refutaciones sin paper: {', '.join(faltan)}"


def test_todo_paper_declara_titulo_y_entradilla(construido: Dict[str, Any]) -> None:
    """La tarjeta del registro cae al gate o a la hipotesis si el paper no los trae."""
    for exp_id, paper in construido["papers"].items():
        meta = paper["meta"]
        assert meta.get("titulo"), f"{exp_id}: paper sin `titulo` en el frontmatter"
        assert meta.get("entradilla"), f"{exp_id}: paper sin `entradilla` en el frontmatter"
        assert meta["titulo"] != exp_id, f"{exp_id}: el titulo no puede ser el propio ID"


def test_ningun_paper_habla_de_un_experimento_inexistente() -> None:
    sellados = {
        d.name
        for d in REGISTRO.ARTEFACTOS.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    }
    huerfanos = sorted(p.stem for p in PAPERS.glob("*.md") if p.stem not in sellados)
    assert not huerfanos, f"papers sin artefacto sellado: {', '.join(huerfanos)}"


def test_un_defecto_abierto_declara_su_reemplazo_en_el_contrato(
    construido: Dict[str, Any], taxonomia: Dict[str, Any]
) -> None:
    """La etiqueta sola es un chip en mayusculas: no dice que cifra dejo de valer.

    Un registro etiquetado `defecto-abierto` conserva cifras selladas que ya no deben
    citarse. El aviso no puede depender de que alguien escribiera un paper —hay registros
    que deliberadamente no lo tienen—, asi que viaja en el contrato: `reemplazado_por`,
    que la vista de Ciencia pinta en la tarjeta y en la ficha.
    """
    marcados = taxonomia.get("etiquetas", {}).get("defecto-abierto", [])
    assert marcados, "la etiqueta defecto-abierto no puede quedarse sin definicion"

    por_id = {e["id"]: e for e in construido["indice"]["experimentos"]}
    for exp_id in marcados:
        assert exp_id in por_id, f"{exp_id} etiquetado pero no esta sellado"
        reemplazo = por_id[exp_id].get("reemplazado_por")
        assert reemplazo, (
            f"{exp_id} tiene el defecto abierto y no declara reemplazo: "
            "sus cifras selladas se publican sin advertencia"
        )
        assert reemplazo in por_id, (
            f"{exp_id} apunta a {reemplazo}, que no es un experimento sellado"
        )
        assert reemplazo != exp_id, f"{exp_id} no puede reemplazarse a si mismo"


def test_el_reemplazo_viaja_al_json_publicado() -> None:
    """El campo tiene que llegar al JSON que sirve la app, no solo al constructor."""
    publicado = json.loads((PUBLICADO / "index.json").read_text(encoding="utf-8"))
    for e in publicado["experimentos"]:
        assert "reemplazado_por" in e, f"{e['id']}: falta reemplazado_por en el contrato"
    marcados = [e["id"] for e in publicado["experimentos"] if e["reemplazado_por"]]
    assert marcados, "ningun registro publicado declara reemplazo; revisa la taxonomia"


def test_la_etiqueta_levantada_no_convive_con_la_abierta(taxonomia: Dict[str, Any]) -> None:
    """Un mismo registro no puede tener el defecto abierto y levantado a la vez."""
    etiquetas = taxonomia.get("etiquetas", {})
    abiertos = set(etiquetas.get("defecto-abierto", []))
    levantados = set(etiquetas.get("defecto-levantado", []))
    assert not (abiertos & levantados), (
        f"registros en las dos listas: {', '.join(sorted(abiertos & levantados))}"
    )


def test_cada_paper_publicado_coincide_con_su_markdown(construido: Dict[str, Any]) -> None:
    """El indice no cambia cuando cambia la prosa: hay que comparar los papers uno a uno.

    `test_el_registro_publicado_esta_al_dia` solo mira `index.json`, y 27 papers
    estuvieron publicados con listas partidas sin que nada fallara.
    """
    distintos = [
        exp_id for exp_id, paper in construido["papers"].items()
        if json.loads((PUBLICADO / "papers" / f"{exp_id}.json").read_text(encoding="utf-8"))
        != paper
    ]
    assert not distintos, (
        f"papers desactualizados: {', '.join(distintos)}; "
        "corre python scripts/build_registro_cientifico.py"
    )


def _textos(bloques: list) -> list:
    return ["".join(f["t"] for f in b["frag"]) for b in bloques if "frag" in b]


def test_un_elemento_de_lista_que_sigue_en_otra_linea_es_el_mismo_elemento() -> None:
    bloques = REGISTRO.markdown_a_bloques(
        "1. **Pose:** reproduce la pose (RMSD ≤ 2 Å, sin\n"
        "   alinear) en 3 de 5 semillas.\n"
        "2. **Calibración:** el IC 95 %\n"
        "   no incluye el cero.\n"
        "\n"
        "Párrafo siguiente."
    )
    assert [b["tipo"] for b in bloques] == ["lista", "parrafo"]
    items = ["".join(f["t"] for f in it) for it in bloques[0]["items"]]
    assert items == [
        "Pose: reproduce la pose (RMSD ≤ 2 Å, sin alinear) en 3 de 5 semillas.",
        "Calibración: el IC 95 % no incluye el cero.",
    ]
    assert bloques[0]["items"][0][0] == {"t": "Pose:", "m": "fuerte"}


def test_un_numero_a_mitad_de_parrafo_no_abre_una_lista() -> None:
    """CommonMark: solo «1.» interrumpe un parrafo. «169. Queda…» es texto."""
    bloques = REGISTRO.markdown_a_bloques(
        "La tarea cambia de ordenar unos 9 candidatos a ordenar unos\n"
        "169. Queda prohibido comparar cifras.\n"
        "\n"
        "Lista real:\n"
        "1. uno\n"
        "- dos"
    )
    assert [b["tipo"] for b in bloques] == ["parrafo", "parrafo", "lista"]
    assert _textos(bloques)[0].endswith("unos 169. Queda prohibido comparar cifras.")
    assert len(bloques[2]["items"]) == 2


def test_la_continuacion_no_se_traga_el_bloque_siguiente() -> None:
    bloques = REGISTRO.markdown_a_bloques(
        "- uno\n"
        "  sigue\n"
        "## Encabezado\n"
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |"
    )
    assert [b["tipo"] for b in bloques] == ["lista", "encabezado", "tabla"]
    assert ["".join(f["t"] for f in it) for it in bloques[0]["items"]] == ["uno sigue"]

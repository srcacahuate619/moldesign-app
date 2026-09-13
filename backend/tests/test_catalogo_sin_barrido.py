"""El catálogo no puede recorrer el árbol de datos una vez por receptor.

EL DEFECTO QUE ESTO IMPIDE

`get_target_pdb_path` resolvía la ruta de cada receptor con globs recursivos:

    local_dir.glob(f"**/targets/**/{pdb_id}*")      # directorio de datos
    library_dir.glob(f"**/{pdb_id}.pdb")            # y tres más, en la biblioteca

El catálogo tiene 380 receptores y sus estructuras viajan comprimidas
(`.pdb.gz`), así que la ruta exacta falla para 403 de 407 y todas caían al glob.
Medido sobre un perfil con 884 entradas: **248,9 ms por glob × 403 = 100 s** para
abrir el catálogo de receptores.

Los tres síntomas que reportó el usuario salen de ahí, y esta prueba los fija:

  - el reloj empieza al ABRIR el catálogo, no al arrancar la aplicación: era
    trabajo por petición;
  - no mejora por mucho que la aplicación lleve abierta: no había caché;
  - **empeora con el uso**, porque el árbol que recorría es justo donde se
    acumulan poses, dossiers y confórmeros.

Ese último punto es el que hace que no baste con «ya va más rápido»: una medida
de tiempo sobre un perfil recién creado no habría detectado nada. Por eso lo que
se comprueba aquí no es la duración sino **el número de recorridos**, que es la
magnitud que crecía.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.docking import preparer  # noqa: E402


@pytest.fixture
def arbol(tmp_path, monkeypatch):
    """Un perfil con datos acumulados, como el de quien lleva usando la app."""
    datos = tmp_path / "datos"
    (datos / "targets").mkdir(parents=True)
    (datos / "targets" / "1ABC.pdb").write_text("ATOM\n", encoding="utf-8")
    # Ruido: lo que se acumula con el uso y que el glob recorría entero.
    for i in range(60):
        sub = datos / "runs" / f"corrida{i:03d}"
        sub.mkdir(parents=True)
        (sub / "poses.sdf").write_text("x", encoding="utf-8")
        (sub / "dossier.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        preparer.settings, "local_data_dir", str(datos), raising=False
    )
    monkeypatch.setattr(
        preparer.get_settings(), "local_data_dir", str(datos), raising=False
    )
    preparer.invalidar_indice_de_targets()
    return datos


def test_resolver_muchos_receptores_no_recorre_el_arbol_una_vez_por_cada_uno(
    arbol, monkeypatch
):
    """380 receptores no pueden costar 380 recorridos del árbol."""
    recorridos = {"n": 0}
    rglob_real = Path.rglob

    def rglob_contado(self, patron):
        recorridos["n"] += 1
        return rglob_real(self, patron)

    monkeypatch.setattr(Path, "rglob", rglob_contado)

    for i in range(380):
        preparer.get_target_pdb_path(f"T{i:03d}")

    # Con el índice: un puñado de recorridos para construirlo, no uno por
    # receptor. El umbral es generoso a propósito -lo que importa es el orden de
    # magnitud, no el número exacto-, pero 380 lo cruza sin discusión.
    assert recorridos["n"] < 100, (
        f"{recorridos['n']} recorridos del árbol para 380 receptores. "
        "El índice no está funcionando: esto es el glob por llamada que costaba "
        "100 s en abrir el catálogo."
    )


def test_el_indice_encuentra_lo_que_encontraba_el_glob(arbol):
    """Rendimiento sin regresión de comportamiento: tiene que seguir hallándolo."""
    ruta = preparer.get_target_pdb_path("1ABC")
    assert Path(ruta).is_file()
    assert Path(ruta).name == "1ABC.pdb"


def test_el_indice_es_insensible_a_mayusculas(arbol):
    """Cubre de una vez los tres globs que había: exacto, upper y lower."""
    for variante in ("1abc", "1ABC", "1AbC"):
        ruta = preparer.get_target_pdb_path(variante)
        assert Path(ruta).is_file(), f"no encontró {variante}"


def test_un_receptor_ausente_devuelve_la_ruta_de_descarga(arbol):
    """No encontrarlo no es un error: es dónde se descargará."""
    ruta = Path(preparer.get_target_pdb_path("9XYZ"))
    assert not ruta.exists()
    assert ruta.name == "9XYZ.pdb"


def test_un_fichero_nuevo_aparece_tras_invalidar(arbol):
    """El índice tiene TTL; quien escribe un .pdb puede forzar que se vea ya."""
    assert not Path(preparer.get_target_pdb_path("2NEW")).exists()

    (arbol / "targets" / "2NEW.pdb").write_text("ATOM\n", encoding="utf-8")
    preparer.invalidar_indice_de_targets()

    assert Path(preparer.get_target_pdb_path("2NEW")).is_file()


def test_el_indice_no_devuelve_un_fichero_que_ya_no_esta(arbol):
    """Un índice rancio no puede afirmar que algo sigue en disco."""
    assert Path(preparer.get_target_pdb_path("1ABC")).is_file()

    (arbol / "targets" / "1ABC.pdb").unlink()
    # Sin invalidar: el índice todavía lo recuerda, pero se confirma en disco.
    ruta = Path(preparer.get_target_pdb_path("1ABC"))
    assert not ruta.exists(), "devolvió la ruta de un fichero borrado"

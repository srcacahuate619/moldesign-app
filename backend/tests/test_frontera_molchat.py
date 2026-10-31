"""La frontera del sidecar MolChat (GPL-3.0-or-later): el backend no lo importa y él no importa al backend.

Mismo patrón que `test_frontera_motor_molcy.py` (del que se reutiliza el
detector): el sidecar se ejecuta por subproceso en loopback y se comunica por
HTTP versionado. Un `import molchat_agent` en el backend lo convertiría en
una sola obra con el producto (PolyForm Noncommercial) y destruiría la
frontera de programa independiente sobre la que se distribuye junto al
instalador. Ver `docs/100_ADR_MOLCHAT_EXTERNO.md`.
"""

from pathlib import Path

import pytest

from tests.test_frontera_motor_molcy import raices_importadas

REPO = Path(__file__).resolve().parents[2]
CARPETAS_DEL_PRODUCTO = ("backend", "rescoring")
#: Lo que sólo existe dentro del sidecar: ningún módulo del producto puede importarlo.
PROHIBIDOS_EN_EL_PRODUCTO = {"molchat_agent"}
#: Lo que el sidecar no puede importar: el producto.
PROHIBIDOS_EN_EL_SIDECAR = {"backend", "services", "api", "core", "db", "rescoring", "utils"}


def _py_del_producto():
    for carpeta in CARPETAS_DEL_PRODUCTO:
        for ruta in (REPO / carpeta).rglob("*.py"):
            if "python-embed" in ruta.parts or "__pycache__" in ruta.parts:
                continue
            yield ruta


def test_el_producto_no_importa_nada_del_sidecar():
    ofensas = []
    revisados = 0
    for ruta in _py_del_producto():
        revisados += 1
        malos = raices_importadas(ruta.read_text(encoding="utf-8")) & PROHIBIDOS_EN_EL_PRODUCTO
        if malos:
            ofensas.append(f"{ruta.relative_to(REPO).as_posix()}: {sorted(malos)}")
    assert revisados > 300, f"el recorrido miró {revisados} ficheros: ¿cambió la estructura?"
    assert not ofensas, "El producto importa el sidecar (frontera GPL):\n  " + "\n  ".join(ofensas)


#: Sin copia vendorizada no hay frontera que defender (modo ausente: verde).
requiere_copia = pytest.mark.skipif(
    not (REPO / "tools" / "molchat" / "molchat-manifest.json").is_file(),
    reason="sin sidecar vendorizado (modo ausente)",
)


@requiere_copia
def test_el_sidecar_no_importa_nada_del_producto():
    ofensas = []
    ficheros = list((REPO / "tools" / "molchat").rglob("*.py"))
    assert len(ficheros) > 30
    for ruta in ficheros:
        malos = raices_importadas(ruta.read_text(encoding="utf-8")) & PROHIBIDOS_EN_EL_SIDECAR
        if malos:
            ofensas.append(f"{ruta.relative_to(REPO).as_posix()}: {sorted(malos)}")
    assert not ofensas, "El sidecar importa el producto:\n  " + "\n  ".join(ofensas)


def test_el_host_solo_lanza_el_sidecar_por_subproceso_con_rutas_absolutas():
    """`launcher.arrancar` ejecuta `sys.executable` con un bootstrap `-c`
    que inserta el `src/` absoluto de la copia verificada en `sys.path`
    (el intérprete empaquetado es aislado: `PYTHONPATH` no existe para él),
    y el `--ui-dist` absoluto: nunca por PATH ni con rutas relativas."""
    from services.molchat_host import launcher as mod

    fuente = (REPO / "backend" / "services" / "molchat_host" / "launcher.py").read_text(encoding="utf-8")
    assert "sys.executable" in fuente
    # El paquete se resuelve desde dentro del proceso: el runtime real es un
    # Python aislado (._pth) que ignora PYTHONPATH y cuyo -m nunca añade cwd.
    assert '"-c", ARRANQUE_CMD' in fuente
    assert "sys.path.insert(0, sys.argv.pop(1))" in mod.ARRANQUE_CMD
    assert "molchat_agent.cli" in mod.ARRANQUE_CMD
    assert "SystemExit(main())" in mod.ARRANQUE_CMD
    assert '"-m"' not in fuente
    assert '"--ui-dist", str(carpeta' in fuente
    assert "shutil.which" not in fuente
